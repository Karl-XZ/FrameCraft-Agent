"""Job 执行：唯一入口为 OpenClaw Agent，禁止固定流水线。"""
from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR, WORKSPACES_DIR
from ..database import SessionLocal
from ..models import Job, JobStatus, Project, ProjectStatus, ProjectVersion
from ..utils import read_json, write_json
from .openclaw_runtime import run_openclaw_task

ANALYZE_PIPELINE = (
    "提取口播音频",
    "Whisper 转录",
    "分析口播结构",
    "抽帧理解 B-roll",
    "匹配素材备注",
    "生成剪辑方案",
)


class JobCancelled(Exception):
    pass


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._local = threading.local()

    def submit(self, job_id: str) -> None:
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()

    def _log(self, message: str) -> None:
        buf = getattr(self._local, "log", None)
        if buf is None:
            return
        line = f"[{datetime.utcnow().isoformat(timespec='seconds')}] {message}"
        buf.append(line)
        log_file = getattr(self._local, "log_file", None)
        if log_file:
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def _update(self, db: Session, job: Job, progress: float, step: str, status: str | None = None):
        db.refresh(job)
        if job.status == JobStatus.CANCELLED.value:
            raise JobCancelled()

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
        db.commit()
        self._log(f"{progress:.0f}% · {step}")

    def _run(self, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return

            log_dir = OUTPUTS_DIR / job.project_id / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{job.id}.log"
            self._local.log = []
            self._local.log_file = log_file
            job.log_path = str(log_file)
            job.meta = {**(job.meta or {}), "completed_steps": [], "plan_progress": 0, "plan_substep": None}
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()
            self._log(f"OpenClaw 任务开始 type={job.type} job={job.id}")

            if job.type == "analyze":
                self._dispatch_openclaw(db, job, "analyze")
            elif job.type == "generate":
                self._dispatch_openclaw(db, job, "generate")
            elif job.type == "chat_regenerate":
                self._dispatch_openclaw(db, job, "chat_regenerate")
            else:
                raise ValueError(f"Unknown job type {job.type}")

            self._log("OpenClaw 任务完成")
            db.refresh(job)
            if job.type == "analyze":
                meta = dict(job.meta or {})
                completed = list(meta.get("completed_steps") or [])
                if "生成剪辑方案" not in completed:
                    completed.append("生成剪辑方案")
                meta["completed_steps"] = completed
                meta["plan_progress"] = 100
                meta["plan_substep"] = None
                job.meta = meta
            job.status = JobStatus.COMPLETED.value
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
        except JobCancelled:
            self._log("任务被取消")
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.CANCELLED.value
                job.current_step = "已取消"
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            self._log(f"任务失败: {e}")
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = f"{e}\n{traceback.format_exc()}"
                job.completed_at = datetime.utcnow()
                project = db.query(Project).filter(Project.id == job.project_id).first()
                if project:
                    project.status = ProjectStatus.FAILED.value
                db.commit()
        finally:
            db.close()
            self._local.log = None
            self._local.log_file = None

    def _dispatch_openclaw(self, db: Session, job: Job, task: str) -> None:
        project = db.query(Project).filter(Project.id == job.project_id).first()
        if not project:
            raise RuntimeError("项目不存在")

        if task == "analyze":
            project.status = ProjectStatus.ANALYZING.value
        elif task in ("generate", "chat_regenerate"):
            project.status = ProjectStatus.RENDERING.value
        db.commit()

        meta = dict(job.meta or {})
        extra = {k: v for k, v in meta.items() if k not in ("patch", "message")}
        user_message = meta.get("message") if task == "chat_regenerate" else None
        if task == "chat_regenerate" and meta.get("patch"):
            extra["patch"] = meta["patch"]

        self._update(db, job, 2, f"OpenClaw Agent · {task}")

        result = run_openclaw_task(
            db,
            job.project_id,
            task,
            job_id=job.id,
            user_message=user_message,
            extra=extra,
            on_log=self._log,
        )
        if not result.ok:
            raise RuntimeError(result.error or "OpenClaw Agent 执行失败")

        self._verify_task_outputs(db, job, task, result.reply)

    def _verify_task_outputs(self, db: Session, job: Job, task: str, agent_reply: str) -> None:
        pid = job.project_id
        analysis = OUTPUTS_DIR / pid / "analysis"

        if task == "analyze":
            manifest = analysis / "asset_manifest.json"
            plan = analysis / "edit_plan.json"
            if not manifest.exists() or not plan.exists():
                raise RuntimeError(
                    "OpenClaw Agent 未产出必需分析文件（asset_manifest.json / edit_plan.json）。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            project = db.query(Project).filter(Project.id == pid).first()
            if project:
                project.status = ProjectStatus.COMPLETED.value
                db.commit()
            self._update(db, job, 100, "Agent 分析完成")
            return

        if task in ("generate", "chat_regenerate"):
            project = db.query(Project).filter(Project.id == pid).first()
            if not project or not project.current_version_id:
                raise RuntimeError(
                    "OpenClaw Agent 未注册新版本（finalize_version）。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            ver = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
            preview = Path(ver.preview_video_path) if ver and ver.preview_video_path else None
            if not preview or not preview.exists():
                raise RuntimeError(
                    f"版本 {project.current_version_id} 缺少 preview.mp4。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            self._update(db, job, 100, "Agent 成片完成")
            return


job_runner = JobRunner()
