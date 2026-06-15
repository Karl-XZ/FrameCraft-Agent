from __future__ import annotations

import shutil
from pathlib import Path

from ..utils import run_cmd


def render_preview_ffmpeg(timeline: dict, preview_path: Path) -> None:
    """FFmpeg 兜底预览：拼接主口播片段生成 MP4。"""
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}
    scenes = timeline.get("scenes") or []
    if not scenes:
        items = [i for i in timeline.get("items", []) if i.get("type") == "video"]
        if items:
            src = assets_by_id.get(items[0]["asset_id"], {}).get("file_path")
            if src:
                shutil.copy2(src, preview_path)
        return

    work = preview_path.parent / "_ffmpeg_tmp"
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for idx, scene in enumerate(scenes):
        sp = scene.get("speech_source") or {}
        aid = sp.get("asset_id")
        src = assets_by_id.get(aid, {}).get("file_path") if aid else None
        if not src:
            continue
        part = work / f"part_{idx:03d}.mp4"
        ss = float(sp.get("source_start", 0))
        dur = float(scene.get("timeline_end", 0) - scene.get("timeline_start", 0))
        run_cmd(
            [
                "ffmpeg", "-y", "-ss", str(ss), "-i", str(src),
                "-t", str(max(0.1, dur)), "-c:v", "libx264", "-c:a", "aac", str(part),
            ]
        )
        if part.exists():
            parts.append(part)

    if not parts:
        raise RuntimeError("No clips for ffmpeg preview")

    list_file = work / "list.txt"
    list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(preview_path)])
    if not preview_path.exists():
        run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:v", "libx264", "-c:a", "aac", str(preview_path)])
