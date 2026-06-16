from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from ..utils import get_model_settings, read_json


def llm_available(db: Session) -> bool:
    """是否已配置可用的大模型 API Key（决定能否启用 Agent 对话修改）。"""
    return bool(get_model_settings(db).get("api_key"))


def _client(db: Session) -> OpenAI | None:
    cfg = get_model_settings(db)
    if not cfg.get("api_key"):
        return None
    kwargs = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return OpenAI(**kwargs)


def llm_json(db: Session, system: str, user: str, fallback: dict) -> dict:
    client = _client(db)
    if not client:
        return fallback
    cfg = get_model_settings(db)
    try:
        resp = client.chat.completions.create(
            model=cfg["text_model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return fallback


def llm_chat(db: Session, system: str, user: str, fallback: str) -> str:
    """普通文本对话（非 JSON patch）。"""
    client = _client(db)
    if not client:
        return fallback
    cfg = get_model_settings(db)
    try:
        resp = client.chat.completions.create(
            model=cfg["text_model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            max_tokens=400,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or fallback
    except Exception:
        return fallback


def _encode_image(image_path: Path) -> tuple[str, str]:
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return data, mime


def vision_describe(db: Session, image_path: Path, user_note: str = "") -> str:
    client = _client(db)
    if not client:
        from .media import describe_image_basic

        base = describe_image_basic(image_path)
        return f"{base}。用户备注：{user_note}" if user_note else base
    cfg = get_model_settings(db)
    data, mime = _encode_image(image_path)
    try:
        resp = client.chat.completions.create(
            model=cfg["vision_model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"用中文简短描述这张素材画面、场景、文字和适合的视频用途。用户备注：{user_note}",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                    ],
                }
            ],
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        from .media import describe_image_basic

        return describe_image_basic(image_path)


def vision_describe_frames(db: Session, frame_paths: list[Path], user_note: str = "") -> str:
    """对视频抽取的多帧做综合理解（需求 §6.3.2）：场景、人物、物体、界面、文字。"""
    frames = [p for p in frame_paths if p and p.exists()][:6]
    if not frames:
        return ""
    client = _client(db)
    if not client:
        from .media import describe_image_basic

        base = describe_image_basic(frames[0])
        return f"视频素材，关键帧 {len(frame_paths)} 张；{base}。用户备注：{user_note}" if user_note else base
    cfg = get_model_settings(db)
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "这是同一段视频按时间顺序抽取的多张关键帧。请用中文综合描述：整体场景、"
                "人物、主要物体、是否包含界面/录屏、画面中的文字内容，并判断是否适合做 B-roll。"
                f"用户备注：{user_note}"
            ),
        }
    ]
    for fp in frames:
        data, mime = _encode_image(fp)
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
    try:
        resp = client.chat.completions.create(
            model=cfg["vision_model"],
            messages=[{"role": "user", "content": content}],
            max_tokens=400,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        from .media import describe_image_basic

        return describe_image_basic(frames[0])


def ocr_image(db: Session, image_path: Path) -> str:
    """提取图片中的文字（需求 §6.3.3 OCR）。优先 VLM，失败返回空串。"""
    client = _client(db)
    if not client:
        return ""
    cfg = get_model_settings(db)
    data, mime = _encode_image(image_path)
    try:
        resp = client.chat.completions.create(
            model=cfg["vision_model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请只输出这张图片中的所有可见文字，按阅读顺序原样转写；若没有文字，输出空。",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                    ],
                }
            ],
            max_tokens=300,
        )
        text = (resp.choices[0].message.content or "").strip()
        return "" if text in {"空", "无", "（空）", "(empty)"} else text
    except Exception:
        return ""


def classify_image_usage(file_name: str, user_label: str, ocr_text: str, summary: str) -> list[str]:
    """根据文件名/标签/OCR/描述判断图片用途（需求 §6.3.3）。"""
    blob = f"{file_name} {user_label} {ocr_text} {summary}".lower()
    usages: list[str] = []
    if "logo" in blob:
        usages.append("logo")
    if any(k in blob for k in ("封面", "cover", "标题", "title")):
        usages.append("cover")
    if any(k in blob for k in ("产品", "界面", "ui", "截图", "screenshot", "product")):
        usages.append("product")
    if any(k in blob for k in ("背景", "background", "bg")):
        usages.append("background")
    if ocr_text.strip():
        usages.append("explainer_card")
    if not usages:
        usages = ["illustration"]
    # 去重保序
    seen: set[str] = set()
    return [u for u in usages if not (u in seen or seen.add(u))]
