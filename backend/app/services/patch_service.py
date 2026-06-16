"""对话修改：timeline patch 生成、校验与应用（需求 §10）。"""
from __future__ import annotations

import uuid
from copy import deepcopy

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..utils import read_json, write_json
from .agent_orchestrator import run_text_json_with_meta
from .llm import llm_available
from .templates import resolve_template
from .timeline_builder import save_timeline

PATCH_OPS_PROMPT = """支持的 patch.operations（每项含 op 字段）：
- update_title(text) 改 Hook 标题
- set_subtitle_text(target_id, text) 改某条字幕文案
- set_subtitle_style(highlight_color, normal_color, font_size, font) 改字幕样式
- set_subtitle_animation(intro, outro: fade|none) 字幕行渐显渐隐
- set_bgm_volume(volume 0-1) 调 BGM 音量
- speed_up(factor>1) 整体节奏加快
- replace_asset(target_id, asset_id) 替换素材
- remove_item(target_id) 删除元素
- add_item(item:{type, role, timeline_start, timeline_end, text?, asset_id?}) 新增片段
- set_cover_title(text) 改封面文案
- set_style(template) 换视频风格模板
- regenerate_segment(scene_id 或 timeline_start) 重生成某段
- update_item(target_id, changes) 通用字段修改"""

# 不同角色的默认轨道 / 导出策略，用于 add_item 自动补全
_ROLE_DEFAULTS = {
    "hook": ("track_text", "text", "native"),
    "lower_third": ("track_text", "text", "native"),
    "chapter_card": ("track_graphics", "text", "native_text"),
    "explainer_card": ("track_graphics", "text", "native_text"),
    "cta": ("track_graphics", "text", "native_text"),
    "keyword_pop": ("track_graphics", "text", "hyperframes_only"),
    "b_roll": ("track_video_broll", "video", "native"),
}


def _gen_id() -> str:
    return f"item_add_{uuid.uuid4().hex[:8]}"


