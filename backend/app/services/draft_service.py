from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from ..config import JIANYING_DRAFT_DIR, VECTCUT_DIR


def _ensure_vectcut_path():
    p = str(VECTCUT_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def export_draft(timeline: dict, out_dir: Path, copy_to_jianying: bool = True) -> tuple[Path, Path | None]:
    _ensure_vectcut_path()
    from add_audio_track import add_audio_track
    from add_image_impl import add_image_impl
    from add_subtitle_impl import add_subtitle_impl
    from add_text_impl import add_text_impl
    from add_video_track import add_video_track
    from create_draft import create_draft
    from draft_cache import update_cache
    from save_draft_impl import save_draft_impl

    out_dir.mkdir(parents=True, exist_ok=True)
    project = timeline["project"]
    width = project["width"]
    height = project["height"]
    assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}

    _, draft_id = create_draft(width=width, height=height)

    for item in timeline.get("items", []):
        itype = item.get("type")
        aid = item.get("asset_id")
        src = assets_by_id.get(aid, {}).get("file_path") if aid else None
        start = float(item.get("timeline_start", 0))
        end = float(item.get("timeline_end", start + 1))
        duration = end - start
        try:
            if itype == "video" and src:
                add_video_track(
                    video_url=src,
                    start=float(item.get("source_start", 0)),
                    end=float(item.get("source_end", duration)),
                    target_start=start,
                    draft_id=draft_id,
                    width=width,
                    height=height,
                    volume=1.0,
                )
            elif itype == "image" and src:
                add_image_impl(draft_id=draft_id, image_url=src, start=start, end=end, draft_folder=None)
            elif itype == "subtitle":
                add_subtitle_impl(
                    draft_id=draft_id,
                    srt="",
                    draft_folder=None,
                    text=item.get("text", ""),
                    start=start,
                    end=end,
                    font_size=42,
                )
            elif itype == "text":
                add_text_impl(draft_id=draft_id, text=item.get("text", ""), start=start, end=end, draft_folder=None, font_size=48)
            elif itype == "audio" and src:
                add_audio_track(
                    audio_url=src,
                    start=float(item.get("source_start", 0)),
                    end=float(item.get("source_end", duration)),
                    target_start=start,
                    draft_id=draft_id,
                    volume=float(item.get("volume", 0.3)),
                )
        except Exception:
            continue

    save_result = save_draft_impl(draft_id=draft_id, draft_folder=str(out_dir))
    draft_folder = out_dir / draft_id
    if not draft_folder.exists():
        candidates = list(out_dir.glob("dfd_*"))
        draft_folder = candidates[0] if candidates else out_dir / draft_id

    zip_path = out_dir / "draft.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if draft_folder.exists():
            for p in draft_folder.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(draft_folder.parent))

    copied = None
    if copy_to_jianying and JIANYING_DRAFT_DIR.exists() and draft_folder.exists():
        dest = JIANYING_DRAFT_DIR / draft_folder.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(draft_folder, dest)
        copied = dest

    guide = out_dir / "draft_import_guide.md"
    guide.write_text(
        f"# 剪映草稿导入说明\n\n- 草稿 ID: {draft_id}\n- 导出结果: {save_result}\n- 已复制到剪映: {'是' if copied else '否'}\n",
        encoding="utf-8",
    )
    return zip_path, copied
