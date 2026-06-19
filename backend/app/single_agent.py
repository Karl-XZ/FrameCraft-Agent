from __future__ import annotations

import os
import shutil
import subprocess
import threading
import json
import queue
import re
from pathlib import Path
from typing import Any

from . import store

CODEX_BIN = os.getenv("CODEX_BIN", "codex")
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "needs_input"}
_CODEX_THREAD_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ProjectBusyError(RuntimeError):
    pass


def codex_cmd() -> list[str]:
    override = os.getenv("CODEX_BIN")
    if override:
        return [override]
    for candidate in (
        shutil.which("codex"),
        "/Applications/Codex.app/Contents/Resources/codex",
        str(Path.home() / ".local" / "bin" / "codex"),
    ):
        if candidate and Path(candidate).exists():
            return [candidate]
    return [CODEX_BIN]


def codex_available() -> bool:
    try:
        proc = subprocess.run(codex_cmd() + ["--version"], capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except Exception:
        return False


class SingleAgentRunner:
    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}

    def start(self, project_id: str, job_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not codex_available():
            raise RuntimeError("本机 Agent 运行时不可用。请先安装/登录本机 Agent，或设置运行时路径。")
        job_id = store.new_id("job")
        now = store.now_iso()

        def op(data):
            active = [
                j for j in data["jobs"].values()
                if j.get("project_id") == project_id and j.get("status") not in TERMINAL_STATUSES
            ]
            if active:
                raise ProjectBusyError(f"该项目已有运行中的 agent 任务：{active[0]['id']}")
            project = data["projects"][project_id]
            project["status"] = (
                "analyzing" if job_type == "analyze"
                else "chatting" if job_type == "chat"
                else "rendering"
            )
            project["updated_at"] = now
            data["jobs"][job_id] = {
                "id": job_id,
                "project_id": project_id,
                "type": job_type,
                "status": "pending",
                "progress": 0.0,
                "current_step": "",
                "error_message": None,
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "payload": payload or {},
                "logs": [],
                "warnings": [],
                "completed_steps": [],
                "plan_substep": None,
                "plan_progress": 0,
            }
            return data["jobs"][job_id]

        job = store.mutate(op)
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        self._threads[job_id] = thread
        thread.start()
        return store.public_job(job)

    def _run(self, job_id: str) -> None:
        self._mark_running(job_id)
        data = store.snapshot()
        job = data["jobs"][job_id]
        project_id = job["project_id"]
        workspace = store.RUNTIME / "jobs" / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        tool = self._write_tool_wrapper(workspace)
        prompt = self._build_prompt(job, tool)
        last_message = workspace / "last-message.txt"
        prompt_path = workspace / "prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        env = os.environ.copy()
        env["FRAMECRAFT_PROJECT_ID"] = project_id
        env["FRAMECRAFT_JOB_ID"] = job_id
        env["FRAMECRAFT_PROJECT_ROOT"] = str(store.ROOT)
        env["CODEX_DISABLE_AUTO_UPDATE"] = "1"
        env["FRAMECRAFT_ALLOWED_ROOTS"] = os.pathsep.join(
            [
                str(store.ROOT),
                str(store.upload_dir(project_id)),
                str(store.project_dir(project_id)),
                str(workspace),
            ]
        )
        session_id = self._project_codex_session(project_id)
        if session_id:
            cmd = codex_cmd() + [
                "exec",
                "resume",
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "-c",
                'approval_policy="never"',
                "--skip-git-repo-check",
                "-o",
                str(last_message),
                session_id,
                prompt,
            ]
            self._append_log(job_id, f"继续项目 Agent 会话：{session_id}", chat=True)
        else:
            cmd = codex_cmd() + [
                "exec",
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "-c",
                'approval_policy="never"',
                "--skip-git-repo-check",
                "--color",
                "never",
                "-C",
                str(store.ROOT),
                "-o",
                str(last_message),
                prompt,
            ]
            self._append_log(job_id, "创建新的项目 Agent 会话", chat=True)
        try:
            proc, stdout_text, stderr_text = self._run_codex_process(job_id, cmd, store.ROOT, env)
        except subprocess.TimeoutExpired:
            self._fail(job_id, "单一 Agent 超时（>7200s）。")
            return
        log_path = workspace / "codex.log"
        log_path.write_text((stdout_text or "") + "\n" + (stderr_text or ""), encoding="utf-8")
        if proc.returncode != 0:
            self._fail(job_id, _tail(stdout_text, stderr_text) or f"Agent exit {proc.returncode}")
            return
        current = store.snapshot()["jobs"].get(job_id, {})
        if current.get("status") == "needs_input":
            self._finish_needs_input(job_id)
            return
        final = last_message.read_text(encoding="utf-8") if last_message.exists() else ""
        if not self._validate_outputs(job_id):
            return
        self._complete(job_id, final)

    def _project_codex_session(self, project_id: str) -> str | None:
        project = store.snapshot()["projects"].get(project_id) or {}
        session_id = str(project.get("agent_session_id") or "").strip()
        return session_id if _CODEX_THREAD_RE.match(session_id) else None

    def _save_project_codex_session(self, project_id: str, session_id: str) -> None:
        if not _CODEX_THREAD_RE.match(session_id):
            return

        def op(data):
            project = data["projects"].get(project_id)
            if project:
                project["agent_session_id"] = session_id
                project["updated_at"] = store.now_iso()
            return project

        store.mutate(op)

    def _clear_project_codex_session(self, project_id: str) -> None:
        def op(data):
            project = data["projects"].get(project_id)
            if project:
                project["agent_session_id"] = None
                project["updated_at"] = store.now_iso()
            return project

        store.mutate(op)

    def _run_codex_process(
        self,
        job_id: str,
        cmd: list[str],
        workspace: Path,
        env: dict[str, str],
    ) -> tuple[subprocess.Popen[str], str, str]:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(workspace),
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        stderr_q: queue.Queue[str] = queue.Queue()

        def read_stderr() -> None:
            if not proc.stderr:
                return
            for line in proc.stderr:
                stderr_q.put(line)

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        try:
            if proc.stdout:
                for line in proc.stdout:
                    stdout_chunks.append(line)
                    self._handle_codex_event(job_id, line)
            proc.wait(timeout=7200)
            stderr_thread.join(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise
        while not stderr_q.empty():
            stderr_chunks.append(stderr_q.get_nowait())
        return proc, "".join(stdout_chunks), "".join(stderr_chunks)

    def _handle_codex_event(self, job_id: str, line: str) -> None:
        raw = line.strip()
        if not raw:
            return
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            self._append_log(job_id, raw[-1200:])
            return
        event_type = event.get("type")
        data = store.snapshot()
        job = data["jobs"].get(job_id) or {}
        project_id = job.get("project_id")
        if event_type == "thread.started":
            thread_id = str(event.get("thread_id") or "")
            if project_id and thread_id:
                self._save_project_codex_session(project_id, thread_id)
                self._append_log(job_id, f"Agent 会话已绑定：{thread_id}", chat=True)
            return
        if event_type == "turn.started":
            self._append_log(job_id, "Agent 已开始处理这一轮任务", chat=True)
            return
        if event_type == "turn.completed":
            usage = event.get("usage") or {}
            if usage:
                self._append_log(
                    job_id,
                    "Agent 本轮完成，token 用量："
                    f"输入 {usage.get('input_tokens', 0)}，输出 {usage.get('output_tokens', 0)}",
                )
            return
        if event_type == "item.completed":
            item = event.get("item") or {}
            item_type = item.get("type")
            if item_type == "agent_message":
                text = str(item.get("text") or "").strip()
                if text:
                    self._append_log(job_id, text[-4000:], chat=True)
            elif item_type in {"command_execution", "tool_call"}:
                summary = str(item.get("command") or item.get("name") or item_type)
                self._append_log(job_id, f"执行工具：{summary[:500]}")

    def _write_tool_wrapper(self, workspace: Path) -> Path:
        tool = workspace / "framecraft-tool.sh"
        tool.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "CALLER_CWD=\"$PWD\"\n"
            f"cd {store.ROOT}\n"
            "FRAMECRAFT_CALLER_CWD=\"$CALLER_CWD\" PYTHONPATH=backend backend/venv/bin/python -m app.agent_tool \"$@\"\n",
            encoding="utf-8",
        )
        tool.chmod(0o755)
        return tool

    def _build_prompt(self, job: dict[str, Any], tool: Path) -> str:
        task = job["type"]
        payload = job.get("payload") or {}
        base = f"""
你是 FrameCraft 项目背后的唯一 Agent。

这次任务从开始到结束只能由你这一轮 Agent 负责：服务端不会再把分析、生成、视觉复审、重做拆给其他 agent。你可以使用本地命令和 `{tool}` 这些哑工具读写项目状态、更新进度、注册版本；但禁止再启动新的 agent、禁止创建子 agent、禁止把设计判断交给固定脚本冒充。

如果依赖、素材、HyperFrames 或视觉验收无法完成，不允许伪装成功。若问题需要用户补充信息或素材，例如缺少可靠逐字稿、源视频无法读取、用户需求互相冲突，必须先用 `write_chat` 在聊天里说明卡点、你已经尝试了什么、用户可以怎么补充；随后调用 `progress --status needs_input --progress 当前进度 --step "需要用户补充：..."`。只有系统错误、依赖损坏、越权请求、渲染无法修复等不可继续问题才让任务失败。

禁止 FFmpeg 拼接兜底冒充 HyperFrames 成片；FFmpeg 只可用于探测、转码、抽帧等辅助。

权限边界：用户通过访问口令进入后，当前任务允许你使用本机完整能力，包括安装/下载必要依赖、调用系统工具、使用网络、下载或加载 ASR 模型。不要读取、复制、扫描或删除与当前视频任务无关的个人文件；不要主动读取其他 `proj_*` 的上传目录、输出目录、聊天记录或其他 job 工作目录，除非用户明确要求并且任务确实需要。

第一步必须执行：
`{tool} read_state`

开始设计前必须阅读：
- `{store.ROOT / "docs" / "single-codex-agent-backend.md"}`
- `{store.ROOT / "docs" / "codex-hyperframes-reproducible-workflow.md"}`

你可以参考 `{store.ROOT / "manual_codex_videos" / "build_manual_hyperframes_videos_v2.py"}` 了解 HyperFrames 工程组织和 QA 抽帧方式，但只能作为实现参考，不能复制固定模板、固定时间轴、旧文案或旧设计参数。

项目目标：
- 保留完整主讲视频，字幕必须是逐字稿、简体中文、固定在画面下方安全区、水平居中且淡入淡出。
- 使用 HyperFrames 真实渲染 preview.mp4，不允许旧流水线/固定模板兜底。
- 动画按内容和构图设计；搞笑类不能全在同一角落，也不能机械排成上中下/左右队列。
- 渲染后你必须自己抽关键帧/截图进行视觉验收；如果主观上不美观、不自然、像脚本排版、遮挡人物/字幕、底色多余、圆角不真实，就修改设计重新渲染。直到通过或明确失败。
- 面向观众的可见文案只写观众应该看到的内容，不写“制作、设计、分镜、实验板、重构、高级口播”等制作过程词。尽量不要使用“不是……而是……”句式。

可用项目工具：
- `{tool} progress --progress N --step "..."`
- `{tool} read_state`
- `{tool} write_analysis --file analysis.json`
- `{tool} write_edit_plan --file edit_plan.json`
- `{tool} create_version_dir`
- `{tool} register_version --version-dir PATH --preview PATH`
- `{tool} write_chat --file chat.json`
- `{tool} probe_media PATH`
- `{tool} copy_file SRC DST`

剪映草稿导出规则：
- 若项目设置 `generate_draft=true`，`register_version` 会自动根据你写入版本目录的 `timeline.json` 同步生成 `jianying_draft.zip`。
- 你仍必须先写清楚统一时间线、字幕和动画 blocks；草稿导出器只负责格式转换，不负责替你做设计判断。
- 草稿包含可编辑主视频、字幕和可降级表达的信息图层。复杂 HyperFrames/CSS/GSAP 动画不保证 100% 剪映原生还原，不能在可见文案或回复里伪装成完整反编译。

当前任务类型：{task}
任务参数：{payload}

任务进行中请频繁调用 `progress` 或 `log`，让前端聊天区能看到你真实在做什么。不要长时间沉默。
"""
        if task == "analyze":
            return base + """
完成目标：分析上传素材并写出 `analysis.json` 与 `edit_plan.json`。不要生成视频。
要求：必须明确主讲素材、时长、推荐剪辑策略、字幕策略、视觉风格、风险。
结束前调用 progress 100。
"""
        if task == "generate":
            return base + """
完成目标：从素材分析到最终成片全部由你一次完成。
步骤建议：
1. 读取素材并必要时用 ffprobe/ASR/你可用的本地能力分析。
2. 写 analysis/edit_plan。
3. 创建 version_dir，写完整 timeline.json、HyperFrames 项目、设计说明和 agent_visual_review.json。
4. 调用 HyperFrames 真实渲染 preview.mp4。
5. 抽逐动画截图，亲自验收；不美观就改设计重新渲染。
6. 通过后 register_version。
结束前 progress 100。
"""
        if task == "chat":
            return base + f"""
用户消息：{payload.get('message', '')}
完成目标：像一个可对话的剪辑 agent 一样回应用户。若用户只是提问，写 chat 回复；若用户要求改片，你可以直接完成改片并重新生成，也可以提出 patch，但必须说明实际完成到哪一步。
写回复：`{tool} write_chat --file chat.json`。
如果需要用户补充信息，不要直接失败；写 chat 回复解释需要什么，并把任务状态设为 needs_input。
"""
        if task == "apply_patch":
            return base + """
完成目标：用户已确认修改。读取当前版本和 patch，由你负责修改 timeline/设计并重新 HyperFrames 渲染，验收通过后 register_version。
"""
        return base

    def _validate_outputs(self, job_id: str) -> bool:
        data = store.snapshot()
        job = data["jobs"][job_id]
        project_id = job["project_id"]
        job_type = job["type"]
        project_root = store.project_dir(project_id)

        if job_type == "analyze":
            missing = [
                str(path)
                for path in (
                    project_root / "analysis" / "analysis.json",
                    project_root / "analysis" / "edit_plan.json",
                )
                if not path.is_file()
            ]
            if missing:
                self._fail(job_id, "单一 Agent 未产出必要分析文件：" + "；".join(missing))
                return False
            return True

        if job_type in {"generate", "apply_patch"}:
            project = data["projects"].get(project_id) or {}
            version_id = project.get("current_version_id")
            version = data["versions"].get(version_id or "")
            if not version:
                self._fail(job_id, "单一 Agent 未注册任何视频版本。")
                return False
            preview = Path(version.get("preview_path") or "")
            if not preview.is_file() or preview.stat().st_size < 1024:
                self._fail(job_id, f"单一 Agent 注册的视频预览不存在或为空：{preview}")
                return False
            version_dir = Path(version.get("version_dir") or "")
            missing_required = [
                str(path)
                for path in (
                    version_dir / "timeline.json",
                    version_dir / "agent_visual_review.json",
                )
                if not path.is_file()
            ]
            hyperframes_markers = [
                version_dir / "hyperframes_project.zip",
                version_dir / "hyperframes",
                version_dir / "hyperframes_project",
                version_dir / "project.tsx",
                version_dir / "src",
            ]
            if not any(path.exists() for path in hyperframes_markers):
                missing_required.append("HyperFrames 工程或源码痕迹")
            if missing_required:
                self._fail(job_id, "单一 Agent 未产出可复现渲染材料：" + "；".join(missing_required))
                return False
            if project.get("generate_draft", True):
                draft_path = Path(version.get("draft_path") or version_dir / "jianying_draft.zip")
                if not version.get("draft_url") or not draft_path.is_file() or draft_path.stat().st_size < 1024:
                    self._fail(job_id, f"项目要求生成剪映草稿，但草稿 zip 不存在或为空：{draft_path}")
                    return False
            return True

        if job_type == "chat":
            messages = data.get("chat", {}).get(project_id, [])
            if not any(
                message.get("role") == "agent"
                and message.get("job_id") == job_id
                and message.get("status") not in {"running", "progress", "log", "failed"}
                and message.get("content")
                for message in messages
            ):
                self._clear_project_codex_session(project_id)
                self._fail(job_id, "单一 Agent 未写入本轮对话回复。已清除该项目损坏的 Agent 会话，下次会自动创建新的项目会话。")
                return False
            return True

        return True

    def _mark_running(self, job_id: str) -> None:
        def op(data):
            job = data["jobs"][job_id]
            job["status"] = "running"
            job["started_at"] = store.now_iso()
            job["progress"] = 2
            job["current_step"] = f"单一 Agent · {job['type']}"
            return job
        store.mutate(op)

    def _complete(self, job_id: str, final: str) -> None:
        def op(data):
            job = data["jobs"][job_id]
            if job.get("status") in {"failed", "cancelled"}:
                return job
            job["status"] = "completed"
            job["progress"] = 100
            job["current_step"] = "单一 Agent 完成"
            job["completed_at"] = store.now_iso()
            job.setdefault("logs", []).append((final or "完成")[:2000])
            project = data["projects"][job["project_id"]]
            if job["type"] == "analyze":
                project["status"] = "planning"
            elif job["type"] == "chat" and not project.get("current_version_id"):
                project["status"] = "planning"
            else:
                project["status"] = "completed"
            project["updated_at"] = store.now_iso()
            return job
        store.mutate(op)

    def _finish_needs_input(self, job_id: str) -> None:
        def op(data):
            job = data["jobs"][job_id]
            job["status"] = "needs_input"
            job["completed_at"] = store.now_iso()
            job["current_step"] = job.get("current_step") or "需要用户补充"
            project = data["projects"][job["project_id"]]
            project["status"] = "needs_input"
            project["updated_at"] = store.now_iso()
            return job

        store.mutate(op)

    def _fail(self, job_id: str, error: str) -> None:
        def op(data):
            job = data["jobs"][job_id]
            if job.get("status") == "cancelled":
                return job
            job["status"] = "failed"
            job["error_message"] = error[:8000]
            job["completed_at"] = store.now_iso()
            job.setdefault("logs", []).append(error[:2000])
            project = data["projects"][job["project_id"]]
            project["status"] = "failed"
            project["updated_at"] = store.now_iso()
            data.setdefault("chat", {}).setdefault(job["project_id"], []).append({
                "id": store.new_id("msg"),
                "project_id": job["project_id"],
                "job_id": job_id,
                "role": "agent",
                "content": (
                    "Agent 这轮没有通过项目验收，已停止继续伪装完成。\n\n"
                    f"原因：{error[:3000]}\n\n"
                    "你可以直接在这里继续发消息，让同一个项目 Agent 会话根据这个问题修正或补充信息后重跑。"
                ),
                "status": "failed",
                "created_at": store.now_iso(),
            })
            return job
        store.mutate(op)

    def _append_log(self, job_id: str, message: str, chat: bool = False) -> None:
        clean = str(message or "").strip()
        if not clean:
            return

        def op(data):
            job = data["jobs"].get(job_id)
            if not job:
                return None
            job.setdefault("logs", []).append(clean[:4000])
            if chat:
                job["current_step"] = clean[:160]
            job["updated_at"] = store.now_iso()
            if chat:
                data.setdefault("chat", {}).setdefault(job["project_id"], []).append({
                    "id": store.new_id("msg"),
                    "project_id": job["project_id"],
                    "job_id": job_id,
                    "role": "agent",
                    "content": clean[:4000],
                    "status": "progress",
                    "created_at": store.now_iso(),
                })
            return job

        store.mutate(op)


def _tail(stdout: str | None, stderr: str | None, limit: int = 5000) -> str:
    merged = "\n".join(x for x in [(stdout or "").strip(), (stderr or "").strip()] if x)
    return merged[-limit:]


runner = SingleAgentRunner()
