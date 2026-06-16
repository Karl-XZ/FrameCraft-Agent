"""Job / Project 进度写入（供 Agent 工具回调）。"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy.orm import Session

from ...database import SessionLocal
from ...models import Job, JobStatus, Project, ProjectStatus

ANALYZE_PIPELINE = (
    "提取口播音频",
    "Whisper 转录",
    "分析口播结构",
    "抽帧理解 B-roll",
    "匹配素材备注",
    "生成剪辑方案",
)


def _job_id() -> str | None:
    return os.getenv("FRAMECRAFT_JOB_ID")


def update_job_progress(
    progress: float,
    step: str,
    *,
    status: str | None = None,
    project_status: str | None = None,
) -> dict:
    job_id = _job_id()
    if not job_id:
        return {"ok": False, "error": "FRAMECRAFT_JOB_ID 未设置"}

    db: Session = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"ok": False, "error": f"job {job_id} 不存在"}

        meta = dict(job.meta or {})
        completed = list(meta.get("completed_steps") or [])
        prev = (job.current_step or "").strip()
        if prev and prev != step:
            prev_base = prev.split(" · ", 1)[0]
            if prev_base in ANALYZE_PIPELINE and prev_base not in completed:
                completed.append(prev_base)
        meta["completed_steps"] = completed

        if step.startswith("生成剪辑方案"):
            sub = step.split(" · ", 1)[1] if " · " in step else ""
            meta["plan_substep"] = sub or None
            meta["plan_progress"] = round(max(0.0, min(100.0, (progress - 90.0) * 10.0)))

        job.meta = meta
        job.progress = progress
        job.current_step = step
        if status:
            job.status = status

        if project_status:
            project = db.query(Project).filter(Project.id == job.project_id).first()
            if project:
                project.status = project_status

        db.commit()
        return {"ok": True, "job_id": job_id, "progress": progress, "step": step}
    finally:
        db.close()
