#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests


MATRIX = [
    {"name": "横屏全屏", "aspect_ratio": "16:9", "layout_variant": "fullscreen"},
    {"name": "横屏非全屏", "aspect_ratio": "16:9", "layout_variant": "nonfullscreen"},
    {"name": "竖屏全屏", "aspect_ratio": "9:16", "layout_variant": "fullscreen"},
    {"name": "竖屏非全屏", "aspect_ratio": "9:16", "layout_variant": "nonfullscreen"},
]


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def yt_dlp_json(url: str) -> dict:
    res = run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--extractor-args",
            "youtube:player_client=android",
            "-J",
            url,
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout or f"读取视频信息失败: {url}")
    return json.loads(res.stdout)


def ensure_download(item: dict, download_dir: Path) -> tuple[Path, dict]:
    download_dir.mkdir(parents=True, exist_ok=True)
    meta = yt_dlp_json(item["source_url"])
    ext = meta.get("ext") or "mp4"
    path = download_dir / f"{item['id']}.{ext}"
    if not path.exists():
        res = run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--extractor-args",
                "youtube:player_client=android",
                "-f",
                "18",
                "-o",
                str(download_dir / "%(id)s.%(ext)s"),
                item["source_url"],
            ]
        )
        if res.returncode != 0:
            raise RuntimeError(res.stderr or res.stdout or f"下载失败: {item['source_url']}")
    if not path.exists():
        raise FileNotFoundError(path)
    return path, meta


def maybe_clip_source(item: dict, source_path: Path, download_dir: Path) -> Path:
    clip_start = float(item.get("clip_start") or 0.0)
    clip_end_raw = item.get("clip_end")
    if clip_end_raw in (None, ""):
        return source_path
    clip_end = float(clip_end_raw)
    if clip_end <= clip_start:
        raise RuntimeError(f"clip_end 必须大于 clip_start: {item}")

    clipped_dir = download_dir / "clipped"
    clipped_dir.mkdir(parents=True, exist_ok=True)
    out_path = clipped_dir / f"{item['id']}_{int(round(clip_start * 10)):05d}_{int(round(clip_end * 10)):05d}.mp4"
    if out_path.exists():
        return out_path

    duration = clip_end - clip_start
    res = run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{clip_start:.3f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration:.3f}",
            "-vf",
            "fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout or f"裁剪失败: {source_path}")
    if not out_path.exists():
        raise FileNotFoundError(out_path)
    return out_path


def ffprobe_json(path: Path) -> dict:
    res = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,channels,sample_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout or f"ffprobe 失败: {path}")
    return json.loads(res.stdout)


def validate_source(path: Path) -> dict:
    data = ffprobe_json(path)
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError(f"缺少视频流: {path}")
    if not audio:
        raise RuntimeError(f"缺少音频流: {path}")
    if duration <= 1 or duration >= 60:
        raise RuntimeError(f"时长不符合要求（需小于 60 秒）: {path} -> {duration:.3f}s")
    return {
        "duration": round(duration, 3),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "audio_channels": int(audio.get("channels") or 0),
    }


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


def create_project(base_url: str, source: Path, source_item: dict, source_meta: dict, variant: dict) -> dict:
    payload = {
        "name": f"{source_item['label']}-{variant['name']}",
        "aspect_ratio": variant["aspect_ratio"],
        "target_style": "modern_talking_head",
        "target_duration": 120,
        "output_language": "zh",
        "layout_variant": variant["layout_variant"],
        "content_category": source_item["category"],
        "generate_draft": False,
        "keep_hyperframes": True,
    }
    res = requests.post(f"{base_url}/api/projects", json=payload, timeout=30)
    res.raise_for_status()
    project = res.json()
    project_id = project["id"]
    print(f"[创建] {project_id} {payload['name']}")

    note = (
        f"{source_item['note']} 完整保留整条原视频，禁止截短、冻结尾帧或循环。"
        f" 当前源视频时长 {source_meta['duration']:.3f} 秒。"
    )
    if source_meta.get("clip_start") is not None and source_meta.get("clip_end") is not None:
        note += f" 该源片来自原视频 {source_meta['clip_start']:.3f}s - {source_meta['clip_end']:.3f}s 的连续片段。"
    with source.open("rb") as fp:
        upload = requests.post(
            f"{base_url}/api/projects/{project_id}/assets/upload",
            files={"file": (source.name, fp, "video/mp4")},
            data={"user_label": source_item["label"], "user_note": note},
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
        "name": payload["name"],
        "variant": variant,
        "version": version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 4 个外部口播视频并按项目 API 流程跑 16 个版式任务")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--config",
        default="configs/online_talking_heads_20260618.json",
        help="在线源视频配置 JSON",
    )
    parser.add_argument("--download-dir", default="temp_sources/online_batch")
    parser.add_argument("--out", default="outputs/online_batch_results_20260618.json")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    download_dir = Path(args.download_dir).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    items = json.loads(config_path.read_text(encoding="utf-8"))

    results: list[dict] = []
    for item in items:
        raw_source_path, raw_meta = ensure_download(item, download_dir)
        source_path = maybe_clip_source(item, raw_source_path, download_dir)
        source_meta = validate_source(source_path)
        source_meta.update(
            {
                "title": raw_meta.get("title"),
                "channel": raw_meta.get("channel"),
                "webpage_url": raw_meta.get("webpage_url") or item["source_url"],
                "original_source_file": str(raw_source_path),
            }
        )
        if item.get("clip_end") not in (None, ""):
            source_meta["clip_start"] = float(item.get("clip_start") or 0.0)
            source_meta["clip_end"] = float(item["clip_end"])
        source_results = []
        for variant in MATRIX:
            source_results.append(create_project(args.base_url, source_path, item, source_meta, variant))
        results.append(
            {
                "source": item,
                "source_file": str(source_path),
                "source_meta": source_meta,
                "results": source_results,
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出 {out_path}")


if __name__ == "__main__":
    main()
