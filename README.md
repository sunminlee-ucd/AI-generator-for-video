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

For physical phones, set the native app's Backend Server setting to the HTTPS URL of the deployed backend (for example a Cloud Run service). Localhost only refers to the phone itself when running on a real device.

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

## Tests

```bash
pytest -q
```

Coverage includes video editing, moving masked video, background video + music, schema validation, mobile-web regression checks, and photo/video interoperability. `tests/test_image_media.py` verifies a still-image project with a moving image overlay and a video project with a star-masked image layer.

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

1. iOS pinch-to-resize + two-finger rotation to match Android direct manipulation.
2. Native motion-point/keyframe UI on both platforms.
3. Visual trim handles and a true multi-track timeline.
4. Curated CC0/CC-BY music library with licence metadata.
5. Cloud Storage + persistent render queue for production deployment.
6. Physical-device usability passes on current iOS and Android devices.
7. Production signing/release pipelines for TestFlight/App Store and signed Android releases.
