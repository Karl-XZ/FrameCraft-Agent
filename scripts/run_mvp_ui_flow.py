"""用 MVP 口播视频跑通工作台 UI 全流程：上传 → 分析 → 确认生成 → 等待成片。"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "fixtures" / "mvp_source.mp4"
API = "http://127.0.0.1:8000"
STUDIO = "http://127.0.0.1:5173/studio"
LOG_DIR = ROOT / "outputs" / "mvp_e2e_logs"
API_KEY = "sk-f4fa1e490f78469eb4433266814d28d2"

MODEL = {
    "provider": "openai",
    "api_key": API_KEY,
    "text_model": "qwen-max",
    "vision_model": "qwen-vl-max",
    "asr_model": "faster-whisper-base",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def log(msg: str, lines: list[str]) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    lines.append(line)


def wait_job(client: httpx.Client, job_id: str, lines: list[str], timeout: int = 3600) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        r = client.get(f"{API}/api/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        step = f"{job['status']} {job['progress']:.0f}% — {job.get('current_step') or ''}"
        if step != last:
            log(f"  job {job_id}: {step}", lines)
            last = step
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            raise RuntimeError(job.get("error_message") or "job failed")
        time.sleep(3)
    raise TimeoutError(f"job {job_id} timeout after {timeout}s")


def configure_model(client: httpx.Client, lines: list[str]) -> None:
    health = client.get(f"{API}/api/health").json()
    assert health.get("status") == "ok", health
    log(f"健康检查 OK openclaw={health.get('openclaw')}", lines)
    client.patch(f"{API}/api/settings/model", json=MODEL).raise_for_status()
    log("已配置 Qwen API Key", lines)


def wait_edit_plan(client: httpx.Client, project_id: str, lines: list[str], timeout: int = 3600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"{API}/api/projects/{project_id}/edit-plan")
        if r.status_code == 200:
            data = r.json()
            if data.get("hook") or data.get("video_concept"):
                log("剪辑方案已就绪", lines)
                return data
        time.sleep(5)
    raise TimeoutError("等待剪辑方案超时")


def ui_workflow(project_id: str, lines: list[str]) -> None:
    if not VIDEO.is_file():
        raise FileNotFoundError(VIDEO)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = f"{STUDIO}?project={project_id}"
        log(f"打开工作台 {url}", lines)
        page.goto(url, wait_until="networkidle", timeout=120_000)

        log("点击「选择文件」并上传口播视频", lines)
        page.get_by_role("button", name="选择文件").click()
        page.locator('input[type="file"]').set_input_files(str(VIDEO))
        page.wait_for_timeout(3000)
        page.get_by_text("口播视频", exact=False).first.wait_for(timeout=120_000)
        log("素材已出现在素材库", lines)

        log("点击「开始 AI 分析」", lines)
        page.get_by_role("button", name="开始 AI 分析").click()

        log("等待剪辑方案页…", lines)
        page.get_by_role("button", name="确认生成").wait_for(timeout=3_600_000)

        log("点击「确认生成」", lines)
        with page.expect_response(
            lambda r: "/generate" in r.url and r.request.method == "POST",
            timeout=3_600_000,
        ) as resp_info:
            page.get_by_role("button", name="确认生成").click()
        gen_job = resp_info.value.json()
        log(f"生成任务已提交 job_id={gen_job['id']}", lines)
        browser.close()
        return gen_job["id"]


def run_once(attempt: int) -> tuple[bool, list[str]]:
    lines: list[str] = []
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log(f"===== 第 {attempt} 次尝试 =====", lines)
    project_id = ""
    try:
        with httpx.Client(timeout=300) as client:
            configure_model(client, lines)

            log("创建新项目", lines)
            project = client.post(
                f"{API}/api/projects",
                json={
                    "name": f"MVP口播测试-{datetime.now().strftime('%m%d-%H%M')}",
                    "aspect_ratio": "9:16",
                    "target_duration": 60,
                    "target_style": "modern_talking_head",
                    "output_language": "zh",
                    "generate_draft": True,
                    "keep_hyperframes": True,
                },
            ).json()
            project_id = project["id"]
            log(f"project_id={project_id}", lines)

            gen_id = ui_workflow(project_id, lines)

            log("等待生成任务完成", lines)
            wait_job(client, gen_id, lines, timeout=3600)

            versions = client.get(f"{API}/api/projects/{project_id}/versions").json()
            if not versions:
                raise RuntimeError("无成片版本")
            v = versions[0]
            log(
                f"成功！版本 v{v['version_number']}.0 preview={bool(v.get('preview_url'))} draft={bool(v.get('draft_url'))}",
                lines,
            )

            report = {
                "success": True,
                "project_id": project_id,
                "version": v,
                "attempt": attempt,
            }
            out = LOG_DIR / f"success_{project_id}.json"
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            (LOG_DIR / f"run_{attempt}.log").write_text("\n".join(lines), encoding="utf-8")
            return True, lines

    except Exception as exc:
        log(f"失败: {exc}", lines)
        log(traceback.format_exc(), lines)
        fail = {
            "success": False,
            "project_id": project_id,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "attempt": attempt,
        }
        (LOG_DIR / f"fail_attempt_{attempt}.json").write_text(
            json.dumps(fail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (LOG_DIR / f"run_{attempt}.log").write_text("\n".join(lines), encoding="utf-8")
        return False, lines


def main() -> int:
    max_attempts = 3
    for i in range(1, max_attempts + 1):
        ok, _ = run_once(i)
        if ok:
            print("\n=== MVP 全流程跑通 ===")
            return 0
        if i < max_attempts:
            print(f"\n等待 15s 后重试 ({i}/{max_attempts})...")
            time.sleep(15)
    print("\n=== 多次尝试后仍失败，见 outputs/mvp_e2e_logs ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
