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

    def create(self, filename: str, source_path: Path, metadata: dict) -> dict:
        project_id = uuid4().hex
        project_dir = PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        target = project_dir / source_path.name
        source_path.replace(target)
        data = {
            "id": project_id,
            "filename": filename,
            "source_path": str(target),
            "metadata": metadata,
            "operations": [],
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

    def apply_plan(self, project_id: str, prompt: str, plan: EditPlan) -> dict:
        with self._lock:
            data = self.get(project_id)
            batch = [op.model_dump(mode="json") for op in plan.operations]
            data["operations"].extend(batch)
            data["history"].append({
                "prompt": prompt,
                "assistant_message": plan.assistant_message,
                "operation_count": len(batch),
            })
            self._write(project_id, data)
            return data

    def undo(self, project_id: str) -> dict:
        with self._lock:
            data = self.get(project_id)
            if not data["history"]:
                return data
            count = data["history"].pop()["operation_count"]
            if count:
                del data["operations"][-count:]
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

    def _write(self, project_id: str, data: dict) -> None:
        path = PROJECTS_DIR / project_id / "project.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
