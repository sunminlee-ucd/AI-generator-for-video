from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_UPLOAD_MB, PROJECTS_DIR
from app.schemas import ApplyPlanRequest, CommandRequest, EditPlan, EditOperation, ReplaceOperationsRequest
from app.services.render_optimizer import OptimizedFFmpegEngine
from app.services.gemini_planner import GeminiPlanner
from app.services.photo_turn import PhotoTurnRenderer
from app.services.project_store import ProjectStore
from app.services.wan_engine import WanEngine

app = FastAPI(title="AI Video Editor", version="0.6.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

store = ProjectStore()
ffmpeg = OptimizedFFmpegEngine()
executor = ThreadPoolExecutor(max_workers=2)
jobs: dict[str, dict] = {}
jobs_lock = Lock()


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "media_kinds": ["video", "image", "audio"],
        "native_clients": ["ios", "android"],
        "manual_editing": True,
        "photo_turn_3d": True,
        "ai": {
            "provider": "gemini",
            "configured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL,
        },
        "runtime": {
            "service": os.getenv("K_SERVICE"),
            "revision": os.getenv("K_REVISION"),
        },
    }


@app.post("/api/projects")
def create_project(file: UploadFile = File(...), still_duration_seconds: float = Form(5.0)):
    if not 0.5 <= still_duration_seconds <= 120:
        raise HTTPException(status_code=400, detail="still_duration_seconds must be between 0.5 and 120")
    temp_path = _save_upload(file)
    try:
        metadata = ffmpeg.inspect_media(temp_path, still_duration_seconds)
        if metadata["kind"] not in {"video", "image"}:
            raise ValueError("The project source must be a photo or video")
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid source media: {exc}") from exc
    project = store.create(file.filename or f"source{temp_path.suffix}", temp_path, metadata, source_kind=metadata["kind"])
    return _public_project(project)


@app.post("/api/projects/{project_id}/assets")
def upload_asset(project_id: str, file: UploadFile = File(...), kind: str = Form("auto"), still_duration_seconds: float = Form(5.0)):
    try:
        store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if kind not in {"auto", "video", "image", "audio"}:
        raise HTTPException(status_code=400, detail="kind must be auto, video, image, or audio")
    temp_path = _save_upload(file)
    try:
        metadata = ffmpeg.inspect_media(temp_path, still_duration_seconds)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid media: {exc}") from exc
    detected = metadata["kind"]
    if kind != "auto" and kind != detected:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Expected {kind}, detected {detected}")
    asset = store.add_asset(project_id, file.filename or f"asset{temp_path.suffix}", temp_path, detected, metadata)
    return _public_asset(project_id, asset)


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
        plan = GeminiPlanner().plan(request.prompt, project["metadata"], project.get("assets", []), project.get("source_kind", "video"))
        _validate_operations_for_project(project, store.operations(project) + plan.operations)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini planning failed: {exc}") from exc
    return {"status": "proposal", "assistant_message": plan.assistant_message, "plan": plan.model_dump(mode="json")}


@app.post("/api/projects/{project_id}/apply-plan")
def apply_plan(project_id: str, request: ApplyPlanRequest):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    _ensure_no_active_render(project_id)
    try:
        _validate_operations_for_project(project, store.operations(project) + request.operations)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    plan = EditPlan(assistant_message=request.assistant_message, operations=request.operations)
    store.apply_plan(project_id, request.prompt, plan)
    return _queue_render(project_id, plan)


@app.put("/api/projects/{project_id}/operations")
def replace_operations(project_id: str, request: ReplaceOperationsRequest):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    _ensure_no_active_render(project_id)
    try:
        _validate_operations_for_project(project, request.operations)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.replace_operations(project_id, request.operations)
    return _queue_render(project_id, EditPlan(assistant_message="Updated the fine-tuned edit settings.", operations=[]))


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
        store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    _ensure_no_active_render(project_id)
    store.undo(project_id)
    return _queue_render(project_id, EditPlan(assistant_message="Undid the last edit.", operations=[]))


