from __future__ import annotations

from pathlib import Path

from app.config import FFMPEG_BIN, PREVIEW_CRF, PREVIEW_MAX_DIMENSION, PREVIEW_PRESET
from app.services.ffmpeg_engine import _run


class PhotoTurnRenderer:
    """Create a lightweight 3D-like turntable clip from front/side/back photos.

    This MVP is deliberately deterministic and CPU-friendly. It does not reconstruct a real
    3D mesh. Instead it normalizes the three views, runs a front -> side -> back -> side -> front
    sequence and blends the views with a directional smooth transition. The result reads as a
    short turntable animation while remaining practical on the current Cloud Run CPU service.
    """

    def render(
        self,
        front: Path,
        side: Path,
        back: Path,
        output: Path,
        *,
        width: int,
        height: int,
        duration_seconds: float = 4.0,
        direction: str = "left",
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        width, height = self._preview_dimensions(width, height)
        duration = max(2.0, min(float(duration_seconds), 8.0))
        transition = min(0.48, duration / 9.0)
        segment = (duration + 4.0 * transition) / 5.0
        step = segment - transition
        transition_name = "smoothright" if direction == "right" else "smoothleft"

        normalize = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0xFFF9E6,"
            f"setsar=1,fps=30,trim=duration={segment:.4f},setpts=PTS-STARTPTS,format=yuv420p"
        )
        filters = [
            f"[0:v]{normalize}[front]",
            f"[1:v]{normalize}[side]",
            f"[2:v]{normalize}[back]",
            "[front]split=2[front_a][front_b]",
            "[side]split=2[side_a][side_b]",
            (
                f"[front_a][side_a]xfade=transition={transition_name}:"
                f"duration={transition:.4f}:offset={step:.4f}[turn1]"
            ),
            (
                f"[turn1][back]xfade=transition={transition_name}:"
                f"duration={transition:.4f}:offset={2 * step:.4f}[turn2]"
            ),
            (
                f"[turn2][side_b]xfade=transition={transition_name}:"
                f"duration={transition:.4f}:offset={3 * step:.4f}[turn3]"
            ),
            (
                f"[turn3][front_b]xfade=transition={transition_name}:"
                f"duration={transition:.4f}:offset={4 * step:.4f},"
                "eq=contrast=1.025:saturation=1.035,format=yuv420p[outv]"
            ),
        ]

        command = [
            FFMPEG_BIN,
            "-y",
            "-loop",
            "1",
            "-i",
            str(front),
            "-loop",
            "1",
            "-i",
            str(side),
            "-loop",
            "1",
            "-i",
            str(back),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-t",
            f"{duration:.4f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            PREVIEW_PRESET,
            "-crf",
            str(PREVIEW_CRF),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
        _run(command)
        return output

    @staticmethod
    def _even(value: int) -> int:
        value = max(2, int(value))
        return value if value % 2 == 0 else value - 1

    def _preview_dimensions(self, width: int, height: int) -> tuple[int, int]:
        width = max(2, int(width or 1280))
        height = max(2, int(height or 720))
        longest = max(width, height)
        if longest > PREVIEW_MAX_DIMENSION:
            scale = PREVIEW_MAX_DIMENSION / longest
            width = int(width * scale)
            height = int(height * scale)
        return self._even(width), self._even(height)
