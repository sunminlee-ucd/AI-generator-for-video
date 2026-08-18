from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.schemas import EditOperation

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class FFmpegError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(result.stderr.strip() or "FFmpeg command failed")
    return result


class FFmpegEngine:
    def probe(self, source: Path) -> dict:
        result = _run([
            FFPROBE_BIN, "-v", "error",
            "-show_entries", "format=duration:stream=index,codec_type,width,height",
            "-of", "json", str(source),
        ])
        payload = json.loads(result.stdout or "{}")
        streams = payload.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        duration_raw = payload.get("format", {}).get("duration")
        duration = round(float(duration_raw), 3) if duration_raw not in {None, "N/A"} else 0.0
        return {
            "duration_seconds": duration,
            "dimensions": {"width": video.get("width"), "height": video.get("height")},
            "has_video": bool(video),
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        }

    def inspect_media(self, source: Path, still_duration_seconds: float = 5.0) -> dict:
        if source.suffix.lower() in IMAGE_EXTENSIONS:
            try:
                with Image.open(source) as image:
                    width, height = image.size
                return {
                    "kind": "image",
                    "duration_seconds": round(float(still_duration_seconds), 3),
                    "dimensions": {"width": width, "height": height},
                    "has_video": False,
                    "has_audio": False,
                }
            except Exception as exc:
                raise FFmpegError(f"Invalid image: {exc}") from exc

        metadata = self.probe(source)
        if metadata["has_video"]:
            return {"kind": "video", **metadata}
        if metadata["has_audio"]:
            return {"kind": "audio", **metadata}
        raise FFmpegError("File contains no supported image, video, or audio media")

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

        with tempfile.TemporaryDirectory(prefix="ai-video-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            normalized_source = source
            if source_kind == "image":
                normalized_source = temp_dir / "source_image.mp4"
                self._image_to_video(source, normalized_source, source_duration or 5.0)
            elif source_kind != "video":
                raise FFmpegError("Project source must be an image or video")

            basic = [op for op in enabled if op.type in {"trim", "speed", "mute", "volume"}]
            compositions = [op for op in enabled if op.type in {"split_screen", "picture_in_picture", "media_overlay", "masked_video", "masked_media"}]
            texts = [op for op in enabled if op.type == "text_overlay"]
            music = [op for op in enabled if op.type == "music"]

            current = temp_dir / "base.mp4"
            self._render_basic(normalized_source, basic, current)

            for index, op in enumerate(compositions):
                next_path = temp_dir / f"composition_{index}.mp4"
                if op.type == "split_screen":
                    self._render_split_screen(current, self._asset(op.secondary_asset_id, assets), op, next_path)
                elif op.type == "picture_in_picture":
                    self._render_overlay(current, self._asset(op.secondary_asset_id, assets), op, next_path)
                elif op.type == "media_overlay":
                    self._render_overlay(current, self._asset(op.source_asset_id, assets), op, next_path)
                elif op.type == "masked_media":
                    self._render_masked_asset(current, self._asset(op.source_asset_id, assets), op, next_path, temp_dir)
                else:
                    self._render_masked_source(current, self._asset(op.secondary_asset_id, assets), op, next_path, temp_dir)
                current = next_path

            for index, op in enumerate(texts):
                next_path = temp_dir / f"text_{index}.mp4"
                self._render_text(current, op, next_path)
                current = next_path

            for index, op in enumerate(music):
                next_path = temp_dir / f"music_{index}.mp4"
                self._render_music(current, self._asset_path(op.source_asset_id, assets), op, next_path)
                current = next_path

            shutil.copy2(current, output)
        return output

    def _image_to_video(self, image: Path, output: Path, duration: float) -> None:
        duration = max(0.1, float(duration))
        cmd = [
            FFMPEG_BIN, "-y", "-loop", "1", "-i", str(image),
            "-t", f"{duration:.3f}", "-r", "30",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart", str(output),
        ]
        _run(cmd)

    def _render_basic(self, source: Path, operations: list[EditOperation], output: Path) -> None:
        if not operations:
            shutil.copy2(source, output)
            return
        metadata = self.probe(source)
        video_filters: list[str] = []
        audio_filters: list[str] = []
        trim_start = None
        trim_end = None
        speed = 1.0
        volume = 1.0
        muted = False

        for op in operations:
            if op.type == "trim":
                if op.start_seconds is not None:
                    trim_start = op.start_seconds if trim_start is None else max(trim_start, op.start_seconds)
                if op.end_seconds is not None:
                    trim_end = op.end_seconds if trim_end is None else min(trim_end, op.end_seconds)
            elif op.type == "speed" and op.speed is not None:
                speed *= op.speed
            elif op.type == "volume" and op.volume is not None:
                volume *= op.volume
            elif op.type == "mute":
                muted = True

        if not 0.5 <= speed <= 2.0:
            raise FFmpegError("Combined speed must remain between 0.5x and 2.0x")
        if trim_start is not None or trim_end is not None:
            params = []
            if trim_start is not None:
                params.append(f"start={trim_start:.3f}")
            if trim_end is not None:
                params.append(f"end={trim_end:.3f}")
            joined = ":".join(params)
            video_filters.extend([f"trim={joined}", "setpts=PTS-STARTPTS"])
            if metadata["has_audio"]:
                audio_filters.extend([f"atrim={joined}", "asetpts=PTS-STARTPTS"])
        if speed != 1.0:
            video_filters.append(f"setpts=PTS/{speed:.6f}")
            if metadata["has_audio"]:
                audio_filters.append(f"atempo={speed:.6f}")
        if metadata["has_audio"]:
            if muted:
                audio_filters.append("volume=0")
            elif volume != 1.0:
                audio_filters.append(f"volume={volume:.6f}")

        cmd = [FFMPEG_BIN, "-y", "-i", str(source)]
        if video_filters:
            cmd += ["-vf", ",".join(video_filters)]
        if metadata["has_audio"] and audio_filters:
            cmd += ["-af", ",".join(audio_filters)]
        cmd += self._encoding_args(metadata["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_text(self, source: Path, op: EditOperation, output: Path) -> None:
        metadata = self.probe(source)
        position = op.position or "bottom"
        y = "h*0.08" if position == "top" else "(h-text_h)/2" if position == "center" else "h-text_h-h*0.08"
        text = self._escape_drawtext(op.text or "")
        font = self._escape_drawtext(op.font_family or "DejaVu Sans")
        enable = self._timeline_enable(op, float(metadata["duration_seconds"]))
        drawtext = (
            f"drawtext=text='{text}':font='{font}':x=(w-text_w)/2:y={y}:"
            f"fontsize={op.font_size or 48}:fontcolor={op.font_color or 'white'}:box=1:"
            f"boxcolor={op.text_background_color or 'black@0.45'}:boxborderw=12{enable}"
        )
        cmd = [FFMPEG_BIN, "-y", "-i", str(source), "-vf", drawtext, "-map", "0:v:0", "-map", "0:a?"]
        cmd += self._encoding_args(metadata["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_split_screen(self, source: Path, second: dict, op: EditOperation, output: Path) -> None:
        meta = self.probe(source)
        w = int(meta["dimensions"]["width"] or 1280)
        h = int(meta["dimensions"]["height"] or 720)
        duration = float(meta["duration_seconds"])
        ratio = op.ratio or 0.5
        if (op.layout or "side_by_side") == "stacked":
            h1 = max(2, int(h * ratio) // 2 * 2)
            h2 = max(2, h - h1)
            fc = f"[0:v]scale={w}:{h1}:force_original_aspect_ratio=increase,crop={w}:{h1}[a];[1:v]scale={w}:{h2}:force_original_aspect_ratio=increase,crop={w}:{h2}[b];[a][b]vstack=inputs=2[v]"
        else:
            w1 = max(2, int(w * ratio) // 2 * 2)
            w2 = max(2, w - w1)
            fc = f"[0:v]scale={w1}:{h}:force_original_aspect_ratio=increase,crop={w1}:{h}[a];[1:v]scale={w2}:{h}:force_original_aspect_ratio=increase,crop={w2}:{h}[b];[a][b]hstack=inputs=2[v]"
        cmd = [FFMPEG_BIN, "-y", "-i", str(source), *self._visual_input(second), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(meta["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_overlay(self, source: Path, layer: dict, op: EditOperation, output: Path) -> None:
        meta = self.probe(source)
        duration = float(meta["duration_seconds"])
        width = op.width or 360
        height = op.height or 202
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 20, op.y if op.y is not None else 20)
        enable = self._timeline_enable(op, duration)
        fc = f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[layer];[0:v][layer]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        cmd = [FFMPEG_BIN, "-y", "-i", str(source), *self._visual_input(layer), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(meta["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_masked_source(self, foreground: Path, background: dict, op: EditOperation, output: Path, temp_dir: Path) -> None:
        meta = self.probe(foreground)
        duration = float(meta["duration_seconds"])
        canvas_w = int(meta["dimensions"]["width"] or 1280)
        canvas_h = int(meta["dimensions"]["height"] or 720)
        mask_w = min(op.width or 360, canvas_w)
        mask_h = min(op.height or 360, canvas_h)
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 40, op.y if op.y is not None else 40)
        enable = self._timeline_enable(op, duration)
        mask = temp_dir / f"mask_{op.id}.png"
        self._create_mask(mask, op.shape or "star", mask_w, mask_h, op.rotation or 0, op.feather or 0, op.opacity or 1.0)
        fc = f"[1:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,crop={canvas_w}:{canvas_h}[bg];[0:v]scale={mask_w}:{mask_h}:force_original_aspect_ratio=increase,crop={mask_w}:{mask_h},format=rgba[fg];[2:v]format=gray[mask];[fg][mask]alphamerge[cut];[bg][cut]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        cmd = [FFMPEG_BIN, "-y", "-i", str(foreground), *self._visual_input(background), "-loop", "1", "-i", str(mask), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(meta["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_masked_asset(self, background: Path, foreground: dict, op: EditOperation, output: Path, temp_dir: Path) -> None:
        meta = self.probe(background)
        duration = float(meta["duration_seconds"])
        canvas_w = int(meta["dimensions"]["width"] or 1280)
        canvas_h = int(meta["dimensions"]["height"] or 720)
        mask_w = min(op.width or 360, canvas_w)
        mask_h = min(op.height or 360, canvas_h)
        x_expr, y_expr = self._motion_coordinates(op, op.x if op.x is not None else 40, op.y if op.y is not None else 40)
        enable = self._timeline_enable(op, duration)
        mask = temp_dir / f"mask_asset_{op.id}.png"
        self._create_mask(mask, op.shape or "star", mask_w, mask_h, op.rotation or 0, op.feather or 0, op.opacity or 1.0)
        fc = f"[1:v]scale={mask_w}:{mask_h}:force_original_aspect_ratio=increase,crop={mask_w}:{mask_h},format=rgba[fg];[2:v]format=gray[mask];[fg][mask]alphamerge[cut];[0:v][cut]overlay=x='{x_expr}':y='{y_expr}':eval=frame{enable}[v]"
        cmd = [FFMPEG_BIN, "-y", "-i", str(background), *self._visual_input(foreground), "-loop", "1", "-i", str(mask), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(meta["has_audio"])
        cmd += [str(output)]
        _run(cmd)

    def _render_music(self, source: Path, music: Path, op: EditOperation, output: Path) -> None:
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
            filters[-1] += f",afade=t=out:st={max(0.0, play_duration-fade):.3f}:d={fade:.3f}"
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
        cmd = [FFMPEG_BIN, "-y", "-i", str(source), *loop_args, "-i", str(music), "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[a]", "-t", f"{duration:.3f}"]
        cmd += self._encoding_args(True)
        cmd += [str(output)]
        _run(cmd)

    @staticmethod
    def _visual_kind(asset: dict) -> str:
        kind = asset.get("kind")
        if kind in {"video", "image"}:
            return kind
        path = Path(asset.get("path", ""))
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return "image"
        if path.exists():
            return "video"
        raise FFmpegError("Visual media asset is missing or unsupported")

    @classmethod
    def _visual_input(cls, asset: dict) -> list[str]:
        path = str(asset["path"])
        if cls._visual_kind(asset) == "image":
            return ["-loop", "1", "-i", path]
        return ["-stream_loop", "-1", "-i", path]

    @classmethod
    def _asset(cls, asset_id: str | None, assets: dict[str, dict]) -> dict:
        if not asset_id or asset_id not in assets:
            raise FFmpegError(f"Missing media asset: {asset_id}")
        asset = assets[asset_id]
        path = Path(asset["path"])
        if not path.exists():
            raise FFmpegError(f"Media asset file is missing: {asset_id}")
        cls._visual_kind(asset)
        return asset

    @staticmethod
    def _asset_path(asset_id: str | None, assets: dict[str, dict]) -> Path:
        if not asset_id or asset_id not in assets:
            raise FFmpegError(f"Missing media asset: {asset_id}")
        path = Path(assets[asset_id]["path"])
        if not path.exists():
            raise FFmpegError(f"Media asset file is missing: {asset_id}")
        return path

    @classmethod
    def _motion_coordinates(cls, op: EditOperation, default_x: int, default_y: int) -> tuple[str, str]:
        frames = op.motion_keyframes
        if not frames:
            return str(default_x), str(default_y)
        return cls._keyframe_expression(frames, "x", default_x), cls._keyframe_expression(frames, "y", default_y)

    @classmethod
    def _keyframe_expression(cls, frames, field: str, default: int) -> str:
        if not frames:
            return str(default)
        if len(frames) == 1:
            return f"{float(getattr(frames[0], field)):.6f}"
        parts: list[tuple[float, str]] = []
        for current, following in zip(frames, frames[1:]):
            t0 = float(current.time_seconds)
            t1 = float(following.time_seconds)
            v0 = float(getattr(current, field))
            v1 = float(getattr(following, field))
            duration = max(0.000001, t1 - t0)
            progress = f"((t-{t0:.6f})/{duration:.6f})"
            eased = cls._easing_expression(progress, current.easing)
            parts.append((t1, f"({v0:.6f}+({v1-v0:.6f})*({eased}))"))
        expression = f"{float(getattr(frames[-1], field)):.6f}"
        for end_time, segment in reversed(parts):
            expression = f"if(lt(t,{end_time:.6f}),{segment},{expression})"
        first_time = float(frames[0].time_seconds)
        first_value = float(getattr(frames[0], field))
        if first_time > 0:
            expression = f"if(lt(t,{first_time:.6f}),{first_value:.6f},{expression})"
        return expression

    @staticmethod
    def _easing_expression(progress: str, easing: str) -> str:
        if easing == "ease_in":
            return f"({progress})*({progress})"
        if easing == "ease_out":
            return f"(1-(1-({progress}))*(1-({progress})))"
        if easing == "ease_in_out":
            return f"(({progress})*({progress})*(3-2*({progress})))"
        return progress

    @staticmethod
    def _timeline_enable(op: EditOperation, duration: float) -> str:
        if op.start_seconds is None and op.end_seconds is None:
            return ""
        start = op.start_seconds or 0.0
        end = op.end_seconds if op.end_seconds is not None else duration
        return f":enable='between(t,{start:.6f},{end:.6f})'"

    def extract_frame(self, source: Path, output: Path, at_seconds: float = 0.0) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        _run([FFMPEG_BIN, "-y", "-ss", str(max(0.0, at_seconds)), "-i", str(source), "-frames:v", "1", "-q:v", "2", str(output)])
        return output

    @staticmethod
    def _encoding_args(has_audio: bool) -> list[str]:
        args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        if has_audio:
            args += ["-c:a", "aac", "-b:a", "128k"]
        return args

    @staticmethod
    def _create_mask(path: Path, shape: str, width: int, height: int, rotation: float, feather: int, opacity: float) -> None:
        image = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(image)
        pad = max(2, int(min(width, height) * 0.04))
        box = (pad, pad, width - pad, height - pad)
        if shape == "circle":
            draw.ellipse(box, fill=int(255 * opacity))
        elif shape == "triangle":
            draw.polygon([(width / 2, pad), (width - pad, height - pad), (pad, height - pad)], fill=int(255 * opacity))
        elif shape == "heart":
            points = []
            for i in range(240):
                t = 2 * math.pi * i / 240
                x = 16 * math.sin(t) ** 3
                y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
                points.append((width / 2 + x * (width - 2 * pad) / 34, height / 2 - y * (height - 2 * pad) / 34))
            draw.polygon(points, fill=int(255 * opacity))
        else:
            points = []
            cx, cy = width / 2, height / 2
            outer = min(width, height) / 2 - pad
            inner = outer * 0.43
            start_angle = math.radians(-90 + rotation)
            for i in range(10):
                radius = outer if i % 2 == 0 else inner
                angle = start_angle + i * math.pi / 5
                points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
            draw.polygon(points, fill=int(255 * opacity))
        if shape != "star" and rotation:
            image = image.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=False)
        if feather:
            image = image.filter(ImageFilter.GaussianBlur(radius=feather))
        image.save(path)

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