def _build_item(tl: dict, spec: dict) -> dict | None:
    """根据简化 spec 构建一个完整 timeline item（用于 add_item）。"""
    role = spec.get("role")
    itype = spec.get("type")
    if not itype:
        itype = _ROLE_DEFAULTS.get(role, (None, "text", None))[1]
    track, _t, mode = _ROLE_DEFAULTS.get(role, ("track_graphics", itype, "native_text" if itype == "text" else "native"))
    start = float(spec.get("timeline_start", 0))
    end = float(spec.get("timeline_end", start + 2.5))
    if end <= start:
        end = start + 2.5
    item: dict = {
        "id": _gen_id(),
        "type": itype,
        "track_id": spec.get("track_id", track),
        "timeline_start": round(start, 3),
        "timeline_end": round(end, 3),
        "editable_in_draft": mode in {"native", "native_text", "native_keyframe"},
        "draft_export_mode": spec.get("draft_export_mode", mode),
    }
    if role:
        item["role"] = role
    if itype == "text":
        item["text"] = spec.get("text", "")
        if spec.get("body"):
            item["body"] = spec["body"]
        item["color"] = spec.get("color", "#FACC15")
    if itype in {"video", "image"}:
        aid = spec.get("asset_id")
        if not aid:
            return None
        item["asset_id"] = aid
        item["source_start"] = float(spec.get("source_start", 0))
        item["source_end"] = float(spec.get("source_end", end - start))
        item["transform"] = {"x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1}
        item.setdefault("role", "b_roll")
        item["intro_animation"] = "zoom_in"
    if itype == "audio":
        aid = spec.get("asset_id")
        if not aid:
            return None
        item["asset_id"] = aid
        item["source_start"] = float(spec.get("source_start", 0))
        item["source_end"] = float(spec.get("source_end", end - start))
        item["volume"] = float(spec.get("volume", 0.5))
    return item


def _recolor(tl: dict, tokens: dict) -> None:
    """切换风格时，重新着色现有元素。"""
    accent = tokens.get("accent", "#FACC15")
    primary = tokens.get("primary", "#38BDF8")
    text_c = tokens.get("text", "#FFFFFF")
    tl["project"]["background"] = tokens.get("bg", tl["project"].get("background"))
    for item in tl.get("items", []):
        role = item.get("role")
        if item.get("type") == "subtitle":
            item["highlight_color"] = accent
            item["normal_color"] = text_c
        elif role in {"keyword_pop", "stat_block", "cta"}:
            item["color"] = accent
        elif role in {"chapter_card", "explainer_card"}:
            item["color"] = primary
        elif role == "progress_bar":
            item["color"] = accent


def _scale_time(tl: dict, factor: float) -> None:
    """整体变速：同步缩放 items 与 scenes 时间，并更新总时长。"""
    inv = 1.0 / factor
    for item in tl.get("items", []):
        if item.get("role") == "progress_bar":
            continue
        item["timeline_start"] = round(item.get("timeline_start", 0) * inv, 3)
        item["timeline_end"] = round(item.get("timeline_end", 0) * inv, 3)
        for w in item.get("words", []) or []:
            w["start"] = round(w["start"] * inv, 3)
            w["end"] = round(w["end"] * inv, 3)
    for scene in tl.get("scenes", []):
        scene["timeline_start"] = round(scene.get("timeline_start", 0) * inv, 3)
        scene["timeline_end"] = round(scene.get("timeline_end", 0) * inv, 3)
    new_dur = max(
        (i.get("timeline_end", 0) for i in tl.get("items", []) if i.get("role") != "progress_bar"),
        default=tl["project"]["duration"] * inv,
    )
    tl["project"]["duration"] = round(new_dur, 3)
    for item in tl.get("items", []):
        if item.get("role") == "progress_bar":
            item["timeline_start"] = 0
            item["timeline_end"] = tl["project"]["duration"]


def apply_patch(timeline: dict, patch: dict) -> dict:
    tl = deepcopy(timeline)
    items = tl.setdefault("items", [])
    for op in patch.get("operations", []):
        kind = op.get("op")
        if kind == "update_item":
            for item in items:
                if item.get("id") == op.get("target_id"):
                    item.update(op.get("changes", {}))
        elif kind == "update_role":
            for item in items:
                if item.get("role") == op.get("role"):
                    item.update(op.get("changes", {}))
        elif kind in {"set_subtitle_color", "set_subtitle_style"}:
            for item in items:
                if item.get("type") == "subtitle":
                    if op.get("highlight_color"):
                        item["highlight_color"] = op["highlight_color"]
                    if op.get("normal_color"):
                        item["normal_color"] = op["normal_color"]
                    if op.get("font_size"):
                        item["font_size"] = op["font_size"]
                    if op.get("font"):
                        item["font"] = op["font"]
        elif kind == "set_subtitle_text":
            for item in items:
                if item.get("id") == op.get("target_id") and item.get("type") == "subtitle":
                    item["text"] = op.get("text", item.get("text"))
                    item["words"] = []  # 文本被改写，放弃逐词时间戳
        elif kind == "update_title":
            for item in items:
                if item.get("role") == "hook":
                    item["text"] = op.get("text", item.get("text"))
            if tl.get("meta"):
                tl["meta"]["hook"] = op.get("text", tl["meta"].get("hook"))
        elif kind == "set_bgm_volume":
            for item in items:
                if item.get("type") == "audio":
                    item["volume"] = op.get("volume", 0.25)
        elif kind == "remove_item":
            tl["items"] = [i for i in items if i.get("id") != op.get("target_id")]
            items = tl["items"]
        elif kind == "replace_asset":
            for item in items:
                if item.get("id") == op.get("target_id"):
                    item["asset_id"] = op.get("asset_id", item.get("asset_id"))
        elif kind == "speed_up":
            _scale_time(tl, op.get("factor", 1.2))
        elif kind == "add_item":
            spec = op.get("item") or op.get("changes") or op
            new_item = _build_item(tl, spec)
            if new_item:
                items.append(new_item)
                # 若新元素超出总时长，扩展 project.duration 与进度条
                if new_item["timeline_end"] > tl["project"].get("duration", 0):
                    tl["project"]["duration"] = new_item["timeline_end"]
                    for it in items:
                        if it.get("role") == "progress_bar":
                            it["timeline_end"] = tl["project"]["duration"]
        elif kind == "set_subtitle_animation":
            tl.setdefault("meta", {})["caption_animation"] = {
                "intro": op.get("intro", "none"),
                "outro": op.get("outro", "none"),
            }
        elif kind == "set_cover_title":
            tl.setdefault("meta", {})["cover_title"] = op.get("text", tl.get("meta", {}).get("cover_title"))
        elif kind in {"set_style", "change_template"}:
            tpl = resolve_template(op.get("template") or op.get("style"))
            tokens = op.get("tokens") or tpl.get("tokens", {})
            tl.setdefault("styles", {})["template"] = {
                "id": tpl["id"], "label": tpl["label"], "tokens": tokens, "features": tpl["features"],
            }
            _recolor(tl, tokens)
        elif kind == "regenerate_segment":
            # 重新生成某一段：把目标字幕恢复为该场景原始转录文案与逐词时间戳
            scenes = {s.get("scene_id"): s for s in tl.get("scenes", [])}
            target = op.get("scene_id")
            tstart = op.get("timeline_start")
            for item in items:
                if item.get("type") != "subtitle":
                    continue
                hit = False
                if target and target in scenes:
                    sc = scenes[target]
                    if abs(item.get("timeline_start", -1) - sc.get("timeline_start", -2)) < 0.01:
                        hit = True
                elif tstart is not None and abs(item.get("timeline_start", -1) - float(tstart)) < 0.5:
                    hit = True
                if hit:
                    sc = next((s for s in tl.get("scenes", []) if abs(s.get("timeline_start", -1) - item.get("timeline_start", -2)) < 0.01), None)
                    if sc:
                        item["text"] = sc.get("caption", item.get("text", ""))
                        item["words"] = sc.get("words", [])
    return tl


def validate_patch(timeline: dict, patch: dict) -> tuple[bool, list[str]]:
    """§10.4 patch 校验。返回 (是否通过, 错误列表)。"""
    errors: list[str] = []
    asset_ids = {a["asset_id"] for a in timeline.get("assets", [])}
    preview = apply_patch(timeline, patch)
    items = preview.get("items", [])

    # 不能删除所有主口播轨
    main_videos = [i for i in items if i.get("role") == "a_roll"]
    orig_main = [i for i in timeline.get("items", []) if i.get("role") == "a_roll"]
    if orig_main and not main_videos:
        errors.append("不能删除全部主口播轨道")

    for op in patch.get("operations", []):
        if op.get("op") == "replace_asset" and op.get("asset_id") not in asset_ids:
            errors.append(f"引用了未上传的素材：{op.get('asset_id')}")
        if op.get("op") == "set_subtitle_text" and not (op.get("text") or "").strip():
            errors.append("字幕文本不能为空")
        if op.get("op") == "add_item":
            spec = op.get("item") or op.get("changes") or op
            if spec.get("type") in {"video", "image", "audio"} and spec.get("asset_id") not in asset_ids:
                errors.append(f"新增片段引用了未上传的素材：{spec.get('asset_id')}")

    # 字幕非空
    for i in items:
        if i.get("type") == "subtitle" and not (i.get("text") or "").strip():
            errors.append(f"字幕 {i.get('id')} 文本为空")

    # 片段不能超出源素材时长
    assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}
    for i in items:
        if i.get("type") in {"video", "audio"} and i.get("asset_id"):
            adur = assets_by_id.get(i["asset_id"], {}).get("duration")
            if adur and i.get("source_end", 0) > adur + 0.5:
                errors.append(f"片段 {i.get('id')} 出点 {i.get('source_end')}s 超出素材时长 {adur}s")

    # 总时长合理（1s ~ 600s）
    dur = preview.get("project", {}).get("duration", 0)
    if dur <= 0.5 or dur > 600:
        errors.append(f"输出总时长不合理：{dur}s")

    return (len(errors) == 0, errors)


