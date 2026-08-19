# AI Video Editor

A native-first conversational media editor with a shared FastAPI/FFmpeg backend.

- **iPhone:** native SwiftUI app in `ios/AIEditor`, built with Xcode command-line tooling (`xcrun xcodebuild`).
- **Android:** native Kotlin app in `android`, built as an installable APK.
- **Backend:** FastAPI + Gemini edit planning + FFmpeg rendering/compositing + optional Wan generative preview.
- **Web UI:** retained as a development/fallback client, but it is no longer the primary product surface.

## Product model

Photos and videos are first-class visual media. A project can start from either a **photo or video**, and extra visual assets can also be photos or videos. Audio remains a separate media kind.

```text
media
├── video
├── image
└── audio
```

A still image is treated as a timed visual clip (5 seconds by default) so the same rendering pipeline can compose it with video, text, masks, motion, and music.

## Generic visual operations

- Photo or video project source.
- Photo/video split screen.
- Photo/video picture-in-picture.
- `media_overlay`: place an uploaded photo or video over the current canvas.
- `masked_media`: place an uploaded photo or video inside a star/circle/heart/triangle.
- Legacy `masked_video`: mask the project source while a photo or video plays/sits behind it.
- X/Y motion paths for visual layers.
- Drag positioning on both native clients.
- Android pinch-to-resize; iOS drag positioning plus simple size controls.
- Text, trim, speed, mute/volume, and background music remain part of the same operation model.

AI edits are proposals first: **Ask AI -> Review -> Fine-tune -> Apply**. AI and manual controls edit the same structured operations.

## Backend setup

Requirements:

- Python 3.10+
- FFmpeg / FFprobe
- Gemini API key
- Pillow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=...
uvicorn app.main:app --reload
```

For physical phones, use the HTTPS URL of the deployed backend. Localhost on a real phone refers to the phone itself.

## Cloud Run + Gemini

The Gemini key belongs only on the backend. Do **not** put it in Swift, Kotlin, the APK, or GitHub source.

A one-command Cloud Run deployment is included:

```bash
export GCP_PROJECT_ID="your-google-cloud-project-id"
export GCP_REGION="europe-west1"
bash deploy/cloud-run.sh
```

On the first deployment, the script prompts for the Gemini API key using hidden input, stores it in Google Secret Manager, grants the Cloud Run runtime service account access to that secret, deploys the backend from source, and verifies `/api/health`.

Subsequent deploys reuse the existing secret automatically:

```bash
GCP_PROJECT_ID="your-google-cloud-project-id" bash deploy/cloud-run.sh
```

The backend uses `gemini-3.6-flash` by default and exposes only safe readiness metadata from `/api/health`; it never returns the API key.

The current Cloud Run profile intentionally keeps **one warm instance** with CPU throttling disabled because project files and background render-job state are still local to a single process. This is an MVP/private-testing profile. Cloud Storage plus a durable render queue are the next step before multi-instance production scaling.

See [`deploy/CLOUD_RUN.md`](deploy/CLOUD_RUN.md) for prerequisites, overrides, key rotation, verification, and native-app connection instructions.

## iPhone app

Open:

```text
ios/AIEditor/AIEditor.xcodeproj
```

Simulator command-line build:

```bash
cd ios/AIEditor
chmod +x build-ios.sh
./build-ios.sh simulator
```

The script uses `xcrun xcodebuild`.

For a physical iPhone, provide your Apple Developer Team ID and let Xcode manage provisioning:

```bash
cd ios/AIEditor
DEVELOPMENT_TEAM=YOUR_TEAM_ID ./build-ios.sh device
```

The iOS app uses `PhotosPicker` to select photos/videos. Selected photos are normalized to JPEG before upload, which also makes common iPhone photo formats usable by the backend without special server-side HEIC handling.

## Android app / APK

The Android client is under `android/` and uses native Android framework UI with touch-first controls.

Local debug APK build:

```bash
cd android
chmod +x build-android.sh
./build-android.sh
```

Output:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

The debug APK is directly installable for testing. A production release APK should be signed with your own Android signing key.

Android photos are downsampled when necessary and normalized to JPEG before upload. Video/audio files are copied from the Android document picker into app cache and uploaded as media assets.

## CI mobile artifacts

`.github/workflows/mobile-builds.yml` runs three jobs:

1. backend FFmpeg/Python tests,
2. Android debug APK build and artifact upload,
3. iOS simulator build with `xcrun xcodebuild` on a macOS runner.

The Android artifact is named `AIEditor-Android-debug-apk`. The iOS simulator artifact is named `AIEditor-iOS-simulator-app`.

A signed iPhone device build is intentionally not produced in CI until Apple signing credentials are configured.

## API highlights

Create a project from a photo or video:

```text
POST /api/projects
```

Optional form field for still-image duration:

```text
still_duration_seconds=5
```

Add another photo/video/audio asset:

```text
POST /api/projects/{project_id}/assets
kind=auto|image|video|audio
```

Ask AI for an edit proposal:

```text
POST /api/projects/{project_id}/commands
```

Apply reviewed changes:

```text
POST /api/projects/{project_id}/apply-plan
```

Fine-tune all applied operations and re-render:

```text
PUT /api/projects/{project_id}/operations
```

Preview/source media endpoints:

```text
GET /api/projects/{project_id}/media/source
GET /api/projects/{project_id}/media/preview
```

The previous `/video/{kind}` route remains as a compatibility alias.

Health/readiness:

```text
GET /api/health
```

The health response reports whether Gemini is configured without exposing the secret.

## Tests

```bash
pytest -q
```

Coverage includes video editing, moving masked video, background video + music, schema validation, mobile-web regression checks, photo/video interoperability, and Cloud Run deployment safeguards. `tests/test_image_media.py` verifies a still-image project with a moving image overlay and a video project with a star-masked image layer.

## Current native UX

Both native clients follow a simple first-run flow:

1. Choose photo or video.
2. Ask AI in plain language.
3. Review proposed edits.
4. Expand only the change you want to adjust.
5. Drag visual layers directly rather than entering coordinates.
6. Apply AI changes or render manual adjustments.
7. Add more photos, videos, or music from the Media tab.

## Next priorities

1. Deploy the backend to Cloud Run and set the resulting HTTPS URL in both native apps.
2. Move project files and rendered outputs to Cloud Storage and replace the in-memory render queue with a durable worker/queue architecture.
3. iOS pinch-to-resize + two-finger rotation to match Android direct manipulation.
4. Native motion-point/keyframe UI on both platforms.
5. Visual trim handles and a true multi-track timeline.
6. Curated CC0/CC-BY music library with licence metadata.
7. Physical-device usability passes on current iOS and Android devices.
8. Production signing/release pipelines for TestFlight/App Store and signed Android releases.
