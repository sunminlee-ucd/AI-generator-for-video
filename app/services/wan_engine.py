from __future__ import annotations

from pathlib import Path
import subprocess

from app.config import WAN_CKPT_DIR, WAN_FRAME_NUM, WAN_PYTHON_BIN, WAN_REPO_PATH, WAN_SIZE, WAN_TASK
from app.services.ffmpeg_engine import FFmpegEngine

class WanError(RuntimeError):
    pass

class WanEngine:
    """Adapter for the official Wan2.2 generate.py script.

    The MVP uses TI2V-5B image-to-video mode for a short generative preview.
    It does not claim frame-perfect source-video motion preservation.
    """

    def __init__(self):
        if not WAN_REPO_PATH or not WAN_CKPT_DIR:
            raise WanError("WAN_REPO_PATH and WAN_CKPT_DIR must be configured")
        self.repo = Path(WAN_REPO_PATH)
        self.ckpt = Path(WAN_CKPT_DIR)
        self.ffmpeg = FFmpegEngine()

    def generate_preview(self, source: Path, style_prompt: str, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame = output.parent / "wan_reference.jpg"
        self.ffmpeg.extract_frame(source, frame, at_seconds=0.0)

        cmd = [
            WAN_PYTHON_BIN,
            str(self.repo / "generate.py"),
            "--task", WAN_TASK,
            "--size", WAN_SIZE,
            "--ckpt_dir", str(self.ckpt),
            "--offload_model", "True",
            "--convert_model_dtype",
            "--t5_cpu",
            "--frame_num", str(WAN_FRAME_NUM),
            "--image", str(frame),
            "--prompt", style_prompt,
            "--save_file", str(output),
        ]
        result = subprocess.run(cmd, cwd=self.repo, capture_output=True, text=True)
        if result.returncode != 0:
            raise WanError(result.stderr.strip() or result.stdout.strip() or "Wan2.2 generation failed")
        if not output.exists():
            raise WanError("Wan2.2 completed without producing the requested output file")
        return output
