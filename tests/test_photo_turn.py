from pathlib import Path

from PIL import Image, ImageDraw

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


def test_photo_turn_renderer_creates_short_mp4(tmp_path: Path):
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
    # Temporary normalized views should always be cleaned up.
    assert not list(tmp_path.glob("turn_front_*.png"))
    assert not list(tmp_path.glob("turn_side_*.png"))
    assert not list(tmp_path.glob("turn_back_*.png"))
