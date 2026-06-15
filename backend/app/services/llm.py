from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from ..utils import get_model_settings, read_json


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


def vision_describe(db: Session, image_path: Path, user_note: str = "") -> str:
    client = _client(db)
    if not client:
        from .media import describe_image_basic

        base = describe_image_basic(image_path)
        return f"{base}。用户备注：{user_note}" if user_note else base
    cfg = get_model_settings(db)
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
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
