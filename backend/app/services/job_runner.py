"""Job 执行：成片编排唯一入口为 OpenClaw Agent；剪映草稿可在 Agent 完成后由服务端导出。"""
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
from .draft_service import export_draft, validate_draft
from .agent_acceptance import (
    build_continuation_message,
    evaluate_agent_phase,
    is_conversational_bailout,
)
from .version_finalize_service import (
    finalize_version_record,
    resolve_version_dir,
    server_render_preview,
)

MAX_AGENT_ATTEMPTS = 3
MAX_LINT_FIX_ATTEMPTS = 2

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

        patched_dir = meta.get("patched_version_dir") if task == "chat_regenerate" else None
        last_reply = ""
        self._update(db, job, 2, f"OpenClaw Agent · {task}")

        for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
            continuation = None
            if attempt > 1:
                _ok, missing = evaluate_agent_phase(
                    job.project_id, task, agent_reply=last_reply, patched_version_dir=patched_dir
                )
                continuation = build_continuation_message(
                    task, missing, prior_reply=last_reply
                )
                self._log(
                    f"Agent 验收未通过（{attempt}/{MAX_AGENT_ATTEMPTS}），打回继续："
                    f"缺 {missing}；对话式退出={is_conversational_bailout(last_reply)}"
                )

            result = run_openclaw_task(
                db,
                job.project_id,
                task,
                job_id=job.id,
                user_message=user_message,
                extra=extra,
                on_log=self._log,
                continuation=continuation,
                retry_attempt=attempt if attempt > 1 else 0,
            )
            if not result.ok:
                raise RuntimeError(result.error or "OpenClaw Agent 执行失败")

            last_reply = result.reply or ""
            accepted, missing = evaluate_agent_phase(
                job.project_id, task, agent_reply=last_reply, patched_version_dir=patched_dir
            )
            if accepted:
                break
            if attempt >= MAX_AGENT_ATTEMPTS:
                raise RuntimeError(
                    f"Agent 阶段验收失败（已重试 {MAX_AGENT_ATTEMPTS} 次）。"
                    f"缺失：{missing}。Agent 回复：{last_reply[:500]}"
                )

        if task in ("generate", "chat_regenerate"):
            self._server_post_agent_production(db, job, task, extra)

        self._verify_task_outputs(db, job, task, last_reply)

    def _dispatch_lint_fix_agent(
        self,
        db: Session,
        job: Job,
        version_dir: Path,
        lint_output: str,
        base_extra: dict,
    ) -> None:
        """HyperFrames lint 未通过：打回 Agent 调整 timeline 并重建 HF 工程。"""
        patched = str(version_dir)
        last_reply = ""
        fix_extra = {
            **base_extra,
            "patched_version_dir": patched,
            "version_dir": patched,
            "lint_output": (lint_output or "")[:4000],
            "lint_fix": True,
        }
        self._update(db, job, 45, "Agent 修复 HyperFrames lint")

        for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
            continuation = build_continuation_message(
                "lint_fix",
                ["hyperframes lint 修复"],
                prior_reply=last_reply if attempt > 1 else "",
                lint_output=lint_output,
                version_dir=patched,
            )
            if attempt > 1:
                _ok, missing = evaluate_agent_phase(
                    job.project_id,
                    "lint_fix",
                    agent_reply=last_reply,
                    patched_version_dir=patched,
                )
                continuation = build_continuation_message(
                    "lint_fix",
                    missing,
                    prior_reply=last_reply,
                    lint_output=lint_output,
                    version_dir=patched,
                )
                self._log(f"lint_fix 验收未通过（{attempt}/{MAX_AGENT_ATTEMPTS}），继续打回")

            result = run_openclaw_task(
                db,
                job.project_id,
                "lint_fix",
                job_id=job.id,
                extra=fix_extra,
                on_log=self._log,
                continuation=continuation,
                retry_attempt=attempt,
            )
            if not result.ok:
                raise RuntimeError(result.error or "lint_fix Agent 执行失败")
            last_reply = result.reply or ""
            accepted, missing = evaluate_agent_phase(
                job.project_id,
                "lint_fix",
                agent_reply=last_reply,
                patched_version_dir=patched,
            )
            if accepted:
                return
            if attempt >= MAX_AGENT_ATTEMPTS:
                raise RuntimeError(
                    f"lint_fix 验收失败。缺失：{missing}。Agent 回复：{last_reply[:500]}"
                )

    def _server_post_agent_production(self, db: Session, job: Job, task: str, base_extra: dict) -> None:
        """Agent 完成 timeline + HyperFrames 设计后，服务端自动渲染并注册版本。"""
        project = db.query(Project).filter(Project.id == job.project_id).first()
        if not project:
            raise RuntimeError("项目不存在")

        meta = dict(job.meta or {})
        patched = meta.get("patched_version_dir") if task == "chat_regenerate" else None
        version_dir = resolve_version_dir(job.project_id, patched_version_dir=patched)
        hf_index = version_dir / "hyperframes" / "index.html"
        if not hf_index.is_file():
            raise RuntimeError(f"HyperFrames 工程未完成：{hf_index}")

        preview_path = version_dir / "preview.mp4"
        if not preview_path.is_file():
            for lint_round in range(MAX_LINT_FIX_ATTEMPTS + 1):
                self._log(f"服务端自动渲染 preview.mp4（{version_dir.name}）…")
                self._update(db, job, 60, "渲染 preview.mp4")
                try:
                    server_render_preview(version_dir)
                    break
                except RuntimeError as exc:
                    is_lint = "lint" in str(exc).lower()
                    if not is_lint or lint_round >= MAX_LINT_FIX_ATTEMPTS:
                        render_log = version_dir / "render_log.json"
                        detail = str(exc)
                        if render_log.is_file():
                            detail += f"\n详见 {render_log}"
                        raise RuntimeError(detail) from exc
                    lint_output = ""
                    if (version_dir / "render_log.json").is_file():
                        lint_output = read_json(version_dir / "render_log.json").get("lint_output") or ""
                    self._log(
                        f"HyperFrames lint 未通过，打回 Agent 修复"
                        f"（{lint_round + 1}/{MAX_LINT_FIX_ATTEMPTS}）"
                    )
                    self._dispatch_lint_fix_agent(db, job, version_dir, lint_output, base_extra)

        preview_path = version_dir / "preview.mp4"
        if not preview_path.is_file():
            raise RuntimeError(f"渲染后仍缺少 preview.mp4：{preview_path}")

        if project.current_version_id != version_dir.name:
            self._log(f"服务端自动注册版本 {version_dir.name}…")
            self._update(db, job, 88, "注册版本与附属产物")
            ver = finalize_version_record(db, project, version_dir)
            if bool(project.generate_draft):
                self._server_export_draft(db, project, ver, version_dir)

    def _verify_task_outputs(self, db: Session, job: Job, task: str, agent_reply: str) -> None:
        pid = job.project_id
        analysis = OUTPUTS_DIR / pid / "analysis"

        if task == "analyze":
            manifest = analysis / "asset_manifest.json"
            plan_path = analysis / "edit_plan.json"
            if not manifest.exists() or not plan_path.exists():
                raise RuntimeError(
                    "OpenClaw Agent 未产出必需分析文件（asset_manifest.json / edit_plan.json）。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            manifest_data = read_json(manifest)
            plan_data = read_json(plan_path)
            warnings: list[dict] = list(manifest_data.get("analysis_warnings") or [])
            asr = manifest_data.get("asr") or {}
            if asr.get("degraded") and not any(w.get("code") == "asr_degraded" for w in warnings):
                warnings.append({
                    "code": "asr_degraded",
                    "message": f"口播转录降级：{asr.get('degraded_reason') or '无逐词字幕'}",
                })
            plan_meta = plan_data.get("meta") or {}
            if plan_meta.get("llm_status") not in (None, "ok", "llm"):
                warnings.append({
                    "code": "edit_plan_llm_degraded",
                    "message": plan_meta.get("llm_note") or plan_meta.get("llm_error") or "剪辑方案未经 LLM 润色",
                })
            if warnings:
                meta = dict(job.meta or {})
                meta["warnings"] = warnings
                job.meta = meta
                db.commit()
                self._log("分析完成，存在降级警告：" + "；".join(w["message"][:80] for w in warnings))
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
                    "成片版本未注册（服务端 finalize）。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            ver = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
            version_dir = Path(ver.timeline_json_path).parent if ver and ver.timeline_json_path else None
            preview = Path(ver.preview_video_path) if ver and ver.preview_video_path else None
            if not preview or not preview.exists():
                raise RuntimeError(
                    f"版本 {project.current_version_id} 缺少 preview.mp4。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            hf_index = (version_dir / "hyperframes" / "index.html") if version_dir else None
            if not hf_index or not hf_index.exists():
                raise RuntimeError(
                    f"版本 {project.current_version_id} 缺少 HyperFrames 工程（hyperframes/index.html）。"
                    " 成片须由 Agent 设计 HyperFrames 工程，并由服务端渲染 preview.mp4。"
                    f" Agent 回复：{agent_reply[:500]}"
                )
            if bool(project.generate_draft) and not (ver.draft_zip_path and Path(ver.draft_zip_path).exists()):
                self._server_export_draft(db, project, ver, version_dir)
            self._update(db, job, 100, "成片完成")
            return

    def _server_export_draft(self, db: Session, project: Project, ver: ProjectVersion, version_dir: Path) -> None:
        """Agent 完成后：将 unified_timeline 机械转换为剪映草稿（非创意环节）。"""
        self._log("服务端自动导出剪映草稿…")
        timeline = read_json(version_dir / "unified_timeline.json")
        draft_dir = version_dir / "draft"
        draft_zip, _ = export_draft(timeline, draft_dir)
        vr = validate_draft(draft_dir)
        if not vr.ok:
            raise RuntimeError("剪映草稿校验失败：" + "；".join(vr.errors))
        ver.draft_zip_path = str(draft_zip)
        db.commit()
        self._log(f"草稿已导出：{draft_zip}")


job_runner = JobRunner()
