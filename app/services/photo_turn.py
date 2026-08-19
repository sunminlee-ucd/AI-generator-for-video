from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter

from app.config import FFMPEG_BIN, PREVIEW_CRF, PREVIEW_MAX_DIMENSION, PREVIEW_PRESET
from app.services.ffmpeg_engine import _run


class PhotoTurnRenderer:
    """Create a lightweight 3D-like turntable clip from front/side/back photos.

    The MVP first isolates the subject from simple/mostly uniform backgrounds, normalizes the
    subject scale/position across all three views, then renders a front -> side -> back -> side
    -> front sequence using smooth directional blends. This is intentionally a CPU-friendly
    2.5D illusion rather than a real 3D reconstruction.
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
        remove_background: bool = True,
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        width, height = self._preview_dimensions(width, height)
        duration = max(2.0, min(float(duration_seconds), 8.0))
        transition = min(0.48, duration / 9.0)
        segment = (duration + 4.0 * transition) / 5.0
        step = segment - transition
        transition_name = "smoothright" if direction == "right" else "smoothleft"

        prepared_paths: list[Path] = []
        try:
            for label, source in (("front", front), ("side", side), ("back", back)):
                target = output.parent / f"turn_{label}_{uuid4().hex}.png"
                self._prepare_view(source, target, width, height, remove_background=remove_background)
                prepared_paths.append(target)

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

            command = [FFMPEG_BIN, "-y"]
            for prepared in prepared_paths:
                command.extend(["-loop", "1", "-i", str(prepared)])
            command.extend(
                [
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
            )
            _run(command)
            return output
        finally:
            for path in prepared_paths:
                path.unlink(missing_ok=True)

    def _prepare_view(self, source: Path, target: Path, width: int, height: int, *, remove_background: bool) -> None:
        with Image.open(source) as opened:
            image = opened.convert("RGBA")

        # Keep segmentation work bounded even when the user uploads a very large phone photo.
        analysis_max = 1400
        longest = max(image.size)
        if longest > analysis_max:
            ratio = analysis_max / longest
            image = image.resize((max(2, int(image.width * ratio)), max(2, int(image.height * ratio))), Image.Resampling.LANCZOS)

        if remove_background:
            image = self._remove_simple_background(image)

        alpha = image.getchannel("A")
        threshold = alpha.point(lambda value: 255 if value > 24 else 0)
        bbox = threshold.getbbox()
        if bbox:
            cropped = image.crop(bbox)
        else:
            cropped = image

        # Normalize all views to nearly the same subject height. This is the most important
        # visual step after background removal for making front/side/back feel like one object.
        target_w = max(2, int(width * 0.84))
        target_h = max(2, int(height * 0.84))
        scale = min(target_w / max(1, cropped.width), target_h / max(1, cropped.height))
        fitted = cropped.resize(
            (max(2, int(cropped.width * scale)), max(2, int(cropped.height * scale))),
            Image.Resampling.LANCZOS,
        )

        canvas = Image.new("RGBA", (width, height), (255, 249, 230, 255))
        x = (width - fitted.width) // 2
        y = max(0, int((height - fitted.height) * 0.46))

        # Soft drop shadow gives the isolated object a little volume without requiring 3D geometry.
        shadow_alpha = fitted.getchannel("A").filter(ImageFilter.GaussianBlur(radius=max(2, width // 300)))
        shadow = Image.new("RGBA", fitted.size, (20, 55, 28, 0))
        shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.18)))
        canvas.alpha_composite(shadow, (x + max(2, width // 180), y + max(3, height // 150)))
        canvas.alpha_composite(fitted, (x, y))
        canvas.convert("RGB").save(target, "PNG", optimize=True)

    def _remove_simple_background(self, image: Image.Image) -> Image.Image:
        """Fast CPU-only background cleanup for product/object photos.

        Flood-filling from all four corners keeps similarly-coloured details inside the object more
        often than a global colour threshold. It works best with plain or softly varying backgrounds.
        If the inferred foreground is implausible, we keep the original image rather than destroying it.
        """
        rgb = image.convert("RGB")
        work = rgb.copy()
        marker = (1, 254, 253)
        corners = [
            (0, 0),
            (max(0, work.width - 1), 0),
            (0, max(0, work.height - 1)),
            (max(0, work.width - 1), max(0, work.height - 1)),
        ]
        for point in corners:
            try:
                ImageDraw.floodfill(work, point, marker, thresh=42)
            except Exception:
                continue

        alpha = Image.new("L", work.size, 255)
        alpha.putdata([0 if pixel == marker else 255 for pixel in work.getdata()])
        foreground = alpha.point(lambda value: 255 if value > 20 else 0)
        bbox = foreground.getbbox()
        if not bbox:
            return image

        foreground_pixels = sum(1 for value in foreground.getdata() if value)
        coverage = foreground_pixels / max(1, work.width * work.height)
        # Too little/too much detected foreground usually means the background was not simple enough.
        if coverage < 0.04 or coverage > 0.94:
            return image

        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=1.2))
        result = image.copy()
        original_alpha = image.getchannel("A")
        combined = Image.new("L", image.size)
        combined.putdata([min(a, b) for a, b in zip(original_alpha.getdata(), alpha.getdata())])
        result.putalpha(combined)
        return result

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
