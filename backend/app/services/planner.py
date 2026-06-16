"""Agent 剪辑规划模块（需求 §6.4）。

输出结构化 edit_plan.json：口播智能剪辑、B-roll 匹配、字幕样式、hook、
lower-third、视觉效果、发布文案。支持两种策略：
- complete：尽量完整保留口播；
- fast：节奏尽量快，优先 highlight 句与核心观点。
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..utils import write_json
from .agent_orchestrator import run_text_json_with_meta
from .templates import feature_on, resolve_template

FILLER_WORDS = ("嗯", "啊", "呃", "那个", "就是说", "然后呢", "um", "uh")

# 数字 / 百分比 / 价格，用于 stat / 对比动画
_STAT_RE = re.compile(r"(?:[¥$￥]\s*)?\d[\d,\.]*\s*(?:%|％|倍|万|亿|元|块|分钟|秒|天|小时|x|X)?")
_SPLIT_RE = re.compile(r"[，。！？、,.!?；;\s]+")


def _is_filler(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t) <= 3 and any(f in t for f in ("嗯", "啊", "呃")):
        return True
    return False


def _talk_asset_id(manifest: dict) -> str | None:
    return next(
        (a["asset_id"] for a in manifest.get("assets", []) if a.get("user_label") == "口播视频"),
        None,
    )


def _rebased_words(seg: dict, timeline_start: float) -> list[dict]:
    """把 ASR 词级时间戳重定位到时间线坐标（用于 karaoke 高亮）。"""
    words = []
    seg_start = seg.get("start", 0.0)
    for w in seg.get("words", []) or []:
        ws = timeline_start + (w.get("start", seg_start) - seg_start)
        we = timeline_start + (w.get("end", seg_start) - seg_start)
        word = (w.get("word") or "").strip()
        if word:
            words.append({"word": word, "start": round(ws, 3), "end": round(we, 3)})
    return words


def _pick_broll(manifest: dict) -> list[dict]:
    # 视觉素材均可作为 B-roll/插入镜头：图片(含截图/插图)与非口播视频
    items = [
        a
        for a in manifest.get("assets", [])
        if (a.get("type") in {"image", "video"} and a.get("user_label") != "口播视频")
        or "broll" in (a.get("recommended_usage") or [])
    ]
    # 匹配优先级（§6.4.4）：must_use > priority > 顺序
    items.sort(key=lambda x: (not x.get("must_use"), -int(x.get("priority", 0) or 0)))
    return items


def _build_scenes(manifest: dict, target_duration: int, strategy: str) -> list[dict]:
    asr = manifest.get("asr") or {}
    segments = asr.get("segments") or []
    talk_id = _talk_asset_id(manifest)

    # fast 策略：优先按句长（信息密度近似）排序选取，再按时间还原
    ordered = list(enumerate(segments))
    if strategy == "fast":
        ordered = sorted(ordered, key=lambda kv: -len(kv[1].get("text", "")))

    kept_idx: list[int] = []
    total = 0.0
    budget = target_duration if strategy == "fast" else target_duration * 1.2
    for idx, seg in ordered:
        text = (seg.get("text") or "").strip()
        if _is_filler(text):
            continue
        dur = max(0.4, seg.get("end", 0) - seg.get("start", 0))
        if total + dur > budget:
            if strategy == "fast":
                continue
            break
        kept_idx.append(idx)
        total += dur
    kept_idx.sort()

    scenes = []
    t = 0.0
    for n, idx in enumerate(kept_idx):
        seg = segments[idx]
        dur = max(0.4, seg.get("end", 0) - seg.get("start", 0))
        scene = {
            "scene_id": f"scene_{n + 1:03d}",
            "purpose": "hook" if n == 0 else ("cta" if n == len(kept_idx) - 1 else "body"),
            "timeline_start": round(t, 3),
            "timeline_end": round(t + dur, 3),
            "speech_source": {
                "asset_id": talk_id,
                "source_start": seg.get("start", 0),
                "source_end": seg.get("end", dur),
            },
            "caption": (seg.get("text") or "").strip(),
            "words": _rebased_words(seg, t),
            "visual_effects": ["hook_title", "word_highlight"] if n == 0 else ["word_highlight"],
            "broll": [],
        }
        scenes.append(scene)
        t += dur

    if not scenes:
        # 无 ASR（如无口播或转录失败）时，用主视频整体兜底，时长不超过素材本身
        talk_dur = next(
            (a.get("duration") for a in manifest.get("assets", []) if a.get("asset_id") == talk_id and a.get("duration")),
            None,
        )
        end = min(target_duration, talk_dur) if talk_dur else min(target_duration, 30)
        end = round(float(end), 3)
        scenes.append(
            {
                "scene_id": "scene_001",
                "purpose": "hook",
                "timeline_start": 0,
                "timeline_end": end,
                "speech_source": {"asset_id": talk_id, "source_start": 0, "source_end": end},
                "caption": "",
                "words": [],
                "visual_effects": ["hook_title"],
                "broll": [],
            }
        )
    return scenes


def _match_broll(scenes: list[dict], manifest: dict) -> list[dict]:
    broll_assets = _pick_broll(manifest)
    broll_plan: list[dict] = []
    bi = 0
    for scene in scenes:
        if scene["purpose"] == "hook":
            continue
        if bi >= len(broll_assets):
            break
        b = broll_assets[bi]
        bi += 1
        scene["broll"] = [{"asset_id": b["asset_id"], "mode": "cutaway"}]
        broll_plan.append(
            {
                "time": scene["timeline_start"],
                "text": b.get("auto_summary") or b.get("user_note") or "B-roll",
                "source": Path(b["file_path"]).name if b.get("file_path") else b["asset_id"],
                "asset_id": b["asset_id"],
            }
        )
    return broll_plan


def _extract_keyword(caption: str, words: list[dict]) -> str:
    """从字幕中提取一个用于「关键词弹出」的短语。"""
    # 英文：取最长单词；中文：取首个 2-4 字片段
    if words:
        eng = [w["word"] for w in words if re.search(r"[A-Za-z]", w.get("word", ""))]
        if eng:
            return max(eng, key=len)[:16]
    parts = [p for p in _SPLIT_RE.split(caption) if p]
    if not parts:
        return caption[:4]
    longest = max(parts, key=len)
    return longest[:6]


def _find_stat(caption: str) -> tuple[str, str] | None:
    m = _STAT_RE.search(caption or "")
    if not m:
        return None
    value = m.group(0).strip()
    if not re.search(r"\d", value):
        return None
    label = (caption[: m.start()] + caption[m.end():]).strip()
    label = (_SPLIT_RE.split(label)[0] if label else "")[:10]
    return value, label


def _build_graphics(scenes: list[dict], manifest: dict, template: dict, duration: float) -> list[dict]:
    """根据模板开关，从场景与素材生成 motion-graphics 元素（需求 §6.5）。"""
    graphics: list[dict] = []
    assets_by_id = {a["asset_id"]: a for a in manifest.get("assets", [])}
    body_scenes = [s for s in scenes if s.get("purpose") == "body"] or scenes[1:]

    chapter_idx = 0
    chapter_every = max(1, len(body_scenes) // 3) if feature_on(template, "chapter_card") else 0
    keyword_every = 3

    for i, scene in enumerate(scenes):
        ss = scene["timeline_start"]
        se = scene["timeline_end"]
        caption = (scene.get("caption") or "").strip()
        words = scene.get("words") or []
        if se - ss < 1.0:
            continue

        # 关键词弹出
        if feature_on(template, "keyword_pop") and caption and i % keyword_every == 1:
            kw = _extract_keyword(caption, words)
            if kw and len(kw) >= 2:
                graphics.append({
                    "kind": "keyword_pop", "text": kw,
                    "timeline_start": round(ss + 0.2, 3),
                    "timeline_end": round(min(se, ss + 1.6), 3),
                })

        # 章节标题卡（按节均匀分布在 body 场景）
        if chapter_every and scene.get("purpose") == "body":
            pos = body_scenes.index(scene) if scene in body_scenes else -1
            if pos >= 0 and pos % chapter_every == 0 and chapter_idx < 4:
                chapter_idx += 1
                title = (_SPLIT_RE.split(caption)[0] if caption else f"第 {chapter_idx} 节")[:14]
                graphics.append({
                    "kind": "chapter_card", "index": chapter_idx, "title": title or f"第 {chapter_idx} 节",
                    "timeline_start": round(ss, 3),
                    "timeline_end": round(min(se, ss + 2.0), 3),
                })

        # 数字 / 价格 → stat 动画
        if feature_on(template, "stat_block") and caption:
            stat = _find_stat(caption)
            if stat:
                graphics.append({
                    "kind": "stat_block", "value": stat[0], "label": stat[1],
                    "timeline_start": round(ss + 0.3, 3),
                    "timeline_end": round(min(se, ss + 2.2), 3),
                })

        # 图文解释卡 / 标注：依据该场景的 B-roll 素材
        for br in scene.get("broll", []):
            ba = assets_by_id.get(br.get("asset_id"))
            if not ba:
                continue
            ocr = (ba.get("ocr_text") or "").strip()
            usage = ba.get("recommended_usage") or []
            label = ba.get("user_label") or ""
            is_screen = ("product" in usage) or any(k in (label + (ba.get("user_note") or "")) for k in ("截图", "界面", "录屏", "screen", "ui"))
            if feature_on(template, "explainer_card") and (ocr or ba.get("auto_summary")):
                graphics.append({
                    "kind": "explainer_card",
                    "title": label or "说明",
                    "body": (ocr or ba.get("auto_summary") or "")[:48],
                    "asset_id": ba.get("asset_id"),
                    "timeline_start": round(ss + 0.4, 3),
                    "timeline_end": round(min(se, ss + 2.8), 3),
                })
            if feature_on(template, "annotation") and is_screen:
                graphics.append({
                    "kind": "annotation", "shape": "circle",
                    "asset_id": ba.get("asset_id"),
                    "timeline_start": round(ss + 0.5, 3),
                    "timeline_end": round(min(se, ss + 2.4), 3),
                })

    # 结尾 CTA
    if feature_on(template, "end_cta") and duration > 3:
        graphics.append({
            "kind": "cta", "text": template.get("cta_text", "关注我，看更多"),
            "timeline_start": round(max(0.0, duration - 3.5), 3),
            "timeline_end": round(duration, 3),
        })

    # 音效：仅当存在标注为音效的音频素材
    if feature_on(template, "sfx"):
        for a in manifest.get("assets", []):
            blob = f"{a.get('user_label','')} {a.get('user_note','')}".lower()
            if a.get("type") == "audio" and any(k in blob for k in ("音效", "sfx", "sound effect")):
                # 在每个章节/hook 开头点缀
                graphics.append({
                    "kind": "sfx", "asset_id": a["asset_id"],
                    "timeline_start": 0.0, "timeline_end": min(0.6, duration),
                })
                break

    return graphics


def plan_edit(
    db: Session,
    project_id: str,
    manifest: dict,
    target_duration: int,
    style: str,
    strategy: str = "complete",
    platform: str = "douyin",
    output_language: str = "zh",
    strategy_draft: dict | None = None,
    on_step=None,
) -> dict:
    def _step(label: str, progress: float) -> None:
        if on_step:
            on_step(label, progress)

    template = resolve_template(style)
    _step("整理场景分段", 91)
    scenes = _build_scenes(manifest, target_duration, strategy)
    _step("匹配 B-roll 计划", 93)
    broll_plan = _match_broll(scenes, manifest)
    real_duration = scenes[-1]["timeline_end"] if scenes else target_duration
    _step("规划动效元素", 94)
    graphics = _build_graphics(scenes, manifest, template, float(real_duration))
    hook = scenes[0]["caption"] if scenes and scenes[0]["caption"] else "三秒抓住注意力的高级口播开场"

    talk = next((a for a in manifest.get("assets", []) if a.get("user_label") == "口播视频"), None)
    has_bgm = any(
        a.get("user_label") == "音频" or "bgm" in (a.get("recommended_usage") or [])
        for a in manifest.get("assets", [])
    )

    fallback = {
        "video_concept": "高级 AI 口播短视频",
        "target_duration": int(round(real_duration)),
        "style": style,
        "strategy": strategy,
        "platform": platform,
        "output_language": output_language,
        "template": {"id": template["id"], "label": template["label"], "tokens": template["tokens"], "features": template["features"]},
        "hook": hook,
        "subtitle_style": "抖音风格 · 白色粗体 · 底部居中 · 关键词黄色高亮",
        "lower_third": {"title": (talk or {}).get("user_label", ""), "subtitle": "帧造 Agent"},
        "bgm_note": "科技感 BGM" if has_bgm else "无 BGM（未上传背景音乐）",
        "scenes": scenes,
        "broll_plan": broll_plan,
        "graphics": graphics,
        "cover_title": hook[:14],
        "publish": {
            "title": hook[:24],
            "description": "由帧造 Agent 自动重构生成的高级口播短视频。",
            "tags": ["AI剪辑", "口播视频", "帧造Agent", "短视频"],
        },
    }

    system = (
        "你是专业的短视频剪辑策划。基于素材清单和口播转录，输出严格合法的 JSON 剪辑方案，"
        "字段：video_concept,target_duration,style,strategy,platform,hook,subtitle_style,"
        "lower_third,bgm_note,scenes,broll_plan,cover_title,publish。"
        "必须保留 scenes 的时间结构与每个 scene 的 words 字段不变，只可优化文案类字段（hook、caption 文本润色、subtitle_style、cover_title、publish）。"
    )
    _lang_label = {"zh": "中文", "en": "英文", "bilingual": "中英双语"}.get(output_language, output_language)
    user = (
        f"目标时长约 {target_duration} 秒，策略={strategy}，风格={style}，平台={platform}。\n"
        f"输出语言要求：{_lang_label}（hook、caption、cover_title、publish 等文案请使用该语言）。\n"
        f"素材与转录 manifest（节选）：{_compact_manifest(manifest)}\n"
        f"当前规则方案：{fallback}"
    )
    # Agent-first：先由 Agent 产出策略草案，planner 仅负责结构化落盘与安全修正。
    if strategy_draft is not None:
        _step("结构化落盘策略草案", 96)
        plan = dict(fallback)
        for key in ("video_concept", "hook", "subtitle_style", "bgm_note", "cover_title"):
            if isinstance(strategy_draft.get(key), str) and strategy_draft.get(key):
                plan[key] = strategy_draft[key]
        pub = strategy_draft.get("publish")
        if isinstance(pub, dict):
            plan["publish"] = {
                "title": str(pub.get("title") or plan["publish"].get("title") or ""),
                "description": str(pub.get("description") or plan["publish"].get("description") or ""),
                "tags": pub.get("tags") if isinstance(pub.get("tags"), list) else plan["publish"].get("tags") or [],
            }
        tr = strategy_draft.get("transition")
        if isinstance(tr, dict):
            style = str(tr.get("style") or "crossfade").strip().lower()
            if style != "crossfade":
                style = "crossfade"
            try:
                opacity = float(tr.get("opacity", 0.22))
            except (TypeError, ValueError):
                opacity = 0.22
            try:
                duration = float(tr.get("duration", 0.18))
            except (TypeError, ValueError):
                duration = 0.18
            plan["transition"] = {
                "style": style,
                "opacity": max(0.0, min(0.8, opacity)),
                "duration": max(0.05, min(0.8, duration)),
            }
        plan["meta"] = {
            **(plan.get("meta") or {}),
            "llm_status": "agent_strategy_draft",
            "llm_error": None,
            "llm_note": "已使用 Agent 策略草案并结构化落盘。",
        }
    else:
        _step("大模型润色文案", 96)
        llm_result = run_text_json_with_meta(db, system, user, fallback)
        plan = llm_result.data
        plan_meta = {
            "llm_status": "ok" if llm_result.ok and llm_result.source == "llm" else llm_result.source,
            "llm_error": llm_result.error,
            "llm_note": None,
        }
        if not llm_result.ok:
            if llm_result.source == "unconfigured":
                plan_meta["llm_note"] = "未配置大模型 API Key，剪辑方案文案为规则生成，未经 LLM 润色。"
            else:
                plan_meta["llm_note"] = f"大模型润色失败，已使用规则方案。原因：{llm_result.error or '未知'}"
        plan["meta"] = {**(plan.get("meta") or {}), **plan_meta}

    # 保护关键结构：LLM 不得破坏 scenes 时间线与 words（Qwen 等模型偶发混入字符串项）
    raw_scenes = plan.get("scenes")
    if not isinstance(raw_scenes, list) or not all(isinstance(s, dict) for s in raw_scenes):
        plan["scenes"] = scenes
    else:
        for i, sc in enumerate(plan["scenes"]):
            if i >= len(scenes):
                break
            base = scenes[i]
            sc["words"] = base["words"]
            sc["timeline_start"] = base["timeline_start"]
            sc["timeline_end"] = base["timeline_end"]
            sc["speech_source"] = base["speech_source"]
            sc.setdefault("scene_id", base.get("scene_id"))
            sc.setdefault("purpose", base.get("purpose"))
            sc["visual_effects"] = base.get("visual_effects", [])
            sc["broll"] = base.get("broll", [])
        if len(plan["scenes"]) != len(scenes):
            plan["scenes"] = scenes
    for k, v in fallback.items():
        plan.setdefault(k, v)
    # 模板与 graphics 为结构化规范，强制采用规则结果，避免 LLM 漂移
    plan["template"] = fallback["template"]
    plan["graphics"] = graphics
    plan.setdefault("transition", {"style": "crossfade", "opacity": 0.22, "duration": 0.18})

    _step("保存剪辑方案", 99)
    out = OUTPUTS_DIR / project_id / "analysis" / "edit_plan.json"
    write_json(out, plan)
    return plan


def _compact_manifest(manifest: dict) -> dict:
    """压缩 manifest，避免把全部词级时间戳塞进 prompt。"""
    assets = [
        {
            "asset_id": a.get("asset_id"),
            "type": a.get("type"),
            "user_label": a.get("user_label"),
            "user_note": a.get("user_note"),
            "must_use": a.get("must_use"),
            "auto_summary": a.get("auto_summary"),
            "duration": a.get("duration"),
        }
        for a in manifest.get("assets", [])
    ]
    asr = manifest.get("asr") or {}
    return {
        "assets": assets,
        "transcript": (asr.get("text") or "")[:1200],
        "segment_count": len(asr.get("segments") or []),
    }
