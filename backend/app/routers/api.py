from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

import uuid

from ..config import OUTPUTS_DIR
from ..database import SessionLocal, get_db
from ..models import Asset, ChatMessage, Job, JobStatus, Project, ProjectVersion
from ..schemas import ApplyPatchIn, ChatIn, ChatOut, JobOut, ModelSettings, VersionOut
from ..services.job_runner import job_runner
from ..services.chat_service import handle_agent_chat
from ..services.patch_service import validate_patch
from ..utils import get_model_settings, read_json, set_setting

router = APIRouter(prefix="/api", tags=["api"])


def _tail_job_log(log_path: str | None, limit: int = 50) -> list[str]:
    if not log_path:
        return []
    p = Path(log_path)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        return lines[-limit:]
    except Exception:
        return []


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
                meta = job.meta or {}
                payload = {
                    "id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "current_step": job.current_step,
                    "error_message": job.error_message,
                    "type": job.type,
                    "completed_steps": meta.get("completed_steps") or [],
                    "plan_substep": meta.get("plan_substep"),
                    "plan_progress": meta.get("plan_progress"),
                    "logs": _tail_job_log(job.log_path),
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

    result = handle_agent_chat(body.message, timeline, project, db)

    if result.status in ("needs_config", "chat", "not_understood"):
        agent_msg = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:10]}", project_id=project_id,
            version_id=project.current_version_id, role="agent", content=result.reply,
        )
        db.add(agent_msg)
        db.commit()
        return ChatOut(
            id=agent_msg.id, role="agent", content=result.reply,
            patch=None, job_id=None, status=result.status, created_at=agent_msg.created_at,
        )

    patch = result.patch or {"operations": []}

    ok, errors = (True, [])
    if timeline:
        try:
            ok, errors = validate_patch(timeline, patch)
        except Exception as exc:
            reply = f"修改方案格式有误，无法校验：{exc}"
            agent_msg = ChatMessage(
                id=f"msg_{uuid.uuid4().hex[:10]}", project_id=project_id,
                version_id=project.current_version_id, role="agent", content=reply,
            )
            db.add(agent_msg)
            db.commit()
            return ChatOut(id=agent_msg.id, role="agent", content=reply, patch=None, job_id=None, status="rejected", created_at=agent_msg.created_at)
    if not ok:
        reply = "这个修改暂时无法安全应用：\n- " + "\n- ".join(errors)
        agent_msg = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:10]}", project_id=project_id,
            version_id=project.current_version_id, role="agent", content=reply,
        )
        db.add(agent_msg)
        db.commit()
        return ChatOut(id=agent_msg.id, role="agent", content=reply, patch=patch, job_id=None, status="rejected", created_at=agent_msg.created_at)

    # 仅生成方案、等待用户确认（接受/撤销），不立即应用（需求 §11.3.6）
    if not body.apply:
        reply = result.reply
        if not reply:
            raise HTTPException(502, "Agent 未返回有效回复")
        agent_msg = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:10]}", project_id=project_id,
            version_id=project.current_version_id, role="agent", content=reply,
        )
        db.add(agent_msg)
        db.commit()
        return ChatOut(id=agent_msg.id, role="agent", content=reply, patch=patch, job_id=None, status="proposed", created_at=agent_msg.created_at)

    reply = result.reply
    if not reply:
        raise HTTPException(502, "Agent 未返回有效回复")
    agent_msg = ChatMessage(
        id=f"msg_{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        version_id=project.current_version_id,
        role="agent",
        content=reply,
        patch_json_path=None,
    )
    db.add(agent_msg)
    job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}",
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


@router.get("/model-providers")
def model_providers():
    return {
        "providers": [
            {"id": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1"},
            {"id": "anthropic", "label": "Anthropic", "base_url": "https://api.anthropic.com/v1"},
            {"id": "deepseek", "label": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
            {"id": "qwen", "label": "Qwen / DashScope", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
            {"id": "openrouter", "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
            {"id": "local", "label": "本地模型 (Ollama/LM Studio)", "base_url": "http://127.0.0.1:11434/v1"},
        ],
        "text_models": ["gpt-4o", "gpt-4o-mini", "deepseek-chat", "qwen-max"],
        "vision_models": ["gpt-4o", "gpt-4o-mini", "qwen-vl-max"],
        "asr_models": ["base", "small", "medium", "large-v3"],
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
        job.status = JobStatus.CANCELLED.value
        db.commit()
    return {"ok": True, "status": job.status}


@router.post("/projects/{project_id}/apply-patch", response_model=JobOut)
def apply_patch_endpoint(project_id: str, body: ApplyPatchIn, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.current_version_id:
        raise HTTPException(404, "Project or current version not found")
    v = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
    timeline = read_json(Path(v.timeline_json_path)) if v and v.timeline_json_path else {}
    ok, errors = validate_patch(timeline, body.patch)
    if not ok:
        raise HTTPException(400, "patch 校验失败：" + "；".join(errors))
    job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}", project_id=project_id, type="chat_regenerate",
        meta={"patch": body.patch, "message": body.patch.get("description", "应用修改")},
    )
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return job


@router.post("/projects/{project_id}/regenerate", response_model=JobOut)
def regenerate(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    job = Job(id=f"job_{uuid.uuid4().hex[:12]}", project_id=project_id, type="generate", meta={})
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return job


@router.post("/projects/{project_id}/versions/{version_id}/activate")
def activate_version(project_id: str, version_id: str, db: Session = Depends(get_db)):
    """将项目当前版本切换到指定历史版本（用于撤销修改，需求 §11.3.6）。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    v = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id, ProjectVersion.project_id == project_id
    ).first()
    if not v:
        raise HTTPException(404, "Version not found")
    project.current_version_id = version_id
    db.commit()
    return {"ok": True, "current_version_id": version_id}


@router.get("/projects/{project_id}/versions/{version_id}/import-guide")
def import_guide(project_id: str, version_id: str, db: Session = Depends(get_db)):
    v = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
    if not v:
        raise HTTPException(404)
    guide = OUTPUTS_DIR / project_id / version_id / "draft" / "draft_import_guide.md"
    if not guide.exists():
        return {"content": "草稿导入说明尚未生成。"}
    return {"content": guide.read_text(encoding="utf-8")}
