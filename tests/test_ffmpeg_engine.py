from pathlib import Path
import subprocess

from app.schemas import EditOperation
from app.services.ffmpeg_engine import FFmpegEngine


def make_sample(path: Path):
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
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
    assert metadata["has_audio"] is True

    operations = [
        EditOperation(type="trim", start_seconds=1.0, end_seconds=3.0),
        EditOperation(type="speed", speed=2.0),
    ]
    engine.render(source, operations, output)

    rendered = engine.probe(output)
    assert 0.8 <= rendered["duration_seconds"] <= 1.2
