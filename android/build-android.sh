#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x ./gradlew ]]; then
  ./gradlew :app:assembleDebug
elif command -v gradle >/dev/null 2>&1; then
  gradle :app:assembleDebug
else
  echo "Gradle is required. Install Gradle 9.5+ or use the GitHub Actions mobile build." >&2
  exit 2
fi

echo "APK: $(pwd)/app/build/outputs/apk/debug/app-debug.apk"
