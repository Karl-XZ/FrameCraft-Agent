#!/usr/bin/env python3
"""FrameCraft Agent 工具 CLI — OpenClaw 唯一制片执行面。

用法:
  python -m app.services.agent_tools <command> [--args...]

所有命令输出 JSON 到 stdout。
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 允许从 backend/ 目录运行
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import OUTPUTS_DIR, ROOT  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Project, ProjectStatus, ProjectVersion  # noqa: E402
from app.utils import read_json, write_json  # noqa: E402


def _out(data: dict, code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(code)


def _project_id() -> str:
    pid = __import__("os").environ.get("FRAMECRAFT_PROJECT_ID")
    if not pid:
        _out({"ok": False, "error": "FRAMECRAFT_PROJECT_ID 未设置"}, 1)
    return pid


def _db_session():
    return SessionLocal()


def cmd_job_progress(args: argparse.Namespace) -> None:
    from .progress import update_job_progress

    r = update_job_progress(
        args.progress,
        args.step,
        status=args.job_status,
        project_status=args.project_status,
    )
    _out(r, 0 if r.get("ok") else 1)


def cmd_read_state(args: argparse.Namespace) -> None:
    pid = _project_id()
    ws = ROOT / "workspaces" / pid
    state_path = ws / "STATE.json"
    state = read_json(state_path) if state_path.exists() else {}
    analysis = OUTPUTS_DIR / pid / "analysis"
    _out({
        "ok": True,
        "state": state,
        "analysis_files": [p.name for p in analysis.iterdir()] if analysis.exists() else [],
        "has_manifest": (analysis / "asset_manifest.json").exists(),
        "has_edit_plan": (analysis / "edit_plan.json").exists(),
    })


def cmd_analyze_assets(args: argparse.Namespace) -> None:
    from .progress import update_job_progress
    from app.services.analyzer import analyze_project_assets

    pid = _project_id()
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        if not project:
            _out({"ok": False, "error": "项目不存在"}, 1)
        update_job_progress(5, "提取口播音频", project_status=ProjectStatus.ANALYZING.value)

        def on_step(step: str, progress: float):
            update_job_progress(progress, step, project_status=ProjectStatus.ANALYZING.value)

        manifest = analyze_project_assets(db, pid, on_step)
        update_job_progress(85, "素材分析完成", project_status=ProjectStatus.PLANNING.value)
        _out({"ok": True, "manifest_path": str(OUTPUTS_DIR / pid / "analysis" / "asset_manifest.json"), "asset_count": len(manifest.get("assets", []))})
    finally:
        db.close()


def cmd_write_edit_plan(args: argparse.Namespace) -> None:
    """Agent 写入 edit_plan.json（路径或 stdin JSON）。"""
    pid = _project_id()
    plan_path = OUTPUTS_DIR / pid / "analysis" / "edit_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if args.file:
        plan = read_json(Path(args.file))
    else:
        plan = json.loads(sys.stdin.read())
    write_json(plan_path, plan)
    from .progress import update_job_progress
    update_job_progress(95, "生成剪辑方案", project_status=ProjectStatus.PLANNING.value)
    _out({"ok": True, "path": str(plan_path)})


def cmd_suggest_edit_plan(args: argparse.Namespace) -> None:
    """可选工具：调用 LLM 辅助生成方案（Agent 决定是否使用，非默认流水线）。"""
    from app.services.planner import plan_edit
    from .progress import update_job_progress

    pid = _project_id()
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        if not project:
            _out({"ok": False, "error": "项目不存在"}, 1)
        manifest = read_json(OUTPUTS_DIR / pid / "analysis" / "asset_manifest.json")

        def on_plan_substep(substep: str, progress: float):
            update_job_progress(progress, f"生成剪辑方案 · {substep}", project_status=ProjectStatus.PLANNING.value)

        plan = plan_edit(
            db, pid, manifest, project.target_duration, project.target_style,
            args.strategy, args.platform, project.output_language or "zh",
            on_step=on_plan_substep,
        )
        _out({"ok": True, "path": str(OUTPUTS_DIR / pid / "analysis" / "edit_plan.json"), "scene_count": len(plan.get("scenes", []))})
    finally:
        db.close()


def cmd_build_timeline(args: argparse.Namespace) -> None:
    from app.services.timeline_builder import build_timeline, save_timeline
    from .progress import update_job_progress

    pid = _project_id()
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        analysis = OUTPUTS_DIR / pid / "analysis"
        manifest = read_json(analysis / "asset_manifest.json")
        plan = read_json(analysis / "edit_plan.json")
        version_id = args.version_id or f"ver_{uuid.uuid4().hex[:12]}"
        version_dir = OUTPUTS_DIR / pid / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        update_job_progress(20, "构建统一时间线", project_status=ProjectStatus.RENDERING.value)
        timeline = build_timeline(
            pid, project.name, project.aspect_ratio, args.fps, plan, manifest, args.resolution,
        )
        tl_path = version_dir / "unified_timeline.json"
        save_timeline(tl_path, timeline)
        _out({"ok": True, "version_id": version_id, "version_dir": str(version_dir), "timeline_path": str(tl_path)})
    finally:
        db.close()


def cmd_list_workflows(args: argparse.Namespace) -> None:
    from app.services.talking_head_workflow_service import _load_registry, workflow_label

    reg = _load_registry()
    workflows = reg.get("workflows") or {}
    items = [{"id": k, "label": workflow_label(k)} for k in workflows]
    _out({"ok": True, "workflows": items})


def cmd_workflow_build(args: argparse.Namespace) -> None:
    from app.services.talking_head_workflow_service import (
        prepare_workspace,
        run_build,
        workflow_label,
    )
    from .progress import update_job_progress

    pid = _project_id()
    version_dir = Path(args.version_dir)
    timeline = read_json(version_dir / "unified_timeline.json")
    manifest = read_json(OUTPUTS_DIR / pid / "analysis" / "asset_manifest.json")
    wf = args.workflow_id
    update_job_progress(40, f"口播工作流 build · {workflow_label(wf)}", project_status=ProjectStatus.RENDERING.value)
    prepare_workspace(version_dir, wf, timeline, manifest)
    hf_dir = run_build(version_dir, wf)
    timeline.setdefault("meta", {})["workflow_id"] = wf
    timeline["meta"]["workflow_label"] = workflow_label(wf)
    write_json(version_dir / "unified_timeline.json", timeline)
    _out({"ok": True, "workflow_id": wf, "hyperframes_dir": str(hf_dir)})


def cmd_render_preview(args: argparse.Namespace) -> None:
    from app.services.hyperframes_service import render_preview
    from app.services.talking_head_workflow_service import extract_qa_frames
    from .progress import update_job_progress

    version_dir = Path(args.version_dir)
    hf_dir = Path(args.hyperframes_dir)
    timeline = read_json(version_dir / "unified_timeline.json")
    fps = int(timeline.get("project", {}).get("fps", 30))
    quality = timeline.get("export_settings", {}).get("resolution", "1080p")
    preview_path = version_dir / "preview.mp4"
    update_job_progress(60, "渲染 preview.mp4", project_status=ProjectStatus.RENDERING.value)
    render_preview(hf_dir, preview_path, fps=fps, quality=quality)
    qa = []
    wf = (timeline.get("meta") or {}).get("workflow_id")
    if wf and preview_path.exists():
        qa = [str(p) for p in extract_qa_frames(preview_path, wf, version_dir / "qa_frames")]
    _out({"ok": True, "preview_path": str(preview_path), "qa_frames": qa})


def cmd_export_draft(args: argparse.Namespace) -> None:
    from app.services.draft_service import export_draft, validate_draft
    from .progress import update_job_progress

    version_dir = Path(args.version_dir)
    timeline = read_json(version_dir / "unified_timeline.json")
    update_job_progress(75, "导出剪映草稿", project_status=ProjectStatus.EXPORTING_DRAFT.value)
    draft_zip, _ = export_draft(timeline, version_dir / "draft")
    vr = validate_draft(version_dir / "draft")
    _out({"ok": True, "draft_zip": str(draft_zip), "validation": vr.to_dict()})


def cmd_finalize_version(args: argparse.Namespace) -> None:
    """注册版本到数据库并写出附属产物（字幕/封面/发布文案）。"""
    from PIL import Image, ImageDraw, ImageFont
    from app.services.hyperframes_service import zip_hyperframes
    from .progress import update_job_progress

    pid = _project_id()
    version_dir = Path(args.version_dir)
    version_id = args.version_id or version_dir.name
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        timeline = read_json(version_dir / "unified_timeline.json")
        plan = read_json(OUTPUTS_DIR / pid / "analysis" / "edit_plan.json")
        preview_path = version_dir / "preview.mp4"
        if not preview_path.exists():
            _out({"ok": False, "error": "preview.mp4 不存在，请先 render_preview"}, 1)

        update_job_progress(88, "生成字幕、封面与发布文案")

        def fmt_time(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_path = version_dir / "subtitles.srt"
        lines = []
        idx = 1
        for item in timeline.get("items", []):
            if item.get("type") != "subtitle":
                continue
            lines.append(f"{idx}\n{fmt_time(item['timeline_start'])} --> {fmt_time(item['timeline_end'])}\n{item.get('text','')}\n")
            idx += 1
        srt_path.write_text("\n".join(lines), encoding="utf-8")

        cover_path = version_dir / "cover.png"
        proj = timeline["project"]
        w, h = proj["width"], proj["height"]
        img = Image.new("RGB", (w, h), color=(13, 19, 33))
        draw = ImageDraw.Draw(img)
        title = (timeline.get("meta") or {}).get("cover_title") or plan.get("hook") or project.name
        try:
            font = ImageFont.truetype("msyh.ttc", int(h * 0.06))
        except Exception:
            font = ImageFont.load_default()
        draw.text((int(w * 0.08), int(h * 0.42)), str(title)[:14], fill=(250, 204, 21), font=font)
        img.save(cover_path, format="PNG")

        publish_path = version_dir / "publish_copy.json"
        publish = (timeline.get("meta") or {}).get("publish") or {
            "title": plan.get("hook", project.name),
            "description": plan.get("video_concept", ""),
            "tags": ["AI剪辑", "口播", "帧造Agent"],
        }
        write_json(publish_path, publish)

        hf_dir = Path(args.hyperframes_dir) if args.hyperframes_dir else version_dir / "hyperframes"
        hf_zip = version_dir / "hyperframes_project.zip"
        if project.keep_hyperframes and hf_dir.exists():
            zip_hyperframes(hf_dir, hf_zip)

        draft_zip = version_dir / "draft" / "draft.zip"
        version_num = db.query(ProjectVersion).filter(ProjectVersion.project_id == pid).count() + 1
        version = ProjectVersion(
            id=version_id,
            project_id=pid,
            version_number=version_num,
            timeline_json_path=str(version_dir / "unified_timeline.json"),
            edit_plan_json_path=str(OUTPUTS_DIR / pid / "analysis" / "edit_plan.json"),
            preview_video_path=str(preview_path),
            hyperframes_path=str(hf_dir) if hf_dir.exists() else None,
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
        update_job_progress(100, "完成")
        _out({"ok": True, "version_id": version_id, "version_number": version_num})
    finally:
        db.close()


def cmd_apply_patch(args: argparse.Namespace) -> None:
    from app.services.patch_service import apply_patch, build_patch_from_message, validate_patch
    from app.services.timeline_builder import save_timeline

    pid = _project_id()
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        if not project.current_version_id:
            _out({"ok": False, "error": "无当前版本"}, 1)
        base = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
        timeline = read_json(Path(base.timeline_json_path))
        if args.patch_file:
            patch = read_json(Path(args.patch_file))
        elif args.message:
            patch = build_patch_from_message(args.message, timeline, db)
            if patch.get("error") and not patch.get("operations"):
                _out({"ok": False, "error": patch["error"]}, 1)
        else:
            patch = json.loads(sys.stdin.read())
        ok, errors = validate_patch(timeline, patch)
        if not ok:
            _out({"ok": False, "errors": errors}, 1)
        timeline = apply_patch(timeline, patch)
        version_id = f"ver_{uuid.uuid4().hex[:12]}"
        version_dir = OUTPUTS_DIR / pid / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        save_timeline(version_dir / "unified_timeline.json", timeline)
        _out({"ok": True, "version_id": version_id, "version_dir": str(version_dir), "patch": patch})
    finally:
        db.close()


def cmd_write_chat_result(args: argparse.Namespace) -> None:
    pid = _project_id()
    ws = ROOT / "workspaces" / pid
    ws.mkdir(parents=True, exist_ok=True)
    if args.file:
        data = read_json(Path(args.file))
    else:
        data = json.loads(sys.stdin.read())
    out_path = ws / "CHAT_RESULT.json"
    write_json(out_path, data)
    _out({"ok": True, "path": str(out_path)})


def cmd_read_timeline(args: argparse.Namespace) -> None:
    pid = _project_id()
    db = _db_session()
    try:
        project = db.query(Project).filter(Project.id == pid).first()
        if not project or not project.current_version_id:
            _out({"ok": False, "error": "无当前版本"}, 1)
        ver = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
        tl = read_json(Path(ver.timeline_json_path))
        subtitle_ids = [i["id"] for i in tl.get("items", []) if i.get("type") == "subtitle"][:30]
        _out({
            "ok": True,
            "timeline_path": ver.timeline_json_path,
            "duration": tl.get("project", {}).get("duration"),
            "subtitle_ids": subtitle_ids,
            "asset_ids": [a["asset_id"] for a in tl.get("assets", [])],
        })
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="framecraft-tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("job_progress")
    p.add_argument("--progress", type=float, required=True)
    p.add_argument("--step", required=True)
    p.add_argument("--job-status")
    p.add_argument("--project-status")
    p.set_defaults(func=cmd_job_progress)

    p = sub.add_parser("read_state")
    p.set_defaults(func=cmd_read_state)

    p = sub.add_parser("analyze_assets")
    p.set_defaults(func=cmd_analyze_assets)

    p = sub.add_parser("write_edit_plan")
    p.add_argument("--file")
    p.set_defaults(func=cmd_write_edit_plan)

    p = sub.add_parser("suggest_edit_plan")
    p.add_argument("--strategy", default="complete")
    p.add_argument("--platform", default="douyin")
    p.set_defaults(func=cmd_suggest_edit_plan)

    p = sub.add_parser("build_timeline")
    p.add_argument("--version-id")
    p.add_argument("--resolution", default="1080p")
    p.add_argument("--fps", type=int, default=30)
    p.set_defaults(func=cmd_build_timeline)

    p = sub.add_parser("list_workflows")
    p.set_defaults(func=cmd_list_workflows)

    p = sub.add_parser("workflow_build")
    p.add_argument("--version-dir", required=True)
    p.add_argument("--workflow-id", required=True)
    p.set_defaults(func=cmd_workflow_build)

    p = sub.add_parser("render_preview")
    p.add_argument("--version-dir", required=True)
    p.add_argument("--hyperframes-dir", required=True)
    p.set_defaults(func=cmd_render_preview)

    p = sub.add_parser("export_draft")
    p.add_argument("--version-dir", required=True)
    p.set_defaults(func=cmd_export_draft)

    p = sub.add_parser("finalize_version")
    p.add_argument("--version-dir", required=True)
    p.add_argument("--version-id")
    p.add_argument("--hyperframes-dir")
    p.set_defaults(func=cmd_finalize_version)

    p = sub.add_parser("apply_patch")
    p.add_argument("--message")
    p.add_argument("--patch-file")
    p.set_defaults(func=cmd_apply_patch)

    p = sub.add_parser("write_chat_result")
    p.add_argument("--file")
    p.set_defaults(func=cmd_write_chat_result)

    p = sub.add_parser("read_timeline")
    p.set_defaults(func=cmd_read_timeline)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
