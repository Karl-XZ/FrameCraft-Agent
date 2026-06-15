from __future__ import annotations

from copy import deepcopy


def apply_patch(timeline: dict, patch: dict) -> dict:
    tl = deepcopy(timeline)
    items = tl.setdefault("items", [])
    for op in patch.get("operations", []):
        kind = op.get("op")
        if kind == "update_item":
            target = op.get("target_id")
            changes = op.get("changes", {})
            for item in items:
                if item.get("id") == target:
                    item.update(changes)
        elif kind == "replace_text_by_style":
            style = op.get("style")
            new_text = op.get("text")
            for item in items:
                if item.get("style") == style:
                    item["text"] = new_text
        elif kind == "set_bgm_volume":
            vol = op.get("volume", 0.3)
            for item in items:
                if item.get("type") == "audio":
                    item["volume"] = vol
        elif kind == "speed_up":
            factor = op.get("factor", 1.15)
            cursor = 0.0
            for scene in tl.get("scenes", []):
                old_len = scene["timeline_end"] - scene["timeline_start"]
                new_len = old_len / factor
                scene["timeline_start"] = cursor
                scene["timeline_end"] = cursor + new_len
                cursor += new_len
            tl["project"]["duration"] = cursor
    return tl


def build_patch_from_message(message: str, timeline: dict) -> dict:
    msg = message.lower()
    ops = []
    if "黄色" in message or "yellow" in msg:
        for item in timeline.get("items", []):
            if item.get("type") == "text":
                ops.append(
                    {
                        "op": "update_item",
                        "target_id": item["id"],
                        "changes": {"style": "hook_bold_yellow", "text": item.get("text", "")},
                    }
                )
    if "bgm" in msg or "背景音乐" in message or "音量" in message:
        vol = 0.15 if ("小" in message or "降低" in message) else 0.4
        ops.append({"op": "set_bgm_volume", "volume": vol})
    if "快" in message or "节奏" in message:
        ops.append({"op": "speed_up", "factor": 1.2})
    if "字幕" in message:
        for item in timeline.get("items", []):
            if item.get("type") == "subtitle":
                new_text = message.split("改成")[-1].strip() if "改成" in message else item.get("text", "")
                if new_text:
                    ops.append(
                        {"op": "update_item", "target_id": item["id"], "changes": {"text": new_text}}
                    )
                break
    if not ops and timeline.get("items"):
        first_sub = next((i for i in timeline["items"] if i.get("type") == "subtitle"), None)
        if first_sub:
            ops.append(
                {
                    "op": "update_item",
                    "target_id": first_sub["id"],
                    "changes": {"text": message[:80]},
                }
            )
    return {
        "patch_id": "patch_auto",
        "description": message,
        "operations": ops,
    }
