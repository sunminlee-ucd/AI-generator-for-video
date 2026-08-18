from pathlib import Path
import subprocess
from unittest.mock import patch

from app.schemas import EditOperation
from app.services.render_optimizer import OptimizedFFmpegEngine


def make_video(path: Path, color: str, duration: float = 1.0, size: str = "320x240") -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={duration}",
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_trim_only_uses_stream_copy_fast_path(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    engine.probe = lambda _: {
        "duration_seconds": 10.0,
        "dimensions": {"width": 320, "height": 240},
        "has_video": True,
        "has_audio": False,
    }

    with patch("app.services.render_optimizer._run") as run:
        engine._render_basic(source, [EditOperation(type="trim", start_seconds=2, end_seconds=6)], output)

    command = run.call_args.args[0]
    assert "-c" in command
    assert command[command.index("-c") + 1] == "copy"
    assert "-ss" in command
    assert "-t" in command


def test_concat_two_videos_produces_one_longer_video(tmp_path: Path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    output = tmp_path / "joined.mp4"
    make_video(first, "red", 1.0, "320x240")
    make_video(second, "blue", 1.0, "240x320")

    engine = OptimizedFFmpegEngine()
    second_meta = engine.inspect_media(second)
    engine.render(
        first,
        [EditOperation(type="concat", secondary_asset_id="second")],
        output,
        assets={
            "second": {
                "id": "second",
                "filename": "second.mp4",
                "kind": "video",
                "path": str(second),
                "metadata": second_meta,
            }
        },
    )

    metadata = engine.probe(output)
    assert output.exists()
    assert metadata["duration_seconds"] >= 1.8
    assert metadata["dimensions"] == {"width": 320, "height": 240}


def test_split_screen_accepts_different_video_shapes(tmp_path: Path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    output = tmp_path / "split.mp4"
    make_video(first, "green", 1.0, "320x240")
    make_video(second, "yellow", 0.6, "240x320")

    engine = OptimizedFFmpegEngine()
    second_meta = engine.inspect_media(second)
    engine.render(
        first,
        [EditOperation(type="split_screen", secondary_asset_id="second", layout="side_by_side")],
        output,
        assets={
            "second": {
                "id": "second",
                "filename": "second.mp4",
                "kind": "video",
                "path": str(second),
                "metadata": second_meta,
            }
        },
    )

    metadata = engine.probe(output)
    assert output.exists()
    assert metadata["duration_seconds"] >= 0.9
    assert metadata["dimensions"] == {"width": 320, "height": 240}
