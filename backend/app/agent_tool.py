from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import store


def _print(data: dict[str, Any], code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def _job_id() -> str:
    jid = os.getenv("FRAMECRAFT_JOB_ID", "")
    if not jid:
        _print({"ok": False, "error": "FRAMECRAFT_JOB_ID 未设置"}, 1)
    return jid


def _project_id() -> str:
    pid = os.getenv("FRAMECRAFT_PROJECT_ID", "")
    if not pid:
        _print({"ok": False, "error": "FRAMECRAFT_PROJECT_ID 未设置"}, 1)
    return pid


def _job_workspace() -> Path:
    jid = os.getenv("FRAMECRAFT_JOB_ID", "")
    if not jid:
        return store.RUNTIME
    return store.RUNTIME / "jobs" / jid


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _allowed_read_roots(pid: str) -> list[Path]:
    return [
        store.upload_dir(pid),
        store.project_dir(pid),
        _job_workspace(),
        store.ROOT / "docs",
        store.ROOT / "resources",
        store.ROOT / "manual_codex_videos",
        store.ROOT / "node_modules",
    ]


def _allowed_write_roots(pid: str) -> list[Path]:
    return [store.project_dir(pid), _job_workspace()]


def _safe_path(raw: str | Path, roots: list[Path], purpose: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not any(_is_under(path, root) for root in roots):
        _print({"ok": False, "error": f"{purpose} 路径越界：{path}"}, 1)
    return path


def _read_payload(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "file", None):
        pid = _project_id()
        base = Path(os.getenv("FRAMECRAFT_CALLER_CWD") or os.getcwd())
        raw = Path(args.file)
        path = raw if raw.is_absolute() else base / raw
        safe = _safe_path(path, _allowed_read_roots(pid), "payload")
        return json.loads(safe.read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read() or "{}")


def cmd_read_state(args: argparse.Namespace) -> None:
    pid = _project_id()
    data = store.snapshot()
    project = data["projects"].get(pid)
    assets = [a for a in data["assets"].values() if a["project_id"] == pid]
    versions = [v for v in data["versions"].values() if v["project_id"] == pid]
    chat = data.get("chat", {}).get(pid, [])
    _print({
        "ok": True,
        "project": project,
        "assets": assets,
        "versions": versions,
        "chat": chat,
        "paths": {
            "root": str(store.ROOT),
            "uploads_dir": str(store.upload_dir(pid)),
            "outputs_dir": str(store.project_dir(pid)),
            "job_workspace": str(_job_workspace()),
            "hyperframes_repo": str(store.ROOT.parent / "hyperframes"),
            "hyperframes_student_kit": str(store.ROOT.parent / "hyperframes-student-kit"),
            "allowed_read_roots": [str(p) for p in _allowed_read_roots(pid)],
            "allowed_write_roots": [str(p) for p in _allowed_write_roots(pid)],
        },
    })


def cmd_progress(args: argparse.Namespace) -> None:
    jid = _job_id()

    def op(data):
        job = data["jobs"].get(jid)
        if not job:
            return None
        job["progress"] = float(args.progress)
        job["current_step"] = args.step
        job["status"] = args.status or job.get("status", "running")
        job["updated_at"] = store.now_iso()
        job.setdefault("logs", []).append(f"{args.progress:.0f}% {args.step}")
        return job

    job = store.mutate(op)
    _print({"ok": bool(job), "job": job})


def cmd_log(args: argparse.Namespace) -> None:
    jid = _job_id()

    def op(data):
        job = data["jobs"].get(jid)
        if job:
            job.setdefault("logs", []).append(args.message)
            job["updated_at"] = store.now_iso()
        return job

    _print({"ok": bool(store.mutate(op))})


def cmd_write_analysis(args: argparse.Namespace) -> None:
    pid = _project_id()
    payload = _read_payload(args)
    out = store.project_dir(pid) / "analysis" / "analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def op(data):
        for asset in data["assets"].values():
            if asset["project_id"] == pid:
                asset["analysis_status"] = "completed"
        data["projects"][pid]["status"] = "planning"
        data["projects"][pid]["updated_at"] = store.now_iso()

    store.mutate(op)
    _print({"ok": True, "path": str(out)})


def cmd_write_edit_plan(args: argparse.Namespace) -> None:
    pid = _project_id()
    payload = _read_payload(args)
    out = store.project_dir(pid) / "analysis" / "edit_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def op(data):
        data["projects"][pid]["status"] = "planning"
        data["projects"][pid]["updated_at"] = store.now_iso()

    store.mutate(op)
    _print({"ok": True, "path": str(out)})


def cmd_create_version_dir(args: argparse.Namespace) -> None:
    pid = _project_id()
    vid = args.version_id or store.new_id("ver")
    version_dir = store.project_dir(pid) / vid
    version_dir.mkdir(parents=True, exist_ok=True)
    _print({"ok": True, "version_id": vid, "version_dir": str(version_dir)})


def cmd_register_version(args: argparse.Namespace) -> None:
    pid = _project_id()
    version_dir = _safe_path(args.version_dir, [store.project_dir(pid)], "version_dir")
    preview = Path(args.preview).resolve() if args.preview else version_dir / "preview.mp4"
    preview = _safe_path(preview, [version_dir], "preview")
    if not preview.is_file():
        _print({"ok": False, "error": f"preview 不存在：{preview}"}, 1)
    vid = version_dir.name

    def op(data):
        existing = [v for v in data["versions"].values() if v["project_id"] == pid]
        number = max([int(v.get("version_number", 0)) for v in existing] or [0]) + 1
        version = {
            "id": vid,
            "project_id": pid,
            "version_number": number,
            "preview_url": f"/api/projects/{pid}/versions/{vid}/preview",
            "draft_url": None,
            "timeline_url": f"/api/projects/{pid}/versions/{vid}/timeline",
            "subtitles_url": f"/api/projects/{pid}/versions/{vid}/subtitles",
            "cover_url": None,
            "publish_copy_url": None,
            "hyperframes_url": f"/api/projects/{pid}/versions/{vid}/hyperframes",
            "version_dir": str(version_dir),
            "preview_path": str(preview),
            "created_at": store.now_iso(),
        }
        data["versions"][vid] = version
        project = data["projects"][pid]
        project["current_version_id"] = vid
        project["status"] = "completed"
        project["updated_at"] = store.now_iso()
        return version

    version = store.mutate(op)
    _print({"ok": True, "version": version})


def cmd_write_chat(args: argparse.Namespace) -> None:
    pid = _project_id()
    payload = _read_payload(args)
    message = {
        "id": store.new_id("msg"),
        "project_id": pid,
        "role": "agent",
        "content": str(payload.get("content") or payload.get("reply") or ""),
        "patch": payload.get("patch"),
        "status": payload.get("status", "chat"),
        "created_at": store.now_iso(),
    }

    def op(data):
        data.setdefault("chat", {}).setdefault(pid, []).append(message)

    store.mutate(op)
    _print({"ok": True, "message": message})


def cmd_probe_media(args: argparse.Namespace) -> None:
    pid = _project_id()
    path = _safe_path(args.path, _allowed_read_roots(pid), "probe_media")
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _print({"ok": False, "error": proc.stderr.strip()}, 1)
    _print({"ok": True, "ffprobe": json.loads(proc.stdout or "{}")})


def cmd_copy_file(args: argparse.Namespace) -> None:
    pid = _project_id()
    src = _safe_path(args.src, _allowed_read_roots(pid), "copy_file src")
    dst = _safe_path(args.dst, _allowed_write_roots(pid), "copy_file dst")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    _print({"ok": True, "path": str(dst)})


def main() -> None:
    parser = argparse.ArgumentParser(prog="framecraft-agent-tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("read_state").set_defaults(func=cmd_read_state)
    p = sub.add_parser("progress")
    p.add_argument("--progress", type=float, required=True)
    p.add_argument("--step", required=True)
    p.add_argument("--status")
    p.set_defaults(func=cmd_progress)
    p = sub.add_parser("log")
    p.add_argument("message")
    p.set_defaults(func=cmd_log)
    p = sub.add_parser("write_analysis")
    p.add_argument("--file")
    p.set_defaults(func=cmd_write_analysis)
    p = sub.add_parser("write_edit_plan")
    p.add_argument("--file")
    p.set_defaults(func=cmd_write_edit_plan)
    p = sub.add_parser("create_version_dir")
    p.add_argument("--version-id")
    p.set_defaults(func=cmd_create_version_dir)
    p = sub.add_parser("register_version")
    p.add_argument("--version-dir", required=True)
    p.add_argument("--preview")
    p.set_defaults(func=cmd_register_version)
    p = sub.add_parser("write_chat")
    p.add_argument("--file")
    p.set_defaults(func=cmd_write_chat)
    p = sub.add_parser("probe_media")
    p.add_argument("path")
    p.set_defaults(func=cmd_probe_media)
    p = sub.add_parser("copy_file")
    p.add_argument("src")
    p.add_argument("dst")
    p.set_defaults(func=cmd_copy_file)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
