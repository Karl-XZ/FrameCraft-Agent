"""Agent 对话：唯一入口 OpenClaw Agent，禁止独立 LLM 路由套壳。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import WORKSPACES_DIR
from ..models import Project
from ..utils import read_json
from .openclaw_runtime import openclaw_available, run_openclaw_task

# OpenClaw 偶发套话（未真正回应用户消息）
_BOILERPLATE_MARKERS = (
    "看起来您可能是在确认我的身份",
    "看起来您可能是在确认我的角色",
    "请告诉我您需要我完成的具体任务",
    "为了更好地帮助您，请回答以下几个问题",
    "负责处理视频分析和成片任务",
    "您的名字",
)

# 用户消息像改片指令时，Agent 应产出 patch 而非闲聊套话
_EDIT_INTENT_KEYWORDS = (
    "字幕", "渐显", "渐隐", "黄色", "大字", "颜色", "字体",
    "bgm", "背景音乐", "节奏", "加快", "放慢", "降低", "提高", "音量",
    "替换", "换成", "改成", "修改", "删除", "增加", "添加",
    "开头", "结尾", "第二段", "第三段", "冲击力", "动效", "动画",
    "封面", "标题", "hook", "b-roll", "broll", "口播",
)


@dataclass
class AgentChatResult:
    reply: str
    patch: dict | None
    status: str  # chat | proposed | not_understood | needs_config


def _chat_result_path(project_id: str) -> Path:
    return WORKSPACES_DIR / project_id / "CHAT_RESULT.json"


def _clear_chat_result(project_id: str) -> None:
    path = _chat_result_path(project_id)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def _read_chat_result(project_id: str) -> dict | None:
    path = _chat_result_path(project_id)
    if path.exists():
        try:
            return read_json(path)
        except Exception:
            return None
    return None


def _is_boilerplate_reply(reply: str) -> bool:
    text = (reply or "").strip()
    if not text:
        return True
    return any(m in text for m in _BOILERPLATE_MARKERS)


def _looks_like_edit_intent(message: str) -> bool:
    blob = (message or "").strip().lower()
    if not blob or len(blob) < 2:
        return False
    if blob in {"你好", "您好", "hi", "hello", "在吗", "你是谁", "你能做什么", "你能干嘛"}:
        return False
    return any(k in blob for k in _EDIT_INTENT_KEYWORDS)


def _is_greeting(message: str) -> bool:
    blob = re.sub(r"\s+", "", (message or "").strip().lower())
    return blob in {
        "你好", "您好", "hi", "hello", "hey", "在吗", "你是谁", "你能做什么",
        "你能干嘛", "介绍一下", "介绍你自己",
    }


def _invoke_openclaw_chat(
    db: Session,
    project: Project,
    user_message: str,
    extra: dict,
) -> tuple:
    """调用 OpenClaw 对话，返回 (OpenClawResult, chat_data|None)。"""
    _clear_chat_result(project.id)
    result = run_openclaw_task(
        db,
        project.id,
        "chat",
        user_message=user_message,
        extra=extra,
        timeout=180,
    )
    chat_data = _read_chat_result(project.id) if result.ok else None
    return result, chat_data


def _result_from_openclaw(
    result,
    chat_data: dict | None,
    *,
    user_message: str,
) -> AgentChatResult:
    if chat_data:
        reply = (chat_data.get("reply") or result.reply or "").strip()
        status = (chat_data.get("status") or "chat").strip().lower()
        patch = chat_data.get("patch") if isinstance(chat_data.get("patch"), dict) else None
        if status == "proposed" and patch and patch.get("operations"):
            return AgentChatResult(reply=reply or "已生成修改方案，请确认是否应用。", patch=patch, status="proposed")
        if status == "not_understood":
            return AgentChatResult(reply=reply or "未能理解修改意图，请换一种说法。", patch=None, status="not_understood")
        if _is_boilerplate_reply(reply):
            return AgentChatResult(
                reply="Agent 返回了通用套话而未回应你的具体问题，请重试或换一种描述。",
                patch=None,
                status="not_understood",
            )
        return AgentChatResult(reply=reply or result.reply, patch=None, status="chat")

    reply = (result.reply or "").strip()
    if not reply:
        return AgentChatResult(reply="OpenClaw Agent 未返回有效回复。", patch=None, status="not_understood")
    if _is_boilerplate_reply(reply):
        if _looks_like_edit_intent(user_message):
            return AgentChatResult(
                reply="改片请求未得到具体方案（Agent 返回了套话）。请确认已生成成片后再试，或重新描述修改内容。",
                patch=None,
                status="not_understood",
            )
        return AgentChatResult(
            reply="Agent 未按预期回应，请重试。",
            patch=None,
            status="not_understood",
        )
    return AgentChatResult(reply=reply, patch=None, status="chat")


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

    extra = {
        "timeline_summary": {
            "duration": timeline.get("project", {}).get("duration"),
            "subtitle_ids": [i["id"] for i in timeline.get("items", []) if i.get("type") == "subtitle"][:20],
            "asset_ids": [a["asset_id"] for a in timeline.get("assets", [])],
            "has_version": bool(timeline.get("items")),
        }
    }

    result, chat_data = _invoke_openclaw_chat(db, project, message, extra)

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

    raw_reply = (result.reply or "").strip()
    raw_boilerplate = _is_boilerplate_reply(raw_reply) and not chat_data

    if raw_boilerplate and _looks_like_edit_intent(message) and timeline.get("items"):
        retry_msg = (
            f"用户改片指令：{message}\n\n"
            "立即执行（禁止自我介绍）：\n"
            "1. cmd /c framecraft-tool.cmd read_timeline\n"
            f'2. cmd /c framecraft-tool.cmd apply_patch --message "{message.replace(chr(34), "")}"\n'
            "3. 将 patch 写入 write_chat_result，status 必须为 proposed。"
        )
        result, chat_data = _invoke_openclaw_chat(db, project, retry_msg, extra)
        if not result.ok:
            return AgentChatResult(
                reply=f"OpenClaw Agent 改片重试失败：{result.error}",
                patch=None,
                status="not_understood",
            )
    elif raw_boilerplate and _is_greeting(message):
        result, chat_data = _invoke_openclaw_chat(db, project, message, extra)
        if not result.ok:
            return AgentChatResult(
                reply=f"OpenClaw Agent 未能完成对话：{result.error}",
                patch=None,
                status="not_understood",
            )

    return _result_from_openclaw(result, chat_data, user_message=message)
