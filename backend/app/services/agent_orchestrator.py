"""Agent 编排层（对应需求文档 §12 OpenClaw 定位）。

外部 OpenClaw 运行时未在本机安装时，本模块以等价方式承担其职责：
1. 调用不同模型（文本 / 视觉 / ASR，经由 llm.py）；
2. 生成剪辑方案 edit_plan 与 timeline patch；
3. 在受控工具白名单与项目工作区内调度任务；
4. 允许平台级模型配置切换。

设计上保持「可替换」：若将来接入真正的 OpenClaw CLI，只需替换
`run_text_json` / `run_vision` 的实现即可，上层 planner / patch_service 不变。
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR, UPLOADS_DIR, VECTCUT_DIR
from .llm import llm_available, llm_json

# §12.4 Agent 工具白名单：编排层只允许访问以下根目录 / 工具
TOOL_WHITELIST = {
    "uploads_dir": UPLOADS_DIR,
    "outputs_dir": OUTPUTS_DIR,
    "vectcut_api": VECTCUT_DIR,
    "tools": {"ffmpeg", "ffprobe", "hyperframes", "asr", "vlm", "draft_exporter"},
}

# 禁止的高危 shell 片段（§21 安全要求）
_FORBIDDEN_SHELL = (
    "rm -rf", "del /f", "format ", "shutdown", "reg delete",
    "mkfs", ":(){", "rmdir /s", "diskpart",
)


def assert_in_workspace(path: Path, project_id: str) -> Path:
    """确保 Agent 访问的路径限制在该项目的 uploads / outputs 工作区内（防路径穿越）。"""
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
    """Agent（LLM 编排）是否就绪。未配置 API Key 时为 False，对话修改不可用。"""
    return llm_available(db)


def run_text_json(db: Session, system: str, user: str, fallback: dict) -> dict:
    """文本 LLM 调用（OpenClaw 文本能力的等价入口）。未配置 Key 时返回 fallback。"""
    return llm_json(db, system, user, fallback)
