from __future__ import annotations

import mimetypes
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import Asset, Job, Project
from ..schemas import AssetOut, AssetUpdate, JobOut, ProjectCreate, ProjectOut, ProjectUpdate
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
    aid = f"asset_{uuid.uuid4().hex[:12]}"
    safe_name = Path(file.filename or "upload.bin").name
    dest_dir = UPLOADS_DIR / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{aid}_{safe_name}"
    content = await file.read()
    dest.write_bytes(content)
    mime = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    if mime.startswith("video"):
        ftype = "video"
    elif mime.startswith("image"):
        ftype = "image"
    elif mime.startswith("audio"):
        ftype = "audio"
    else:
        ftype = "video"
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
def analyze_assets(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    job = Job(id=f"job_{uuid.uuid4().hex[:12]}", project_id=project_id, type="analyze")
    db.add(job)
    db.commit()
    job_runner.submit(job.id)
    return job


@router.post("/{project_id}/generate", response_model=JobOut)
def generate_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    job = Job(id=f"job_{uuid.uuid4().hex[:12]}", project_id=project_id, type="generate")
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
