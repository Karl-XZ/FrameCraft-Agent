from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from .config import TEST_LLM_DEFAULTS
from .models import PlatformSetting


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row and (row.value or "").strip():
        return row.value
    env_key = key.upper()
    env_val = os.getenv(env_key, "")
    if env_val.strip():
        return env_val
    return default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(PlatformSetting(key=key, value=value))
    db.commit()


def seed_test_llm_defaults(db: Session) -> None:
    """比赛 Demo：数据库缺项时写入 DashScope 默认配置（含内置 API Key）。"""
    mapping = {
        "provider": "llm_provider",
        "api_key": "llm_api_key",
        "text_model": "llm_model",
        "vision_model": "vlm_model",
        "asr_model": "asr_model",
        "base_url": "llm_base_url",
    }
    for field, db_key in mapping.items():
        if not get_setting(db, db_key, "").strip():
            set_setting(db, db_key, TEST_LLM_DEFAULTS[field])


def get_model_settings(db: Session) -> dict:
    d = TEST_LLM_DEFAULTS
    return {
        "provider": get_setting(db, "llm_provider", d["provider"]),
        "api_key": get_setting(db, "llm_api_key", os.getenv("OPENAI_API_KEY", d["api_key"])),
        "text_model": get_setting(db, "llm_model", d["text_model"]),
        "vision_model": get_setting(db, "vlm_model", d["vision_model"]),
        "asr_model": get_setting(db, "asr_model", d["asr_model"]),
        "base_url": get_setting(db, "llm_base_url", os.getenv("OPENAI_BASE_URL", d["base_url"])),
    }


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))
