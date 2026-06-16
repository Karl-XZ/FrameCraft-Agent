from __future__ import annotations

import mimetypes
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import (
    ALLOWED_AUDIO_EXT,
    ALLOWED_IMAGE_EXT,
    ALLOWED_VIDEO_EXT,
    MAX_ASSETS_PER_PROJECT,
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    MAX_PROJECT_TOTAL_BYTES,
    MAX_VIDEO_BYTES,
    UPLOADS_DIR,
)
from ..database import get_db
from ..models import Asset, Job, Project
from ..schemas import (
    AnalyzeRequest,
    AssetOut,
    GenerateRequest,
    JobOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from ..services.job_runner import job_runner
from ..services.media import probe_media

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _asset_out(asset: Asset) -> AssetOut:
    thumb = f"/api/assets/{asset.id}/thumbnail" if asset.thumbnail_path else None
    return AssetOut(
        id=asset.id,
        project_id=asset.project_id,
        file_name=asset.file_name,
        file_type=asset.file_type,
        mime_type=asset.mime_type,
        size=asset.size,
        duration=asset.duration,
        width=asset.width,
        height=asset.height,
        user_label=asset.user_label,
        user_note=asset.user_note,
        must_use=asset.must_use,
        priority=asset.priority,
        analysis_status=asset.analysis_status,
        thumbnail_url=thumb,
        created_at=asset.created_at,
    )


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    pid = f"proj_{uuid.uuid4().hex[:12]}"
    project = Project(
        id=pid,
        name=body.name,
        aspect_ratio=body.aspect_ratio,
        target_style=body.target_style,
        target_duration=body.target_duration,
        output_language=body.output_language,
        generate_draft=body.generate_draft,
        keep_hyperframes=body.keep_hyperframes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    (UPLOADS_DIR / pid).mkdir(parents=True, exist_ok=True)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.updated_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(project, k, v)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    shutil.rmtree(UPLOADS_DIR / project_id, ignore_errors=True)
    return {"ok": True}


@router.get("/{project_id}/assets", response_model=list[AssetOut])
def list_assets(project_id: str, db: Session = Depends(get_db)):
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    return [_asset_out(a) for a in assets]


@router.post("/{project_id}/assets/upload", response_model=AssetOut)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    user_label: str = Form(""),
    user_note: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    existing = db.query(Asset).filter(Asset.project_id == project_id).all()
    if len(existing) >= MAX_ASSETS_PER_PROJECT:
        raise HTTPException(400, f"单项目素材数量上限为 {MAX_ASSETS_PER_PROJECT}")

    aid = f"asset_{uuid.uuid4().hex[:12]}"
    safe_name = Path(file.filename or "upload.bin").name
    ext = Path(safe_name).suffix.lower()

    mime = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    if ext in ALLOWED_VIDEO_EXT or mime.startswith("video"):
        ftype, limit = "video", MAX_VIDEO_BYTES
    elif ext in ALLOWED_IMAGE_EXT or mime.startswith("image"):
        ftype, limit = "image", MAX_IMAGE_BYTES
    elif ext in ALLOWED_AUDIO_EXT or mime.startswith("audio"):
        ftype, limit = "audio", MAX_AUDIO_BYTES
    else:
        raise HTTPException(400, f"不支持的文件类型：{ext or mime}")

    content = await file.read()
    if len(content) > limit:
        raise HTTPException(400, f"文件超出大小限制（{limit // (1024 * 1024)}MB）")
    total = sum(a.size for a in existing) + len(content)
    if total > MAX_PROJECT_TOTAL_BYTES:
        raise HTTPException(400, "项目素材总大小超出 3GB 限制")

    dest_dir = UPLOADS_DIR / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{aid}_{safe_name}"
    dest.write_bytes(content)
    meta = probe_media(dest) if ftype in {"video", "audio"} else {}
    asset = Asset(
        id=aid,
        project_id=project_id,
        file_name=safe_name,
        file_path=str(dest),
        file_type=ftype,
        mime_type=mime,
        size=len(content),
        duration=meta.get("duration"),
        width=meta.get("width"),
        height=meta.get("height"),
        user_label=user_label,
        user_note=user_note,
    )
    db.add(asset)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.post("/{project_id}/assets/analyze", response_model=JobOut)
def analyze_assets(project_id: str, body: AnalyzeRequest | None = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not db.query(Asset).filter(Asset.project_id == project_id).count():
        raise HTTPException(400, "请先上传至少一个素材")
    body = body or AnalyzeRequest()
    job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        type="analyze",
        meta={"strategy": body.strategy, "platform": body.platform},
    )
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return job


@router.post("/{project_id}/generate", response_model=JobOut)
def generate_project(project_id: str, body: GenerateRequest | None = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    body = body or GenerateRequest()
    job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        type="generate",
        meta={"resolution": body.resolution, "fps": body.fps, "strategy": body.strategy},
    )
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return job


@router.get("/{project_id}/edit-plan")
def get_edit_plan(project_id: str, db: Session = Depends(get_db)):
    from ..config import OUTPUTS_DIR
    from ..utils import read_json

    path = OUTPUTS_DIR / project_id / "analysis" / "edit_plan.json"
    if not path.exists():
        raise HTTPException(404, "Edit plan not ready")
    return read_json(path)
