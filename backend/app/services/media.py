from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from ..config import ROOT
from ..utils import run_cmd, write_json


def probe_media(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = run_cmd(cmd)
    if result.returncode != 0:
        return {"duration": None, "width": None, "height": None, "has_video": False, "has_audio": False}
    data = json.loads(result.stdout or "{}")
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    width = height = None
    has_video = has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and width is None:
            width = int(stream.get("width") or 0) or None
            height = int(stream.get("height") or 0) or None
            has_video = True
        if stream.get("codec_type") == "audio":
            has_audio = True
    return {
        "duration": duration or None,
        "width": width,
        "height": height,
        "has_video": has_video,
        "has_audio": has_audio,
    }


def extract_audio(video_path: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out_path)])
    return out_path


def extract_thumbnail(video_path: Path, out_path: Path, at_sec: float = 1.0) -> Path | None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_cmd(
        ["ffmpeg", "-y", "-ss", str(at_sec), "-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(out_path)]
    )
    return out_path if result.returncode == 0 and out_path.exists() else None


def extract_keyframes(video_path: Path, out_dir: Path, every_sec: float = 2.0, max_frames: int = 8) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = probe_media(video_path)
    duration = meta.get("duration") or 10
    frames: list[Path] = []
    count = min(max_frames, max(1, int(duration / every_sec)))
    for i in range(count):
        t = min(duration - 0.1, i * every_sec + 0.5)
        out = out_dir / f"frame_{i:03d}.jpg"
        run_cmd(["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path), "-frames:v", "1", "-q:v", "3", str(out)])
        if out.exists():
            frames.append(out)
    return frames


def image_thumbnail(image_path: Path, out_path: Path, size: tuple[int, int] = (320, 180)) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as img:
        img.thumbnail(size)
        img.save(out_path, format="JPEG", quality=85)
    return out_path


def describe_image_basic(path: Path) -> str:
    with Image.open(path) as img:
        w, h = img.size
        mode = img.mode
    return f"图片 {path.name}，分辨率 {w}x{h}，模式 {mode}"


def describe_frame_basic(path: Path) -> str:
    return describe_image_basic(path)
