#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def ffprobe_json(path: Path) -> dict:
    res = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout or f"ffprobe 失败: {path}")
    return json.loads(res.stdout)


def extract_frame(video_path: Path, second: float, out_path: Path) -> None:
    res = run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{second:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(out_path),
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout or f"抽帧失败: {video_path} @ {second}")


def frame_diff_score(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        if ia.size != ib.size:
            ib = ib.resize(ia.size)
        diff = ImageChops.difference(ia.convert("RGB"), ib.convert("RGB"))
        stat = ImageStat.Stat(diff)
        return float(sum(stat.mean) / len(stat.mean))


def sample_motion_score(video_path: Path, duration: float) -> dict:
    if duration <= 1.0:
        return {"samples": [], "diffs": [], "min_diff": 0.0}

    sample_points = sorted(
        {
            max(0.2, min(duration - 0.2, duration * 0.08)),
            max(0.2, min(duration - 0.2, duration * 0.45)),
            max(0.2, min(duration - 0.2, duration * 0.82)),
        }
    )
    with tempfile.TemporaryDirectory(prefix="framecraft-qa-") as td:
        temp_dir = Path(td)
        frame_paths: list[Path] = []
        for idx, sec in enumerate(sample_points, start=1):
            frame_path = temp_dir / f"frame_{idx:03d}.jpg"
            extract_frame(video_path, sec, frame_path)
            frame_paths.append(frame_path)
        diffs = [
            round(frame_diff_score(frame_paths[i], frame_paths[i + 1]), 3)
            for i in range(len(frame_paths) - 1)
        ]
    return {
        "samples": [round(x, 3) for x in sample_points],
        "diffs": diffs,
        "min_diff": min(diffs) if diffs else 0.0,
    }


def subtitle_count(timeline_path: Path) -> int:
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    return len([item for item in timeline.get("items", []) if item.get("type") == "subtitle"])


def analyze_version(outputs_root: Path, project_id: str, version_id: str, expected_duration: float) -> dict:
    version_dir = outputs_root / project_id / version_id
    preview_path = version_dir / "preview.mp4"
    timeline_path = version_dir / "unified_timeline.json"

    errors: list[str] = []
    warnings: list[str] = []
    if not preview_path.exists():
        errors.append(f"缺少 preview.mp4: {preview_path}")
        return {
            "project_id": project_id,
            "version_id": version_id,
            "ok": False,
            "errors": errors,
            "warnings": warnings,
        }
    if not timeline_path.exists():
        errors.append(f"缺少 unified_timeline.json: {timeline_path}")
        return {
            "project_id": project_id,
            "version_id": version_id,
            "ok": False,
            "errors": errors,
            "warnings": warnings,
        }

    probe = ffprobe_json(preview_path)
    streams = probe.get("streams") or []
    duration = float((probe.get("format") or {}).get("duration") or 0.0)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        errors.append("preview 缺少视频流")
    if not audio:
        errors.append("preview 缺少音频流")
    if expected_duration > 1.0 and duration < expected_duration * 0.95:
        errors.append(f"preview 时长不足: {duration:.3f}s / 预期 {expected_duration:.3f}s")

    motion = sample_motion_score(preview_path, duration)
    if motion["min_diff"] < 1.5:
        errors.append(f"抽帧差异过小，疑似静帧或冻结: diffs={motion['diffs']}")
    elif motion["min_diff"] < 4.0:
        warnings.append(f"抽帧差异偏低，请人工复核: diffs={motion['diffs']}")

    subtitles = subtitle_count(timeline_path)
    if subtitles <= 0:
        errors.append("timeline 中没有 subtitle items")

    return {
        "project_id": project_id,
        "version_id": version_id,
        "ok": not errors,
        "duration": round(duration, 3),
        "expected_duration": round(expected_duration, 3),
        "resolution": [int(video.get("width") or 0), int(video.get("height") or 0)] if video else None,
        "subtitle_count": subtitles,
        "motion": motion,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="对批量生成的 FrameCraft 成片做机械 QA")
    parser.add_argument("--results", required=True, help="run_online_codex_batch.py 输出的 results JSON")
    parser.add_argument("--outputs-root", default="outputs", help="项目 outputs 根目录")
    parser.add_argument("--out", help="可选，写出 QA JSON")
    args = parser.parse_args()

    results_path = Path(args.results).expanduser().resolve()
    outputs_root = Path(args.outputs_root).expanduser().resolve()
    if not results_path.exists():
        raise SystemExit(f"results JSON 不存在: {results_path}")
    rows = json.loads(results_path.read_text(encoding="utf-8"))

    report: list[dict] = []
    failed = 0
    for row in rows:
        expected_duration = float((row.get("source_meta") or {}).get("duration") or 0.0)
        source = row.get("source") or {}
        for result in row.get("results") or []:
            version = result.get("version") or {}
            item = analyze_version(
                outputs_root,
                result["project_id"],
                version["id"],
                expected_duration,
            )
            item["source_id"] = source.get("id")
            item["source_label"] = source.get("label")
            item["variant_name"] = (result.get("variant") or {}).get("name")
            report.append(item)
            status = "PASS" if item["ok"] else "FAIL"
            print(
                f"[{status}] {item['source_id']} {item['variant_name']} "
                f"{item.get('resolution')} {item.get('duration')}s subs={item.get('subtitle_count')} "
                f"diffs={item.get('motion', {}).get('diffs')}"
            )
            if item["warnings"]:
                print("  warnings:", " | ".join(item["warnings"]))
            if item["errors"]:
                print("  errors:", " | ".join(item["errors"]))
                failed += 1

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写出 {out_path}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
