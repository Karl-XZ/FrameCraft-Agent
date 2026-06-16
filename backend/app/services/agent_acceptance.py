"""OpenClaw Agent 阶段验收：检测产物是否就绪、是否提前对话式退出。"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import OUTPUTS_DIR

# 模型提前结束工具循环、改为闲聊/反问时常出现的片段
_CONVERSATIONAL_PATTERNS = (
    r"请告诉我",
    r"你想要执行",
    r"请记住",
    r"让我们开始",
    r"如果不确定",
    r"随时询问",
    r"需要进一步的帮助",
    r"是什么任务",
    r"有什么可以帮",
    r"你好[！!]?我是",
    r"Who am I",
    r"bootstrap",
)


def is_conversational_bailout(reply: str) -> bool:
    text = (reply or "").strip()
    if not text:
        return True
    if len(text) < 12 and "完成" not in text and "已" not in text:
        return False
    lowered = text.lower()
    for pat in _CONVERSATIONAL_PATTERNS:
        if re.search(pat, text, re.I) or pat.lower() in lowered:
            return True
    # 长回复但没有任何路径/工具/产物关键词，且含问号
    if "？" in text or "?" in text:
        productive = ("framecraft-tool", "outputs/", "ver_", "hyperframes", "manifest", "edit_plan", "timeline")
        if not any(k in text for k in productive):
            return True
    return False


def check_agent_phase(project_id: str, task: str, *, patched_version_dir: str | None = None) -> tuple[bool, list[str]]:
    """检查 Agent 阶段产物是否满足验收。返回 (通过, 缺失项列表)。"""
    missing: list[str] = []
    analysis = OUTPUTS_DIR / project_id / "analysis"

    if task == "analyze":
        if not (analysis / "asset_manifest.json").is_file():
            missing.append("analysis/asset_manifest.json")
        if not (analysis / "edit_plan.json").is_file():
            missing.append("analysis/edit_plan.json")
        return (not missing, missing)

    if task in ("generate", "chat_regenerate", "lint_fix"):
        version_dir = _resolve_hf_version_dir(project_id, patched_version_dir)
        if version_dir is None:
            missing.append("含 unified_timeline.json 的 ver_* 版本目录")
            return (False, missing)
        if not (version_dir / "unified_timeline.json").is_file():
            missing.append(f"{version_dir.name}/unified_timeline.json")
        hf_index = version_dir / "hyperframes" / "index.html"
        if not hf_index.is_file():
            missing.append(f"{version_dir.name}/hyperframes/index.html")
        meta = version_dir / "hyperframes" / "meta.json"
        if not meta.is_file():
            missing.append(f"{version_dir.name}/hyperframes/meta.json")
        return (not missing, missing)

    return (True, [])


def _resolve_hf_version_dir(project_id: str, patched_version_dir: str | None) -> Path | None:
    if patched_version_dir:
        p = Path(patched_version_dir)
        return p if p.is_dir() else None
    out = OUTPUTS_DIR / project_id
    candidates = [d for d in out.glob("ver_*") if d.is_dir() and (d / "unified_timeline.json").is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def evaluate_agent_phase(
    project_id: str,
    task: str,
    *,
    agent_reply: str = "",
    patched_version_dir: str | None = None,
) -> tuple[bool, list[str]]:
    """文件验收 + 对话式提前退出检测。"""
    accepted, missing = check_agent_phase(
        project_id, task, patched_version_dir=patched_version_dir
    )
    if not accepted and is_conversational_bailout(agent_reply):
        tag = "对话式提前退出（须继续调用 framecraft-tool）"
        if tag not in missing:
            missing.append(tag)
    return accepted, missing


def build_continuation_message(
    task: str,
    missing: list[str],
    *,
    prior_reply: str = "",
    lint_output: str = "",
    version_dir: str = "",
) -> str:
    lines = [
        "【验收未通过 · 必须继续执行工具】",
        "禁止输出对话式反问；禁止结束本轮。",
        "必须使用 cmd /c framecraft-tool.cmd <子命令>，禁止用 OpenClaw read/edit 直接读 outputs 相对路径。",
        "产物根目录见 STATE.json 的 outputs_dir（不是 workspace 下的 outputs/）。",
    ]
    if missing:
        lines.append("缺失产物：" + "、".join(missing))
    if version_dir:
        lines.append(f"当前版本目录：{version_dir}")
    if lint_output:
        lines.append("HyperFrames lint 报告（请调整 unified_timeline 后重跑 build_hyperframes，禁止手改 index.html）：")
        lines.append(lint_output[:3000])
    if prior_reply and is_conversational_bailout(prior_reply):
        lines.append(f"你上一轮提前结束了工具循环，回复内容无效：{prior_reply[:400]}")
    if task == "analyze":
        lines.append("继续完成：read_state → analyze_assets → suggest_edit_plan → job_progress 100")
    elif task == "lint_fix":
        lines.append(
            "lint_fix：read_state → 读取 lint 报告 → 调整 edit_plan 或 unified_timeline → "
            "build_hyperframes --version-dir <dir> → job_progress 90"
        )
    elif task in ("generate", "chat_regenerate"):
        lines.append("继续完成：read_state → build_timeline → build_hyperframes → job_progress 90")
    return "\n".join(lines)
