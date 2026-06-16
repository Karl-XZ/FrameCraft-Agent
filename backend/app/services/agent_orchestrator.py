"""Agent 编排层（对应需求文档 §12 OpenClaw 定位）。

文本/视觉工具由 framecraft-tool 在 OpenClaw 调度下调用；本模块提供受控 LLM 入口。
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR, UPLOADS_DIR, VECTCUT_DIR
from .llm import LlmCallResult, llm_available, llm_json, llm_json_with_meta

TOOL_WHITELIST = {
    "uploads_dir": UPLOADS_DIR,
    "outputs_dir": OUTPUTS_DIR,
    "vectcut_api": VECTCUT_DIR,
    "tools": {"ffmpeg", "ffprobe", "hyperframes", "asr", "vlm", "draft_exporter"},
}

_FORBIDDEN_SHELL = (
    "rm -rf", "del /f", "format ", "shutdown", "reg delete",
    "mkfs", ":(){", "rmdir /s", "diskpart",
)


def assert_in_workspace(path: Path, project_id: str) -> Path:
    resolved = path.resolve()
    allowed_roots = [
        (UPLOADS_DIR / project_id).resolve(),
        (OUTPUTS_DIR / project_id).resolve(),
    ]
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise PermissionError(f"路径越权访问被拒绝: {resolved}")


def is_command_allowed(cmd: list[str]) -> bool:
    joined = " ".join(cmd).lower()
    if any(bad in joined for bad in _FORBIDDEN_SHELL):
        return False
    return True


def agent_available(db: Session) -> bool:
    return llm_available(db)


def run_text_json_with_meta(db: Session, system: str, user: str, fallback: dict) -> LlmCallResult:
    return llm_json_with_meta(db, system, user, fallback)


def run_text_json(db: Session, system: str, user: str, fallback: dict) -> dict:
    return llm_json(db, system, user, fallback)
