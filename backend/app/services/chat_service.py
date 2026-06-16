"""Agent 对话：唯一入口 OpenClaw Agent，禁止独立 LLM 路由套壳。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import WORKSPACES_DIR
from ..models import Project
from ..utils import read_json
from .openclaw_runtime import openclaw_available, run_openclaw_task


@dataclass
class AgentChatResult:
    reply: str
    patch: dict | None
    status: str  # chat | proposed | not_understood | needs_config


def _read_chat_result(project_id: str) -> dict | None:
    path = WORKSPACES_DIR / project_id / "CHAT_RESULT.json"
    if path.exists():
        try:
            return read_json(path)
        except Exception:
            return None
    return None


def handle_agent_chat(
    message: str,
    timeline: dict,
    project: Project,
    db: Session,
) -> AgentChatResult:
    if not openclaw_available():
        return AgentChatResult(
            reply="OpenClaw 未安装。请在服务器执行: npm install -g openclaw@latest",
            patch=None,
            status="needs_config",
        )

    result = run_openclaw_task(
        db,
        project.id,
        "chat",
        user_message=message,
        extra={
            "timeline_summary": {
                "duration": timeline.get("project", {}).get("duration"),
                "subtitle_ids": [i["id"] for i in timeline.get("items", []) if i.get("type") == "subtitle"][:20],
                "asset_ids": [a["asset_id"] for a in timeline.get("assets", [])],
            }
        },
        timeout=120,
    )

    if not result.ok:
        if "API Key" in (result.error or ""):
            return AgentChatResult(
                reply=(
                    "对话修改需要先接入大模型。\n\n"
                    "请前往「平台设置 → 模型配置」填写 API Key 与 Base URL，保存后再试。"
                ),
                patch=None,
                status="needs_config",
            )
        return AgentChatResult(
            reply=f"OpenClaw Agent 未能完成对话：{result.error}",
            patch=None,
            status="not_understood",
        )

    chat_data = _read_chat_result(project.id)
    if chat_data:
        reply = (chat_data.get("reply") or result.reply or "").strip()
        status = (chat_data.get("status") or "chat").strip().lower()
        patch = chat_data.get("patch") if isinstance(chat_data.get("patch"), dict) else None
        if status == "proposed" and patch and patch.get("operations"):
            return AgentChatResult(reply=reply or "已生成修改方案", patch=patch, status="proposed")
        if status == "not_understood":
            return AgentChatResult(reply=reply or "未能理解修改意图", patch=None, status="not_understood")
        return AgentChatResult(reply=reply or result.reply, patch=None, status="chat")

    reply = (result.reply or "").strip()
    if not reply:
        return AgentChatResult(reply="OpenClaw Agent 未返回有效回复", patch=None, status="not_understood")
    return AgentChatResult(reply=reply, patch=None, status="chat")
