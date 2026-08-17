# AI Video Editor

A conversational web video editor built around three layers:

1. **Gemini 3.6 Flash** converts natural-language requests into a validated edit plan.
2. **FFmpeg** performs deterministic edits such as trim, speed, audio changes, and text overlays.
3. **Wan 2.2 TI2V-5B** produces short generative visual-style previews when a request needs generation rather than ordinary editing.

## Why this architecture

The language model does not generate arbitrary shell commands. It can only return a small typed set of edit operations. This keeps edits predictable and makes validation possible before rendering.

Ordinary edits are always re-rendered from the original source in one FFmpeg pass. This avoids cumulative quality loss and keeps preview latency low. Long Wan jobs run separately so the web request does not remain blocked.

## Current MVP capabilities

- Upload a video from the browser.
- Chat with Gemini 3.6 Flash.
- Trim video.
- Change playback speed from 0.5x to 2.0x.
- Mute or change volume.
- Add text overlays.
- Undo the latest command.
- Route generative style requests to Wan 2.2.
- Poll render jobs from the browser and replace the preview when complete.

## Important Wan 2.2 limitation

The first MVP uses Wan 2.2 TI2V-5B in image-to-video mode. It extracts a reference frame from the currently edited video and generates a short restyled preview from that frame and the style prompt.

This is **not frame-perfect video-to-video style transfer** and does not preserve every motion in the source clip. The adapter is intentionally isolated so a stronger video-to-video provider can be added later without changing the chat, planner, timeline, or FFmpeg layers.

## Requirements

- Python 3.10+
- FFmpeg and FFprobe
- Gemini API key
- Optional: CUDA-capable machine for Wan 2.2

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GEMINI_API_KEY` in your environment, then run:

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

## Wan 2.2 setup

Clone the official Wan 2.2 repository and install its dependencies in a GPU environment. For the consumer-GPU path, download the `Wan2.2-TI2V-5B` checkpoint and configure:

```bash
export WAN_REPO_PATH=/absolute/path/to/Wan2.2
export WAN_CKPT_DIR=/absolute/path/to/Wan2.2-TI2V-5B
```

The app invokes the official `generate.py` script using `ti2v-5B`, image-to-video input, CPU offloading, and a short default preview of 49 frames. Change `WAN_FRAME_NUM` to trade speed for preview length.

## API

### Upload

`POST /api/projects` with multipart field `file`.

### Apply a conversational edit

`POST /api/projects/{project_id}/commands`

```json
{
  "prompt": "Cut the first four seconds and make the result 1.2x faster"
}
```

### Check a render

`GET /api/jobs/{job_id}`

### Undo

`POST /api/projects/{project_id}/undo`

## Tests

```bash
pytest -q
```

The FFmpeg test generates a synthetic four-second clip, applies trim + speed, and verifies the resulting duration.

## Next engineering priorities

1. Send sampled frames/transcript context to Gemini for semantic commands such as "keep only the parts where the cat appears".
2. Replace the in-process thread pool with Redis + a worker queue for production.
3. Store media in object storage instead of the local filesystem.
4. Add authentication and per-user project isolation.
5. Add proxy generation for large source videos.
6. Add a true video-to-video generative provider while keeping the Wan adapter as an optional backend.
