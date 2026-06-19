from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import store
from .security import cors_origin_regex, cors_origins, get_access_token, require_access_token, token_help
from .single_agent import ProjectBusyError, runner

app = FastAPI(title="FrameCraft Single Codex Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(require_access_token)


@app.on_event("startup")
def startup_security_notice():
    if os.getenv("FRAMECRAFT_DISABLE_AUTH", "").strip() in {"1", "true", "yes"}:
        print("[FrameCraft] WARNING auth disabled by FRAMECRAFT_DISABLE_AUTH", flush=True)
    else:
        get_access_token()
        print(f"[FrameCraft] Access token source: {token_help()}", flush=True)


class ProjectIn(BaseModel):
    name: str
    aspect_ratio: str = "9:16"
    target_duration: int = 60
    target_style: str = "modern_talking_head"
    output_language: str = "zh"
    generate_draft: bool = True
    keep_hyperframes: bool = True


class AnalyzeIn(BaseModel):
    strategy: str = "complete"
    platform: str = "douyin"


class GenerateIn(BaseModel):
    resolution: str = "1080p"
    fps: int = 30
    strategy: str = "complete"


class ChatIn(BaseModel):
    message: str
    apply: bool = True


class ApplyPatchIn(BaseModel):
    patch: dict[str, Any]


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "single-codex-agent"}


@app.post("/api/projects")
def create_project(body: ProjectIn):
    pid = store.new_id("proj")
    now = store.now_iso()
    project = {
        "id": pid,
        "agent_session_id": store.new_id("agent"),
        "name": body.name,
        "status": "uploading",
        "aspect_ratio": body.aspect_ratio,
        "target_style": body.target_style,
        "target_duration": body.target_duration,
        "output_language": body.output_language,
        "generate_draft": body.generate_draft,
        "keep_hyperframes": body.keep_hyperframes,
        "current_version_id": None,
        "created_at": now,
        "updated_at": now,
    }

    def op(data):
        data["projects"][pid] = project
        data["chat"][pid] = []
        return project

    return store.public_project(store.mutate(op))


@app.get("/api/projects")
def list_projects():
    data = store.snapshot()
    projects = list(data["projects"].values())
    projects.sort(key=lambda p: p.get("updated_at") or "", reverse=True)
    return [store.public_project(p) for p in projects]


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = store.snapshot()["projects"].get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return store.public_project(project)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    def op(data):
        if project_id not in data["projects"]:
            raise HTTPException(404, "Project not found")
        data["projects"].pop(project_id, None)
        data["chat"].pop(project_id, None)
        for key in [k for k, a in data["assets"].items() if a["project_id"] == project_id]:
            data["assets"].pop(key, None)
        for key in [k for k, v in data["versions"].items() if v["project_id"] == project_id]:
            data["versions"].pop(key, None)
        for key in [k for k, j in data["jobs"].items() if j["project_id"] == project_id]:
            data["jobs"].pop(key, None)
    store.mutate(op)
    shutil.rmtree(store.upload_dir(project_id), ignore_errors=True)
    shutil.rmtree(store.project_dir(project_id), ignore_errors=True)
    return None


@app.get("/api/projects/{project_id}/assets")
def list_assets(project_id: str):
    data = store.snapshot()
    return [store.public_asset(a) for a in data["assets"].values() if a["project_id"] == project_id]


@app.post("/api/projects/{project_id}/assets/upload")
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    user_label: str = Form(""),
    user_note: str = Form(""),
):
    data = store.snapshot()
    if project_id not in data["projects"]:
        raise HTTPException(404, "Project not found")
    aid = store.new_id("asset")
    filename = Path(file.filename or f"{aid}.bin").name
    dest = store.upload_dir(project_id) / f"{aid}_{filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    guessed_mime = mimetypes.guess_type(filename)[0]
    mime = guessed_mime if not file.content_type or file.content_type == "application/octet-stream" else file.content_type
    mime = mime or "application/octet-stream"
    file_type = "video" if mime.startswith("video/") else "audio" if mime.startswith("audio/") else "image" if mime.startswith("image/") else "file"
    asset = {
        "id": aid,
        "project_id": project_id,
        "file_name": filename,
        "file_type": file_type,
        "mime_type": mime,
        "size": dest.stat().st_size,
        "duration": None,
        "user_label": user_label,
        "user_note": user_note,
        "must_use": False,
        "priority": 0,
        "analysis_status": "pending",
        "thumbnail_url": None,
        "path": str(dest),
        "created_at": store.now_iso(),
    }

    def op(db):
        db["assets"][aid] = asset
        db["projects"][project_id]["status"] = "uploading"
        db["projects"][project_id]["updated_at"] = store.now_iso()
        return asset

    return store.public_asset(store.mutate(op))


