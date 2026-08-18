from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from app.config import FFMPEG_BIN
from app.schemas import EditOperation
from app.services.ffmpeg_engine import FFmpegEngine, FFmpegError, _run


class OptimizedFFmpegEngine(FFmpegEngine):
    """FFmpeg engine with fast-path trims and more robust multi-video composition."""

    def render(
        self,
        source: Path,
        operations: list[EditOperation],
        output: Path,
        assets: dict[str, dict] | None = None,
        source_kind: str = "video",
        source_duration: float | None = None,
    ) -> Path:
        assets = assets or {}
        enabled = [op for op in operations if op.enabled and op.type != "style_transfer"]
        concat_ops = [op for op in enabled if op.type == "concat"]
        if not concat_ops:
            return super().render(source, operations, output, assets, source_kind, source_duration)

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-video-optimized-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            normalized_source = source
            if source_kind == "image":
                normalized_source = temp_dir / "source_image.mp4"
                self._image_to_video(source, normalized_source, source_duration or 5.0)
            elif source_kind != "video":
                raise FFmpegError("Project source must be an image or video")

            basic = [op for op in enabled if op.type in {"trim", "speed", "mute", "volume"}]
            current = temp_dir / "base.mp4"
            self._render_basic(normalized_source, basic, current)

            for index, op in enumerate(concat_ops):
                next_path = temp_dir / f"concat_{index}.mp4"
                self._render_concat(current, self._asset(op.secondary_asset_id, assets), next_path)
                current = next_path

            remaining = [
                op for op in enabled
                if op.type not in {"trim", "speed", "mute", "volume", "concat"}
            ]
            if remaining:
                super().render(current, remaining, output, assets, source_kind="video")
            else:
                shutil.copy2(current, output)
        return output

    def _render_basic(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        enabled = [op for op in operations if op.enabled]
        if enabled and all(op.type == "trim" for op in enabled):
            try:
                self._fast_trim(source, enabled, output)
                return
            except Exception:
                output.unlink(missing_ok=True)
        super()._render_basic(source, operations, output)

    def _fast_trim(self, source: Path, trims: list[EditOperation], output: Path) -> None:
        metadata = self.probe(source)
        duration = float(metadata.get("duration_seconds") or 0.0)
        start = max((op.start_seconds or 0.0) for op in trims)
        ends = [op.end_seconds for op in trims if op.end_seconds is not None]
        end = min(ends) if ends else duration
        if duration > 0:
            end = min(end, duration)
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

    def _render_split_screen(self, source: Path, second: dict, op: EditOperation, output: Path) -> None:
        meta = self.probe(source)
        width = self._even(int(meta["dimensions"]["width"] or 1280))
        height = self._even(int(meta["dimensions"]["height"] or 720))
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

    def _render_overlay(self, source: Path, layer: dict, op: EditOperation, output: Path) -> None:
        meta = self.probe(source)
        duration = float(meta["duration_seconds"])
        width = self._even(op.width or 360)
        height = self._even(op.height or 202)
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 20, op.y if op.y is not None else 20)
        enable = self._timeline_enable(op, duration)
        filter_complex = (
            f"[1:v]setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1[layer];"
            f"[0:v]setpts=PTS-STARTPTS[base];"
            f"[base][layer]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        )
        cmd = [
            FFMPEG_BIN, "-y", "-i", str(source), *self._visual_input(layer),
            "-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?", "-t", f"{duration:.3f}",
        ]
        cmd += self._encoding_args(meta["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_concat(self, source: Path, second: dict, output: Path) -> None:
        source_meta = self.probe(source)
        second_meta = second.get("metadata") or {}
        width = self._even(int(source_meta["dimensions"]["width"] or 1280))
        height = self._even(int(source_meta["dimensions"]["height"] or 720))
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

    @staticmethod
    def _even(value: int) -> int:
        value = max(2, int(value))
        return value if value % 2 == 0 else value - 1
