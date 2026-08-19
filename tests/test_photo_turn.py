import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from app.config import FFPROBE_BIN
from app.schemas import EditOperation
from app.services.photo_turn import PhotoTurnRenderer


def _view(path: Path, x: int, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (320, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x, 35, x + 90, 215), radius=18, fill=color)
    image.save(path)


def test_photo_turn_schema_defaults_to_background_cleanup():
    operation = EditOperation(
        type="photo_turn_3d",
        secondary_asset_id="side",
        tertiary_asset_id="back",
    )
    assert operation.remove_background is True
    assert operation.turn_duration_seconds == 4.0


def test_photo_turn_renderer_creates_smooth_60fps_mp4(tmp_path: Path):
    front = tmp_path / "front.png"
    side = tmp_path / "side.png"
    back = tmp_path / "back.png"
    output = tmp_path / "turn.mp4"
    _view(front, 115, (46, 125, 50))
    _view(side, 130, (65, 142, 68))
    _view(back, 110, (38, 102, 42))

    PhotoTurnRenderer().render(
        front,
        side,
        back,
        output,
        width=320,
        height=240,
        duration_seconds=2.0,
        direction="left",
        remove_background=True,
    )

    assert output.exists()
    assert output.stat().st_size > 1000

    probe = subprocess.run(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate:stream_tags=rotate",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["width"] == 320
    assert stream["height"] == 240
    assert stream["avg_frame_rate"] == "60/1"
    assert stream.get("tags", {}).get("rotate") in {None, "0"}

    # Temporary normalized views should always be cleaned up.
    assert not list(tmp_path.glob("turn_front_*.png"))
    assert not list(tmp_path.glob("turn_side_*.png"))
    assert not list(tmp_path.glob("turn_back_*.png"))


def test_photo_turn_uses_exif_correct_display_orientation(tmp_path: Path):
    source = tmp_path / "portrait-by-exif.jpg"
    image = Image.new("RGB", (200, 120), "white")
    exif = Image.Exif()
    exif[274] = 6  # 90 degrees clockwise for display.
    image.save(source, "JPEG", exif=exif)
    image.close()

    assert PhotoTurnRenderer._display_dimensions(source) == (120, 200)
