from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from app.config import (
    FFMPEG_BIN,
    PREVIEW_AUDIO_BITRATE,
    PREVIEW_CRF,
    PREVIEW_MAX_DIMENSION,
    PREVIEW_PRESET,
)
from app.schemas import EditOperation
from app.services.ffmpeg_engine import FFmpegEngine, FFmpegError, _run


class OptimizedFFmpegEngine(FFmpegEngine):
    """FFmpeg engine tuned for responsive mobile previews.

    Preview rendering intentionally prefers speed over archival quality. Operations that only
    touch audio keep the original video bitstream, speed changes are downscaled to a phone-sized
    preview in the same pass, compatible overlays/text are grouped, and the final stage writes
    directly to the requested output instead of creating redundant full-file copies.
    """

    def render(
        self,
        source: Path,
        operations: list[EditOperation],
        output: Path,
        assets: dict[str, dict] | None = None,
        source_kind: str = "video",
        source_duration: float | None = None,
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        assets = assets or {}
        enabled = [op for op in operations if op.enabled and op.type != "style_transfer"]

        with tempfile.TemporaryDirectory(prefix="ai-video-optimized-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            normalized_source = source
            if source_kind == "image":
                normalized_source = temp_dir / "source_image.mp4"
                self._image_to_video(source, normalized_source, source_duration or 5.0)
            elif source_kind != "video":
                raise FFmpegError("Project source must be an image or video")

            basic = [op for op in enabled if op.type in {"trim", "speed", "mute", "volume"}]
            concat_ops = [op for op in enabled if op.type == "concat"]
            compositions = [
                op
                for op in enabled
                if op.type in {"split_screen", "picture_in_picture", "media_overlay", "masked_video", "masked_media"}
            ]
            texts = [op for op in enabled if op.type == "text_overlay"]
            music = [op for op in enabled if op.type == "music"]

            current = normalized_source

            def has_after(*counts: int) -> bool:
                return any(value > 0 for value in counts)

            if basic:
                target = (
                    temp_dir / "base.mp4"
                    if has_after(len(concat_ops), len(compositions), len(texts), len(music))
                    else output
                )
                self._render_basic(current, basic, target)
                current = target

            for index, op in enumerate(concat_ops):
                more = has_after(
                    len(concat_ops) - index - 1,
                    len(compositions),
                    len(texts),
                    len(music),
                )
                target = temp_dir / f"concat_{index}.mp4" if more else output
                self._render_concat(current, self._asset(op.secondary_asset_id, assets), target)
                current = target

            composition_index = 0
            group_index = 0
            while composition_index < len(compositions):
                op = compositions[composition_index]
                if op.type in {"picture_in_picture", "media_overlay"}:
                    group: list[tuple[EditOperation, dict]] = []
                    while composition_index < len(compositions):
                        candidate = compositions[composition_index]
                        if candidate.type not in {"picture_in_picture", "media_overlay"}:
                            break
                        asset_id = (
                            candidate.secondary_asset_id
                            if candidate.type == "picture_in_picture"
                            else candidate.source_asset_id
                        )
                        group.append((candidate, self._asset(asset_id, assets)))
                        composition_index += 1
                    more = has_after(
                        len(compositions) - composition_index,
                        len(texts),
                        len(music),
                    )
                    target = temp_dir / f"overlay_group_{group_index}.mp4" if more else output
                    self._render_overlay_group(current, group, target)
                    current = target
                    group_index += 1
                    continue

                composition_index += 1
                more = has_after(
                    len(compositions) - composition_index,
                    len(texts),
                    len(music),
                )
                target = temp_dir / f"composition_{composition_index}.mp4" if more else output
                if op.type == "split_screen":
                    self._render_split_screen(current, self._asset(op.secondary_asset_id, assets), op, target)
                elif op.type == "masked_media":
                    self._render_masked_asset(current, self._asset(op.source_asset_id, assets), op, target, temp_dir)
                else:
                    self._render_masked_source(current, self._asset(op.secondary_asset_id, assets), op, target, temp_dir)
                current = target

            if texts:
                target = temp_dir / "texts.mp4" if music else output
                self._render_texts(current, texts, target)
                current = target

            for index, op in enumerate(music):
                target = temp_dir / f"music_{index}.mp4" if index < len(music) - 1 else output
                self._render_music(current, self._asset_path(op.source_asset_id, assets), op, target)
                current = target

            if current != output:
                # No edits (or an image normalized only for preview) still needs a preview path.
                shutil.copy2(current, output)

        return output

    def _render_basic(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        enabled = [op for op in operations if op.enabled]
        if not enabled:
            shutil.copy2(source, output)
            return

        if all(op.type == "trim" for op in enabled):
            try:
                self._fast_trim(source, enabled, output)
                return
            except Exception:
                output.unlink(missing_ok=True)

        if all(op.type in {"trim", "mute", "volume"} for op in enabled):
            try:
                self._fast_audio_and_trim(source, enabled, output)
                return
            except Exception:
                output.unlink(missing_ok=True)

        if any(op.type == "speed" for op in enabled):
            self._render_speed_preview(source, enabled, output)
            return

        super()._render_basic(source, operations, output)

    def _render_speed_preview(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        metadata = self.probe(source)
        start, end = self._combined_trim(operations, float(metadata.get("duration_seconds") or 0.0))
        speed = 1.0
        volume = 1.0
        muted = False
        for op in operations:
            if op.type == "speed" and op.speed is not None:
                speed *= op.speed
            elif op.type == "volume" and op.volume is not None:
                volume *= op.volume
            elif op.type == "mute":
                muted = True

        if not 0.5 <= speed <= 2.0:
            raise FFmpegError("Combined speed must remain between 0.5x and 2.0x")

        cmd = [FFMPEG_BIN, "-y"]
        if start > 0:
            cmd += ["-ss", f"{start:.3f}"]
        if end is not None:
            cmd += ["-t", f"{max(0.001, end - start):.3f}"]
        cmd += ["-i", str(source)]

        video_filters = [f"setpts=PTS/{speed:.6f}"]
        target_w, target_h = self._preview_dimensions(metadata)
        source_w = int(metadata.get("dimensions", {}).get("width") or target_w)
        source_h = int(metadata.get("dimensions", {}).get("height") or target_h)
        if (target_w, target_h) != (source_w, source_h):
            video_filters.append(f"scale={target_w}:{target_h}:flags=fast_bilinear")
        cmd += ["-vf", ",".join(video_filters)]

        if metadata.get("has_audio"):
            audio_filters = [f"atempo={speed:.6f}"]
            if muted:
                audio_filters.append("volume=0")
            elif abs(volume - 1.0) > 1e-6:
                audio_filters.append(f"volume={volume:.6f}")
            cmd += ["-af", ",".join(audio_filters)]

        cmd += self._encoding_args(bool(metadata.get("has_audio")))
        cmd += [str(output)]
        _run(cmd)

    def _fast_audio_and_trim(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        metadata = self.probe(source)
        start, end = self._combined_trim(operations, float(metadata.get("duration_seconds") or 0.0))
        volume = 1.0
        muted = False
        for op in operations:
            if op.type == "volume" and op.volume is not None:
                volume *= op.volume
            elif op.type == "mute":
                muted = True

        cmd = [FFMPEG_BIN, "-y"]
        if start > 0:
            cmd += ["-ss", f"{start:.3f}"]
        if end is not None:
            cmd += ["-t", f"{max(0.001, end - start):.3f}"]
        cmd += ["-i", str(source), "-map", "0:v:0", "-map", "0:a?"]
        cmd += ["-c:v", "copy"]
        if metadata.get("has_audio"):
            if muted:
                cmd += ["-af", "volume=0"]
            elif abs(volume - 1.0) > 1e-6:
                cmd += ["-af", f"volume={volume:.6f}"]
            cmd += ["-c:a", "aac", "-b:a", PREVIEW_AUDIO_BITRATE]
        else:
            cmd += ["-an"]
        cmd += ["-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(output)]
        _run(cmd)

    def _fast_trim(self, source: Path, trims: list[EditOperation], output: Path) -> None:
        metadata = self.probe(source)
        duration = float(metadata.get("duration_seconds") or 0.0)
        start, end = self._combined_trim(trims, duration)
        if end is None:
            end = duration
        if end <= start:
            raise FFmpegError("Trim end must be after trim start")

        if start <= 0.001 and (duration <= 0 or abs(end - duration) <= 0.001):
            shutil.copy2(source, output)
            return

        cmd = [FFMPEG_BIN, "-y"]
        if start > 0:
            cmd += ["-ss", f"{start:.3f}"]
        cmd += ["-i", str(source), "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a?"]
        cmd += ["-c", "copy", "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(output)]
        _run(cmd)

    def _render_texts(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        metadata = self.probe(source)
        target_w, target_h = self._preview_dimensions(metadata)
        source_w = int(metadata.get("dimensions", {}).get("width") or target_w)
        source_h = int(metadata.get("dimensions", {}).get("height") or target_h)
        filters: list[str] = []
        if (target_w, target_h) != (source_w, source_h):
            filters.append(f"scale={target_w}:{target_h}:flags=fast_bilinear")

        duration = float(metadata.get("duration_seconds") or 0.0)
        for op in operations:
            position = op.position or "bottom"
            y = "h*0.08" if position == "top" else "(h-text_h)/2" if position == "center" else "h-text_h-h*0.08"
            text = self._escape_drawtext(op.text or "")
            font = self._escape_drawtext(op.font_family or "DejaVu Sans")
            enable = self._timeline_enable(op, duration)
            filters.append(
                f"drawtext=text='{text}':font='{font}':x=(w-text_w)/2:y={y}:"
                f"fontsize={op.font_size or 48}:fontcolor={op.font_color or 'white'}:box=1:"
                f"boxcolor={op.text_background_color or 'black@0.45'}:boxborderw=12{enable}"
            )

        cmd = [FFMPEG_BIN, "-y", "-i", str(source), "-vf", ",".join(filters), "-map", "0:v:0", "-map", "0:a?"]
        cmd += self._encoding_args(bool(metadata.get("has_audio")))
        cmd += [str(output)]
        _run(cmd)

    def _render_overlay_group(
        self,
        source: Path,
        group: list[tuple[EditOperation, dict]],
        output: Path,
    ) -> None:
        metadata = self.probe(source)
        duration = float(metadata.get("duration_seconds") or 0.0)
        canvas_w, canvas_h = self._preview_dimensions(metadata)

        cmd = [FFMPEG_BIN, "-y", "-i", str(source)]
        for _, asset in group:
            cmd += self._visual_input(asset)

        filters = [f"[0:v]setpts=PTS-STARTPTS,scale={canvas_w}:{canvas_h}:flags=fast_bilinear,setsar=1[base0]"]
        for index, (op, _) in enumerate(group, start=1):
            width = self._even(min(op.width or 360, canvas_w))
            height = self._even(min(op.height or 202, canvas_h))
            x_expr, y_expr = self._motion_coordinates(
                op,
                op.x if op.x is not None else 20,
                op.y if op.y is not None else 20,
            )
            enable = self._timeline_enable(op, duration)
            filters.append(
                f"[{index}:v]setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1[layer{index}]"
            )
            filters.append(
                f"[base{index - 1}][layer{index}]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[base{index}]"
            )

        final_ref = f"[base{len(group)}]"
        cmd += ["-filter_complex", ";".join(filters), "-map", final_ref, "-map", "0:a?", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(bool(metadata.get("has_audio")))
        cmd += [str(output)]
        _run(cmd)

    def _render_split_screen(self, source: Path, second: dict, op: EditOperation, output: Path) -> None:
        meta = self.probe(source)
        width, height = self._preview_dimensions(meta)
        duration = float(meta["duration_seconds"])
        ratio = op.ratio or 0.5

        if (op.layout or "side_by_side") == "stacked":
            h1 = self._even(max(2, int(height * ratio)))
            h2 = self._even(max(2, height - h1))
            height = h1 + h2
            video_filter = (
                f"[0:v]setpts=PTS-STARTPTS,scale={width}:{h1}:force_original_aspect_ratio=increase,"
                f"crop={width}:{h1},setsar=1,fps=30[a];"
                f"[1:v]setpts=PTS-STARTPTS,scale={width}:{h2}:force_original_aspect_ratio=increase,"
                f"crop={width}:{h2},setsar=1,fps=30[b];[a][b]vstack=inputs=2[v]"
            )
        else:
            w1 = self._even(max(2, int(width * ratio)))
            w2 = self._even(max(2, width - w1))
            width = w1 + w2
            video_filter = (
                f"[0:v]setpts=PTS-STARTPTS,scale={w1}:{height}:force_original_aspect_ratio=increase,"
                f"crop={w1}:{height},setsar=1,fps=30[a];"
                f"[1:v]setpts=PTS-STARTPTS,scale={w2}:{height}:force_original_aspect_ratio=increase,"
                f"crop={w2}:{height},setsar=1,fps=30[b];[a][b]hstack=inputs=2[v]"
            )

        second_has_audio = bool(second.get("metadata", {}).get("has_audio", False))
        filters = [video_filter]
        cmd = [FFMPEG_BIN, "-y", "-i", str(source), *self._visual_input(second)]
        map_args = ["-map", "[v]"]
        has_output_audio = bool(meta["has_audio"] or second_has_audio)
        if meta["has_audio"] and second_has_audio:
            filters.append("[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]")
            map_args += ["-map", "[a]"]
        elif meta["has_audio"]:
            map_args += ["-map", "0:a:0"]
        elif second_has_audio:
            map_args += ["-map", "1:a:0"]

        cmd += ["-filter_complex", ";".join(filters), *map_args, "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(has_output_audio)
        cmd += [str(output)]
        _run(cmd)

    def _render_masked_source(self, foreground: Path, background: dict, op: EditOperation, output: Path, temp_dir: Path) -> None:
        meta = self.probe(foreground)
        duration = float(meta["duration_seconds"])
        canvas_w, canvas_h = self._preview_dimensions(meta)
        mask_w = self._even(min(op.width or 360, canvas_w))
        mask_h = self._even(min(op.height or 360, canvas_h))
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 40, op.y if op.y is not None else 40)
        enable = self._timeline_enable(op, duration)
        mask = temp_dir / f"mask_{op.id}.png"
        self._create_mask(mask, op.shape or "star", mask_w, mask_h, op.rotation or 0, op.feather or 0, op.opacity or 1.0)
        fc = (
            f"[1:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,crop={canvas_w}:{canvas_h}[bg];"
            f"[0:v]scale={mask_w}:{mask_h}:force_original_aspect_ratio=increase,crop={mask_w}:{mask_h},format=rgba[fg];"
            f"[2:v]format=gray[mask];[fg][mask]alphamerge[cut];"
            f"[bg][cut]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        )
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(foreground),
            *self._visual_input(background),
            "-loop",
            "1",
            "-i",
            str(mask),
            "-filter_complex",
            fc,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-t",
            f"{duration:.3f}",
        ]
        cmd += self._encoding_args(bool(meta["has_audio"]))
        cmd += [str(output)]
        _run(cmd)

    def _render_masked_asset(self, background: Path, foreground: dict, op: EditOperation, output: Path, temp_dir: Path) -> None:
        meta = self.probe(background)
        duration = float(meta["duration_seconds"])
        canvas_w, canvas_h = self._preview_dimensions(meta)
        mask_w = self._even(min(op.width or 360, canvas_w))
        mask_h = self._even(min(op.height or 360, canvas_h))
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 40, op.y if op.y is not None else 40)
        enable = self._timeline_enable(op, duration)
        mask = temp_dir / f"mask_asset_{op.id}.png"
        self._create_mask(mask, op.shape or "star", mask_w, mask_h, op.rotation or 0, op.feather or 0, op.opacity or 1.0)
        fc = (
            f"[0:v]scale={canvas_w}:{canvas_h}:flags=fast_bilinear[bg];"
            f"[1:v]scale={mask_w}:{mask_h}:force_original_aspect_ratio=increase,crop={mask_w}:{mask_h},format=rgba[fg];"
            f"[2:v]format=gray[mask];[fg][mask]alphamerge[cut];"
            f"[bg][cut]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        )
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(background),
            *self._visual_input(foreground),
            "-loop",
            "1",
            "-i",
            str(mask),
            "-filter_complex",
            fc,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-t",
            f"{duration:.3f}",
        ]
        cmd += self._encoding_args(bool(meta["has_audio"]))
        cmd += [str(output)]
        _run(cmd)

    def _render_music(self, source: Path, music: Path, op: EditOperation, output: Path) -> None:
        """Mix audio while stream-copying video; no video re-encode is needed for music."""
        meta = self.probe(source)
        duration = float(meta["duration_seconds"])
        volume = op.volume if op.volume is not None else 0.35
        start = op.start_seconds or 0.0
        end = min(op.end_seconds if op.end_seconds is not None else duration, duration)
        play_duration = max(0.05, end - start)
        delay_ms = int(start * 1000)
        filters = [f"[1:a]atrim=duration={play_duration:.3f},asetpts=PTS-STARTPTS,volume={volume:.4f}"]
        if (op.fade_in_seconds or 0) > 0:
            filters[-1] += f",afade=t=in:st=0:d={min(op.fade_in_seconds or 0, play_duration):.3f}"
        if (op.fade_out_seconds or 0) > 0:
            fade = min(op.fade_out_seconds or 0, play_duration)
            filters[-1] += f",afade=t=out:st={max(0.0, play_duration - fade):.3f}:d={fade:.3f}"
        filters[-1] += f",adelay={delay_ms}|{delay_ms}[music]"
        if meta["has_audio"]:
            if op.ducking:
                filters.append("[music][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[ducked]")
                filters.append("[0:a][ducked]amix=inputs=2:duration=first:normalize=0[a]")
            else:
                filters.append("[0:a][music]amix=inputs=2:duration=first:normalize=0[a]")
        else:
            filters.append("[music]apad=pad_dur=1[a]")
        loop_args = ["-stream_loop", "-1"] if op.loop else []
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(source),
            *loop_args,
            "-i",
            str(music),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            PREVIEW_AUDIO_BITRATE,
            "-movflags",
            "+faststart",
            str(output),
        ]
        _run(cmd)

    def _render_concat(self, source: Path, second: dict, output: Path) -> None:
        source_meta = self.probe(source)
        second_meta = second.get("metadata") or {}
        width, height = self._preview_dimensions(source_meta)
        first_duration = float(source_meta.get("duration_seconds") or 0.1)
        second_duration = float(second_meta.get("duration_seconds") or 5.0)

        cmd = [FFMPEG_BIN, "-y", "-i", str(source)]
        if self._visual_kind(second) == "image":
            cmd += ["-loop", "1", "-t", f"{second_duration:.3f}", "-i", str(second["path"])]
        else:
            cmd += ["-i", str(second["path"])]

        next_input = 2
        first_audio_ref = "0:a"
        second_audio_ref = "1:a"
        if not source_meta["has_audio"]:
            cmd += ["-f", "lavfi", "-t", f"{first_duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            first_audio_ref = f"{next_input}:a"
            next_input += 1
        if not bool(second_meta.get("has_audio", False)):
            cmd += ["-f", "lavfi", "-t", f"{second_duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            second_audio_ref = f"{next_input}:a"

        filter_complex = ";".join([
            f"[0:v]setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0]",
            f"[1:v]setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1]",
            f"[{first_audio_ref}]aresample=48000,asetpts=PTS-STARTPTS[a0]",
            f"[{second_audio_ref}]aresample=48000,asetpts=PTS-STARTPTS[a1]",
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        ])
        cmd += ["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"]
        cmd += self._encoding_args(True)
        cmd += [str(output)]
        _run(cmd)

    def _image_to_video(self, image: Path, output: Path, duration: float) -> None:
        duration = max(0.1, float(duration))
        # The source image is only materialized as a preview clip, so cap it to the same phone-sized
        # working resolution used for video previews.
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            f"{duration:.3f}",
            "-r",
            "30",
            "-vf",
            f"scale='min({PREVIEW_MAX_DIMENSION},iw)':'min({PREVIEW_MAX_DIMENSION},ih)':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2,format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            PREVIEW_PRESET,
            "-crf",
            str(PREVIEW_CRF),
            "-threads",
            "0",
            "-movflags",
            "+faststart",
            str(output),
        ]
        _run(cmd)

    @staticmethod
    def _combined_trim(operations: list[EditOperation], duration: float) -> tuple[float, float | None]:
        starts = [op.start_seconds for op in operations if op.type == "trim" and op.start_seconds is not None]
        ends = [op.end_seconds for op in operations if op.type == "trim" and op.end_seconds is not None]
        start = max(starts) if starts else 0.0
        end: float | None = min(ends) if ends else (duration if duration > 0 else None)
        if end is not None and duration > 0:
            end = min(end, duration)
        if end is not None and end <= start:
            raise FFmpegError("Trim end must be after trim start")
        return start, end

    @classmethod
    def _preview_dimensions(cls, metadata: dict) -> tuple[int, int]:
        dimensions = metadata.get("dimensions", {})
        width = max(2, int(dimensions.get("width") or 1280))
        height = max(2, int(dimensions.get("height") or 720))
        largest = max(width, height)
        if largest <= PREVIEW_MAX_DIMENSION:
            return cls._even(width), cls._even(height)
        scale = PREVIEW_MAX_DIMENSION / float(largest)
        return cls._even(width * scale), cls._even(height * scale)

    @staticmethod
    def _encoding_args(has_audio: bool) -> list[str]:
        args = [
            "-c:v",
            "libx264",
            "-preset",
            PREVIEW_PRESET,
            "-crf",
            str(PREVIEW_CRF),
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "0",
            "-movflags",
            "+faststart",
        ]
        if has_audio:
            args += ["-c:a", "aac", "-b:a", PREVIEW_AUDIO_BITRATE]
        return args

    @staticmethod
    def _even(value: int | float) -> int:
        value = max(2, int(value))
        return value if value % 2 == 0 else value - 1