@app.get("/api/projects/{project_id}/media/{kind}")
@app.get("/api/projects/{project_id}/video/{kind}")
def project_media(project_id: str, kind: str):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if kind == "source":
        path = Path(project["source_path"])
    elif kind == "preview" and project.get("preview_path"):
        path = Path(project["preview_path"])
    else:
        raise HTTPException(status_code=404, detail="Media not available")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media not available")
    return FileResponse(path)


@app.get("/api/projects/{project_id}/assets/{asset_id}")
def project_asset(project_id: str, asset_id: str):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    asset = store.asset_map(project).get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(asset["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset file not available")
    return FileResponse(path)


def _save_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    suffix = Path(file.filename).suffix.lower() or ".bin"
    temp_dir = PROJECTS_DIR / "_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid4().hex}{suffix}"
    size = 0
    with temp_path.open("wb") as target:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB")
            target.write(chunk)
    return temp_path


def _validate_operations_for_project(project: dict, operations: list[EditOperation]) -> None:
    duration = float(project.get("metadata", {}).get("duration_seconds") or 0.0)
    assets = {asset["id"]: asset for asset in project.get("assets", [])}

    turn_ops = [op for op in operations if op.enabled and op.type == "photo_turn_3d"]
    if len(turn_ops) > 1:
        raise ValueError("Use only one Photo 3D Turn operation per project")
    if turn_ops:
        duration = float(turn_ops[-1].turn_duration_seconds or duration or 4.0)

    def require_asset(asset_id: str | None, kinds: set[str], label: str) -> None:
        if not asset_id or asset_id not in assets:
            raise ValueError(f"{label} requires an uploaded media asset")
        actual = assets[asset_id].get("kind")
        if actual not in kinds:
            expected = "photo or video" if kinds == {"video", "image"} else "/".join(sorted(kinds))
            raise ValueError(f"{label} requires {expected} media")

    for operation in operations:
        if not operation.enabled:
            continue
        if operation.type == "photo_turn_3d":
            if project.get("source_kind") != "image":
                raise ValueError("Photo 3D Turn requires the project source to be the front photo")
            require_asset(operation.secondary_asset_id, {"image"}, "Photo 3D Turn side view")
            require_asset(operation.tertiary_asset_id, {"image"}, "Photo 3D Turn back view")
            if operation.secondary_asset_id == operation.tertiary_asset_id:
                raise ValueError("Photo 3D Turn needs different side and back photos")
        elif operation.type == "trim":
            start = operation.start_seconds or 0.0
            end = operation.end_seconds if operation.end_seconds is not None else duration
            if end <= start:
                raise ValueError("Trim end must be after trim start")
            if duration > 0 and end > duration + 0.05:
                raise ValueError(f"Trim end cannot exceed project duration ({duration:.2f}s)")
        elif operation.type in {"split_screen", "picture_in_picture"}:
            require_asset(operation.secondary_asset_id, {"video", "image"}, operation.type.replace("_", " "))
        elif operation.type == "concat":
            require_asset(operation.secondary_asset_id, {"video"}, "Join clips")
        elif operation.type in {"media_overlay", "masked_media"}:
            require_asset(operation.source_asset_id, {"video", "image"}, operation.type.replace("_", " "))
        elif operation.type == "masked_video":
            require_asset(operation.secondary_asset_id, {"video", "image"}, "Shape background")
        elif operation.type == "music":
            require_asset(operation.source_asset_id, {"audio"}, "Background music")

        if operation.motion_keyframes and duration > 0:
            latest = max(frame.time_seconds for frame in operation.motion_keyframes)
            if latest > duration + 0.05:
                raise ValueError(f"Motion point at {latest:.2f}s exceeds project duration ({duration:.2f}s)")


def _ensure_no_active_render(project_id: str) -> None:
    with jobs_lock:
        active = any(
            job.get("project_id") == project_id and job.get("status") in {"queued", "running"}
            for job in jobs.values()
        )
    if active:
        raise HTTPException(status_code=409, detail="A render is already running for this project. Please wait for it to finish.")


def _queue_render(project_id: str, plan: EditPlan) -> dict:
    job_id = uuid4().hex
    with jobs_lock:
        active = any(
            job.get("project_id") == project_id and job.get("status") in {"queued", "running"}
            for job in jobs.values()
        )
        if active:
            raise HTTPException(status_code=409, detail="A render is already running for this project. Please wait for it to finish.")
        _prune_jobs_locked()
        jobs[job_id] = {
            "id": job_id,
            "project_id": project_id,
            "status": "queued",
            "error": None,
            "output_url": None,
            "assistant_message": plan.assistant_message,
            "plan": plan.model_dump(mode="json"),
        }
    executor.submit(_render_job, job_id, project_id)
    return {"job_id": job_id, "status": "queued", "assistant_message": plan.assistant_message}


def _prune_jobs_locked(limit: int = 250) -> None:
    if len(jobs) < limit:
        return
    removable = [job_id for job_id, job in jobs.items() if job.get("status") in {"completed", "failed"}]
    while len(jobs) >= limit and removable:
        jobs.pop(removable.pop(0), None)


def _render_job(job_id: str, project_id: str) -> None:
    _update_job(job_id, status="running")
    try:
        project = store.get(project_id)
        source = Path(project["source_path"])
        operations = store.operations(project)
        assets = store.asset_map(project)
        project_dir = PROJECTS_DIR / project_id

        photo_turn_ops = [op for op in operations if op.enabled and op.type == "photo_turn_3d"]
        standard_ops = [op for op in operations if op.type not in {"style_transfer", "photo_turn_3d"}]
        style_ops = [op for op in operations if op.enabled and op.type == "style_transfer"]

        render_source = source
        render_source_kind = project.get("source_kind", "video")
        render_duration = float(project.get("metadata", {}).get("duration_seconds") or 5.0)

        if photo_turn_ops:
            turn = photo_turn_ops[-1]
            side = assets[turn.secondary_asset_id]
            back = assets[turn.tertiary_asset_id]
            dims = project.get("metadata", {}).get("dimensions", {})
            render_duration = float(turn.turn_duration_seconds or 4.0)
            render_source = project_dir / "photo_turn_work.mp4"
            PhotoTurnRenderer().render(
                source,
                Path(side["path"]),
                Path(back["path"]),
                render_source,
                width=int(dims.get("width") or 1280),
                height=int(dims.get("height") or 720),
                duration_seconds=render_duration,
                direction=turn.turn_direction or "left",
            )
            render_source_kind = "video"

            if not standard_ops and not style_ops:
                final = project_dir / "preview.mp4"
                if render_source != final:
                    render_source.replace(final)
                store.set_preview(project_id, final)
                _update_job(job_id, status="completed", output_url=f"/api/projects/{project_id}/media/preview")
                return

        # Without a generative style stage the FFmpeg preview is already the final preview, so
        # render directly to it and avoid copying the complete video once more.
        base_preview = project_dir / ("preview_style_base.mp4" if style_ops else "preview.mp4")
        ffmpeg.render(
            render_source,
            standard_ops,
            base_preview,
            assets,
            source_kind=render_source_kind,
            source_duration=render_duration,
        )
        if style_ops:
            final = project_dir / "preview_wan.mp4"
            latest_style = style_ops[-1]
            WanEngine().generate_preview(base_preview, latest_style.style_prompt or "", final)
        else:
            final = base_preview
        store.set_preview(project_id, final)
        _update_job(job_id, status="completed", output_url=f"/api/projects/{project_id}/media/preview")
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc))


def _update_job(job_id: str, **changes) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(changes)


def _public_project(project: dict) -> dict:
    return store.public_project(project)


def _public_asset(project_id: str, asset: dict) -> dict:
    return store.public_asset(project_id, asset)
