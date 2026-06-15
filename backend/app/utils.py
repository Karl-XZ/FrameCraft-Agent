from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from .models import PlatformSetting


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row:
        return row.value
    env_key = key.upper()
    return os.getenv(env_key, default)


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(PlatformSetting(key=key, value=value))
    db.commit()


def get_model_settings(db: Session) -> dict:
    return {
        "provider": get_setting(db, "llm_provider", "openai"),
        "api_key": get_setting(db, "llm_api_key", os.getenv("OPENAI_API_KEY", "")),
        "text_model": get_setting(db, "llm_model", "gpt-4o-mini"),
        "vision_model": get_setting(db, "vlm_model", "gpt-4o-mini"),
        "asr_model": get_setting(db, "asr_model", "base"),
        "base_url": get_setting(db, "llm_base_url", os.getenv("OPENAI_BASE_URL", "")),
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
