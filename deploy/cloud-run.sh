#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE="${CLOUD_RUN_SERVICE:-ai-media-editor}"
RUNTIME_SA_NAME="${CLOUD_RUN_SERVICE_ACCOUNT:-ai-media-editor-runtime}"
SECRET_NAME="${GEMINI_SECRET_NAME:-gemini-api-key}"
MODEL="${GEMINI_MODEL:-gemini-3.6-flash}"
MIN_INSTANCES="${CLOUD_RUN_MIN_INSTANCES:-1}"
MAX_INSTANCES="${CLOUD_RUN_MAX_INSTANCES:-1}"
CPU="${CLOUD_RUN_CPU:-2}"
MEMORY="${CLOUD_RUN_MEMORY:-4Gi}"
CONCURRENCY="${CLOUD_RUN_CONCURRENCY:-4}"
MAX_UPLOAD_MB="${MAX_UPLOAD_MB:-500}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "GCP_PROJECT_ID is required."
  echo "Example: GCP_PROJECT_ID=my-project bash deploy/cloud-run.sh"
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required. Install Google Cloud CLI and run 'gcloud auth login' first."
  exit 1
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  echo "No active gcloud account. Run: gcloud auth login"
  exit 1
fi

echo "Deploying AI Media Editor"
echo "  project: $PROJECT_ID"
echo "  region:  $REGION"
echo "  service: $SERVICE"
echo "  model:   $MODEL"
echo "  account: $ACTIVE_ACCOUNT"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT_ID"

RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Creating Cloud Run runtime service account..."
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name "AI Media Editor Cloud Run runtime"
fi

SECRET_EXISTS=0
if gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  SECRET_EXISTS=1
fi

if [[ "$SECRET_EXISTS" -eq 0 ]]; then
  if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    read -r -s -p "Gemini API key: " GEMINI_API_KEY
    echo
  fi
  if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "Gemini API key cannot be empty."
    exit 1
  fi
  echo "Creating Secret Manager secret '$SECRET_NAME'..."
  printf '%s' "$GEMINI_API_KEY" | gcloud secrets create "$SECRET_NAME" \
    --project "$PROJECT_ID" \
    --replication-policy=automatic \
    --data-file=-
elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
  echo "Adding a new Gemini API key secret version..."
  printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
    --project "$PROJECT_ID" \
    --data-file=-
else
  echo "Reusing the existing '$SECRET_NAME' secret."
fi
unset GEMINI_API_KEY || true

SECRET_VERSION="$(gcloud secrets versions list "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --filter='state=ENABLED' \
  --sort-by='~createTime' \
  --limit=1 \
  --format='value(name)' | awk -F/ '{print $NF}')"

if [[ -z "$SECRET_VERSION" ]]; then
  echo "No enabled version exists for secret '$SECRET_NAME'."
  exit 1
fi

echo "Granting the runtime service account access to the Gemini secret..."
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  >/dev/null

echo "Building from source and deploying to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  --service-account "$RUNTIME_SA_EMAIL" \
  --cpu "$CPU" \
  --memory "$MEMORY" \
  --concurrency "$CONCURRENCY" \
  --timeout 900 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --no-cpu-throttling \
  --set-env-vars="GEMINI_MODEL=${MODEL},DATA_DIR=/tmp/ai-editor-data,MAX_UPLOAD_MB=${MAX_UPLOAD_MB}" \
  --update-secrets="GEMINI_API_KEY=${SECRET_NAME}:${SECRET_VERSION}"

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)')"

echo
echo "Cloud Run deployment complete: $SERVICE_URL"
echo "Checking backend and Gemini secret injection..."
HEALTH="$(curl --fail --silent --show-error "$SERVICE_URL/api/health")"
echo "$HEALTH"

if command -v python3 >/dev/null 2>&1; then
  SERVICE_URL="$SERVICE_URL" HEALTH="$HEALTH" python3 - <<'PY'
import json
import os

health = json.loads(os.environ["HEALTH"])
if health.get("status") != "ok":
    raise SystemExit("Health check did not return status=ok")
if not health.get("ai", {}).get("configured"):
    raise SystemExit("Cloud Run is healthy, but GEMINI_API_KEY was not injected")
print("AI configuration check passed.")
print("Set the iPhone and Android Backend Server URL to:")
print(os.environ["SERVICE_URL"])
PY
fi

echo
echo "NOTE: This MVP intentionally keeps one warm Cloud Run instance because render jobs and project files are currently in-memory/local to one instance. Move projects to Cloud Storage and jobs to a durable queue before scaling beyond one instance."
