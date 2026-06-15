from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Asset, ChatMessage, Job, Project, ProjectVersion
from ..schemas import ApplyPatchIn, ChatIn, ChatOut, JobOut, ModelSettings, VersionOut
from ..services.job_runner import job_runner
from ..services.patch_service import build_patch_from_message
from ..utils import get_model_settings, read_json, set_setting

router = APIRouter(prefix="/api", tags=["api"])


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: str, body: dict, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    for k in ("user_label", "user_note", "must_use", "priority"):
        if k in body:
            setattr(asset, k, body[k])
    db.commit()
    return {"ok": True}


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    db.delete(asset)
    db.commit()
    return {"ok": True}


@router.get("/assets/{asset_id}/thumbnail")
def asset_thumbnail(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset or not asset.thumbnail_path or not Path(asset.thumbnail_path).exists():
        raise HTTPException(404, "Thumbnail not found")
    return FileResponse(asset.thumbnail_path)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, db: Session = Depends(get_db)):
    async def event_stream():
        while True:
            local = SessionLocal()
            try:
                job = local.query(Job).filter(Job.id == job_id).first()
                if not job:
                    break
                payload = {
                    "id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "current_step": job.current_step,
                    "error_message": job.error_message,
                    "type": job.type,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if job.status in {"completed", "failed", "cancelled"}:
                    break
            finally:
                local.close()
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/projects/{project_id}/versions", response_model=list[VersionOut])
def list_versions(project_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
        .all()
    )
    out = []
    for v in versions:
        out.append(
            VersionOut(
                id=v.id,
                project_id=v.project_id,
                version_number=v.version_number,
                status=v.status,
                preview_url=f"/api/projects/{project_id}/versions/{v.id}/preview",
                draft_url=f"/api/projects/{project_id}/versions/{v.id}/draft",
                timeline_url=f"/api/projects/{project_id}/versions/{v.id}/timeline",
                subtitles_url=f"/api/projects/{project_id}/versions/{v.id}/subtitles",
                cover_url=f"/api/projects/{project_id}/versions/{v.id}/cover",
                publish_copy_url=f"/api/projects/{project_id}/versions/{v.id}/publish_copy",
                hyperframes_url=f"/api/projects/{project_id}/versions/{v.id}/hyperframes",
                created_at=v.created_at,
            )
        )
    return out


def _version_file(project_id: str, version_id: str, field: str, db: Session) -> FileResponse:
    v = db.query(ProjectVersion).filter(ProjectVersion.id == version_id, ProjectVersion.project_id == project_id).first()
    if not v:
        raise HTTPException(404, "Version not found")
    path = getattr(v, field, None)
    if not path or not Path(path).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.get("/projects/{project_id}/versions/{version_id}/preview")
def preview_video(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "preview_video_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/draft")
def draft_zip(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "draft_zip_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/timeline")
def timeline_json(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "timeline_json_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/subtitles")
def subtitles(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "subtitles_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/cover")
def cover(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "cover_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/publish_copy")
def publish_copy(project_id: str, version_id: str, db: Session = Depends(get_db)):
    return _version_file(project_id, version_id, "publish_copy_path", db)


@router.get("/projects/{project_id}/versions/{version_id}/hyperframes")
def hyperframes_zip(project_id: str, version_id: str, db: Session = Depends(get_db)):
    v = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
    if not v:
        raise HTTPException(404)
    from ..config import OUTPUTS_DIR

    z = OUTPUTS_DIR / project_id / version_id / "hyperframes_project.zip"
    if not z.exists():
        raise HTTPException(404)
    return FileResponse(z)


@router.post("/projects/{project_id}/chat", response_model=ChatOut)
def chat(project_id: str, body: ChatIn, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404)
    user_msg = ChatMessage(
        id=f"msg_{__import__('uuid').uuid4().hex[:10]}",
        project_id=project_id,
        version_id=project.current_version_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    timeline = {}
    if project.current_version_id:
        v = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
        if v and v.timeline_json_path:
            timeline = read_json(Path(v.timeline_json_path))
    patch = build_patch_from_message(body.message, timeline)
    reply = f"已理解你的修改：{body.message}\n\n将应用 {len(patch.get('operations', []))} 项 timeline 变更，并重新生成预览与剪映草稿。"
    agent_msg = ChatMessage(
        id=f"msg_{__import__('uuid').uuid4().hex[:10]}",
        project_id=project_id,
        version_id=project.current_version_id,
        role="agent",
        content=reply,
        patch_json_path=None,
    )
    db.add(agent_msg)
    job = Job(
        id=f"job_{__import__('uuid').uuid4().hex[:12]}",
        project_id=project_id,
        type="chat_regenerate",
        meta={"patch": patch, "message": body.message},
    )
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return ChatOut(
        id=agent_msg.id,
        role="agent",
        content=reply,
        patch=patch,
        job_id=job.id,
        created_at=agent_msg.created_at,
    )


@router.get("/projects/{project_id}/chat", response_model=list[ChatOut])
def chat_history(project_id: str, db: Session = Depends(get_db)):
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [ChatOut(id=m.id, role=m.role, content=m.content, patch=None, created_at=m.created_at) for m in msgs]


@router.get("/settings/model", response_model=ModelSettings)
def get_settings(db: Session = Depends(get_db)):
    return ModelSettings(**get_model_settings(db))


@router.patch("/settings/model", response_model=ModelSettings)
def patch_settings(body: ModelSettings, db: Session = Depends(get_db)):
    mapping = {
        "provider": "llm_provider",
        "api_key": "llm_api_key",
        "text_model": "llm_model",
        "vision_model": "vlm_model",
        "asr_model": "asr_model",
        "base_url": "llm_base_url",
    }
    data = body.model_dump()
    for k, v in data.items():
        set_setting(db, mapping[k], v)
    return ModelSettings(**get_model_settings(db))
