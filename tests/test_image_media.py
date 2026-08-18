from pathlib import Path
import subprocess

from PIL import Image

from app.schemas import EditOperation, MotionKeyframe
from app.services.ffmpeg_engine import FFmpegEngine


def make_video(path: Path, duration: int = 2):
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=24:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ], check=True, capture_output=True)


def test_image_source_and_image_overlay(tmp_path):
    source = tmp_path / "source.jpg"
    overlay = tmp_path / "overlay.png"
    output = tmp_path / "out.mp4"
    Image.new("RGB", (320, 240), "navy").save(source)
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(overlay)

    engine = FFmpegEngine()
    metadata = engine.inspect_media(source, 3)
    assert metadata["kind"] == "image"
    assert metadata["duration_seconds"] == 3

    operations = [
        EditOperation(
            type="media_overlay",
            source_asset_id="img",
            x=20,
            y=30,
            width=100,
            height=100,
            motion_keyframes=[
                MotionKeyframe(time_seconds=0, x=20, y=30),
                MotionKeyframe(time_seconds=2, x=180, y=100, easing="ease_in_out"),
            ],
        )
    ]
    engine.render(
        source,
        operations,
        output,
        {"img": {"path": str(overlay), "kind": "image"}},
        source_kind="image",
        source_duration=3,
    )
    rendered = engine.probe(output)
    assert rendered["has_video"] is True
    assert 2.8 <= rendered["duration_seconds"] <= 3.2


def test_video_source_with_masked_image_layer(tmp_path):
    source = tmp_path / "source.mp4"
    photo = tmp_path / "photo.jpg"
    output = tmp_path / "out.mp4"
    make_video(source, 2)
    Image.new("RGB", (200, 200), "green").save(photo)

    engine = FFmpegEngine()
    operations = [
        EditOperation(
            type="masked_media",
            source_asset_id="photo",
            shape="star",
            x=60,
            y=20,
            width=140,
            height=140,
        )
    ]
    engine.render(
        source,
        operations,
        output,
        {"photo": {"path": str(photo), "kind": "image"}},
        source_kind="video",
    )
    rendered = engine.probe(output)
    assert rendered["has_video"] is True
    assert rendered["has_audio"] is True
