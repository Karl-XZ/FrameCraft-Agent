"""OpenClaw 运行时：HyperFrames 成片编排唯一入口。

analyze / generate / chat_regenerate 必须经此模块调用 OpenClaw Agent。
剪映草稿导出可在 job_runner 中于 Agent 完成后自动执行（非创意环节）。

Gateway 常驻策略
────────────────
应用启动时由 _GatewayManager 拉起 `openclaw gateway run`（端口 18789）。
进程死亡时自动重启，永不回收（无超时退出）。
任务调用优先走 Gateway（无 --local），Gateway 不可用时 fallback 到 --local。
"""
from __future__ import annotations

import atexit
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from ..config import ROOT, UPLOADS_DIR, OUTPUTS_DIR, WORKSPACES_DIR
from ..utils import get_model_settings, write_json

logger = logging.getLogger(__name__)

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
AGENT_ID_PREFIX = "framecraft"
TEMPLATE_DIR = WORKSPACES_DIR / "_template"
_CONFIG_SYNC_KEY: str | None = None

GATEWAY_PORT = int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789"))
GATEWAY_HOST = os.getenv("OPENCLAW_GATEWAY_HOST", "127.0.0.1")

# OpenClaw 默认脚手架会写入 BOOTSTRAP.md，触发「身份对话」而非制片工具链
_BOOTSTRAP_FILES = ("BOOTSTRAP.md", "HEARTBEAT.md")


def _resolve_python_executable() -> str:
    """优先使用当前后端进程的 Python，其次 venv，最后 sys.executable。"""
    venv_py = ROOT / "backend" / "venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _strip_openclaw_bootstrap(workspace: Path) -> None:
    """移除 OpenClaw 脚手架 bootstrap 文件，避免 Agent 进入身份对话而非执行任务。"""
    for name in _BOOTSTRAP_FILES:
        path = workspace / name
        if path.is_file():
            try:
                path.unlink()
                logger.info("[OpenClaw] 已移除 bootstrap 文件: %s", path)
            except OSError as exc:
                logger.warning("[OpenClaw] 无法删除 %s: %s", path, exc)
    identity = workspace / "IDENTITY.md"
    if TEMPLATE_DIR.exists():
        tpl = TEMPLATE_DIR / "IDENTITY.md"
        if tpl.is_file() and (not identity.is_file() or identity.stat().st_size < 80):
            shutil.copy2(tpl, identity)


# ---------------------------------------------------------------------------
# Gateway 常驻进程管理
# ---------------------------------------------------------------------------

