from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..database import SessionLocal
from ..models import Job, JobStatus, Project, ProjectStatus, ProjectVersion
from ..utils import read_json, write_json
from .analyzer import analyze_project_assets
from .draft_service import export_draft
from .ffmpeg_preview import render_preview_ffmpeg
from .hyperframes_service import generate_hyperframes_project, render_preview, zip_hyperframes
from .patch_service import apply_patch, build_patch_from_message
from .planner import plan_edit
from .timeline_builder import build_timeline, save_timeline


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()

    def submit(self, job_id: str) -> None:
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()

    def _update(self, db: Session, job: Job, progress: float, step: str, status: str | None = None):
        job.progress = progress
        job.current_step = step
        if status:
            job.status = status
        db.commit()

    def _run(self, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()

            if job.type == "analyze":
                self._run_analyze(db, job)
            elif job.type == "generate":
                self._run_generate(db, job)
            elif job.type == "chat_regenerate":
                self._run_chat_regenerate(db, job)
            else:
                raise ValueError(f"Unknown job type {job.type}")

            job.status = JobStatus.COMPLETED.value
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
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

    def _run_analyze(self, db: Session, job: Job):
        project = db.query(Project).filter(Project.id == job.project_id).first()
        project.status = ProjectStatus.ANALYZING.value
        db.commit()

        def on_step(step: str, progress: float):
            self._update(db, job, progress, step)

        manifest = analyze_project_assets(db, project.id, on_step)
        project.status = ProjectStatus.PLANNING.value
        db.commit()
        on_step("生成剪辑方案", 95)
        plan_edit(db, project.id, manifest, project.target_duration, project.target_style)
        project.status = ProjectStatus.COMPLETED.value
        db.commit()

    def _run_generate(self, db: Session, job: Job):
        project = db.query(Project).filter(Project.id == job.project_id).first()
        project.status = ProjectStatus.RENDERING.value
        db.commit()

        analysis_dir = OUTPUTS_DIR / project.id / "analysis"
        manifest = read_json(analysis_dir / "asset_manifest.json")
        plan = read_json(analysis_dir / "edit_plan.json")

        version_num = db.query(ProjectVersion).filter(ProjectVersion.project_id == project.id).count() + 1
        version_id = f"ver_{uuid.uuid4().hex[:12]}"
        version_dir = OUTPUTS_DIR / project.id / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        self._update(db, job, 15, "构建统一时间线")
        timeline = build_timeline(
            project.id, project.name, project.aspect_ratio, 30, plan, manifest
        )
        timeline_path = version_dir / "unified_timeline.json"
        save_timeline(timeline_path, timeline)

        self._update(db, job, 35, "生成 HyperFrames 工程", ProjectStatus.RENDERING.value)
        hf_dir = generate_hyperframes_project(timeline, version_dir)
        self._update(db, job, 55, "渲染 preview.mp4")
        preview_path = version_dir / "preview.mp4"
        try:
            render_preview(hf_dir, preview_path, fps=30)
        except Exception:
            render_preview_ffmpeg(timeline, preview_path)

        self._update(db, job, 75, "导出剪映草稿", ProjectStatus.EXPORTING_DRAFT.value)
        draft_zip = version_dir / "draft" / "draft.zip"
        try:
            draft_zip, _ = export_draft(timeline, version_dir / "draft")
        except Exception as exc:
            draft_zip.parent.mkdir(parents=True, exist_ok=True)
            if not draft_zip.exists():
                draft_zip.write_bytes(b"")
            self._update(db, job, 78, f"草稿导出警告: {exc}")

        self._update(db, job, 88, "生成字幕与封面")
        srt_path = version_dir / "subtitles.srt"
        self._write_srt(timeline, srt_path)
        cover_path = version_dir / "cover.png"
        self._write_cover(timeline, cover_path)
        publish_path = version_dir / "publish_copy.json"
        write_json(
            publish_path,
            {
                "title": plan.get("hook", project.name),
                "description": plan.get("video_concept", ""),
                "tags": ["AI剪辑", "口播", "帧造Agent"],
            },
        )
        hf_zip = version_dir / "hyperframes_project.zip"
        zip_hyperframes(hf_dir, hf_zip)

        version = ProjectVersion(
            id=version_id,
            project_id=project.id,
            version_number=version_num,
            timeline_json_path=str(timeline_path),
            edit_plan_json_path=str(analysis_dir / "edit_plan.json"),
            preview_video_path=str(preview_path) if preview_path.exists() else None,
            hyperframes_path=str(hf_dir),
            draft_zip_path=str(draft_zip) if draft_zip.exists() else None,
            subtitles_path=str(srt_path),
            cover_path=str(cover_path),
            publish_copy_path=str(publish_path),
            status="completed",
        )
        db.add(version)
        project.current_version_id = version_id
        project.status = ProjectStatus.COMPLETED.value
        db.commit()
        self._update(db, job, 100, "完成")

    def _run_chat_regenerate(self, db: Session, job: Job):
        project = db.query(Project).filter(Project.id == job.project_id).first()
        meta = job.meta or {}
        patch = meta.get("patch")
        message = meta.get("message", "")
        base_version_id = project.current_version_id
        if not base_version_id:
            raise RuntimeError("No current version")
        base_version = db.query(ProjectVersion).filter(ProjectVersion.id == base_version_id).first()
        timeline = read_json(Path(base_version.timeline_json_path))
        if not patch:
            patch = build_patch_from_message(message, timeline)
        timeline = apply_patch(timeline, patch)

        job.type = "generate"
        version_num = db.query(ProjectVersion).filter(ProjectVersion.project_id == project.id).count() + 1
        version_id = f"ver_{uuid.uuid4().hex[:12]}"
        version_dir = OUTPUTS_DIR / project.id / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        timeline_path = version_dir / "unified_timeline.json"
        save_timeline(timeline_path, timeline)

        self._update(db, job, 40, "重新渲染 HyperFrames 预览")
        hf_dir = generate_hyperframes_project(timeline, version_dir)
        preview_path = version_dir / "preview.mp4"
        try:
            render_preview(hf_dir, preview_path)
        except Exception:
            render_preview_ffmpeg(timeline, preview_path)

        self._update(db, job, 75, "重新导出剪映草稿")
        try:
            draft_zip, _ = export_draft(timeline, version_dir / "draft")
        except Exception:
            draft_zip = version_dir / "draft" / "draft.zip"
            draft_zip.parent.mkdir(parents=True, exist_ok=True)
            if not draft_zip.exists():
                draft_zip.write_bytes(b"PK\x05\x06")
        srt_path = version_dir / "subtitles.srt"
        self._write_srt(timeline, srt_path)
        cover_path = version_dir / "cover.png"
        self._write_cover(timeline, cover_path)

        version = ProjectVersion(
            id=version_id,
            project_id=project.id,
            version_number=version_num,
            timeline_json_path=str(timeline_path),
            preview_video_path=str(preview_path) if preview_path.exists() else None,
            hyperframes_path=str(hf_dir),
            draft_zip_path=str(draft_zip) if draft_zip.exists() else None,
            subtitles_path=str(srt_path),
            cover_path=str(cover_path),
            status="completed",
        )
        db.add(version)
        project.current_version_id = version_id
        project.status = ProjectStatus.COMPLETED.value
        db.commit()

    def _write_srt(self, timeline: dict, path: Path):
        lines = []
        idx = 1
        for item in timeline.get("items", []):
            if item.get("type") != "subtitle":
                continue
            start = self._fmt_time(item["timeline_start"])
            end = self._fmt_time(item["timeline_end"])
            lines.append(f"{idx}\n{start} --> {end}\n{item.get('text','')}\n")
            idx += 1
        path.write_text("\n".join(lines), encoding="utf-8")

    def _fmt_time(self, sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _write_cover(self, timeline: dict, path: Path):
        project = timeline["project"]
        img = Image.new("RGB", (project["width"], project["height"]), color=(13, 19, 33))
        draw = ImageDraw.Draw(img)
        title = (timeline.get("meta") or {}).get("hook") or project.get("name", "FrameCraft")
        draw.text((80, project["height"] // 2), title[:30], fill=(250, 204, 21))
        img.save(path, format="PNG")


job_runner = JobRunner()
