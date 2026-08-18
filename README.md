# AI Video Editor

A conversational web video editor built around three layers:

1. **Gemini 3.6 Flash** converts natural-language requests into validated edit proposals.
2. **FFmpeg** performs deterministic video/audio editing and compositing.
3. **Wan 2.2 TI2V-5B** produces short generative visual-style previews when a request needs generation rather than ordinary editing.

## Editing model

AI edits are no longer applied immediately. Gemini first returns a typed proposal. The user can fine-tune every proposed operation, disable it, remove it, or change its parameters before rendering.

The same operation model is used for AI edits and manual edits, so later commands can target the same project state instead of creating a separate AI-only workflow.

## Current MVP capabilities

- Upload a source video from the browser.
- Upload additional video and audio assets.
- Ask Gemini 3.6 Flash for an edit proposal.
- Review and fine-tune AI changes before applying them.
- Re-edit already applied operations and render again.
- Enable/disable/remove individual operations.
- Trim, speed, mute, and volume edits.
- Text overlays with position, font family, font size, colour, and background colour.
- Side-by-side and stacked split screen.
- Picture-in-picture positioning and sizing.
- Shape masks: star, circle, heart, and triangle.
- Play the main video inside a shape while a separate background video continues behind it.
- Animate masked-video and PiP position with editable keyframes.
- Use linear, ease-in, ease-out, or ease-in-out motion between keyframes.
- Allow negative keyframe positions so a layer can enter from or leave the screen.
- Add a keyframe at the current preview playhead and fine-tune its time/X/Y values.
- Background music with volume, start/end time, fade in/out, looping, and speech ducking.
- Undo the latest AI edit batch.
- Route generative style requests to Wan 2.2.
- Poll render jobs and refresh the browser preview when complete.

## Free/licensed music workflow

The app deliberately does not scrape or redistribute third-party stock-music catalogues. Verified CC0/CC-BY music can be added as project audio assets and then selected by Gemini or the user. This keeps the rendering path licence-aware while allowing a curated music library to be added later.

## Important Wan 2.2 limitation

The current Wan 2.2 adapter uses TI2V-5B in image-to-video mode. It extracts a reference frame from the currently edited video and generates a short restyled preview from that frame and the style prompt.

This is **not frame-perfect video-to-video style transfer** and does not preserve every motion in the source clip. The adapter is isolated so a stronger video-to-video provider can replace it later without changing the planner, operation editor, or FFmpeg composition layer.

## Requirements

- Python 3.10+
- FFmpeg and FFprobe
- Gemini API key
- Pillow
- Optional: CUDA-capable machine for Wan 2.2

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GEMINI_API_KEY`, then run:

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

## Workflow

1. Upload the source video.
2. Upload any extra video/audio assets needed for background video, split-screen, PiP, or music.
3. Ask AI for an edit.
4. Review the proposal in **AI changes**.
5. Change timing, font, shape, position, size, opacity, music volume, fades, ducking, etc.
6. For a masked/PiP layer, move the preview playhead and add motion keyframes with time/X/Y/easing values.
7. Apply the proposal.
8. Fine-tune applied operations and render again as needed.

## Motion model

`masked_video` and `picture_in_picture` operations can contain `motion_keyframes`. Each keyframe stores:

```json
{
  "time_seconds": 1.5,
  "x": 420,
  "y": 180,
  "easing": "ease_in_out"
}
```

FFmpeg evaluates the layer position on every frame and interpolates between keyframes. Negative X/Y positions are valid for entrance and exit animations.

## API

### Upload source video

`POST /api/projects`

### Upload another video or audio asset

`POST /api/projects/{project_id}/assets`

### Ask Gemini for an edit proposal

`POST /api/projects/{project_id}/commands`

```json
{
  "prompt": "Put the main video inside a star, use my beach clip as the background, and move the star from left to right"
}
```

This endpoint returns a proposal and does **not** render it yet.

### Apply a reviewed proposal

`POST /api/projects/{project_id}/apply-plan`

### Replace/fine-tune all applied operations

`PUT /api/projects/{project_id}/operations`

### Check a render

`GET /api/jobs/{job_id}`

### Undo

`POST /api/projects/{project_id}/undo`

## Tests

```bash
pytest -q
```

The test suite covers schema validation, trim/speed rendering, motion-keyframe validation, and a real FFmpeg integration path that combines a moving star-shaped foreground video, a separately playing background video, text, background music, fade-out, and speech ducking.

## Next engineering priorities

1. Add a visual drag/resize/rotate canvas so mask/PiP controls and keyframe positions can be set directly on the preview.
2. Add scale/rotation/opacity animation to motion keyframes in addition to X/Y movement.
3. Add a real multi-track timeline with clip handles and per-layer timing.
4. Add a curated CC0/CC-BY music catalogue with licence metadata.
5. Send sampled frames/transcript context to Gemini for semantic commands such as "keep only the parts where the cat appears".
6. Store media in Cloud Storage and move render state to a persistent database/queue for Cloud Run.
7. Add proxy generation for large source videos.
8. Add a true video-to-video generative provider while keeping Wan as an optional backend.
