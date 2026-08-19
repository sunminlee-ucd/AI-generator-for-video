import pytest

from app.main import _validate_operations_for_project, health
from app.schemas import EditOperation
from app.services.project_store import ProjectStore


def test_health_exposes_ai_readiness_without_secret():
    payload = health()
    assert payload["status"] == "ok"
    assert payload["manual_editing"] is True
    assert payload["ai"]["provider"] == "gemini"
    assert isinstance(payload["ai"]["configured"], bool)
    assert payload["ai"]["model"]
    assert "api_key" not in payload["ai"]


def test_public_project_contract_for_native_clients():
    project = {
        "id": "project-1",
        "filename": "photo.jpg",
        "source_kind": "image",
        "metadata": {"kind": "image", "duration_seconds": 5.0},
        "operations": [],
        "assets": [
            {
                "id": "asset-1",
                "filename": "clip.mp4",
                "kind": "video",
                "path": "/tmp/clip.mp4",
                "metadata": {"kind": "video", "duration_seconds": 2.0},
            }
        ],
        "preview_path": "/tmp/preview.mp4",
    }

    payload = ProjectStore.public_project(project)
    assert payload["source_kind"] == "image"
    assert payload["source_url"] == "/api/projects/project-1/media/source"
    assert payload["preview_url"] == "/api/projects/project-1/media/preview"
    assert payload["assets"][0]["url"] == "/api/projects/project-1/assets/asset-1"
    assert "path" not in payload["assets"][0]


def test_manual_edit_preflight_rejects_wrong_asset_kind():
    project = {
        "metadata": {"duration_seconds": 10.0},
        "assets": [{"id": "audio-1", "kind": "audio"}],
    }
    operation = EditOperation(type="picture_in_picture", secondary_asset_id="audio-1")
    with pytest.raises(ValueError, match="photo or video"):
        _validate_operations_for_project(project, [operation])


def test_manual_edit_preflight_rejects_trim_beyond_duration():
    project = {"metadata": {"duration_seconds": 10.0}, "assets": []}
    operation = EditOperation(type="trim", start_seconds=1, end_seconds=11)
    with pytest.raises(ValueError, match="project duration"):
        _validate_operations_for_project(project, [operation])
