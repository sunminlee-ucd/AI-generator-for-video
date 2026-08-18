from pathlib import Path


def test_dockerfile_uses_cloud_run_port():
    dockerfile = Path("Dockerfile").read_text()
    assert "${PORT:-8080}" in dockerfile
    assert "--host 0.0.0.0" in dockerfile
    assert "ENV DATA_DIR=/tmp/ai-editor-data" in dockerfile


def test_cloud_run_deploy_uses_secret_manager_and_single_instance_mvp():
    script = Path("deploy/cloud-run.sh").read_text()
    assert "secretmanager.googleapis.com" in script
    assert "roles/secretmanager.secretAccessor" in script
    assert "--update-secrets=\"GEMINI_API_KEY=${SECRET_NAME}:${SECRET_VERSION}\"" in script
    assert "--no-cpu-throttling" in script
    assert 'CLOUD_RUN_MIN_INSTANCES:-1' in script
    assert 'CLOUD_RUN_MAX_INSTANCES:-1' in script
    assert "--allow-unauthenticated" in script


def test_cloud_build_context_does_not_upload_native_apps_or_env_files():
    ignored = Path(".gcloudignore").read_text().splitlines()
    assert ".env" in ignored
    assert "android/" in ignored
    assert "ios/" in ignored
    assert "data/" in ignored
