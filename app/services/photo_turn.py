from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter

from app.config import FFMPEG_BIN, PREVIEW_CRF, PREVIEW_MAX_DIMENSION, PREVIEW_PRESET
from app.services.ffmpeg_engine import _run


class PhotoTurnRenderer:
    """Create a lightweight 3D-like turntable clip from front/side/back photos.

    The MVP first isolates the subject from simple/mostly uniform backgrounds, normalizes the
    subject scale/position across all three views, then renders a front -> side -> back -> side
    -> front sequence. The transition frames are generated with Pillow instead of FFmpeg xfade.
    This avoids xfade constant-frame-rate compatibility failures seen on newer FFmpeg builds
    while keeping the feature CPU-friendly for the current Cloud Run service.
    """

    FPS = 24

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
        frame_count = max(self.FPS * 2, int(round(duration * self.FPS)))

        prepared_paths: list[Path] = []
        try:
            for label, source in (("front", front), ("side", side), ("back", back)):
                target = output.parent / f"turn_{label}_{uuid4().hex}.png"
                self._prepare_view(source, target, width, height, remove_background=remove_background)
                prepared_paths.append(target)

            with TemporaryDirectory(prefix="photo-turn-", dir=output.parent) as temp_dir:
                frame_dir = Path(temp_dir)
                views: list[Image.Image] = []
                try:
                    for path in prepared_paths:
                        with Image.open(path) as opened:
                            views.append(opened.convert("RGB"))

                    # Reusing the same side view on the return leg is deliberate for the 3-photo MVP.
                    sequence = [views[0], views[1], views[2], views[1], views[0]]
                    direction_sign = -1 if direction == "left" else 1

                    for index in range(frame_count):
                        progress = index / max(1, frame_count - 1) * 4.0
                        segment = min(3, int(progress))
                        local = progress - segment
                        eased = self._smoothstep(local)

                        frame = Image.blend(sequence[segment], sequence[segment + 1], eased)

                        # A very small directional drift makes the cross-view blend feel more like
                        # a turntable movement without introducing expensive 3D reconstruction.
                        drift = int(round(math.sin(local * math.pi) * width * 0.012)) * direction_sign
                        if drift:
                            shifted = Image.new("RGB", (width, height), (255, 249, 230))
                            shifted.paste(frame, (drift, 0))
                            frame.close()
                            frame = shifted

                        frame.save(frame_dir / f"frame_{index:04d}.jpg", "JPEG", quality=88)
                        frame.close()
                finally:
                    for view in views:
                        view.close()

                command = [
                    FFMPEG_BIN,
                    "-y",
                    "-framerate",
                    str(self.FPS),
                    "-i",
                    str(frame_dir / "frame_%04d.jpg"),
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

        image.close()
        if cropped is not image:
            cropped.close()
        fitted.close()
        shadow.close()
        shadow_alpha.close()
        canvas.close()

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
            rgb.close()
            work.close()
            alpha.close()
            foreground.close()
            return image

        foreground_pixels = sum(1 for value in foreground.getdata() if value)
        coverage = foreground_pixels / max(1, work.width * work.height)
        # Too little/too much detected foreground usually means the background was not simple enough.
        if coverage < 0.04 or coverage > 0.94:
            rgb.close()
            work.close()
            alpha.close()
            foreground.close()
            return image

        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=1.2))
        result = image.copy()
        original_alpha = image.getchannel("A")
        combined = Image.new("L", image.size)
        combined.putdata([min(a, b) for a, b in zip(original_alpha.getdata(), alpha.getdata())])
        result.putalpha(combined)

        rgb.close()
        work.close()
        alpha.close()
        foreground.close()
        original_alpha.close()
        combined.close()
        return result

    @staticmethod
    def _smoothstep(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

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
