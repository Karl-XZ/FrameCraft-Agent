"""OpenClaw 运行时：帧造 Agent 唯一编排入口。

所有 analyze / generate / chat_regenerate / 对话改片 必须经此模块调用 OpenClaw。
禁止在 job_runner 或其他模块中直接编排 fixed pipeline。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from ..config import ROOT, UPLOADS_DIR, OUTPUTS_DIR, WORKSPACES_DIR
from ..utils import get_model_settings, read_json, write_json

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
AGENT_ID_PREFIX = "framecraft"
TEMPLATE_DIR = WORKSPACES_DIR / "_template"
_CONFIG_SYNC_KEY: str | None = None


def _openclaw_cmd() -> list[str]:
    """Resolve OpenClaw CLI on Windows (.cmd) and Unix."""
    override = os.getenv("OPENCLAW_BIN")
    if override:
        return [override]
    for name in ("openclaw.cmd", "openclaw.exe", "openclaw"):
        found = shutil.which(name)
        if found:
            return [found]
    mjs = Path(os.getenv("APPDATA", "")) / "npm" / "node_modules" / "openclaw" / "openclaw.mjs"
    if mjs.exists():
        node = shutil.which("node") or "node"
        return [node, str(mjs)]
    return [OPENCLAW_BIN]


@dataclass
class OpenClawResult:
    ok: bool
    reply: str
    raw: dict | None
    error: str | None = None


def openclaw_available() -> bool:
    try:
        proc = subprocess.run(
            _openclaw_cmd() + ["--version"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _openclaw_config_path() -> Path:
    return Path(os.getenv("OPENCLAW_CONFIG_PATH", Path.home() / ".openclaw" / "openclaw.json"))


def sync_openclaw_config(db: Session, *, force: bool = False) -> None:
    """将 FrameCraft 模型设置同步到 OpenClaw 配置。"""
    global _CONFIG_SYNC_KEY
    cfg = get_model_settings(db)
    api_key = cfg.get("api_key") or ""
    base_url = cfg.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    text_model = cfg.get("text_model") or "qwen-max"
    sync_key = f"{api_key}|{base_url}|{text_model}|{cfg.get('vision_model') or 'qwen-vl-max'}"
    if not force and _CONFIG_SYNC_KEY == sync_key:
        return
    _CONFIG_SYNC_KEY = sync_key

    patch = {
        "models": {
            "mode": "merge",
            "providers": {
                "dashscope": {
                    "baseUrl": base_url,
                    "apiKey": api_key,
                    "api": "openai-completions",
                    "models": [
                        {"id": text_model, "name": text_model, "contextWindow": 128000, "maxTokens": 8192},
                        {"id": cfg.get("vision_model") or "qwen-vl-max", "name": "qwen-vl-max", "contextWindow": 128000, "maxTokens": 8192},
                    ],
                }
            },
        },
        "agents": {
            "defaults": {
                "model": {"primary": f"dashscope/{text_model}"},
            }
        },
    }
    patch_path = ROOT / "config" / ".openclaw.runtime.patch.json"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")

    config_dir = _openclaw_config_path().parent
    config_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        _openclaw_cmd() + ["config", "patch", "--file", str(patch_path)],
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "OPENAI_API_KEY": api_key, "OPENAI_BASE_URL": base_url},
        shell=False,
    )


def _safe_agent_name(project_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", f"{AGENT_ID_PREFIX}-{project_id}")[:64]


def ensure_project_workspace(project_id: str, db: Session, job_id: str | None = None) -> Path:
    """准备 OpenClaw 项目工作区：AGENTS.md / TOOLS.md / STATE.json / tools 链接。"""
    ws = WORKSPACES_DIR / project_id
    ws.mkdir(parents=True, exist_ok=True)

    if TEMPLATE_DIR.exists():
        for name in ("AGENTS.md", "TOOLS.md", "SOUL.md", "framecraft-tool.cmd"):
            src = TEMPLATE_DIR / name
            if src.exists():
                shutil.copy2(src, ws / name)

    from ..models import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    assets = []
    uploads = UPLOADS_DIR / project_id
    if uploads.exists():
        for f in uploads.iterdir():
            if f.is_file():
                assets.append({"file": f.name, "path": str(f)})

    state = {
        "project_id": project_id,
        "project_name": project.name if project else project_id,
        "aspect_ratio": project.aspect_ratio if project else "9:16",
        "target_duration": project.target_duration if project else 60,
        "target_style": project.target_style if project else "modern_talking_head",
        "job_id": job_id,
        "uploads_dir": str(UPLOADS_DIR / project_id),
        "outputs_dir": str(OUTPUTS_DIR / project_id),
        "assets_on_disk": assets,
        "tools_root": str(ROOT / "backend" / "app" / "services" / "agent_tools"),
        "python": str(ROOT / "backend" / "venv" / "Scripts" / "python.exe"),
        "project_root": str(ROOT),
    }
    write_json(ws / "STATE.json", state)
    return ws


def ensure_openclaw_agent(project_id: str, workspace: Path, db: Session) -> str:
    """注册/更新 OpenClaw 隔离 Agent（每个项目一个 workspace）。"""
    sync_openclaw_config(db)
    agent_name = _safe_agent_name(project_id)
    cfg = get_model_settings(db)
    text_model = cfg.get("text_model") or "qwen-max"

    proc = subprocess.run(
        _openclaw_cmd() + ["agents", "list", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    exists = agent_name in (proc.stdout or "")
    if not exists:
        subprocess.run(
            _openclaw_cmd() + [
                "agents", "add", agent_name,
                "--non-interactive",
                "--workspace", str(workspace),
                "--model", f"dashscope/{text_model}",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    return agent_name


def _thinking_level(task: str, provider: str, text_model: str) -> str:
    """DashScope/Qwen 仅支持 thinking=off；其他任务也不需 high。"""
    if provider == "dashscope" or "qwen" in text_model.lower():
        return "off"
    if task == "chat":
        return "low"
    return "medium"


def _extract_reply(data: dict) -> str:
    """从 OpenClaw --json 输出提取助手可见文本。"""
    if not isinstance(data, dict):
        return ""
    meta = data.get("meta") or {}
    for key in ("finalAssistantVisibleText", "finalAssistantRawText"):
        text = (meta.get(key) or "").strip()
        if text:
            return text
    payloads = data.get("payloads") or []
    if payloads and isinstance(payloads[0], dict):
        text = (payloads[0].get("text") or "").strip()
        if text:
            return text
    for key in ("reply", "message", "text"):
        text = (data.get(key) or "").strip()
        if text:
            return text
    return ""


def _build_chat_message(user_message: str, extra: dict | None = None) -> str:
    """对话任务：只传用户消息 + 极简上下文，制片规则见 AGENTS.md。"""
    msg = (user_message or "").strip()
    if not msg:
        return msg
    if extra and extra.get("timeline_summary"):
        ts = extra["timeline_summary"]
        if ts.get("has_version"):
            dur = ts.get("duration")
            n_sub = len(ts.get("subtitle_ids") or [])
            header = f"[当前成片] 时长 {dur}s，{n_sub} 条字幕。"
            return f"{header}\n\n用户：{msg}"
    return msg


def _build_goal(task: str, project_id: str, extra: dict | None = None, user_message: str | None = None) -> str:
    if task == "chat":
        return _build_chat_message(user_message or "", extra)

    base = (
        f"你是帧造 Agent 制片系统。项目 ID：{project_id}。\n"
        f"必须先阅读 workspace 内 AGENTS.md、TOOLS.md、STATE.json。\n"
        f"你只能调用 TOOLS.md 中列出的 framecraft-tool.cmd 命令完成任务，禁止臆测或跳过工具。\n"
        f"每完成一个阶段请调用 framecraft-tool.cmd job_progress 更新进度。\n"
        f"任务类型：{task}\n\n"
        f"【硬性要求】本轮必须执行工具链并产出磁盘文件，禁止只回复文字就结束。\n"
        f"在 Windows PowerShell 下请用：cmd /c framecraft-tool.cmd <子命令>\n"
    )
    if task == "analyze":
        base += (
            "\nanalyze 必须依次 exec：\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. cmd /c framecraft-tool.cmd analyze_assets\n"
            "3. cmd /c framecraft-tool.cmd suggest_edit_plan\n"
            "4. cmd /c framecraft-tool.cmd job_progress --progress 100 --step \"Agent 分析完成\"\n"
            "完成后确认 outputs 下已有 asset_manifest.json 与 edit_plan.json。\n"
        )
    elif task == "generate":
        base += (
            "\n【前置】analyze 已完成，已有 asset_manifest.json 与 edit_plan.json。禁止再 analyze。\n"
            "generate 必须自行规划并 exec（至少包含）：\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. cmd /c framecraft-tool.cmd list_workflows\n"
            "3. cmd /c framecraft-tool.cmd build_timeline\n"
            "4. cmd /c framecraft-tool.cmd workflow_build --version-dir <dir> --workflow-id vertical_pip\n"
            "   （竖屏 nov26 口播优先 vertical_pip，由你根据 list_workflows 决策）\n"
            "5. cmd /c framecraft-tool.cmd render_preview --version-dir <dir> --hyperframes-dir <hf>\n"
            "6. cmd /c framecraft-tool.cmd finalize_version --version-dir <dir> --hyperframes-dir <hf>\n"
            "7. cmd /c framecraft-tool.cmd job_progress --progress 100 --step \"完成\"\n"
            "未调用 finalize_version 并产出 preview.mp4 不得结束。\n"
        )
    elif task == "chat_regenerate":
        base += (
            "\nchat_regenerate：用户已确认 patch，必须基于 meta 中的 patch 重新渲染。\n"
            "1. read_state / read_timeline\n"
            "2. 对新 version_dir 执行 workflow_build → render_preview → finalize_version\n"
            "3. job_progress --progress 100\n"
        )
    if extra:
        base += "\n附加参数：\n" + json.dumps(extra, ensure_ascii=False, indent=2)
    if user_message:
        base += f"\n\n用户消息：{user_message}"
    return base


def run_openclaw_task(
    db: Session,
    project_id: str,
    task: str,
    *,
    job_id: str | None = None,
    user_message: str | None = None,
    extra: dict | None = None,
    on_log: Callable[[str], None] | None = None,
    timeout: int = 1800,
) -> OpenClawResult:
    """执行一次 OpenClaw Agent 制片/对话任务。"""
    if not openclaw_available():
        return OpenClawResult(False, "", None, "OpenClaw 未安装。请运行: npm install -g openclaw@latest")

    cfg = get_model_settings(db)
    if not cfg.get("api_key"):
        return OpenClawResult(False, "", None, "未配置大模型 API Key，无法启动 OpenClaw Agent")

    workspace = ensure_project_workspace(project_id, db, job_id)
    agent_name = ensure_openclaw_agent(project_id, workspace, db)

    goal = _build_goal(task, project_id, extra, user_message)
    thinking = _thinking_level(task, cfg.get("provider") or "dashscope", cfg.get("text_model") or "qwen-max")

    if task == "chat":
        if not (user_message or "").strip():
            return OpenClawResult(False, "", None, "缺少用户消息")
        timeout = max(timeout, 180)
    elif task == "analyze":
        timeout = max(timeout, 2400)
    elif task in ("generate", "chat_regenerate"):
        timeout = max(timeout, 3600)

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = cfg["api_key"]
    env["OPENAI_BASE_URL"] = cfg.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    env["FRAMECRAFT_PROJECT_ROOT"] = str(ROOT)
    env["FRAMECRAFT_PROJECT_ID"] = project_id
    if job_id:
        env["FRAMECRAFT_JOB_ID"] = job_id

    cmd = _openclaw_cmd() + [
        "agent",
        "--local",
        "--agent", agent_name,
        "--message", goal,
        "--json",
        "--timeout", str(timeout),
        "--thinking", thinking,
    ]
    if task == "chat":
        cmd.extend(["--session-key", f"agent:{agent_name}:studio-chat"])
    elif task in ("analyze", "generate", "chat_regenerate"):
        cmd.extend(["--session-key", f"agent:{agent_name}:production"])
    if on_log:
        on_log(f"[OpenClaw] 启动 Agent `{agent_name}` task={task}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
            encoding="utf-8",
            errors="replace",
            cwd=str(workspace),
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return OpenClawResult(
            False,
            "",
            None,
            f"OpenClaw Agent 超时（>{timeout}s）。请检查模型配置或缩小任务范围。",
        )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if on_log:
        for line in (stdout + stderr).splitlines()[-40:]:
            if line.strip():
                on_log(line.strip())

    if proc.returncode != 0:
        return OpenClawResult(False, "", None, stderr.strip() or stdout.strip() or f"OpenClaw exit {proc.returncode}")

    data = _parse_openclaw_json(stdout)
    if data is None:
        return OpenClawResult(True, stdout.strip()[:4000], {"raw_stdout": stdout})

    reply = _extract_reply(data)
    if not reply:
        reply = json.dumps(data, ensure_ascii=False)[:2000]
    return OpenClawResult(True, str(reply), data)


def _parse_openclaw_json(stdout: str) -> dict | None:
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    # OpenClaw 偶发在 stdout 前部混入日志行，取首个完整 JSON 对象
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None
