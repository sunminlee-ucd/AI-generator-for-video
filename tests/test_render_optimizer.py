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


def metadata(width=320, height=240, duration=10.0, has_audio=False):
    return {
        "duration_seconds": duration,
        "dimensions": {"width": width, "height": height},
        "has_video": True,
        "has_audio": has_audio,
    }


def test_trim_only_uses_stream_copy_fast_path(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    engine.probe = lambda _: metadata()

    with patch("app.services.render_optimizer._run") as run:
        engine._render_basic(source, [EditOperation(type="trim", start_seconds=2, end_seconds=6)], output)

    command = run.call_args.args[0]
    assert "-c" in command
    assert command[command.index("-c") + 1] == "copy"
    assert "-ss" in command
    assert "-t" in command


def test_volume_only_stream_copies_video_instead_of_reencoding(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    engine.probe = lambda _: metadata(width=1920, height=1080, has_audio=True)

    with patch("app.services.render_optimizer._run") as run:
        engine._render_basic(source, [EditOperation(type="volume", volume=0.5)], output)

    command = run.call_args.args[0]
    assert command[command.index("-c:v") + 1] == "copy"
    assert "-af" in command
    assert "volume=0.500000" in command


def test_speed_preview_downscales_4k_and_uses_ultrafast_encoder(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    engine.probe = lambda _: metadata(width=3840, height=2160, has_audio=True)

    with patch("app.services.render_optimizer._run") as run:
        engine._render_basic(source, [EditOperation(type="speed", speed=1.5)], output)

    command = run.call_args.args[0]
    video_filter = command[command.index("-vf") + 1]
    assert "setpts=PTS/1.500000" in video_filter
    assert "scale=1280:720:flags=fast_bilinear" in video_filter
    assert command[command.index("-preset") + 1] == "ultrafast"
    assert command[command.index("-crf") + 1] == "28"
    assert "atempo=1.500000" in command[command.index("-af") + 1]


def test_multiple_text_overlays_share_one_video_encode(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    engine.probe = lambda _: metadata(width=1920, height=1080)

    operations = [
        EditOperation(type="text_overlay", text="One", position="top"),
        EditOperation(type="text_overlay", text="Two", position="bottom"),
    ]
    with patch("app.services.render_optimizer._run") as run:
        engine.render(source, operations, output)

    assert run.call_count == 1
    command = run.call_args.args[0]
    video_filter = command[command.index("-vf") + 1]
    assert video_filter.count("drawtext=") == 2
    assert "scale=1280:720:flags=fast_bilinear" in video_filter


def test_music_mix_stream_copies_video(tmp_path: Path):
    engine = OptimizedFFmpegEngine()
    source = tmp_path / "source.mp4"
    music = tmp_path / "music.m4a"
    output = tmp_path / "out.mp4"
    source.write_bytes(b"placeholder")
    music.write_bytes(b"placeholder")
    engine.probe = lambda _: metadata(has_audio=True)

    with patch("app.services.render_optimizer._run") as run:
        engine._render_music(source, music, EditOperation(type="music", source_asset_id="music"), output)

    command = run.call_args.args[0]
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "aac"


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

    output_meta = engine.probe(output)
    assert output.exists()
    assert output_meta["duration_seconds"] >= 1.8
    assert output_meta["dimensions"] == {"width": 320, "height": 240}


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

    output_meta = engine.probe(output)
    assert output.exists()
    assert output_meta["duration_seconds"] >= 0.9
    assert output_meta["dimensions"] == {"width": 320, "height": 240}
