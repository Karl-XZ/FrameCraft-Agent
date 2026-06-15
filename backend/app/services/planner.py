from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..utils import read_json, write_json
from .llm import llm_json


def _pick_broll(manifest: dict, used: set[str]) -> list[dict]:
    items = []
    for a in manifest.get("assets", []):
        if a.get("user_label") in {"B-roll", "图片", "LOGO"} or "broll" in a.get("recommended_usage", []):
            items.append(a)
    items.sort(key=lambda x: (not x.get("must_use"), -x.get("priority", 0)))
    return [a for a in items if a["asset_id"] not in used]


def plan_edit(db: Session, project_id: str, manifest: dict, target_duration: int, style: str) -> dict:
    asr = manifest.get("asr") or {}
    segments = asr.get("segments") or []
    kept = []
    t = 0.0
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        if any(x in text for x in ("嗯", "啊")) and len(text) < 4:
            continue
        dur = seg["end"] - seg["start"]
        if t + dur > target_duration:
            break
        kept.append(
            {
                "scene_id": f"scene_{len(kept)+1:03d}",
                "purpose": "hook" if len(kept) == 0 else "body",
                "timeline_start": t,
                "timeline_end": t + dur,
                "speech_source": {
                    "asset_id": next(
                        (a["asset_id"] for a in manifest["assets"] if a.get("user_label") == "口播视频"),
                        None,
                    ),
                    "source_start": seg["start"],
                    "source_end": seg["end"],
                },
                "caption": text,
                "visual_effects": ["word_highlight"] if len(kept) == 0 else [],
                "broll": [],
            }
        )
        t += dur

    broll_assets = _pick_broll(manifest, set())
    broll_plan = []
    for i, scene in enumerate(kept):
        if i < len(broll_assets) and scene["purpose"] != "hook":
            b = broll_assets[i]
            scene["broll"] = [{"asset_id": b["asset_id"], "mode": "cutaway"}]
            broll_plan.append(
                {
                    "time": scene["timeline_start"],
                    "text": b.get("auto_summary", b.get("user_note", "B-roll")),
                    "source": Path(b["file_path"]).name,
                    "asset_id": b["asset_id"],
                }
            )

    hook = kept[0]["caption"] if kept else "精彩口播开场"
    fallback = {
        "video_concept": "高级 AI 口播短视频",
        "target_duration": int(t or target_duration),
        "style": style,
        "hook": hook,
        "subtitle_style": "抖音风格 · 白色粗体 · 底部居中 · 关键词高亮",
        "bgm_note": "科技感 BGM",
        "scenes": kept,
        "broll_plan": broll_plan,
    }

    prompt = (
        "你是专业短视频剪辑策划。根据素材清单和口播转录，输出 JSON："
        "video_concept,target_duration,style,hook,subtitle_style,bgm_note,scenes,broll_plan。"
        f"目标时长约 {target_duration} 秒。manifest={manifest}"
    )
    plan = llm_json(
        db,
        "输出合法 JSON 剪辑方案，保留 scenes 时间结构。",
        prompt,
        fallback,
    )
    for k, v in fallback.items():
        plan.setdefault(k, v)
    out = OUTPUTS_DIR / project_id / "analysis" / "edit_plan.json"
    write_json(out, plan)
    return plan
