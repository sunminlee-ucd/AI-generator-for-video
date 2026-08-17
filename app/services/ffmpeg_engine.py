from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.schemas import EditOperation

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
            FFPROBE_BIN, "-v", "error", "-show_entries",
            "format=duration:stream=index,codec_type,width,height",
            "-of", "json", str(source),
        ])
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        return {
            "duration_seconds": round(float(payload["format"]["duration"]), 3),
            "dimensions": {"width": video.get("width"), "height": video.get("height")},
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        }

    def render(self, source: Path, operations: list[EditOperation], output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        metadata = self.probe(source)
        standard_ops = [op for op in operations if op.type != "style_transfer"]
        if not standard_ops:
            shutil.copy2(source, output)
            return output

        video_filters: list[str] = []
        audio_filters: list[str] = []
        trim_start = None
        trim_end = None
        speed = 1.0
        volume = 1.0
        muted = False
        overlays: list[EditOperation] = []

        for op in standard_ops:
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
            elif op.type == "text_overlay":
                overlays.append(op)

        if not 0.5 <= speed <= 2.0:
            raise FFmpegError("Combined speed must remain between 0.5x and 2.0x in the MVP")

        if trim_start is not None or trim_end is not None:
            params = []
            if trim_start is not None:
                params.append(f"start={trim_start:.3f}")
            if trim_end is not None:
                params.append(f"end={trim_end:.3f}")
            video_filters.extend([f"trim={':'.join(params)}", "setpts=PTS-STARTPTS"])
            if metadata["has_audio"]:
                audio_filters.extend([f"atrim={':'.join(params)}", "asetpts=PTS-STARTPTS"])

        if speed != 1.0:
            video_filters.append(f"setpts=PTS/{speed:.6f}")
            if metadata["has_audio"]:
                audio_filters.append(f"atempo={speed:.6f}")

        if metadata["has_audio"]:
            if muted:
                audio_filters.append("volume=0")
            elif volume != 1.0:
                audio_filters.append(f"volume={volume:.6f}")

        for overlay in overlays:
            position = overlay.position or "bottom"
            y = "h*0.08" if position == "top" else "(h-text_h)/2" if position == "center" else "h-text_h-h*0.08"
            text = self._escape_drawtext(overlay.text or "")
            video_filters.append(
                "drawtext="
                f"text='{text}':x=(w-text_w)/2:y={y}:"
                "fontsize=h/18:fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=12"
            )

        cmd = [FFMPEG_BIN, "-y", "-i", str(source)]
        if video_filters:
            cmd += ["-vf", ",".join(video_filters)]
        if metadata["has_audio"] and audio_filters:
            cmd += ["-af", ",".join(audio_filters)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart"]
        if metadata["has_audio"]:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += [str(output)]
        _run(cmd)
        return output

    def extract_frame(self, source: Path, output: Path, at_seconds: float = 0.0) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        _run([FFMPEG_BIN, "-y", "-ss", str(max(0.0, at_seconds)), "-i", str(source), "-frames:v", "1", "-q:v", "2", str(output)])
        return output

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