class _GatewayManager:
    """管理 OpenClaw Gateway 常驻后台进程。
    
    - 应用启动时调用 start()，进程永不主动退出
    - 监控线程检测进程存活，退出后自动重启（无冷却限制）
    - stop() 仅在应用关闭时调用
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._log_path = Path(os.getenv("TEMP", "/tmp")) / "openclaw" / "gateway-framecraft.log"

    def _spawn(self) -> subprocess.Popen:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fd = open(self._log_path, "a", encoding="utf-8", errors="replace")
        cmd = _openclaw_cmd() + [
            "gateway", "run",
            "--port", str(GATEWAY_PORT),
            "--bind", "loopback",
            "--auth", "none",
            "--allow-unconfigured",
        ]
        logger.info("[Gateway] 启动进程: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=log_fd,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=os.environ.copy(),
            )
        finally:
            # 子进程已继承 fd 副本，父进程关闭自身引用，避免重启时句柄泄漏
            log_fd.close()
        logger.info("[Gateway] PID=%d，日志: %s", proc.pid, self._log_path)
        return proc

    def _wait_ready(self, timeout: float = 15.0) -> bool:
        """轮询 Gateway 是否就绪（HTTP health 端点）。"""
        import urllib.request, urllib.error
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = urllib.request.urlopen(
                    f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health",
                    timeout=2,
                )
                if resp.status == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def start(self) -> None:
        """启动 Gateway 并阻塞直到就绪，同时启动监控线程。"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._proc = self._spawn()

        ready = self._wait_ready(20.0)
        if ready:
            logger.info("[Gateway] 已就绪 ws://%s:%d", GATEWAY_HOST, GATEWAY_PORT)
        else:
            logger.warning("[Gateway] 启动超时，将继续尝试（任务可 fallback --local）")

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="openclaw-gateway-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        """永不退出的监控循环：进程死了立即重启。"""
        while self._running:
            with self._lock:
                proc = self._proc
            if proc is not None:
                ret = proc.poll()
                if ret is not None:
                    logger.warning("[Gateway] 进程(PID=%d)已退出(code=%d)，立即重启", proc.pid, ret)
                    with self._lock:
                        try:
                            self._proc = self._spawn()
                        except Exception as exc:
                            logger.error("[Gateway] 重启失败: %s", exc)
            time.sleep(3)

    def stop(self) -> None:
        """应用关闭时调用，终止 Gateway 进程。"""
        self._running = False
        with self._lock:
            if self._proc and self._proc.poll() is None:
                logger.info("[Gateway] 关闭进程 PID=%d", self._proc.pid)
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._proc = None

    def is_ready(self) -> bool:
        """快速探测 Gateway 是否可用。"""
        import urllib.request, urllib.error
        try:
            resp = urllib.request.urlopen(
                f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health",
                timeout=2,
            )
            return resp.status == 200
        except Exception:
            return False


# 全局单例
gateway_manager = _GatewayManager()
_EXIT_HOOKS_INSTALLED = False


def install_gateway_exit_hooks() -> None:
    """安装进程退出清理钩子，确保项目关闭时回收 Gateway。"""
    global _EXIT_HOOKS_INSTALLED
    if _EXIT_HOOKS_INSTALLED:
        return
    _EXIT_HOOKS_INSTALLED = True

    # 使用 atexit 即可覆盖正常退出路径；避免覆盖 Uvicorn 默认信号处理流程。
    atexit.register(gateway_manager.stop)


def _openclaw_cmd() -> list[str]:
    """Resolve OpenClaw CLI on Windows (.cmd) and Unix."""
    override = os.getenv("OPENCLAW_BIN")
    if override:
        return [override]
    mjs = Path(os.getenv("APPDATA", "")) / "npm" / "node_modules" / "openclaw" / "openclaw.mjs"
    if mjs.exists():
        # Windows 上可能被 Python 的 node.exe shim 污染，优先用可执行的真实 Node 跑 mjs。
        node_candidates: list[str] = []
        nvm_node = os.getenv("NVM_SYMLINK")
        if nvm_node:
            node_candidates.append(str(Path(nvm_node) / "node.exe"))
        node_candidates.extend(
            [
                str(Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "node-v22.20.0-win-x64" / "node.exe"),
                str(Path("C:/nvm4w/nodejs/node.exe")),
                shutil.which("node") or "",
            ]
        )
        for node in node_candidates:
            if not node:
                continue
            node_path = Path(node)
            if not node_path.exists():
                continue
            if "Python" in str(node_path):
                continue
            try:
                probe = subprocess.run(
                    [str(node_path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False,
                )
                if probe.returncode == 0:
                    return [str(node_path), str(mjs)]
            except Exception:
                continue
    for name in ("openclaw.cmd", "openclaw.exe", "openclaw"):
        found = shutil.which(name)
        if found:
            return [found]
    if mjs.exists():
        return ["node", str(mjs)]
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
        timeout=180,
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
        for name in ("AGENTS.md", "TOOLS.md", "SOUL.md", "IDENTITY.md", "framecraft-tool.cmd", "framecraft-env.cmd"):
            src = TEMPLATE_DIR / name
            if src.exists():
                shutil.copy2(src, ws / name)

    _strip_openclaw_bootstrap(ws)

    from ..models import Asset, Project

    project = db.query(Project).filter(Project.id == project_id).first()
    db_assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    assets = []
    uploads = UPLOADS_DIR / project_id
    if uploads.exists():
        for f in uploads.iterdir():
            if f.is_file():
                assets.append({"file": f.name, "path": str(f)})
    assets_with_user_notes = []
    for a in db_assets:
        assets_with_user_notes.append(
            {
                "asset_id": a.id,
                "file_name": a.file_name,
                "file_type": a.file_type,
                "user_label": a.user_label or "",
                "user_note": a.user_note or "",
                "must_use": bool(a.must_use),
                "priority": int(a.priority or 0),
                "analysis_status": a.analysis_status or "pending",
            }
        )

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
        "assets_with_user_notes": assets_with_user_notes,
        "tools_root": str(ROOT / "backend" / "app" / "services" / "agent_tools"),
        "python": _resolve_python_executable(),
        "project_root": str(ROOT),
    }
    write_json(ws / "STATE.json", state)
    env_cmd = ws / "framecraft-env.cmd"
    job_val = job_id or ""
    env_cmd.write_text(
        f"@echo off\r\n"
        f'set "FRAMECRAFT_PROJECT_ID={project_id}"\r\n'
        f'set "FRAMECRAFT_JOB_ID={job_val}"\r\n',
        encoding="utf-8",
    )
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
        timeout=180,
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
            timeout=180,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    _strip_openclaw_bootstrap(workspace)
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
        f"【立即执行，禁止反问】后端已指定任务类型={task}，禁止询问用户「要做什么」或进行 bootstrap/身份对话。\n"
        f"忽略 BOOTSTRAP.md（若存在）；直接阅读 AGENTS.md、TOOLS.md、STATE.json 并 exec 工具链。\n"
        f"你是帧造 Agent 制片系统。项目 ID：{project_id}。\n"
        f"必须读取并使用 STATE.json 中 assets_with_user_notes 的 user_label/user_note。\n"
        f"你只能调用 TOOLS.md 中列出的 framecraft-tool.cmd 命令完成任务，禁止臆测或跳过工具。\n"
        f"每完成一个阶段请调用 framecraft-tool.cmd job_progress 更新进度。\n"
        f"任务类型：{task}\n\n"
        f"【硬性要求】本轮必须执行工具链并产出磁盘文件，禁止只回复文字就结束。\n"
        f"在 Windows PowerShell 下请用：cmd /c framecraft-tool.cmd <子命令>\n"
        f"第一步必须是：cmd /c framecraft-tool.cmd read_state\n"
        f"【路径】产物在 STATE.json 的 outputs_dir（绝对路径）；禁止在 workspace 下用 outputs/ 相对路径；"
        f"禁止用 OpenClaw read/edit 直接读工程文件；version_dir 以 build_timeline 返回的 JSON 为准。\n"
    )
    if task == "analyze":
        base += (
            "\n目标：产出 asset_manifest.json 与 edit_plan.json。\n"
            "建议步骤（可根据 STATE.json 调整顺序，但每步须真实 exec）：\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. cmd /c framecraft-tool.cmd analyze_assets\n"
            "3. 先输出策略草案 strategy_draft.json（hook、subtitle_style、bgm_note、publish、transition 参数等）\n"
            "4. cmd /c framecraft-tool.cmd suggest_edit_plan --draft-file strategy_draft.json\n"
            "5. cmd /c framecraft-tool.cmd job_progress --progress 100 --step \"Agent 分析完成\"\n"
            "若 ASR/VLM/LLM 降级，须在回复中向用户说明 warnings，不得假装全部成功。\n"
        )
    elif task == "generate":
        base += (
            "\n【前置】analyze 已完成，已有 asset_manifest.json 与 edit_plan.json。禁止再 analyze。\n"
            "【你的职责】完成 timeline 设计与 HyperFrames 工程生成；render/finalize 由服务端自动执行。\n"
            "【禁止输出规范文本】不要输出「请记住/让我们开始吧/请告诉我任务」等对话；执行完工具链后用中文简述产物路径即可。\n"
            "制片步骤（顺序可微调，但须真实 exec）：\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. cmd /c framecraft-tool.cmd build_timeline\n"
            "3. cmd /c framecraft-tool.cmd build_hyperframes --version-dir <dir>\n"
            "4. cmd /c framecraft-tool.cmd job_progress --progress 90 --step \"HyperFrames 工程完成\"\n"
            "不要调用 render_preview / finalize_version / export_draft（服务端在 Agent 结束后自动执行）。\n"
        )
    elif task == "chat_regenerate":
        base += (
            "\nchat_regenerate：patch 已由服务端写入 patched_version_dir/unified_timeline.json。\n"
            "【你的职责】仅重建 HyperFrames 工程；渲染与注册版本由服务端自动执行。\n"
            "禁止再次 apply_patch；不要调用 render_preview / finalize_version / export_draft。\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. 使用附加参数 patched_version_dir 作为 --version-dir\n"
            "3. cmd /c framecraft-tool.cmd build_hyperframes --version-dir <patched_version_dir>\n"
            "4. cmd /c framecraft-tool.cmd job_progress --progress 90 --step \"HyperFrames 工程完成\"\n"
        )
    elif task == "lint_fix":
        base += (
            "\n【lint_fix】服务端 HyperFrames lint 未通过，必须修复后重跑 build_hyperframes。\n"
            "禁止手改 hyperframes/index.html；应调整 unified_timeline / edit_plan 后重建工程。\n"
            "1. cmd /c framecraft-tool.cmd read_state\n"
            "2. 阅读附加参数中的 lint_output 与 version_dir\n"
            "3. 必要时调整剪辑方案或 timeline（build_timeline 若需重建）\n"
            "4. cmd /c framecraft-tool.cmd build_hyperframes --version-dir <version_dir>\n"
            "5. cmd /c framecraft-tool.cmd job_progress --progress 90 --step \"HyperFrames lint 修复完成\"\n"
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
    continuation: str | None = None,
    retry_attempt: int = 0,
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
    if continuation:
        goal = continuation.strip() + "\n\n" + goal
    thinking = _thinking_level(task, cfg.get("provider") or "dashscope", cfg.get("text_model") or "qwen-max")

    if task == "chat":
        if not (user_message or "").strip():
            return OpenClawResult(False, "", None, "缺少用户消息")
        timeout = max(timeout, 180)
    elif task == "analyze":
        timeout = max(timeout, 2400)
    elif task in ("generate", "chat_regenerate", "lint_fix"):
        timeout = max(timeout, 3600)

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = cfg["api_key"]
    env["OPENAI_BASE_URL"] = cfg.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    env["FRAMECRAFT_PROJECT_ROOT"] = str(ROOT)
    env["FRAMECRAFT_PROJECT_ID"] = project_id
    if job_id:
        env["FRAMECRAFT_JOB_ID"] = job_id

    # 制片任务强制 --local：embedded 模式 bundle exec 工具；Gateway 在本环境常未就绪
    production_tasks = ("analyze", "generate", "chat_regenerate", "lint_fix")
    use_gateway = task not in production_tasks and gateway_manager.is_ready()
    local_flag = [] if use_gateway else ["--local"]
    if on_log:
        mode = "Gateway" if use_gateway else "Local(embedded)"
        on_log(f"[OpenClaw] 启动 Agent `{agent_name}` task={task} mode={mode}")

    cmd = _openclaw_cmd() + (
        ["agent"]
        + local_flag
        + [
            "--agent", agent_name,
            "--message", goal,
            "--json",
            "--timeout", str(timeout),
            "--thinking", thinking,
        ]
    )
    if task == "chat":
        cmd.extend(["--session-key", f"agent:{agent_name}:studio-chat"])
    elif task in production_tasks:
        session_suffix = job_id or f"{task}-{int(time.time())}"
        if retry_attempt:
            session_suffix = f"{session_suffix}-r{retry_attempt}"
        cmd.extend(["--session-key", f"agent:{agent_name}:job-{session_suffix}"])

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
