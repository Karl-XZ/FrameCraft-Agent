"""统一时间线构建（需求 §7）。

把 edit_plan.json 转换为 unified_timeline.json —— 整个项目的唯一事实来源。
所有元素都带 editable_in_draft 与 draft_export_mode 标记（§7.5）。
"""
from __future__ import annotations

from pathlib import Path

from ..utils import write_json


def aspect_to_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def build_timeline(
    project_id: str,
    project_name: str,
    aspect_ratio: str,
    fps: int,
    plan: dict,
    manifest: dict,
    resolution: str = "1080p",
) -> dict:
    width, height = aspect_to_size(aspect_ratio)
    if resolution.startswith("720"):
        scale = 720 / min(width, height)
        width, height = int(width * scale), int(height * scale)

    assets_by_id = {a["asset_id"]: a for a in manifest.get("assets", [])}
    scenes = [s for s in (plan.get("scenes") or []) if isinstance(s, dict)]
    duration = max((s.get("timeline_end", 0) for s in scenes), default=plan.get("target_duration", 60))

    template = plan.get("template") or {}
    tokens = template.get("tokens") or {}
    features = template.get("features") or {}

    def feat(name: str, default: bool = True) -> bool:
        return bool(features.get(name, default))

    tracks = [
        {"id": "track_video_main", "type": "video", "name": "main"},
        {"id": "track_video_broll", "type": "video", "name": "broll"},
        {"id": "track_image", "type": "image", "name": "image"},
        {"id": "track_audio_bgm", "type": "audio", "name": "bgm"},
        {"id": "track_audio_sfx", "type": "audio", "name": "sfx"},
        {"id": "track_subtitle", "type": "subtitle", "name": "subtitle"},
        {"id": "track_text", "type": "text", "name": "text"},
        {"id": "track_graphics", "type": "effect", "name": "graphics"},
        {"id": "track_overlay", "type": "shape", "name": "overlay"},
    ]
    items: list[dict] = []
    idx = 1

    def nid() -> str:
        nonlocal idx
        s = f"item_{idx:03d}"
        idx += 1
        return s

    n_scenes = len(scenes)
    for si, scene in enumerate(scenes):
        sp = scene.get("speech_source") or {}
        aid = sp.get("asset_id")
        s_start = scene["timeline_start"]
        s_end = scene["timeline_end"]
        seg_dur = s_end - s_start

        if aid and aid in assets_by_id:
            a_dur = assets_by_id[aid].get("duration")
            src_start = float(sp.get("source_start", 0))
            src_end = float(sp.get("source_end", src_start + seg_dur))
            if a_dur:
                src_end = min(src_end, float(a_dur))
                src_start = min(src_start, max(0.0, src_end - 0.1))
            main_item = {
                "id": nid(),
                "type": "video",
                "role": "a_roll",
                "asset_id": aid,
                "track_id": "track_video_main",
                "timeline_start": s_start,
                "timeline_end": s_end,
                "source_start": round(src_start, 3),
                "source_end": round(src_end, 3),
                "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1},
                # 轻微 ken-burns 推近，导出为剪映关键帧（§7.5 native_keyframe）
                "animations": [{"type": "scale", "from": 1.0, "to": 1.06}],
                "editable_in_draft": True,
                "draft_export_mode": "native",
            }
            if si < n_scenes - 1:
                main_item["transition"] = {"type": "dissolve", "duration": 0.4}
            items.append(main_item)

        # 逐词 karaoke 字幕
        words = scene.get("words") or []
        caption = (scene.get("caption") or "").strip()
        if not caption and words:
            caption = "".join(w.get("word", "") for w in words)
        if caption or words:
            items.append(
                {
                    "id": nid(),
                    "type": "subtitle",
                    "track_id": "track_subtitle",
                    "timeline_start": s_start,
                    "timeline_end": s_end,
                    "text": caption,
                    "words": words,
                    "style": "karaoke_bold",
                    "highlight_color": tokens.get("accent", "#FACC15"),
                    "normal_color": tokens.get("text", "#FFFFFF"),
                    "editable_in_draft": True,
                    "draft_export_mode": "native",
                }
            )

        # B-roll 插入
        for br in scene.get("broll") or []:
            if not isinstance(br, dict):
                continue
            baid = br.get("asset_id")
            if baid and baid in assets_by_id:
                ba = assets_by_id[baid]
                btype = "image" if ba.get("type") == "image" else "video"
                items.append(
                    {
                        "id": nid(),
                        "type": btype,
                        "role": "b_roll",
                        "asset_id": baid,
                        "track_id": "track_video_broll" if btype == "video" else "track_image",
                        "timeline_start": s_start,
                        "timeline_end": min(s_end, s_start + 3),
                        "source_start": 0,
                        "source_end": min(3, seg_dur),
                        "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1},
                        "intro_animation": "zoom_in",
                        "transition": {"type": "dissolve", "duration": 0.3},
                        "editable_in_draft": True,
                        "draft_export_mode": "native",
                    }
                )

    # Hook 大标题
    if plan.get("hook") and feat("hook"):
        items.append(
            {
                "id": nid(),
                "type": "text",
                "role": "hook",
                "track_id": "track_text",
                "timeline_start": 0,
                "timeline_end": min(4, duration),
                "text": plan["hook"][:40],
                "style": "hook_bold_yellow",
                "intro_animation": "fade_in",
                "outro_animation": "fade_out",
                "editable_in_draft": True,
                "draft_export_mode": "native",
            }
        )

    # Lower-third 信息条
    lt = plan.get("lower_third") or {}
    if lt.get("title") and feat("lower_third"):
        items.append(
            {
                "id": nid(),
                "type": "text",
                "role": "lower_third",
                "track_id": "track_text",
                "timeline_start": min(2, duration),
                "timeline_end": min(7, duration),
                "text": lt.get("title", ""),
                "subtitle": lt.get("subtitle", ""),
                "style": "lower_third",
                "intro_animation": "slide_in",
                "editable_in_draft": True,
                "draft_export_mode": "native",
            }
        )

    # 进度条（仅 HyperFrames 预览，剪映烘焙为覆盖层）
    if feat("progress_bar"):
        items.append(
            {
                "id": nid(),
                "type": "shape",
                "role": "progress_bar",
                "track_id": "track_overlay",
                "timeline_start": 0,
                "timeline_end": duration,
                "color": tokens.get("accent", "#EF4444"),
                "editable_in_draft": False,
                "draft_export_mode": "baked_overlay",
            }
        )

    # Motion graphics（§6.5）：关键词弹出 / 章节卡 / 解释卡 / stat / 标注 / CTA / 音效
    for g in plan.get("graphics", []):
        kind = g.get("kind")
        gs = float(g.get("timeline_start", 0))
        ge = float(g.get("timeline_end", gs + 1.5))
        if kind == "keyword_pop":
            items.append({
                "id": nid(), "type": "text", "role": "keyword_pop", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "text": g.get("text", ""),
                "color": tokens.get("accent", "#FACC15"),
                "editable_in_draft": False, "draft_export_mode": "hyperframes_only",
            })
        elif kind == "chapter_card":
            items.append({
                "id": nid(), "type": "text", "role": "chapter_card", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "text": g.get("title", ""),
                "index": g.get("index", 1), "color": tokens.get("primary", "#38BDF8"),
                "editable_in_draft": True, "draft_export_mode": "native_text",
            })
        elif kind == "explainer_card":
            items.append({
                "id": nid(), "type": "text", "role": "explainer_card", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "text": g.get("title", ""),
                "body": g.get("body", ""), "asset_id": g.get("asset_id"),
                "color": tokens.get("primary", "#38BDF8"),
                "editable_in_draft": True, "draft_export_mode": "native_text",
            })
        elif kind == "stat_block":
            items.append({
                "id": nid(), "type": "effect", "role": "stat_block", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "value": g.get("value", ""),
                "text": g.get("label", ""), "color": tokens.get("accent", "#FACC15"),
                "editable_in_draft": False, "draft_export_mode": "baked_overlay",
            })
        elif kind == "annotation":
            items.append({
                "id": nid(), "type": "effect", "role": "annotation", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "shape": g.get("shape", "circle"),
                "asset_id": g.get("asset_id"), "color": tokens.get("accent", "#FACC15"),
                "editable_in_draft": False, "draft_export_mode": "baked_overlay",
            })
        elif kind == "cta":
            items.append({
                "id": nid(), "type": "text", "role": "cta", "track_id": "track_graphics",
                "timeline_start": gs, "timeline_end": ge, "text": g.get("text", ""),
                "color": tokens.get("accent", "#FACC15"), "primary": tokens.get("primary", "#38BDF8"),
                "editable_in_draft": True, "draft_export_mode": "native_text",
            })
        elif kind == "sfx" and g.get("asset_id") in assets_by_id:
            items.append({
                "id": nid(), "type": "audio", "role": "sfx", "asset_id": g.get("asset_id"),
                "track_id": "track_audio_sfx", "timeline_start": gs, "timeline_end": ge,
                "source_start": 0, "source_end": max(0.2, ge - gs), "volume": 0.6,
                "editable_in_draft": True, "draft_export_mode": "native",
            })

    # BGM
    for a in manifest.get("assets", []):
        if a.get("user_label") == "音频" or "bgm" in (a.get("recommended_usage") or []):
            items.append(
                {
                    "id": nid(),
                    "type": "audio",
                    "asset_id": a["asset_id"],
                    "track_id": "track_audio_bgm",
                    "timeline_start": 0,
                    "timeline_end": duration,
                    "source_start": 0,
                    "source_end": duration,
                    "volume": 0.25,
                    "editable_in_draft": True,
                    "draft_export_mode": "native",
                }
            )
            break

    timeline = {
        "version": "1.0",
        "project": {
            "id": project_id,
            "name": project_name,
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
            "background": tokens.get("bg", "#0D1321"),
        },
        "assets": manifest.get("assets", []),
        "tracks": tracks,
        "items": items,
        "scenes": scenes,
        "styles": {
            "subtitle_default": plan.get("subtitle_style", ""),
            "hook": "hook_bold_yellow",
            "template": template,
        },
        "export_settings": {
            "resolution": resolution,
            "draft_target": "jianying",
            "fps": fps,
            "transition": plan.get("transition") or {"style": "crossfade", "opacity": 0.22, "duration": 0.18},
        },
        "meta": {
            "hook": plan.get("hook"),
            "video_concept": plan.get("video_concept"),
            "bgm_note": plan.get("bgm_note"),
            "strategy": plan.get("strategy"),
            "cover_title": plan.get("cover_title"),
            "publish": plan.get("publish"),
        },
    }
    return timeline


def save_timeline(path: Path, timeline: dict) -> None:
    write_json(path, timeline)
