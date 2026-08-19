from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import FFMPEG_BIN, PREVIEW_CRF, PREVIEW_MAX_DIMENSION, PREVIEW_PRESET
from app.services.ffmpeg_engine import _run


class PhotoTurnRenderer:
    """Create a lightweight 3D-like turntable clip from front/side/back photos.

    This remains a deterministic 2.5D MVP rather than a true mesh reconstruction. The renderer
    isolates and aligns the subject, then uses perspective-like horizontal foreshortening plus a
    directional wipe between neighbouring views. That avoids the double-exposure/ghosting caused
    by full-frame crossfades and reads much more like a physical object rotating.
    """

    FPS = 60
    CREAM = (255, 249, 230)

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

        # Phone photos commonly carry EXIF orientation rather than physically rotated pixels.
        # Use the visually-correct front-photo dimensions so the output itself is encoded upright
        # instead of relying on a rotation metadata flag that some players ignore.
        natural_width, natural_height = self._display_dimensions(front)
        width, height = self._preview_dimensions(natural_width or width, natural_height or height)

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
                            views.append(opened.convert("RGBA"))

                    # With only three photos the side view is intentionally reused on the return leg.
                    sequence = [views[0], views[1], views[2], views[1], views[0]]
                    direction_sign = -1 if direction == "left" else 1

                    for index in range(frame_count):
                        # Divide by frame_count rather than frame_count - 1 so the last frame sits just
                        # before the first one. This removes a visible pause when the result loops.
                        progress = index / frame_count * 4.0
                        segment = min(3, int(progress))
                        local = progress - segment
                        eased = self._smootherstep(local)

                        frame = self._yaw_frame(
                            sequence[segment],
                            sequence[segment + 1],
                            eased,
                            direction_sign,
                            width,
                            height,
                        )
                        frame.save(frame_dir / f"frame_{index:04d}.jpg", "JPEG", quality=92, subsampling=1)
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
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    PREVIEW_PRESET,
                    "-crf",
                    str(PREVIEW_CRF),
                    "-r",
                    str(self.FPS),
                    "-pix_fmt",
                    "yuv420p",
                    "-map_metadata",
                    "-1",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
                _run(command)

            return output
        finally:
            for path in prepared_paths:
                path.unlink(missing_ok=True)

    def _yaw_frame(
        self,
        current: Image.Image,
        next_view: Image.Image,
        progress: float,
        direction_sign: int,
        width: int,
        height: int,
    ) -> Image.Image:
        """Build one pseudo-yaw frame without full-frame opacity blending.

        Each neighbouring photo is horizontally foreshortened as if it were a face rotating away
        from / toward the camera. Around the middle of the turn a soft directional wipe switches
        spatial regions from one view to the next, so there is no translucent double image.
        """
        angle = progress * math.pi / 2.0
        current_factor = max(0.12, math.cos(angle))
        next_factor = max(0.12, math.sin(angle))

        current_shift = int(round((1.0 - current_factor) * width * 0.025)) * direction_sign
        next_shift = -int(round((1.0 - next_factor) * width * 0.025)) * direction_sign

        current_layer = self._foreshorten(current, current_factor, current_shift)
        next_layer = self._foreshorten(next_view, next_factor, next_shift)

        switch_start = 0.24
        switch_end = 0.76
        if progress <= switch_start:
            layer = current_layer
            next_layer.close()
        elif progress >= switch_end:
            layer = next_layer
            current_layer.close()
        else:
            reveal = self._smootherstep((progress - switch_start) / (switch_end - switch_start))
            mask = self._directional_wipe_mask(width, height, reveal, direction_sign)
            layer = Image.composite(next_layer, current_layer, mask)
            mask.close()
            current_layer.close()
            next_layer.close()

        # A slight vertical settle at the most foreshortened point makes the movement feel grounded.
        settle = int(round(math.sin(progress * math.pi) * height * 0.006))
        if settle:
            settled = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            settled.alpha_composite(layer, (0, settle))
            layer.close()
            layer = settled

        result = self._composite_subject(layer, width, height)
        layer.close()
        return result

    def _foreshorten(self, view: Image.Image, factor: float, shift_x: int) -> Image.Image:
        target_width = max(2, int(round(view.width * factor)))
        compressed = view.resize((target_width, view.height), Image.Resampling.BICUBIC)
        layer = Image.new("RGBA", view.size, (0, 0, 0, 0))
        x = (view.width - target_width) // 2 + shift_x
        layer.alpha_composite(compressed, (x, 0))
        compressed.close()
        return layer

    def _directional_wipe_mask(
        self,
        width: int,
        height: int,
        reveal: float,
        direction_sign: int,
    ) -> Image.Image:
        reveal = max(0.0, min(1.0, reveal))
        feather = max(10, width // 30)
        edge = reveal * (width + feather * 2) - feather
        values: list[int] = []
        for x in range(width):
            position = x if direction_sign < 0 else width - 1 - x
            value = int(round((edge - position + feather / 2) / feather * 255))
            values.append(max(0, min(255, value)))
        strip = Image.new("L", (width, 1))
        strip.putdata(values)
        mask = strip.resize((width, height), Image.Resampling.NEAREST)
        strip.close()
        return mask

    def _composite_subject(self, layer: Image.Image, width: int, height: int) -> Image.Image:
        canvas = Image.new("RGBA", (width, height), (*self.CREAM, 255))

        alpha = layer.getchannel("A")
        shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=max(2, width // 260)))
        shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.16))
        shadow = Image.new("RGBA", (width, height), (18, 48, 27, 0))
        shadow.putalpha(shadow_alpha)
        canvas.alpha_composite(shadow, (max(2, width // 190), max(3, height // 155)))
        canvas.alpha_composite(layer)

        result = canvas.convert("RGB")
        alpha.close()
        shadow_alpha.close()
        shadow.close()
        canvas.close()
        return result

    def _prepare_view(self, source: Path, target: Path, width: int, height: int, *, remove_background: bool) -> None:
        with Image.open(source) as opened:
            oriented = ImageOps.exif_transpose(opened)
            image = oriented.convert("RGBA")
            if oriented is not opened:
                oriented.close()

        # Keep segmentation work bounded even when the user uploads a very large phone photo.
        analysis_max = 1400
        longest = max(image.size)
        if longest > analysis_max:
            ratio = analysis_max / longest
            resized = image.resize(
                (max(2, int(image.width * ratio)), max(2, int(image.height * ratio))),
                Image.Resampling.LANCZOS,
            )
            image.close()
            image = resized

        if remove_background:
            cleaned = self._remove_simple_background(image)
            if cleaned is not image:
                image.close()
                image = cleaned

        alpha = image.getchannel("A")
        threshold = alpha.point(lambda value: 255 if value > 24 else 0)
        bbox = threshold.getbbox()
        alpha.close()
        threshold.close()

        cropped = image.crop(bbox) if bbox else image.copy()

        # Normalize all views to nearly the same subject height so view changes do not jump in size.
        target_w = max(2, int(width * 0.84))
        target_h = max(2, int(height * 0.84))
        scale = min(target_w / max(1, cropped.width), target_h / max(1, cropped.height))
        fitted = cropped.resize(
            (max(2, int(cropped.width * scale)), max(2, int(cropped.height * scale))),
            Image.Resampling.LANCZOS,
        )

        # Keep the prepared view transparent. The background and shadow are added after perspective
        # warping, otherwise the background itself would appear to rotate with the object.
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        x = (width - fitted.width) // 2
        y = max(0, int((height - fitted.height) * 0.46))
        canvas.alpha_composite(fitted, (x, y))
        canvas.save(target, "PNG", optimize=True)

        image.close()
        cropped.close()
        fitted.close()
        canvas.close()

    def _remove_simple_background(self, image: Image.Image) -> Image.Image:
        """Fast CPU-only background cleanup for simple product/object photos."""
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
        if coverage < 0.04 or coverage > 0.94:
            rgb.close()
            work.close()
            alpha.close()
            foreground.close()
            return image

        softened = alpha.filter(ImageFilter.GaussianBlur(radius=1.2))
        result = image.copy()
        original_alpha = image.getchannel("A")
        combined = Image.new("L", image.size)
        combined.putdata([min(a, b) for a, b in zip(original_alpha.getdata(), softened.getdata())])
        result.putalpha(combined)

        rgb.close()
        work.close()
        alpha.close()
        foreground.close()
        softened.close()
        original_alpha.close()
        combined.close()
        return result

    @staticmethod
    def _display_dimensions(source: Path) -> tuple[int, int]:
        with Image.open(source) as opened:
            oriented = ImageOps.exif_transpose(opened)
            size = oriented.size
            if oriented is not opened:
                oriented.close()
        return int(size[0]), int(size[1])

    @staticmethod
    def _smootherstep(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)

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
