"""用 nov26 口播素材在帧造 Agent（OpenClaw）内跑 analyze → generate → chat，并采集 session 日志。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
NOV26 = Path(r"C:\hf_demo\input\nov26-edit.mp4")
PY = ROOT / "backend" / "venv" / "Scripts" / "python.exe"


def wait_job(client: httpx.Client, job_id: str, timeout: int = 3600):
    last = ""
    for _ in range(timeout // 2):
        r = client.get(f"{API}/api/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        line = f"  job {job_id}: {job['status']} {job['progress']:.0f}% - {job['current_step']}"
        if line != last:
            print(line)
            last = line
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            err = job.get("error_message") or "job failed"
            log = job.get("log_path")
            if log and Path(log).exists():
                tail = Path(log).read_text(encoding="utf-8", errors="replace")[-8000:]
                err += f"\n--- log tail ---\n{tail}"
            raise RuntimeError(err)
        time.sleep(2)
    raise TimeoutError(job_id)


def collect_sessions(project_id: str) -> Path:
    script = ROOT / "scripts" / "collect_openclaw_sessions.py"
    proc = subprocess.run(
        [str(PY), str(script), project_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    out = ROOT / "outputs" / f"openclaw_session_{project_id}.md"
    if proc.stdout:
        print(proc.stdout[-6000:])
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
    return out


def main():
    if not NOV26.exists():
        print(f"素材不存在: {NOV26}", file=sys.stderr)
        sys.exit(1)

    with httpx.Client(timeout=600) as client:
        health = client.get(f"{API}/api/health").json()
        print("health:", json.dumps(health, ensure_ascii=False))
        assert health["status"] == "ok", health
        assert health.get("openclaw") is True, "OpenClaw 不可用"
        settings = client.get(f"{API}/api/settings/model").json()
        print(f"模型: {settings['provider']} text={settings['text_model']}")
        if not settings.get("api_key"):
            print("请先配置 API Key", file=sys.stderr)
            sys.exit(1)

        project = client.post(f"{API}/api/projects", json={
            "name": "nov26 OpenClaw E2E",
            "aspect_ratio": "9:16",
            "target_duration": 30,
            "target_style": "modern_talking_head",
            "generate_draft": False,
            "keep_hyperframes": True,
        }).json()
        pid = project["id"]
        print(f"project_id={pid}")

        with open(NOV26, "rb") as f:
            files = {"file": (NOV26.name, f, "video/mp4")}
            data = {"user_label": "口播视频", "user_note": "nov26 欧盟贸易数据口播切片 pip 竖屏"}
            client.post(f"{API}/api/projects/{pid}/assets/upload", files=files, data=data).raise_for_status()

        print("\n=== [1/3] OpenClaw analyze ===")
        job = client.post(f"{API}/api/projects/{pid}/assets/analyze").json()
        wait_job(client, job["id"], timeout=3600)

        plan_path = ROOT / "outputs" / pid / "analysis" / "edit_plan.json"
        manifest_path = ROOT / "outputs" / pid / "analysis" / "asset_manifest.json"
        print(f"manifest: {manifest_path.exists()} plan: {plan_path.exists()}")
        if plan_path.exists():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            print(f"剪辑方案 hook: {(plan.get('hook') or '')[:80]}")

        print("\n=== [2/3] OpenClaw generate ===")
        job = client.post(f"{API}/api/projects/{pid}/generate").json()
        wait_job(client, job["id"], timeout=3600)

        versions = client.get(f"{API}/api/projects/{pid}/versions").json()
        assert versions, "无版本"
        v = versions[0]
        vdir = ROOT / "outputs" / pid / v["id"]
        preview = vdir / "preview.mp4"
        print(f"preview: {preview} exists={preview.exists()} size={preview.stat().st_size if preview.exists() else 0}")

        print("\n=== [3/3] OpenClaw chat ===")
        chat = client.post(f"{API}/api/projects/{pid}/chat", json={"message": "你好", "apply": False}).json()
        print(f"chat status={chat.get('status')} content={chat.get('content','')[:100]}")

        print("\n=== OpenClaw session 日志 ===")
        sess_out = collect_sessions(pid)

        report = {
            "project_id": pid,
            "version_id": v["id"],
            "preview": str(preview),
            "preview_exists": preview.exists(),
            "preview_size": preview.stat().st_size if preview.exists() else 0,
            "openclaw_session_log": str(sess_out),
            "health": health,
        }
        out = ROOT / "outputs" / "nov26_openclaw_e2e_report.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告: {out}")
        print(f"Session 日志: {sess_out}")


if __name__ == "__main__":
    main()