def prepare_patched_version(db: Session, project_id: str, patch: dict) -> tuple[str, Path]:
    """服务端先落地 patch：校验、应用并写入新版本 unified_timeline.json。"""
    from ..models import Project, ProjectVersion

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.current_version_id:
        raise ValueError("项目或当前版本不存在")
    base = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_version_id).first()
    if not base or not base.timeline_json_path:
        raise ValueError("当前版本缺少 unified_timeline.json")

    timeline = read_json(Path(base.timeline_json_path))
    ok, errors = validate_patch(timeline, patch)
    if not ok:
        raise ValueError("patch 校验失败：" + "；".join(errors))

    patched = apply_patch(timeline, patch)
    version_id = f"ver_{uuid.uuid4().hex[:12]}"
    version_dir = OUTPUTS_DIR / project_id / version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    save_timeline(version_dir / "unified_timeline.json", patched)
    write_json(version_dir / "applied_patch.json", patch)
    return version_id, version_dir


def build_patch_from_message(message: str, timeline: dict, db: Session | None = None) -> dict:
    """由 LLM 把自然语言转成 patch（仅由 OpenClaw 通过 apply_patch 工具调用，禁止 API 直调）。"""
    empty = {"patch_id": "patch_auto", "description": message, "operations": []}
    if db is None or not llm_available(db):
        empty["error"] = "未配置 LLM，无法生成 patch"
        return empty

    subtitle_ids = [i["id"] for i in timeline.get("items", []) if i.get("type") == "subtitle"][:20]
    asset_ids = [a["asset_id"] for a in timeline.get("assets", [])]
    scene_ids = [{"scene_id": s.get("scene_id"), "start": s.get("timeline_start")} for s in timeline.get("scenes", [])][:20]
    system = (
        "你是视频剪辑助手。把用户的自然语言修改意图转成 JSON patch，仅输出 JSON："
        "{patch_id,description,operations}。\n"
        f"{PATCH_OPS_PROMPT}\n"
        "target_id 必须来自给定 id；无法理解则 operations 为空数组。"
    )
    user = (
        f"用户消息：{message}\n"
        f"可用字幕 id：{subtitle_ids}\n可用素材 id：{asset_ids}\n可用场景：{scene_ids}"
    )
    llm_result = run_text_json_with_meta(db, system, user, empty)
    plan = llm_result.data
    plan.setdefault("patch_id", "patch_auto")
    plan.setdefault("description", message)
    plan.setdefault("operations", [])
    if not llm_result.ok:
        plan["llm_status"] = llm_result.source
        plan["llm_error"] = llm_result.error
        if not plan.get("operations"):
            plan["error"] = plan.get("error") or (
                f"大模型未能生成 patch：{llm_result.error or '未配置 API Key'}"
            )
    return plan
