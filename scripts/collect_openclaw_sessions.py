"""提取 OpenClaw session JSONL 中的 Agent 决策轨迹（tool call / exec）。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_AGENTS = Path.home() / ".openclaw" / "agents"


def _short(text: str, n: int = 200) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 3] + "..."


def _parse_trajectory_line(obj: dict) -> list[str]:
    lines: list[str] = []
    t = obj.get("type") or ""
    ts = obj.get("ts") or ""
    run_id = (obj.get("runId") or "")[:8]
    data = obj.get("data") or {}

    if t == "prompt.submitted":
        prompt = _short(data.get("prompt") or "", 180)
        lines.append(f"  [{ts}] RUN {run_id} PROMPT: {prompt}")
    elif t == "tool.invoked":
        name = data.get("toolName") or data.get("name") or "tool"
        inp = data.get("input") or data.get("arguments") or {}
        lines.append(f"  [{ts}] RUN {run_id} >>> TOOL {name}: {_short(json.dumps(inp, ensure_ascii=False), 400)}")
    elif t == "tool.completed":
        name = data.get("toolName") or data.get("name") or "tool"
        out = data.get("output") or data.get("result") or ""
        lines.append(f"  [{ts}] RUN {run_id} <<< TOOL {name} done: {_short(str(out), 300)}")
    elif t == "assistant.text":
        lines.append(f"  [{ts}] RUN {run_id} ASSISTANT: {_short(data.get('text') or '', 250)}")
    elif t == "run.completed":
        lines.append(f"  [{ts}] RUN {run_id} COMPLETED status={data.get('status')}")
    elif t == "run.failed":
        lines.append(f"  [{ts}] RUN {run_id} FAILED: {_short(str(data), 300)}")
    return lines


def _parse_line(obj: dict) -> list[str]:
    lines: list[str] = []

    if obj.get("traceSchema") == "openclaw-trajectory":
        return _parse_trajectory_line(obj)

    if obj.get("type") == "message" and isinstance(obj.get("message"), dict):
        msg = obj["message"]
        role = msg.get("role") or ""
        ts = obj.get("timestamp") or ""
        for part in msg.get("content") or []:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type") or ""
            if ptype == "text":
                lines.append(f"  [{ts}] [{role}] {_short(part.get('text') or '', 250)}")
            elif ptype in ("toolCall", "tool_use"):
                name = part.get("name") or "tool"
                args = part.get("arguments") or part.get("input") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                if name == "exec" and isinstance(args, dict):
                    cmd = args.get("command") or ""
                    lines.append(f"  [{ts}] >>> AGENT EXEC: {_short(cmd, 450)}")
                else:
                    lines.append(f"  [{ts}] >>> AGENT TOOL {name}: {_short(json.dumps(args, ensure_ascii=False), 400)}")
        if role == "toolResult":
            tname = msg.get("toolName") or "tool"
            content = msg.get("content") or []
            text = ""
            if content and isinstance(content[0], dict):
                text = content[0].get("text") or ""
            lines.append(f"  [{ts}] <<< TOOL RESULT {tname}: {_short(text, 350)}")
        return lines

    role = obj.get("role") or obj.get("type") or ""
    ts = obj.get("timestamp") or obj.get("createdAt") or ""

    # OpenClaw jsonl 多种格式兼容
    content = obj.get("content")
    if isinstance(content, str) and content.strip():
        lines.append(f"  [{role}] {_short(content, 300)}")

    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type") or part.get("kind") or ""
            if ptype in ("text", "output_text"):
                lines.append(f"  [{role}/text] {_short(part.get('text') or '', 300)}")
            elif ptype in ("toolCall", "tool_use", "function"):
                name = part.get("name") or part.get("toolName") or part.get("function", {}).get("name") or "tool"
                args = part.get("arguments") or part.get("input") or part.get("parameters") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                if name == "exec" or "framecraft" in str(args).lower() or "framecraft" in str(name).lower():
                    cmd = args.get("command") or args.get("cmd") or args if isinstance(args, str) else args
                    lines.append(f"  >>> AGENT EXEC: {_short(str(cmd), 400)}")
                else:
                    lines.append(f"  >>> AGENT TOOL {name}: {_short(json.dumps(args, ensure_ascii=False), 350)}")

    tool_calls = obj.get("tool_calls") or obj.get("toolCalls") or []
    for tc in tool_calls:
        fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
        name = fn.get("name") or tc.get("name") or "tool"
        raw = fn.get("arguments") or tc.get("arguments") or ""
        lines.append(f"  >>> AGENT TOOL {name}: {_short(str(raw), 400)}")

    message = obj.get("message")
    if isinstance(message, dict):
        for sub in _parse_line(message):
            lines.append(sub)

    return lines


def collect_project_sessions(project_id: str) -> str:
    agent_name = f"framecraft-{project_id}"
    sess_dir = OPENCLAW_AGENTS / agent_name / "sessions"
    if not sess_dir.exists():
        return f"未找到 OpenClaw session 目录: {sess_dir}\n"

    files = sorted(sess_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    out_lines = [
        f"# OpenClaw Agent 决策日志 — {agent_name}",
        f"# 目录: {sess_dir}",
        f"# 采集时间: {datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"# session 文件数: {len(files)}",
        "",
    ]

    for sf in files[:8]:
        out_lines.append(f"## Session: {sf.name} ({sf.stat().st_size} bytes)")
        out_lines.append("")
        # 优先解析 trajectory（含 tool.invoked）
        traj = sf.with_suffix("").with_suffix(".trajectory.jsonl") if sf.suffix == ".jsonl" and not sf.name.endswith(".trajectory.jsonl") else None
        candidates = [sf]
        traj_path = Path(str(sf).replace(".jsonl", ".trajectory.jsonl"))
        if traj_path.exists() and traj_path != sf:
            candidates.insert(0, traj_path)
        for cf in candidates:
            if not cf.exists():
                continue
            out_lines.append(f"### File: {cf.name}")
            try:
                raw = cf.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                out_lines.append(f"  (读取失败: {exc})")
                continue
            for line_no, line in enumerate(raw.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    if "framecraft" in line.lower() or "tool.invoked" in line.lower():
                        out_lines.append(f"  L{line_no} raw: {_short(line, 250)}")
                    continue
                parsed = _parse_line(obj)
                if parsed:
                    out_lines.extend(parsed)
            out_lines.append("")

    return "\n".join(out_lines)


def main() -> None:
    pid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not pid:
        print("用法: python collect_openclaw_sessions.py <project_id>", file=sys.stderr)
        sys.exit(1)
    text = collect_project_sessions(pid)
    out = ROOT / "outputs" / f"openclaw_session_{pid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n--- 已写入 {out} ---")


if __name__ == "__main__":
    main()
