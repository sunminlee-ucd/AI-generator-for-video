from pathlib import Path
import subprocess

from app.schemas import EditOperation
from app.services.ffmpeg_engine import FFmpegEngine


def make_sample(path: Path, duration: int = 4):
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=24:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ], check=True, capture_output=True)


def test_probe_and_render_trim_speed(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    make_sample(source)
    engine = FFmpegEngine()

    metadata = engine.probe(source)
    assert 3.8 <= metadata["duration_seconds"] <= 4.2
    assert metadata["has_video"] is True
    assert metadata["has_audio"] is True

    operations = [
        EditOperation(type="trim", start_seconds=1.0, end_seconds=3.0),
        EditOperation(type="speed", speed=2.0),
    ]
    engine.render(source, operations, output)

    rendered = engine.probe(output)
    assert 0.8 <= rendered["duration_seconds"] <= 1.2


def test_masked_video_with_background_and_music(tmp_path):
    source = tmp_path / "source.mp4"
    background = tmp_path / "background.mp4"
    music = tmp_path / "music.wav"
    output = tmp_path / "composite.mp4"
    make_sample(source, 2)

    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:size=320x240:rate=24",
        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(background),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100",
        "-t", "2", str(music),
    ], check=True, capture_output=True)

    assets = {
        "bg": {"path": str(background)},
        "music": {"path": str(music)},
    }
    operations = [
        EditOperation(
            type="masked_video", secondary_asset_id="bg", shape="star",
            x=80, y=40, width=160, height=160, feather=2,
        ),
        EditOperation(type="text_overlay", text="Hello", font_family="DejaVu Sans", font_size=24),
        EditOperation(
            type="music", source_asset_id="music", volume=0.1,
            ducking=True, fade_out_seconds=0.3,
        ),
    ]

    engine = FFmpegEngine()
    engine.render(source, operations, output, assets)
    rendered = engine.probe(output)
    assert output.exists()
    assert rendered["has_video"] is True
    assert rendered["has_audio"] is True
    assert 1.7 <= rendered["duration_seconds"] <= 2.2
