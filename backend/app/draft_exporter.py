from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import store

VECTCUT_ROOT = store.ROOT / "vendor" / "VectCutAPI"
SAFE_DRAFT_NAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


@dataclass(frozen=True)
class DraftExportResult:
    draft_id: str
    draft_dir: Path
    zip_path: Path
    guide_path: Path


class DraftExportError(RuntimeError):
    pass


def export_jianying_draft(project_id: str, version_dir: Path) -> DraftExportResult:
    """Export an editable Jianying/CapCut draft from a FrameCraft version directory.

    The preview remains the HyperFrames source of truth. This exporter converts the
    unified timeline into native draft tracks where the format can represent them:
    source video/audio, editable captions, and editable text/card overlays.
    """

    version_dir = version_dir.resolve()
    timeline_path = version_dir / "timeline.json"
    if not timeline_path.is_file():
        raise DraftExportError(f"无法导出剪映草稿：缺少 timeline.json：{timeline_path}")

    timeline = _read_json(timeline_path)
    meta = timeline.get("meta") if isinstance(timeline.get("meta"), dict) else {}
    width, height = _timeline_size(meta, project_id)
    duration = _timeline_duration(timeline, version_dir)
    source_video = _resolve_source_video(timeline, version_dir, project_id)

    draft = _load_draft_lib(jianying=True)
    draft_id = _safe_draft_id(f"dfd_framecraft_{project_id}_{version_dir.name}")
    draft_parent = version_dir / "jianying_draft"
    draft_dir = draft_parent / draft_id
    if draft_parent.exists():
        shutil.rmtree(draft_parent)
    draft_dir.mkdir(parents=True, exist_ok=True)

    _copy_template(draft_dir)
    assets_video = draft_dir / "assets" / "video"
    assets_video.mkdir(parents=True, exist_ok=True)
    source_copy = assets_video / f"source{source_video.suffix.lower() or '.mp4'}"
    shutil.copy2(source_video, source_copy)

    script = draft.Script_file(width, height, fps=int(float(meta.get("fps") or 30)))
    script.add_track(draft.Track_type.video, "main_video", relative_index=0)
    _add_main_video(script, draft, source_copy, source_video, width, height, duration, timeline)
    _add_caption_tracks(script, draft, timeline, width, height)
    _add_block_tracks(script, draft, timeline, width, height)
    script.dump(str(draft_dir / "draft_info.json"))
    _patch_draft_files(draft_dir, draft_id, width, height, duration)

    guide_path = version_dir / "jianying_import_guide.md"
    guide_path.write_text(_guide_text(draft_id, draft_dir, source_copy), encoding="utf-8")

    zip_base = version_dir / "jianying_draft"
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=draft_parent, base_dir=draft_id))
    manifest = {
        "draft_id": draft_id,
        "draft_dir": str(draft_dir),
        "zip_path": str(zip_path),
        "source_video": str(source_video),
        "exported_at": store.now_iso(),
        "notes": [
            "preview.mp4 仍为 HyperFrames 真渲染成片。",
            "剪映草稿包含可编辑主视频、字幕和可降级表达的信息图层。",
            "复杂 CSS/GSAP 动画无法完整反编译为剪映原生动画。",
        ],
    }
    (version_dir / "jianying_draft_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return DraftExportResult(draft_id=draft_id, draft_dir=draft_dir, zip_path=zip_path, guide_path=guide_path)


def _load_draft_lib(*, jianying: bool):
    if str(VECTCUT_ROOT) not in sys.path:
        sys.path.insert(0, str(VECTCUT_ROOT))

    import settings  # type: ignore
    import settings.local as settings_local  # type: ignore

    settings_local.IS_CAPCUT_ENV = not jianying
    settings.IS_CAPCUT_ENV = not jianying

    import pyJianYingDraft as draft  # type: ignore

    # These modules import IS_CAPCUT_ENV by value, so keep them aligned when the
    # backend process has imported the package before.
    for module_name in (
        "pyJianYingDraft.script_file",
        "pyJianYingDraft.video_segment",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            setattr(module, "IS_CAPCUT_ENV", not jianying)
    return draft


def _copy_template(draft_dir: Path) -> None:
    template = VECTCUT_ROOT / "template_jianying"
    if not template.is_dir():
        raise DraftExportError(f"剪映草稿模板不存在：{template}")
    shutil.copytree(template, draft_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".backup"))


def _add_main_video(script: Any, draft: Any, source_copy: Path, original_source: Path, width: int, height: int, duration: float, timeline: dict[str, Any]) -> None:
    info = _ffprobe_video(original_source)
    src_w = int(info.get("width") or width)
    src_h = int(info.get("height") or height)
    material = draft.Video_material(
        material_type="video",
        path=str(source_copy),
        material_name=source_copy.name,
        duration=duration,
        width=src_w,
        height=src_h,
    )
    track = _main_video_track(timeline)
    fit = str(track.get("fit") or (timeline.get("source", {}) or {}).get("fit") or "cover")
    scale = _fit_scale(src_w, src_h, width, height, fit)
    clip = draft.Clip_settings(
        scale_x=scale,
        scale_y=scale,
        transform_x=float(track.get("transform_x") or 0),
        transform_y=float(track.get("transform_y") or 0),
    )
    segment = draft.Video_segment(
        material,
        target_timerange=draft.trange("0s", f"{duration}s"),
        source_timerange=draft.trange("0s", f"{duration}s"),
        speed=1.0,
        volume=float(track.get("volume", 1.0)),
        clip_settings=clip,
    )
    script.add_segment(segment, "main_video")


def _add_caption_tracks(script: Any, draft: Any, timeline: dict[str, Any], width: int, height: int) -> None:
    captions = _captions(timeline)
    if not captions:
        return
    script.add_track(draft.Track_type.text, "captions", relative_index=900)
    is_vertical = height > width
    style = draft.Text_style(size=7.2 if is_vertical else 6.4, bold=True, color=(1, 1, 1), alpha=1, align=1)
    border = draft.Text_border(alpha=0.92, color=(0, 0, 0), width=28)
    shadow = draft.Text_shadow(has_shadow=True, alpha=0.55, color="#000000", distance=5, smoothing=0.2)
    fixed_width = int(width * (0.78 if is_vertical else 0.62))
    y = -0.78 if is_vertical else -0.76
    for caption in captions:
        start, end = _safe_time_pair(caption.get("start"), caption.get("end"))
        text = _clean_visible_text(str(caption.get("text") or ""))
        if not text or end <= start:
            continue
        segment = draft.Text_segment(
            text,
            draft.trange(f"{start}s", f"{end - start}s"),
            style=style,
            clip_settings=draft.Clip_settings(transform_x=0, transform_y=y),
            border=border,
            shadow=shadow,
            fixed_width=fixed_width,
        )
        _add_fade_keyframes(segment, draft, end - start, base_x=0, base_y=y, move_x=0, move_y=0.015)
        script.add_segment(segment, "captions")


def _add_block_tracks(script: Any, draft: Any, timeline: dict[str, Any], width: int, height: int) -> None:
    blocks = _blocks(timeline)
    if not blocks:
        return
    is_vertical = height > width
    for block_index, block in enumerate(blocks[:16]):
        start, end = _safe_time_pair(block.get("start"), block.get("end"))
        if end - start < 0.7:
            continue
        title = _block_title(block)
        items = [_clean_visible_text(str(item)) for item in block.get("items", []) if str(item).strip()]
        x, y = _block_position(block, block_index, is_vertical)
        color = _block_color(block.get("kind"))
        title_track = f"block_{block_index:02d}_title"
        script.add_track(draft.Track_type.text, title_track, relative_index=520 + block_index * 4)
        _add_text_card(
            script,
            draft,
            track_name=title_track,
            text=title,
            start=start,
            end=min(end, start + max(1.2, (end - start) * 0.92)),
            x=x,
            y=y,
            width=width,
            height=height,
            color=color,
            size=6.7 if is_vertical else 6.2,
            strong=True,
        )
        row_y = y - (0.09 if is_vertical else 0.12)
        for item_index, item in enumerate(items[:4]):
            item_start = min(end - 0.55, start + 0.28 + item_index * 0.32)
            if item_start >= end:
                break
            item_track = f"block_{block_index:02d}_item_{item_index:02d}"
            script.add_track(draft.Track_type.text, item_track, relative_index=521 + block_index * 4 + item_index)
            _add_text_card(
                script,
                draft,
                track_name=item_track,
                text=item,
                start=item_start,
                end=end,
                x=x + (0.02 if item_index % 2 else 0),
                y=row_y - item_index * (0.075 if is_vertical else 0.095),
                width=width,
                height=height,
                color=color,
                size=5.6 if is_vertical else 5.0,
                strong=False,
            )


def _add_text_card(
    script: Any,
    draft: Any,
    *,
    track_name: str,
    text: str,
    start: float,
    end: float,
    x: float,
    y: float,
    width: int,
    height: int,
    color: str,
    size: float,
    strong: bool,
) -> None:
    duration = end - start
    if not text or duration <= 0.3:
        return
    rgb = _hex_to_rgb_tuple(color)
    background = draft.Text_background(
        color="#101318",
        alpha=0.34 if strong else 0.24,
        round_radius=0.82,
        height=0.18 if strong else 0.13,
        width=0.62 if height > width else 0.42,
    )
    border = draft.Text_border(alpha=0.45, color=rgb, width=10 if strong else 6)
    shadow = draft.Text_shadow(has_shadow=True, alpha=0.35, color="#000000", distance=4, smoothing=0.18)
    style = draft.Text_style(size=size, bold=strong, color=(1, 1, 1), alpha=1, align=1)
    segment = draft.Text_segment(
        _clean_visible_text(text),
        draft.trange(f"{start}s", f"{duration}s"),
        style=style,
        clip_settings=draft.Clip_settings(transform_x=x, transform_y=y),
        border=border,
        background=background,
        shadow=shadow,
        fixed_width=int(width * (0.46 if height <= width else 0.66)),
    )
    move = 0.045 if x <= 0 else -0.045
    _add_fade_keyframes(segment, draft, duration, base_x=x, base_y=y, move_x=move, move_y=0.015)
    script.add_segment(segment, track_name)


def _add_fade_keyframes(segment: Any, draft: Any, duration: float, *, base_x: float, base_y: float, move_x: float, move_y: float) -> None:
    dur_us = max(1, int(duration * 1_000_000))
    fade_us = min(int(0.28 * 1_000_000), max(1, dur_us // 4))
    segment.add_keyframe(draft.Keyframe_property.alpha, 0, 0)
    segment.add_keyframe(draft.Keyframe_property.alpha, fade_us, 1)
    segment.add_keyframe(draft.Keyframe_property.alpha, max(fade_us, dur_us - fade_us), 1)
    segment.add_keyframe(draft.Keyframe_property.alpha, dur_us, 0)
    if move_x or move_y:
        segment.add_keyframe(draft.Keyframe_property.position_x, 0, base_x + move_x)
        segment.add_keyframe(draft.Keyframe_property.position_x, fade_us, base_x)
        segment.add_keyframe(draft.Keyframe_property.position_y, 0, base_y - move_y)
        segment.add_keyframe(draft.Keyframe_property.position_y, fade_us, base_y)


def _patch_draft_files(draft_dir: Path, draft_id: str, width: int, height: int, duration: float) -> None:
    now = int(time.time())
    now_us = int(time.time() * 1_000_000)
    draft_info_path = draft_dir / "draft_info.json"
    draft_info = _read_json(draft_info_path)
    draft_uuid = str(uuid.uuid4()).upper()
    draft_info["id"] = draft_uuid
    draft_info["name"] = draft_id
    draft_info["create_time"] = now_us
    draft_info["update_time"] = now_us
    draft_info["duration"] = int(duration * 1_000_000)
    draft_info["canvas_config"] = {"width": width, "height": height, "ratio": "original"}
    draft_info_path.write_text(json.dumps(draft_info, ensure_ascii=False, indent=4), encoding="utf-8")

    meta_path = draft_dir / "draft_meta_info.json"
    if meta_path.is_file():
        meta = _read_json(meta_path)
        meta["draft_id"] = draft_uuid
        meta["draft_name"] = draft_id
        meta["draft_fold_path"] = str(draft_dir)
        meta["draft_root_path"] = str(draft_dir.parent)
        meta["tm_draft_create"] = now_us
        meta["tm_draft_modified"] = now_us
        meta["tm_duration"] = int(duration * 1_000_000)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    settings_path = draft_dir / "draft_settings"
    settings_path.write_text(
        "[General]\n"
        f"draft_create_time={now}\n"
        f"draft_last_edit_time={now}\n"
        "real_edit_keys=1\n"
        "real_edit_seconds=1\n",
        encoding="utf-8",
    )


def _guide_text(draft_id: str, draft_dir: Path, source_copy: Path) -> str:
    return f"""# 剪映草稿导入说明

草稿名称：`{draft_id}`

## 推荐方式

1. 在下载的 zip 中解压出 `{draft_id}` 文件夹。
2. 将整个 `{draft_id}` 文件夹复制到剪映专业版草稿目录。
3. 常见 macOS 路径：`~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/`
4. 常见 Windows 路径：`%LOCALAPPDATA%\\JianyingPro\\User Data\\Projects\\com.lveditor.draft\\`
5. 重启剪映专业版后，在草稿列表中打开该项目。

## 本机直接打开

当前服务端已经在这里生成了草稿目录：

`{draft_dir}`

草稿里的主素材路径指向：

`{source_copy}`

如果你在同一台电脑上使用剪映，通常可以直接复制草稿文件夹到剪映草稿目录并打开。

## 真实边界

该草稿不是从 MP4 反编译得到的。它由 `timeline.json` 同步生成，包含可编辑主视频、字幕和信息图层。HyperFrames 里的复杂 CSS/GSAP 动画会尽量转换成剪映可表达的文字卡片、淡入淡出和位移关键帧；无法保证 100% 原生还原。
"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DraftExportError(f"无法读取 JSON：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise DraftExportError(f"JSON 顶层必须是对象：{path}")
    return data


def _timeline_size(meta: dict[str, Any], project_id: str) -> tuple[int, int]:
    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    if width > 0 and height > 0:
        return width, height
    project = store.snapshot()["projects"].get(project_id) or {}
    ratio = str(project.get("aspect_ratio") or "9:16")
    if ratio == "16:9":
        return 1920, 1080
    return 1080, 1920


def _timeline_duration(timeline: dict[str, Any], version_dir: Path) -> float:
    meta = timeline.get("meta") if isinstance(timeline.get("meta"), dict) else {}
    duration = _as_float(meta.get("duration"), 0)
    if duration > 0:
        return duration
    candidates: list[float] = []
    for item in _captions(timeline) + _blocks(timeline):
        candidates.append(_as_float(item.get("end"), 0))
    source_video = _maybe_resolve_source_video(timeline, version_dir, None)
    if source_video and source_video.is_file():
        candidates.append(_ffprobe_duration(source_video))
    duration = max(candidates or [0])
    if duration <= 0:
        raise DraftExportError("无法判断草稿时长")
    return duration


def _resolve_source_video(timeline: dict[str, Any], version_dir: Path, project_id: str) -> Path:
    source = _maybe_resolve_source_video(timeline, version_dir, project_id)
    if source and source.is_file():
        return source
    data = store.snapshot()
    uploads = [
        Path(asset["path"])
        for asset in data["assets"].values()
        if asset.get("project_id") == project_id and asset.get("file_type") == "video" and asset.get("path")
    ]
    for path in uploads:
        if path.is_file():
            return path
    raise DraftExportError("无法导出剪映草稿：没有找到主视频素材")


def _maybe_resolve_source_video(timeline: dict[str, Any], version_dir: Path, project_id: str | None) -> Path | None:
    candidates: list[str] = []
    source = timeline.get("source") if isinstance(timeline.get("source"), dict) else {}
    if source.get("video"):
        candidates.append(str(source["video"]))
    track = _main_video_track(timeline)
    if track.get("src"):
        candidates.append(str(track["src"]))
    for raw in candidates:
        path = Path(raw).expanduser()
        possible = path if path.is_absolute() else version_dir / path
        if possible.is_file():
            return possible.resolve()
    if project_id:
        uploads = store.upload_dir(project_id)
        videos = sorted(uploads.glob("*"))
        for path in videos:
            if path.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}:
                return path.resolve()
    return None


def _main_video_track(timeline: dict[str, Any]) -> dict[str, Any]:
    tracks = timeline.get("tracks") if isinstance(timeline.get("tracks"), dict) else {}
    videos = tracks.get("video") if isinstance(tracks.get("video"), list) else []
    for item in videos:
        if isinstance(item, dict):
            return item
    return {}


def _captions(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(timeline.get("subtitles"), list):
        return [item for item in timeline["subtitles"] if isinstance(item, dict)]
    tracks = timeline.get("tracks") if isinstance(timeline.get("tracks"), dict) else {}
    captions = tracks.get("captions") if isinstance(tracks.get("captions"), list) else []
    return [item for item in captions if isinstance(item, dict)]


def _blocks(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(timeline.get("blocks"), list):
        return [item for item in timeline["blocks"] if isinstance(item, dict)]
    tracks = timeline.get("tracks") if isinstance(timeline.get("tracks"), dict) else {}
    blocks = tracks.get("blocks") if isinstance(tracks.get("blocks"), list) else []
    return [item for item in blocks if isinstance(item, dict)]


def _block_title(block: dict[str, Any]) -> str:
    title = _clean_visible_text(str(block.get("title") or ""))
    if title:
        return title
    kind = str(block.get("kind") or "")
    block_id = str(block.get("id") or "")
    mapping = {
        "reaction": "反应来了",
        "meme": "灵感闪现",
        "sticker": "重点提示",
        "metric": "情绪指数",
        "flow": "过程拆解",
        "compare": "对比一下",
        "table": "信息整理",
        "timeline": "时间线",
        "text_card": "关键一句",
        "info_card": "重点信息",
        "quote": "关键表达",
    }
    if kind in mapping:
        return mapping[kind]
    if "idea" in block_id:
        return "灵感闪现"
    if "plan" in block_id:
        return "计划成形"
    return "重点提示"


def _block_position(block: dict[str, Any], index: int, is_vertical: bool) -> tuple[float, float]:
    position = str(block.get("position") or "")
    if is_vertical:
        table = {
            "left_top": (-0.16, 0.58),
            "left_mid": (-0.18, 0.32),
            "left_lower": (-0.14, -0.28),
            "spread_top": (0.0, 0.58),
            "top_band": (0.0, 0.62),
        }
        fallback = [(-0.18, 0.56), (0.18, 0.36), (-0.16, 0.08), (0.16, -0.22)]
    else:
        table = {
            "left_top": (-0.54, 0.56),
            "left_mid": (-0.56, 0.18),
            "left_lower": (-0.52, -0.36),
            "spread_top": (-0.18, 0.58),
            "top_band": (0.0, 0.62),
        }
        fallback = [(-0.54, 0.48), (0.48, 0.34), (-0.56, -0.16), (0.48, -0.22)]
    return table.get(position, fallback[index % len(fallback)])


def _block_color(kind: Any) -> str:
    return {
        "reaction": "#FFB000",
        "meme": "#FF5C8A",
        "sticker": "#48D597",
        "metric": "#55D6FF",
        "flow": "#7CE37C",
        "compare": "#FFD166",
        "table": "#7AC8FF",
        "timeline": "#D4A8FF",
        "quote": "#F5C542",
    }.get(str(kind), "#8FE3FF")


def _clean_visible_text(text: str) -> str:
    forbidden = [
        "FrameCraft",
        "帧造",
        "高级口播",
        "观点重构",
        "AI 重构",
        "主口播原片",
        "DISTRIBUTION EXPERIMENT BOARD",
        "CREATOR",
        "不整块解释",
    ]
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    for word in forbidden:
        cleaned = cleaned.replace(word, "")
    return cleaned.strip()


def _safe_time_pair(start: Any, end: Any) -> tuple[float, float]:
    s = max(0.0, _as_float(start, 0.0))
    e = max(s, _as_float(end, s))
    return s, e


def _fit_scale(src_w: int, src_h: int, width: int, height: int, fit: str) -> float:
    if src_w <= 0 or src_h <= 0:
        return 1.0
    scale_x = width / src_w
    scale_y = height / src_h
    if fit in {"contain", "fit", "inside"}:
        return min(scale_x, scale_y)
    return max(scale_x, scale_y)


def _ffprobe_video(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise DraftExportError(f"ffprobe 读取视频失败：{path}：{proc.stderr.strip()}")
    info = json.loads(proc.stdout or "{}")
    stream = (info.get("streams") or [{}])[0]
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration": _as_float((info.get("format") or {}).get("duration"), 0),
    }


def _ffprobe_duration(path: Path) -> float:
    return _as_float(_ffprobe_video(path).get("duration"), 0)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _hex_to_rgb_tuple(hex_color: str) -> tuple[float, float, float]:
    text = hex_color.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return (1, 1, 1)
    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
    )


def _safe_draft_id(raw: str) -> str:
    return "".join(ch if ch in SAFE_DRAFT_NAME_CHARS else "_" for ch in raw)[:96]
