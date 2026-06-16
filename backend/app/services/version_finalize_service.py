"""成片后处理：HyperFrames 工程就绪后的机械步骤（渲染、注册版本）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..models import Project, ProjectStatus, ProjectVersion
from ..utils import read_json, write_json
from .hyperframes_service import render_preview, zip_hyperframes


def resolve_version_dir(project_id: str, *, patched_version_dir: str | None = None) -> Path:
    """定位 Agent 产出的版本目录（含 unified_timeline + hyperframes）。"""
    if patched_version_dir:
        version_dir = Path(patched_version_dir)
        if not version_dir.is_dir():
            raise RuntimeError(f"patched_version_dir 不存在：{patched_version_dir}")
        return version_dir

    out = OUTPUTS_DIR / project_id
    candidates = [
        d
        for d in out.glob("ver_*")
        if d.is_dir()
        and (d / "unified_timeline.json").is_file()
        and (d / "hyperframes" / "index.html").is_file()
    ]
    if not candidates:
        raise RuntimeError("未找到含 HyperFrames 工程的版本目录（ver_*/hyperframes/index.html）")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def server_render_preview(version_dir: Path) -> Path:
    """lint + 渲染 preview.mp4。"""
    hf_dir = version_dir / "hyperframes"
    timeline = read_json(version_dir / "unified_timeline.json")
    fps = int(timeline.get("project", {}).get("fps", 30))
    quality = timeline.get("export_settings", {}).get("resolution", "1080p")
    preview_path = version_dir / "preview.mp4"
    render_preview(hf_dir, preview_path, fps=fps, quality=quality)
    return preview_path


def finalize_version_record(
    db: Session,
    project: Project,
    version_dir: Path,
    *,
    hyperframes_dir: Path | None = None,
) -> ProjectVersion:
    """将已渲染的 preview 注册为 DB 版本，并写出字幕/封面/发布文案。"""
    pid = project.id
    version_id = version_dir.name
    timeline = read_json(version_dir / "unified_timeline.json")
    plan = read_json(OUTPUTS_DIR / pid / "analysis" / "edit_plan.json")
    preview_path = version_dir / "preview.mp4"
    if not preview_path.is_file():
        raise RuntimeError("preview.mp4 不存在，无法注册版本")

    def fmt_time(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_path = version_dir / "subtitles.srt"
    lines: list[str] = []
    idx = 1
    for item in timeline.get("items", []):
        if item.get("type") != "subtitle":
            continue
        lines.append(
            f"{idx}\n{fmt_time(item['timeline_start'])} --> {fmt_time(item['timeline_end'])}\n"
            f"{item.get('text', '')}\n"
        )
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

    hf_dir = hyperframes_dir or version_dir / "hyperframes"
    hf_zip = version_dir / "hyperframes_project.zip"
    if project.keep_hyperframes and hf_dir.exists():
        zip_hyperframes(hf_dir, hf_zip)

    draft_zip = version_dir / "draft" / "draft.zip"
    existing = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
    if existing:
        version = existing
        version.timeline_json_path = str(version_dir / "unified_timeline.json")
        version.edit_plan_json_path = str(OUTPUTS_DIR / pid / "analysis" / "edit_plan.json")
        version.preview_video_path = str(preview_path)
        version.hyperframes_path = str(hf_dir) if hf_dir.exists() else None
        version.subtitles_path = str(srt_path)
        version.cover_path = str(cover_path)
        version.publish_copy_path = str(publish_path)
        version.status = "completed"
    else:
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
    db.refresh(version)
    return version
