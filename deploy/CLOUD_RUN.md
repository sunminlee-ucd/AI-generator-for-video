# Cloud Run + Gemini deployment

The mobile apps should call the FastAPI backend. The backend owns the Gemini API key; never put the key in the iOS project, Android APK, or GitHub source.

## What the deployment script configures

`deploy/cloud-run.sh`:

1. enables Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and IAM APIs;
2. creates a dedicated Cloud Run runtime service account if needed;
3. creates or updates a Secret Manager secret for the Gemini API key;
4. grants only that runtime service account `roles/secretmanager.secretAccessor` on the Gemini secret;
5. deploys this repository from source to Cloud Run;
6. injects the pinned secret version as `GEMINI_API_KEY`;
7. sets `GEMINI_MODEL` (default `gemini-3.6-flash`);
8. checks `/api/health` and verifies that the backend sees an AI configuration.

## One-time prerequisites

Install the Google Cloud CLI and authenticate:

```bash
gcloud auth login
gcloud auth application-default login
```

Choose or create a Google Cloud project with billing enabled. You need permission to enable APIs, create service accounts/secrets, deploy Cloud Run, and build from source.

Create a Gemini API key in Google AI Studio. Do not commit it and do not paste it into mobile source code.

## First deployment

From the repository root:

```bash
export GCP_PROJECT_ID="your-google-cloud-project-id"
export GCP_REGION="europe-west1"
bash deploy/cloud-run.sh
```

If the secret does not exist, the script asks for the Gemini API key using hidden terminal input. The key is written directly to Secret Manager and is not written to `.env` or repository files.

You can also provide the key for a non-interactive first deployment:

```bash
GCP_PROJECT_ID="your-google-cloud-project-id" \
GEMINI_API_KEY="your-key" \
bash deploy/cloud-run.sh
```

Be careful with shell history and CI logs when using the non-interactive form. The interactive hidden prompt is preferred for local setup.

## Redeploy without re-entering the key

Once `gemini-api-key` exists in Secret Manager:

```bash
GCP_PROJECT_ID="your-google-cloud-project-id" bash deploy/cloud-run.sh
```

The current enabled secret version is reused.

To rotate the Gemini key, provide a new `GEMINI_API_KEY` when running the script. It creates a new Secret Manager version and pins the new Cloud Run revision to that numeric version.

## Service defaults

The deployment defaults are intentionally conservative for the current MVP:

```text
service:        ai-media-editor
region:         europe-west1
CPU:            2
memory:         4 GiB
concurrency:    4
min instances:  1
max instances:  1
CPU throttling: disabled
public access:  enabled
```

Override any of them with environment variables:

```bash
CLOUD_RUN_SERVICE=ai-media-editor-dev
CLOUD_RUN_CPU=4
CLOUD_RUN_MEMORY=8Gi
CLOUD_RUN_CONCURRENCY=2
CLOUD_RUN_MIN_INSTANCES=1
CLOUD_RUN_MAX_INSTANCES=1
```

## Why one warm instance for now

The current MVP stores project files on the container filesystem and keeps job state in Python memory. Rendering also continues in a background executor after an API request returns. Therefore the current deployment deliberately keeps a single warm instance and disables CPU throttling.

This is suitable for development and private testing, but not the final scalable architecture. Before multi-user production scaling, migrate:

- uploaded media and rendered outputs to Cloud Storage;
- project/job state to a persistent database/store;
- render execution to a durable queue / Cloud Run Jobs or another worker system.

After that, `min-instances=0` and horizontal scaling can be used safely.

## Connect the native apps

At the end of deployment, the script prints a URL such as:

```text
https://ai-media-editor-xxxxx-ew.a.run.app
```

Use that HTTPS URL as **Backend Server** in both the iPhone and Android apps. The mobile apps never need the Gemini API key.

## Verify

Open:

```text
https://YOUR_SERVICE_URL/api/health
```

Expected shape:

```json
{
  "status": "ok",
  "ai": {
    "provider": "gemini",
    "configured": true,
    "model": "gemini-3.6-flash"
  }
}
```

`configured: true` proves that the secret was injected into Cloud Run. The first real AI editing command verifies that the key itself is valid and permitted to call the configured Gemini model.
