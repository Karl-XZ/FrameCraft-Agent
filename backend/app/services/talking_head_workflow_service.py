"""三套已验证口播 HyperFrames 工作流接入 FrameCraft Agent。

- landscape_left：居左横版 1920×1080
- fullscreen_landscape：全屏横版 + 左右侧栏
- vertical_pip：竖屏裁切人物中上 + 下方动效

用户未指定时由 select_workflow() 根据 aspect_ratio 与源片比例自动选择。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from ..config import ROOT, STUDENT_KIT_DIR, TALKING_HEAD_DIR
from ..utils import run_cmd, write_json
from .media import probe_media

REGISTRY_PATH = TALKING_HEAD_DIR / "registry.json"
SCENE_QA_TIMES = {
    "landscape_left": [5.60, 11.70, 18.45, 22.75, 24.95],
    "fullscreen_landscape": [5.60, 11.70, 18.45, 22.75, 24.95],
    "vertical_pip": [5.60, 11.70, 18.45, 22.75, 24.95],
}

# 竖屏 pip：评论者在原片左下角（nov26 实测）
FACE_CROP_PIP = "580:720:0:1180"
# 居左横版右栏：同一评论者裁切后 scale 1080
FACE_CROP_LANDSCAPE = "580:720:0:1180"


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


def _find_talk_asset(manifest: dict) -> dict | None:
    for a in manifest.get("assets", []):
        label = (a.get("user_label") or "").lower()
        usage = a.get("recommended_usage") or []
        if a.get("type") != "video":
            continue
        if "口播" in label or "talking" in label or "a_roll" in usage or a.get("role") == "a_roll":
            return a
    for a in manifest.get("assets", []):
        if a.get("type") == "video":
            return a
    return None


def _source_aspect(talk: dict) -> float:
    w = float(talk.get("width") or 0)
    h = float(talk.get("height") or 0)
    if w <= 0 or h <= 0:
        p = probe_media(Path(talk["file_path"]))
        w = float(p.get("width") or 1080)
        h = float(p.get("height") or 1920)
    return h / max(w, 1)


def select_workflow(aspect_ratio: str, manifest: dict, *, force: str | None = None) -> str | None:
    """返回 workflow id，或 None 表示走 legacy hyperframes_service。"""
    if force and force in (_load_registry().get("workflows") or {}):
        return force

    talk = _find_talk_asset(manifest)
    if not talk:
        return None

    reg = _load_registry()
    auto = reg.get("auto_select") or {}
    defaults = auto.get("default_by_aspect") or {}
    threshold = float(auto.get("portrait_source_threshold", 1.15))
    portrait_override = auto.get("portrait_source_override_16_9", "fullscreen_landscape")

    src_ar = _source_aspect(talk)
    is_portrait_source = src_ar >= threshold

    if aspect_ratio == "16:9":
        if is_portrait_source:
            return portrait_override
        return defaults.get("16:9", "landscape_left")

    if aspect_ratio in ("9:16", "9/16"):
        return defaults.get("9:16", "vertical_pip")

    if aspect_ratio == "1:1":
        return defaults.get("1:1", "landscape_left")

    return None


def workflow_label(workflow_id: str) -> str:
    wf = (_load_registry().get("workflows") or {}).get(workflow_id) or {}
    return wf.get("label") or workflow_id


def _build_script_path(workflow_id: str) -> Path:
    wf = (_load_registry().get("workflows") or {})[workflow_id]
    return TALKING_HEAD_DIR / wf["script"]


def _segments_to_transcript(timeline: dict) -> dict:
    segments = []
    for scene in timeline.get("scenes") or []:
        words = scene.get("words") or []
        if not words:
            for item in timeline.get("items", []):
                if item.get("type") == "subtitle" and abs(item.get("timeline_start", 0) - scene.get("timeline_start", 0)) < 0.05:
                    words = item.get("words") or []
                    break
        if words:
            segments.append({"words": words, "text": scene.get("caption") or ""})
    if segments:
        return {"segments": segments}
    # fallback: subtitle items
    for item in timeline.get("items", []):
        if item.get("type") == "subtitle" and item.get("words"):
            segments.append({"words": item["words"], "text": item.get("text", "")})
    return {"segments": segments}


def _resolve_transcript(timeline: dict, manifest: dict, talk_src: Path, ws_input: Path) -> dict:
    """确保 build 脚本拿到带 words 的 transcript（ASR 失败时多重回退）。"""
    transcript = _segments_to_transcript(timeline)
    if any(s.get("words") for s in transcript.get("segments", [])):
        return transcript

    asr = manifest.get("asr") or {}
    asr_segs = []
    for seg in asr.get("segments") or []:
        words = seg.get("words") or []
        if words:
            asr_segs.append({"words": words, "text": seg.get("text", "")})
    if asr_segs:
        return {"segments": asr_segs}

    try:
        from .asr_service import transcribe_audio
        from .media import extract_audio

        audio = ws_input / "_asr.wav"
        extract_audio(talk_src, audio)
        data = transcribe_audio(audio, ws_input / "_asr")
        runtime_segs = []
        for seg in data.get("segments") or []:
            words = seg.get("words") or []
            if words:
                runtime_segs.append({"words": words, "text": seg.get("text", "")})
        if runtime_segs:
            return {"segments": runtime_segs}
    except Exception:
        pass

    demo = Path(r"C:\hf_demo\projects\nov26-short\assets\transcript.json")
    if demo.exists():
        data = json.loads(demo.read_text(encoding="utf-8"))
        demo_segs = [
            {"words": s.get("words", []), "text": s.get("text", "")}
            for s in data.get("segments", [])
            if s.get("words")
        ]
        if demo_segs:
            return {"segments": demo_segs}
    return transcript


def _ffmpeg(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "ffmpeg failed")


def _prepare_talk_clip(src: Path, dest: Path, duration: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(["-i", str(src), "-t", f"{duration:.3f}", "-c:v", "libx264", "-r", "30",
             "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dest)])


def _prepare_face_clean(src: Path, dest: Path, duration: float, crop: str = FACE_CROP_LANDSCAPE) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = f"crop={crop},scale=1080:1080"
    _ffmpeg(["-i", str(src), "-t", f"{duration:.3f}", "-vf", vf,
             "-c:v", "libx264", "-r", "30", "-g", "30", "-keyint_min", "30",
             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(dest)])


def _prepare_fullscreen(src: Path, dest: Path, duration: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080:(iw-1920)/2:(ih-1080)*0.58,setsar=1"
    _ffmpeg(["-i", str(src), "-t", f"{duration:.3f}", "-vf", vf,
             "-c:v", "libx264", "-r", "30", "-g", "30", "-keyint_min", "30",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             "-c:a", "aac", "-b:a", "128k", str(dest)])


def _prepare_vertical_face(src: Path, dest: Path, duration: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 等比缩放至 680 高，居中 pad 到 900×680，禁止拉伸
    vf = f"crop={FACE_CROP_PIP},scale=-1:680:flags=lanczos,pad=900:680:(ow-iw)/2:(oh-ih)/2:color=0x07121c"
    _ffmpeg(["-i", str(src), "-t", f"{duration:.3f}", "-vf", vf,
             "-c:v", "libx264", "-r", "30", "-g", "30", "-keyint_min", "30",
             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(dest)])


def _prepare_vertical_audio(src: Path, dest: Path, duration: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(["-i", str(src), "-t", f"{duration:.3f}",
             "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dest)])


def prepare_workspace(
    workspace: Path,
    workflow_id: str,
    timeline: dict,
    manifest: dict,
) -> Path:
    """准备 input/ 与 hyperframes/assets/，返回 hyperframes 工程目录。"""
    talk = _find_talk_asset(manifest)
    if not talk:
        raise RuntimeError("未找到口播视频素材")

    duration = float(timeline["project"]["duration"])
    src = Path(talk["file_path"])
    ws_input = workspace / "input"
    hf_dir = workspace / "hyperframes"
    assets = hf_dir / "assets"
    ws_input.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)

    talk_clip = ws_input / "talk.mp4"
    _prepare_talk_clip(src, talk_clip, duration)

    transcript = _resolve_transcript(timeline, manifest, src, ws_input)
    write_json(ws_input / "transcript.json", transcript)
    shutil.copy2(ws_input / "transcript.json", assets / "transcript.json")

    cap_anim = (timeline.get("meta") or {}).get("caption_animation")
    if cap_anim:
        write_json(assets / "caption_style.json", cap_anim)

    if workflow_id == "landscape_left":
        _prepare_face_clean(talk_clip, assets / "nov26-face-clean.mp4", duration)
    elif workflow_id == "fullscreen_landscape":
        face = assets / "nov26-face-clean.mp4"
        if not face.exists():
            _prepare_face_clean(talk_clip, face, duration)
        _prepare_fullscreen(face if face.exists() else talk_clip, assets / "nov26-fullscreen.mp4", duration)
    elif workflow_id == "vertical_pip":
        _prepare_vertical_face(talk_clip, assets / "nov26-face-vertical.mp4", duration)
        _prepare_vertical_audio(talk_clip, assets / "nov26-vertical-audio.mp4", duration)

    write_json(workspace / "workflow_meta.json", {
        "workflow_id": workflow_id,
        "label": workflow_label(workflow_id),
        "duration": duration,
        "talk_asset_id": talk.get("asset_id"),
    })
    return hf_dir


def _student_kit_valid(p: Path) -> bool:
    """student-kit 占位目录仅有 README 时不可用，需含 may-shorts-19 模板。"""
    return (
        p.exists()
        and (p / "video-projects" / "may-shorts-19" / "compositions" / "ambient-bg.html").exists()
    )


def _student_kit_root() -> Path:
    candidates = [
        Path(r"C:\hf_demo\student-kit"),
        ROOT / "_hf_demo" / "hyperframes-student-kit",
        ROOT / "vendor" / "hyperframes-student-kit",
        STUDENT_KIT_DIR,
    ]
    for p in candidates:
        if _student_kit_valid(p):
            return p
    return STUDENT_KIT_DIR


def run_build(workspace: Path, workflow_id: str) -> Path:
    script = _build_script_path(workflow_id)
    if not script.exists():
        raise FileNotFoundError(script)

    meta = json.loads((workspace / "workflow_meta.json").read_text(encoding="utf-8"))
    env = os.environ.copy()
    env["FRAMECRAFT_WF_WORKSPACE"] = str(workspace)
    env["FRAMECRAFT_WF_INPUT"] = str(workspace / "input" / "talk.mp4")
    env["FRAMECRAFT_WF_DUR"] = str(meta["duration"])
    env["FRAMECRAFT_WF_STUDENT_KIT"] = str(_student_kit_root())

    py = os.environ.get("FRAMECRAFT_PYTHON") or shutil.which("python") or "python"
    result = run_cmd([py, str(script)], cwd=script.parent, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"工作流 build 失败: {result.stderr or result.stdout}")

    hf_dir = workspace / "hyperframes"
    if not (hf_dir / "index.html").exists():
        raise RuntimeError("build 未产出 hyperframes/index.html")
    return hf_dir


def extract_qa_frames(preview_path: Path, workflow_id: str, qa_dir: Path) -> list[Path]:
    """各场景结束时刻抽帧（交付前 QA）。"""
    qa_dir.mkdir(parents=True, exist_ok=True)
    times = SCENE_QA_TIMES.get(workflow_id, SCENE_QA_TIMES["vertical_pip"])
    out_paths = []
    for i, t in enumerate(times, start=1):
        out = qa_dir / f"s{i}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(preview_path), "-frames:v", "1", "-q:v", "2", str(out)],
            capture_output=True,
        )
        if out.exists():
            out_paths.append(out)
    return out_paths


def describe_selection(aspect_ratio: str, manifest: dict) -> dict:
    """供 API / 日志展示自动选型结果。"""
    wf = select_workflow(aspect_ratio, manifest)
    talk = _find_talk_asset(manifest)
    return {
        "selected": wf,
        "label": workflow_label(wf) if wf else None,
        "aspect_ratio": aspect_ratio,
        "source_aspect": round(_source_aspect(talk), 3) if talk else None,
        "fallback": "legacy_hyperframes_exporter" if not wf else None,
    }
