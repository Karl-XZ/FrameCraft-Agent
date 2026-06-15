"""端到端 API 测试：生成样例素材并跑完整链路。"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
API = "http://127.0.0.1:8000"


def run(cmd: list[str]):
    subprocess.run(cmd, check=True)


def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    talk = FIXTURES / "talk.mp4"
    broll = FIXTURES / "broll.mp4"
    img = FIXTURES / "product.jpg"
    bgm = FIXTURES / "bgm.mp3"
    if not talk.exists():
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#1e293b:s=1080x1920:d=8",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=8",
            "-vf", "drawtext=text='帧造 Agent 产品介绍测试':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h/2",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(talk),
        ])
    if not broll.exists():
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#0ea5e9:s=1080x1920:d=4",
            "-vf", "drawtext=text='B-roll Demo':fontsize=42:fontcolor=white:x=40:y=80",
            "-c:v", "libx264", "-an", str(broll),
        ])
    if not img.exists():
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#334155:s=1080x1920:d=1",
            "-frames:v", "1", str(img),
        ])
    if not bgm.exists():
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-c:a", "mp3", str(bgm),
        ])
    return talk, broll, img, bgm


def wait_job(client: httpx.Client, job_id: str, timeout: int = 600):
    for _ in range(timeout):
        r = client.get(f"{API}/api/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        print(f"  job {job_id}: {job['status']} {job['progress']:.0f}% - {job['current_step']}")
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            raise RuntimeError(job.get("error_message") or "job failed")
        time.sleep(2)
    raise TimeoutError(job_id)


def main():
    print("1) 健康检查")
    with httpx.Client(timeout=120) as client:
        assert client.get(f"{API}/api/health").json()["status"] == "ok"

        print("2) 生成测试素材")
        talk, broll, img, bgm = ensure_fixtures()

        print("3) 创建项目")
        project = client.post(f"{API}/api/projects", json={
            "name": "E2E 测试项目",
            "aspect_ratio": "9:16",
            "target_duration": 30,
            "target_style": "modern_talking_head",
        }).json()
        pid = project["id"]
        print(f"   project_id={pid}")

        print("4) 上传素材")
        uploads = [
            (talk, "口播视频", "核心产品介绍口播"),
            (broll, "B-roll", "产品界面演示镜头"),
            (img, "图片", "产品封面图"),
            (bgm, "音频", "科技感背景音乐"),
        ]
        for path, label, note in uploads:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "application/octet-stream")}
                data = {"user_label": label, "user_note": note}
                client.post(f"{API}/api/projects/{pid}/assets/upload", files=files, data=data).raise_for_status()

        print("5) 分析素材")
        job = client.post(f"{API}/api/projects/{pid}/assets/analyze").json()
        wait_job(client, job["id"], timeout=900)

        plan = client.get(f"{API}/api/projects/{pid}/edit-plan").json()
        print(f"   剪辑方案 hook: {plan.get('hook', '')[:50]}")

        print("6) 生成视频与剪映草稿")
        job = client.post(f"{API}/api/projects/{pid}/generate").json()
        wait_job(client, job["id"], timeout=1200)

        versions = client.get(f"{API}/api/projects/{pid}/versions").json()
        assert versions, "no versions"
        v = versions[0]
        print(f"   version v{v['version_number']}.0 id={v['id']}")

        print("7) 对话修改")
        chat = client.post(f"{API}/api/projects/{pid}/chat", json={"message": "BGM 小一点，节奏再快一点"}).json()
        assert chat.get("job_id")
        wait_job(client, chat["job_id"], timeout=1200)

        versions2 = client.get(f"{API}/api/projects/{pid}/versions").json()
        print(f"   新版本数量: {len(versions2)}")

        out = ROOT / "outputs" / "e2e_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"project_id": pid, "versions": versions2}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"8) 完成，报告: {out}")


if __name__ == "__main__":
    main()