@app.patch("/api/assets/{asset_id}")
def update_asset(asset_id: str, body: dict[str, Any]):
    def op(data):
        asset = data["assets"].get(asset_id)
        if not asset:
            raise HTTPException(404, "Asset not found")
        for key in ("user_label", "user_note", "must_use", "priority"):
            if key in body:
                asset[key] = body[key]
        return asset
    return store.public_asset(store.mutate(op))


@app.get("/api/assets/{asset_id}/analysis")
def get_asset_analysis(asset_id: str):
    data = store.snapshot()
    asset = data["assets"].get(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return {
        "ready": asset.get("analysis_status") == "completed",
        "asset_id": asset_id,
        "auto_summary": asset.get("auto_summary", "由单一 Codex agent 在任务中分析。"),
        "recommended_usage": asset.get("recommended_usage", []),
        "ocr_text": asset.get("ocr_text", ""),
        "vision_status": "agent-managed",
        "vision_error": None,
        "ocr_status": "agent-managed",
        "ocr_error": None,
        "meta": {},
        "frame_urls": [],
        "broll_segments": [],
    }


@app.post("/api/projects/{project_id}/assets/analyze")
def analyze(project_id: str, body: AnalyzeIn):
    _ensure_project(project_id)
    return _start_job(project_id, "analyze", body.model_dump())


@app.get("/api/projects/{project_id}/edit-plan")
def get_edit_plan(project_id: str):
    _ensure_project(project_id)
    path = store.project_dir(project_id) / "analysis" / "edit_plan.json"
    if not path.is_file():
        raise HTTPException(404, "Edit plan not found; run analyze first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/projects/{project_id}/generate")
def generate(project_id: str, body: GenerateIn):
    _ensure_project(project_id)
    return _start_job(project_id, "generate", body.model_dump())


@app.post("/api/projects/{project_id}/apply-patch")
def apply_patch(project_id: str, body: ApplyPatchIn):
    _ensure_project(project_id)
    return _start_job(project_id, "apply_patch", {"patch": body.patch})


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = store.snapshot()["jobs"].get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return store.public_job(job)


@app.get("/api/projects/{project_id}/jobs/active")
def get_active_project_job(project_id: str):
    _ensure_project(project_id)
    jobs = [
        j for j in store.snapshot()["jobs"].values()
        if j.get("project_id") == project_id and j.get("status") not in {"completed", "failed", "cancelled"}
    ]
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return store.public_job(jobs[0]) if jobs else None


@app.post("/api/jobs/{job_id}/cancel", status_code=204)
def cancel_job(job_id: str):
    def op(data):
        job = data["jobs"].get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        job["status"] = "cancelled"
        job["completed_at"] = store.now_iso()
        return job
    store.mutate(op)
    return None


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    async def stream():
        while True:
            data = store.snapshot()
            job = data["jobs"].get(job_id)
            if not job:
                yield "event: error\ndata: {\"error\":\"Job not found\"}\n\n"
                return
            payload = json.dumps(store.public_job(job), ensure_ascii=False)
            yield f"data: {payload}\n\n"
            if job["status"] in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/versions")
def list_versions(project_id: str):
    _ensure_project(project_id)
    versions = [v for v in store.snapshot()["versions"].values() if v["project_id"] == project_id]
    versions.sort(key=lambda v: int(v.get("version_number", 0)), reverse=True)
    return [store.public_version(v) for v in versions]


@app.post("/api/projects/{project_id}/versions/{version_id}/activate")
def activate_version(project_id: str, version_id: str):
    def op(data):
        if version_id not in data["versions"]:
            raise HTTPException(404, "Version not found")
        data["projects"][project_id]["current_version_id"] = version_id
        data["projects"][project_id]["updated_at"] = store.now_iso()
    store.mutate(op)
    return {"ok": True, "current_version_id": version_id}


@app.get("/api/projects/{project_id}/versions/{version_id}/preview")
def version_preview(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    return FileResponse(version["preview_path"], media_type="video/mp4")


@app.get("/api/projects/{project_id}/versions/{version_id}/timeline")
def version_timeline(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "timeline.json"
    return _file_or_json(path, {"project_id": project_id, "version_id": version_id})


@app.get("/api/projects/{project_id}/versions/{version_id}/subtitles")
def version_subtitles(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "subtitles.srt"
    return _file_or_json(path, "")


@app.get("/api/projects/{project_id}/versions/{version_id}/hyperframes")
def version_hyperframes(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version["version_dir"]) / "hyperframes_project.zip"
    if path.is_file():
        return FileResponse(path)
    raise HTTPException(404, "HyperFrames zip not found")


@app.get("/api/projects/{project_id}/versions/{version_id}/draft")
def version_draft(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    path = Path(version.get("draft_path") or Path(version["version_dir"]) / "jianying_draft.zip")
    if path.is_file():
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"{version_id}_jianying_draft.zip",
        )
    raise HTTPException(404, "Jianying draft zip not found")


@app.get("/api/projects/{project_id}/versions/{version_id}/import-guide")
def import_guide(project_id: str, version_id: str):
    version = _version(project_id, version_id)
    guide_path = Path(version.get("import_guide_path") or Path(version["version_dir"]) / "jianying_import_guide.md")
    if guide_path.is_file():
        return {"content": guide_path.read_text(encoding="utf-8")}
    return {"content": "该版本没有生成剪映草稿导入说明。若项目开启了草稿导出，这应视为生成失败而不是成功兜底。"}


@app.post("/api/projects/{project_id}/chat")
def chat(project_id: str, body: ChatIn):
    _ensure_project(project_id)
    user = {
        "id": store.new_id("msg"),
        "role": "user",
        "content": body.message,
        "created_at": store.now_iso(),
    }

    def op(data):
        data.setdefault("chat", {}).setdefault(project_id, []).append(user)
    store.mutate(op)
    job = _start_job(project_id, "chat", {"message": body.message, "apply": body.apply})
    return {
        "id": store.new_id("msg"),
        "role": "agent",
        "content": "已交给单一 Codex agent 处理；请在任务进度完成后查看回复或新版本。",
        "patch": None,
        "job_id": job["id"],
        "status": "running",
        "created_at": store.now_iso(),
    }


@app.get("/api/projects/{project_id}/chat")
def get_chat(project_id: str):
    _ensure_project(project_id)
    return store.snapshot().get("chat", {}).get(project_id, [])


@app.get("/api/model-providers")
def model_providers():
    return {
        "providers": [
            {
                "id": "codex",
                "label": "Codex CLI",
                "base_url": "",
                "note": "模型、登录状态和工具权限由本机 Codex CLI 配置决定。",
            }
        ],
        "codex": {
            "label": "Codex CLI",
            "note": "新后端只启动一个 Codex supervisor agent；模型与登录状态由本机 Codex 配置决定。",
        }
    }


@app.get("/api/settings/model")
def get_settings():
    return store.public_settings(store.snapshot()["settings"])


@app.patch("/api/settings/model")
def save_settings(body: dict[str, str]):
    def op(data):
        allowed = {"provider", "text_model", "vision_model", "base_url", "asr_model"}
        for key in allowed:
            if key in body:
                data["settings"][key] = body[key]
        # The current Codex backend does not need browser-submitted API keys.
        # Do not persist or echo them from the public web UI.
        data["settings"]["api_key"] = ""
        return store.public_settings(data["settings"])
    return store.mutate(op)


def _ensure_project(project_id: str) -> dict[str, Any]:
    project = store.snapshot()["projects"].get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _start_job(project_id: str, job_type: str, payload: dict[str, Any]):
    try:
        return runner.start(project_id, job_type, payload)
    except ProjectBusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


def _version(project_id: str, version_id: str) -> dict[str, Any]:
    version = store.snapshot()["versions"].get(version_id)
    if not version or version["project_id"] != project_id:
        raise HTTPException(404, "Version not found")
    return version


def _file_or_json(path: Path, fallback: Any):
    if path.is_file():
        return FileResponse(path)
    return JSONResponse(fallback)
