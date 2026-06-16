from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from ..utils import get_model_settings


@dataclass
class LlmCallResult:
    data: dict
    ok: bool
    source: str  # llm | fallback_rules | unconfigured
    error: str | None = None


@dataclass
class VisionCallResult:
    text: str
    vision_status: str  # vlm | degraded_basic | unavailable
    error: str | None = None


@dataclass
class OcrCallResult:
    text: str
    ocr_status: str  # vlm | unavailable | failed
    error: str | None = None


def llm_available(db: Session) -> bool:
    return bool(get_model_settings(db).get("api_key"))


def _client(db: Session) -> OpenAI | None:
    cfg = get_model_settings(db)
    if not cfg.get("api_key"):
        return None
    kwargs = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return OpenAI(**kwargs)


def llm_json_with_meta(db: Session, system: str, user: str, fallback: dict) -> LlmCallResult:
    client = _client(db)
    if not client:
        return LlmCallResult(
            data=fallback,
            ok=False,
            source="unconfigured",
            error="未配置大模型 API Key，已使用规则方案",
        )
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
        return LlmCallResult(data=json.loads(content), ok=True, source="llm")
    except Exception as exc:
        return LlmCallResult(
            data=fallback,
            ok=False,
            source="fallback_rules",
            error=str(exc)[:500],
        )


def llm_json(db: Session, system: str, user: str, fallback: dict) -> dict:
    return llm_json_with_meta(db, system, user, fallback).data


def llm_chat(db: Session, system: str, user: str, fallback: str) -> str:
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


def vision_describe_with_meta(db: Session, image_path: Path, user_note: str = "") -> VisionCallResult:
    from .media import describe_image_basic

    client = _client(db)
    if not client:
        base = describe_image_basic(image_path)
        text = f"{base}。用户备注：{user_note}" if user_note else base
        return VisionCallResult(
            text=text,
            vision_status="unavailable",
            error="未配置视觉模型 API Key，仅为基础文件描述",
        )
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
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            base = describe_image_basic(image_path)
            return VisionCallResult(
                text=base,
                vision_status="degraded_basic",
                error="视觉模型返回空内容，已降级为基础描述",
            )
        return VisionCallResult(text=text, vision_status="vlm")
    except Exception as exc:
        base = describe_image_basic(image_path)
        return VisionCallResult(
            text=base,
            vision_status="degraded_basic",
            error=str(exc)[:500],
        )


def vision_describe(db: Session, image_path: Path, user_note: str = "") -> str:
    return vision_describe_with_meta(db, image_path, user_note).text


def vision_describe_frames_with_meta(
    db: Session, frame_paths: list[Path], user_note: str = ""
) -> VisionCallResult:
    from .media import describe_image_basic

    frames = [p for p in frame_paths if p and p.exists()][:6]
    if not frames:
        return VisionCallResult(text="", vision_status="unavailable", error="无可用关键帧")
    client = _client(db)
    if not client:
        base = describe_image_basic(frames[0])
        text = f"视频素材，关键帧 {len(frame_paths)} 张；{base}。用户备注：{user_note}" if user_note else base
        return VisionCallResult(
            text=text,
            vision_status="unavailable",
            error="未配置视觉模型 API Key，仅为基础文件描述",
        )
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
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            base = describe_image_basic(frames[0])
            return VisionCallResult(
                text=base,
                vision_status="degraded_basic",
                error="视觉模型返回空内容，已降级为基础描述",
            )
        return VisionCallResult(text=text, vision_status="vlm")
    except Exception as exc:
        base = describe_image_basic(frames[0])
        return VisionCallResult(
            text=base,
            vision_status="degraded_basic",
            error=str(exc)[:500],
        )


def vision_describe_frames(db: Session, frame_paths: list[Path], user_note: str = "") -> str:
    return vision_describe_frames_with_meta(db, frame_paths, user_note).text


def ocr_image_with_meta(db: Session, image_path: Path) -> OcrCallResult:
    client = _client(db)
    if not client:
        return OcrCallResult(text="", ocr_status="unavailable", error="未配置视觉模型，跳过 OCR")
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
        if text in {"空", "无", "（空）", "(empty)"}:
            text = ""
        return OcrCallResult(text=text, ocr_status="vlm")
    except Exception as exc:
        return OcrCallResult(text="", ocr_status="failed", error=str(exc)[:500])


def ocr_image(db: Session, image_path: Path) -> str:
    return ocr_image_with_meta(db, image_path).text


def classify_image_usage(file_name: str, user_label: str, ocr_text: str, summary: str) -> list[str]:
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
    seen: set[str] = set()
    return [u for u in usages if not (u in seen or seen.add(u))]
