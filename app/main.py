from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import MAX_UPLOAD_MB, PROJECTS_DIR
from app.schemas import CommandRequest, EditPlan
from app.services.ffmpeg_engine import FFmpegEngine
from app.services.gemini_planner import GeminiPlanner
from app.services.project_store import ProjectStore
from app.services.wan_engine import WanEngine

app = FastAPI(title="AI Video Editor", version="0.1.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

store = ProjectStore()
ffmpeg = FFmpegEngine()
executor = ThreadPoolExecutor(max_workers=2)
jobs: dict[str, dict] = {}
jobs_lock = Lock()

@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/projects")
def create_project(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    suffix = Path(file.filename).suffix.lower() or ".mp4"
    temp_dir = PROJECTS_DIR / "_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid4().hex}{suffix}"
    size = 0
    with temp_path.open("wb") as target:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                target.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB")
            target.write(chunk)
    try:
        metadata = ffmpeg.probe(temp_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid video: {exc}") from exc
    project = store.create(file.filename, temp_path, metadata)
    return _public_project(project)

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    try:
        return _public_project(store.get(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

@app.post("/api/projects/{project_id}/commands")
def command(project_id: str, request: CommandRequest):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    try:
        plan = GeminiPlanner().plan(request.prompt, project["metadata"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini planning failed: {exc}") from exc
    if not plan.operations:
        return {"job_id": None, "status": "completed", "assistant_message": plan.assistant_message, "plan": plan}
    store.apply_plan(project_id, request.prompt, plan)
    job_id = uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "project_id": project_id,
            "status": "queued",
            "error": None,
            "output_url": None,
            "assistant_message": plan.assistant_message,
            "plan": plan.model_dump(mode="json"),
        }
    executor.submit(_render_job, job_id, project_id, plan)
    return {"job_id": job_id, "status": "queued", "assistant_message": plan.assistant_message, "plan": plan}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.copy()

@app.post("/api/projects/{project_id}/undo")
def undo(project_id: str):
    try:
        store.undo(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    job_id = uuid4().hex
    plan = EditPlan(assistant_message="Undid the last edit.", operations=[])
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "project_id": project_id,
            "status": "queued",
            "error": None,
            "output_url": None,
            "assistant_message": plan.assistant_message,
            "plan": plan.model_dump(mode="json"),
        }
    executor.submit(_render_job, job_id, project_id, plan)
    return {"job_id": job_id, "status": "queued", "assistant_message": plan.assistant_message}

@app.get("/api/projects/{project_id}/video/{kind}")
def project_video(project_id: str, kind: str):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if kind == "source":
        path = Path(project["source_path"])
    elif kind == "preview" and project.get("preview_path"):
        path = Path(project["preview_path"])
    else:
        raise HTTPException(status_code=404, detail="Video not available")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not available")
    return FileResponse(path)

def _render_job(job_id: str, project_id: str, plan: EditPlan) -> None:
    _update_job(job_id, status="running")
    try:
        project = store.get(project_id)
        source = Path(project["source_path"])
        operations = store.operations(project)
        project_dir = PROJECTS_DIR / project_id
        standard_ops = [op for op in operations if op.type != "style_transfer"]
        base_preview = project_dir / "preview_base.mp4"
        ffmpeg.render(source, standard_ops, base_preview)
        style_ops = [op for op in operations if op.type == "style_transfer"]
        if style_ops:
            final = project_dir / "preview_wan.mp4"
            latest_style = style_ops[-1]
            WanEngine().generate_preview(base_preview, latest_style.style_prompt or "", final)
        else:
            final = project_dir / "preview.mp4"
            shutil.copy2(base_preview, final)
        store.set_preview(project_id, final)
        _update_job(job_id, status="completed", output_url=f"/api/projects/{project_id}/video/preview")
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc))

def _update_job(job_id: str, **changes) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(changes)

def _public_project(project: dict) -> dict:
    return {
        "id": project["id"],
        "filename": project["filename"],
        "metadata": project["metadata"],
        "operations": project["operations"],
        "history": project["history"],
        "source_url": f"/api/projects/{project['id']}/video/source",
        "preview_url": f"/api/projects/{project['id']}/video/preview" if project.get("preview_path") else None,
    }
