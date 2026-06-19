#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


MATRIX = [
    {"name": "横屏全屏", "aspect_ratio": "16:9", "layout_variant": "fullscreen"},
    {"name": "横屏非全屏", "aspect_ratio": "16:9", "layout_variant": "nonfullscreen"},
    {"name": "竖屏全屏", "aspect_ratio": "9:16", "layout_variant": "fullscreen"},
    {"name": "竖屏非全屏", "aspect_ratio": "9:16", "layout_variant": "nonfullscreen"},
]


def wait_job(base_url: str, project_id: str, job_id: str, timeout: int = 7200) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = requests.get(f"{base_url}/api/jobs/{job_id}", timeout=30)
        res.raise_for_status()
        job = res.json()
        print(f"[{project_id}] {job['type']} {job['status']} {job['progress']:.0f}% {job['current_step']}")
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(5)
    raise TimeoutError(f"任务超时: {job_id}")


def latest_version(base_url: str, project_id: str) -> dict:
    res = requests.get(f"{base_url}/api/projects/{project_id}/versions", timeout=30)
    res.raise_for_status()
    versions = res.json()
    if not versions:
        raise RuntimeError(f"项目 {project_id} 没有产出版本")
    return versions[0]


def run_case(base_url: str, source: Path, category: str, prefix: str, index: int, total: int) -> dict:
    case = MATRIX[index]
    payload = {
        "name": f"{prefix}-{case['name']}",
        "aspect_ratio": case["aspect_ratio"],
        "target_style": "modern_talking_head",
        "target_duration": 120,
        "output_language": "zh",
        "layout_variant": case["layout_variant"],
        "content_category": category,
        "generate_draft": False,
        "keep_hyperframes": True,
    }
    res = requests.post(f"{base_url}/api/projects", json=payload, timeout=30)
    res.raise_for_status()
    project = res.json()
    project_id = project["id"]
    print(f"[{index + 1}/{total}] 创建项目 {project_id} {case['name']}")

    with source.open("rb") as fp:
        upload = requests.post(
            f"{base_url}/api/projects/{project_id}/assets/upload",
            files={"file": (source.name, fp, "video/mp4")},
            data={"user_label": "口播视频", "user_note": "主讲原片，完整保留人物表达，禁止遮挡脸部"},
            timeout=600,
        )
    upload.raise_for_status()

    analyze = requests.post(
        f"{base_url}/api/projects/{project_id}/assets/analyze",
        json={"strategy": "complete", "platform": "douyin"},
        timeout=30,
    )
    analyze.raise_for_status()
    analyze_job = wait_job(base_url, project_id, analyze.json()["id"])
    if analyze_job["status"] != "completed":
        raise RuntimeError(f"分析失败: {project_id} {analyze_job.get('error_message')}")

    generate = requests.post(
        f"{base_url}/api/projects/{project_id}/generate",
        json={"confirm_plan": True, "resolution": "1080p", "fps": 30, "strategy": "complete"},
        timeout=30,
    )
    generate.raise_for_status()
    generate_job = wait_job(base_url, project_id, generate.json()["id"])
    if generate_job["status"] != "completed":
        raise RuntimeError(f"生成失败: {project_id} {generate_job.get('error_message')}")

    version = latest_version(base_url, project_id)
    return {
        "project_id": project_id,
        "case": case,
        "version": version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="按项目 API 流程运行 4 个 Codex 版式测试视频")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--source", required=True)
    parser.add_argument("--category", default="funny_reaction")
    parser.add_argument("--prefix", default="codex-矩阵测试")
    parser.add_argument("--out", default="")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    results = []
    end = len(MATRIX) if args.count <= 0 else min(len(MATRIX), args.start_index + args.count)
    for idx in range(args.start_index, end):
        results.append(run_case(args.base_url, source, args.category, args.prefix, idx, len(MATRIX)))

    text = json.dumps(results, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写出 {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
