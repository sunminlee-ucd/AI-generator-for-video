from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")

# Mobile previews favour responsiveness over archival quality. Final export can later use a
# separate high-quality profile while previews stay fast enough for repeated adjustments.
PREVIEW_MAX_DIMENSION = max(360, int(os.getenv("PREVIEW_MAX_DIMENSION", "1280")))
PREVIEW_CRF = min(40, max(18, int(os.getenv("PREVIEW_CRF", "28"))))
PREVIEW_PRESET = os.getenv("PREVIEW_PRESET", "ultrafast").strip() or "ultrafast"
PREVIEW_AUDIO_BITRATE = os.getenv("PREVIEW_AUDIO_BITRATE", "96k").strip() or "96k"

WAN_REPO_PATH = os.getenv("WAN_REPO_PATH", "")
WAN_CKPT_DIR = os.getenv("WAN_CKPT_DIR", "")
WAN_PYTHON_BIN = os.getenv("WAN_PYTHON_BIN", "python")
WAN_TASK = os.getenv("WAN_TASK", "ti2v-5B")
WAN_SIZE = os.getenv("WAN_SIZE", "1280*704")
WAN_FRAME_NUM = int(os.getenv("WAN_FRAME_NUM", "49"))

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
