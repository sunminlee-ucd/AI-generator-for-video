#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-simulator}"
if [[ "$MODE" == "simulator" ]]; then
  xcrun xcodebuild -project AIEditor.xcodeproj -scheme AIEditor -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build
  exit 0
fi
if [[ -z "${DEVELOPMENT_TEAM:-}" ]]; then
  echo "Set DEVELOPMENT_TEAM to your Apple Developer Team ID for a physical iPhone build." >&2
  exit 2
fi
xcrun xcodebuild -project AIEditor.xcodeproj -scheme AIEditor -sdk iphoneos -configuration Debug -destination 'generic/platform=iOS' DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM" CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates build
