from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fcntl

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "backend" / "storage"
UPLOADS = ROOT / "uploads"
OUTPUTS = ROOT / "outputs"
RUNTIME = ROOT / "backend" / "runtime"
DB_PATH = STORAGE / "db.json"
LOCK_PATH = STORAGE / "db.lock"

for directory in (STORAGE, UPLOADS, OUTPUTS, RUNTIME):
    directory.mkdir(parents=True, exist_ok=True)

_LOCK = threading.RLock()


@contextmanager
def _file_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def default_db() -> dict[str, Any]:
    return {
        "projects": {},
        "assets": {},
        "jobs": {},
        "versions": {},
        "chat": {},
        "settings": {
            "provider": "codex",
            "api_key": "",
            "text_model": "",
            "vision_model": "",
            "base_url": "",
            "asr_model": "agent-managed",
        },
    }


def load_db() -> dict[str, Any]:
    if not DB_PATH.is_file():
        data = default_db()
        DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        broken = DB_PATH.with_suffix(f".broken-{int(datetime.now().timestamp())}.json")
        shutil.copy2(DB_PATH, broken)
        data = default_db()
    base = default_db()
    for key, value in base.items():
        data.setdefault(key, value)
    return data


def save_db(data: dict[str, Any]) -> None:
    tmp = DB_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DB_PATH)


def mutate(fn):
    with _LOCK:
        with _file_lock():
            data = load_db()
            result = fn(data)
            save_db(data)
            return result


def snapshot() -> dict[str, Any]:
    with _LOCK:
        with _file_lock():
            return deepcopy(load_db())


def sanitize_visible_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    replacements = (
        ("Codex Agent", "Agent"),
        ("Codex agent", "Agent"),
        ("Codex supervisor agent", "Agent"),
        ("Codex supervisor", "Agent"),
        ("Codex CLI", "本机 Agent 运行时"),
        ("Codex", "Agent"),
        ("codex agent", "agent"),
        ("codex", "agent"),
    )
    out = value
    for src, dst in replacements:
        out = out.replace(src, dst)
    return out


def sanitize_visible_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_visible_text(value)
    if isinstance(value, list):
        return [sanitize_visible_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_visible_payload(item) for key, item in value.items()}
    return value


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(project)
    out.pop("agent_session_id", None)
    return out


def public_asset(asset: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(asset)
    out.pop("path", None)
    return out


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(job)
    out.setdefault("completed_steps", [])
    out.setdefault("logs", [])
    out.setdefault("warnings", [])
    out.setdefault("plan_substep", None)
    out.setdefault("plan_progress", out.get("progress", 0))
    out.pop("payload", None)
    return sanitize_visible_payload(out)


def public_chat_message(message: dict[str, Any]) -> dict[str, Any]:
    return sanitize_visible_payload(deepcopy(message))


def public_version(version: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(version)
    for key in ("version_dir", "preview_path", "draft_path", "draft_dir", "import_guide_path"):
        out.pop(key, None)
    return out


def public_settings(settings: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(settings)
    out["api_key"] = ""
    out["api_key_configured"] = bool(settings.get("api_key"))
    return out


def project_dir(project_id: str) -> Path:
    p = OUTPUTS / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def upload_dir(project_id: str) -> Path:
    p = UPLOADS / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p
