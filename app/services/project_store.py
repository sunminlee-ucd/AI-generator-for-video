from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.config import PROJECTS_DIR
from app.schemas import EditOperation, EditPlan


class ProjectStore:
    def __init__(self):
        self._lock = Lock()

    def create(self, filename: str, source_path: Path, metadata: dict, source_kind: str = "video") -> dict:
        project_id = uuid4().hex
        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        target = project_dir / source_path.name
        source_path.replace(target)
        data = {
            "id": project_id,
            "filename": filename,
            "source_kind": source_kind,
            "source_path": str(target),
            "metadata": metadata,
            "operations": [],
            "assets": [],
            "history": [],
            "preview_path": None,
        }
        self._write(project_id, data)
        return data

    def get(self, project_id: str) -> dict:
        path = PROJECTS_DIR / project_id / "project.json"
        if not path.exists():
            raise KeyError(project_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def add_asset(self, project_id: str, filename: str, source_path: Path, kind: str, metadata: dict) -> dict:
        with self._lock:
            data = self.get(project_id)
            asset_id = uuid4().hex
            assets_dir = PROJECTS_DIR / project_id / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            target = assets_dir / f"{asset_id}{source_path.suffix.lower()}"
            source_path.replace(target)
            asset = {"id": asset_id, "filename": filename, "kind": kind, "path": str(target), "metadata": metadata}
            data.setdefault("assets", []).append(asset)
            self._write(project_id, data)
            return asset

    def apply_plan(self, project_id: str, prompt: str, plan: EditPlan) -> dict:
        with self._lock:
            data = self.get(project_id)
            batch = [op.model_dump(mode="json") for op in plan.operations]
            data["operations"].extend(batch)
            data["history"].append({"prompt": prompt, "assistant_message": plan.assistant_message, "operation_count": len(batch)})
            self._write(project_id, data)
            return data

    def replace_operations(self, project_id: str, operations: list[EditOperation]) -> dict:
        with self._lock:
            data = self.get(project_id)
            data["operations"] = [op.model_dump(mode="json") for op in operations]
            data["history"].append({"prompt": "Manual fine-tuning", "assistant_message": "Updated operation parameters.", "operation_count": 0})
            self._write(project_id, data)
            return data

    def undo(self, project_id: str) -> dict:
        with self._lock:
            data = self.get(project_id)
            while data["history"]:
                item = data["history"].pop()
                count = item.get("operation_count", 0)
                if count:
                    del data["operations"][-count:]
                    break
            data["preview_path"] = None
            self._write(project_id, data)
            return data

    def set_preview(self, project_id: str, preview_path: Path) -> dict:
        with self._lock:
            data = self.get(project_id)
            data["preview_path"] = str(preview_path)
            self._write(project_id, data)
            return data

    @staticmethod
    def operations(data: dict) -> list[EditOperation]:
        return [EditOperation.model_validate(op) for op in data.get("operations", [])]

    @staticmethod
    def asset_map(data: dict) -> dict[str, dict]:
        return {asset["id"]: asset for asset in data.get("assets", [])}

    @staticmethod
    def public_asset(project_id: str, asset: dict) -> dict:
        return {
            "id": asset["id"],
            "filename": asset["filename"],
            "kind": asset["kind"],
            "metadata": asset.get("metadata", {}),
            "url": f"/api/projects/{project_id}/assets/{asset['id']}",
        }

    @classmethod
    def public_project(cls, project: dict) -> dict:
        project_id = project["id"]
        return {
            "id": project_id,
            "filename": project["filename"],
            "source_kind": project.get("source_kind", "video"),
            "metadata": project.get("metadata", {}),
            "operations": project.get("operations", []),
            "assets": [cls.public_asset(project_id, asset) for asset in project.get("assets", [])],
            "source_url": f"/api/projects/{project_id}/media/source",
            "preview_url": f"/api/projects/{project_id}/media/preview" if project.get("preview_path") else None,
        }

    def _write(self, project_id: str, data: dict) -> None:
        path = PROJECTS_DIR / project_id / "project.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
