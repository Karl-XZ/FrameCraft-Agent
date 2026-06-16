"""高级口播模板 profile 注册表（需求 §17）。

口播 HyperFrames **成片工作流**（居左/全屏横版/竖屏 pip）见：
- workflows/talking-head/
- backend/app/services/talking_head_workflow_service.py

本模块的 TEMPLATES 仍用于 edit_plan 图形元素与 legacy exporter 配色。
"""
from __future__ import annotations

# 通用设计 token 基线（AIS 数值参考，非品牌资产）
_BASE_TOKENS = {
    "bg": "#07121C",
    "bg_grad": "linear-gradient(180deg,#07121C 0%,#0D2031 100%)",
    "primary": "#38BDF8",
    "accent": "#FACC15",
    "muted": "#96A2B6",
    "text": "#FFFFFF",
    "kicker": "FRAMECRAFT",
}

# 各模板：开关 + token 覆盖
TEMPLATES: dict[str, dict] = {
    "modern_talking_head": {
        "id": "modern_talking_head",
        "label": "Modern Talking Head 高级口播",
        "scenarios": "通用口播、观点表达、个人 IP",
        "tokens": {**_BASE_TOKENS, "kicker": "FRAMECRAFT · 高级口播", "stamp": "AI 重构"},
        "features": {
            "hook": True, "karaoke": True, "lower_third": True, "progress_bar": True,
            "ken_burns": True, "keyword_pop": True, "chapter_card": True,
            "explainer_card": False, "stat_block": False, "annotation": False,
            "sfx": True, "end_cta": True,
        },
        "cta_text": "关注我，看更多高级口播拆解",
    },
    "product_demo": {
        "id": "product_demo",
        "label": "Product Demo 产品介绍",
        "scenarios": "产品功能演示、官网转视频、SaaS 介绍",
        "tokens": {**_BASE_TOKENS, "primary": "#22D3EE", "accent": "#A3E635",
                   "kicker": "PRODUCT · 功能演示", "stamp": "立即体验"},
        "features": {
            "hook": True, "karaoke": True, "lower_third": True, "progress_bar": True,
            "ken_burns": True, "keyword_pop": True, "chapter_card": False,
            "explainer_card": True, "stat_block": True, "annotation": True,
            "sfx": True, "end_cta": True,
        },
        "cta_text": "现在就去试试这个功能",
    },
    "educational_explainer": {
        "id": "educational_explainer",
        "label": "Educational Explainer 知识科普",
        "scenarios": "课程切片、知识讲解、教程",
        "tokens": {**_BASE_TOKENS, "primary": "#818CF8", "accent": "#FBBF24",
                   "kicker": "LESSON · 知识讲解", "stamp": "重点"},
        "features": {
            "hook": True, "karaoke": True, "lower_third": True, "progress_bar": True,
            "ken_burns": True, "keyword_pop": True, "chapter_card": True,
            "explainer_card": True, "stat_block": True, "annotation": False,
            "sfx": False, "end_cta": True,
        },
        "cta_text": "学会了就点赞收藏，方便复习",
    },
    "viral_short": {
        "id": "viral_short",
        "label": "Viral Short 爆款短视频",
        "scenarios": "强 Hook、快节奏、比赛路演压缩版",
        "tokens": {**_BASE_TOKENS, "primary": "#F472B6", "accent": "#FDE047",
                   "kicker": "VIRAL · 三秒抓人", "stamp": "继续看"},
        "features": {
            "hook": True, "karaoke": True, "lower_third": False, "progress_bar": True,
            "ken_burns": True, "keyword_pop": True, "chapter_card": False,
            "explainer_card": False, "stat_block": True, "annotation": False,
            "sfx": True, "end_cta": True,
        },
        "cta_text": "你怎么看？评论区告诉我",
    },
}

# target_style 别名归一
_ALIASES = {
    "modern_talking_head": "modern_talking_head",
    "talking_head": "modern_talking_head",
    "高级口播": "modern_talking_head",
    "product_demo": "product_demo",
    "产品介绍": "product_demo",
    "product": "product_demo",
    "educational_explainer": "educational_explainer",
    "education": "educational_explainer",
    "知识科普": "educational_explainer",
    "course": "educational_explainer",
    "课程讲解": "educational_explainer",
    "viral_short": "viral_short",
    "viral": "viral_short",
    "比赛路演": "viral_short",
    "探店种草": "viral_short",
    "vlog": "modern_talking_head",
    "student_kit_vertical": "viral_short",
}


def resolve_template(target_style: str | None) -> dict:
    """根据项目 target_style 解析模板 profile，未知风格回退 modern_talking_head。"""
    key = _ALIASES.get((target_style or "").strip(), None)
    if key is None:
        # 模糊匹配
        s = (target_style or "").lower()
        for alias, tid in _ALIASES.items():
            if alias in s:
                key = tid
                break
    return TEMPLATES.get(key or "modern_talking_head", TEMPLATES["modern_talking_head"])


def feature_on(template: dict, name: str) -> bool:
    return bool((template.get("features") or {}).get(name))
