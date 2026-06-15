from __future__ import annotations

from pathlib import Path

from ..utils import write_json


def aspect_to_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def build_timeline(project_id: str, project_name: str, aspect_ratio: str, fps: int, plan: dict, manifest: dict) -> dict:
    width, height = aspect_to_size(aspect_ratio)
    assets_by_id = {a["asset_id"]: a for a in manifest.get("assets", [])}
    duration = max((s.get("timeline_end", 0) for s in plan.get("scenes", [])), default=plan.get("target_duration", 60))

    tracks = [
        {"id": "track_video_main", "type": "video", "name": "main"},
        {"id": "track_video_broll", "type": "video", "name": "broll"},
        {"id": "track_image", "type": "image", "name": "image"},
        {"id": "track_audio_bgm", "type": "audio", "name": "bgm"},
        {"id": "track_subtitle", "type": "subtitle", "name": "subtitle"},
        {"id": "track_text", "type": "text", "name": "text"},
    ]
    items = []
    item_idx = 1

    for scene in plan.get("scenes", []):
        sp = scene.get("speech_source") or {}
        aid = sp.get("asset_id")
        if aid and aid in assets_by_id:
            items.append(
                {
                    "id": f"item_{item_idx:03d}",
                    "type": "video",
                    "asset_id": aid,
                    "track_id": "track_video_main",
                    "timeline_start": scene["timeline_start"],
                    "timeline_end": scene["timeline_end"],
                    "source_start": sp.get("source_start", 0),
                    "source_end": sp.get("source_end", scene["timeline_end"] - scene["timeline_start"]),
                    "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1},
                    "animations": [],
                    "editable_in_draft": True,
                    "draft_export_mode": "native",
                }
            )
            item_idx += 1
            items.append(
                {
                    "id": f"item_{item_idx:03d}",
                    "type": "subtitle",
                    "track_id": "track_subtitle",
                    "timeline_start": scene["timeline_start"],
                    "timeline_end": scene["timeline_end"],
                    "text": scene.get("caption", ""),
                    "style": "karaoke_bold",
                    "editable_in_draft": True,
                    "draft_export_mode": "native",
                }
            )
            item_idx += 1
        for br in scene.get("broll", []):
            baid = br.get("asset_id")
            if baid and baid in assets_by_id:
                ba = assets_by_id[baid]
                btype = "image" if ba.get("type") == "image" else "video"
                items.append(
                    {
                        "id": f"item_{item_idx:03d}",
                        "type": btype,
                        "asset_id": baid,
                        "track_id": "track_video_broll" if btype == "video" else "track_image",
                        "timeline_start": scene["timeline_start"],
                        "timeline_end": min(scene["timeline_end"], scene["timeline_start"] + 3),
                        "source_start": 0,
                        "source_end": 3,
                        "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1},
                        "editable_in_draft": True,
                        "draft_export_mode": "native",
                    }
                )
                item_idx += 1

    # hook title
    if plan.get("hook"):
        items.append(
            {
                "id": f"item_{item_idx:03d}",
                "type": "text",
                "track_id": "track_text",
                "timeline_start": 0,
                "timeline_end": min(4, duration),
                "text": plan["hook"][:40],
                "style": "hook_bold_yellow",
                "editable_in_draft": True,
                "draft_export_mode": "native",
            }
        )
        item_idx += 1

    # bgm
    for a in manifest.get("assets", []):
        if a.get("user_label") == "音频" or "bgm" in a.get("recommended_usage", []):
            items.append(
                {
                    "id": f"item_{item_idx:03d}",
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
            "background": "#0D1321",
        },
        "assets": manifest.get("assets", []),
        "tracks": tracks,
        "items": items,
        "scenes": plan.get("scenes", []),
        "styles": {"subtitle_default": plan.get("subtitle_style", "")},
        "export_settings": {"resolution": "1080p", "draft_target": "jianying"},
        "meta": {
            "hook": plan.get("hook"),
            "video_concept": plan.get("video_concept"),
            "bgm_note": plan.get("bgm_note"),
        },
    }
    return timeline


def save_timeline(path: Path, timeline: dict) -> None:
    write_json(path, timeline)
