from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..models import Asset
from ..utils import write_json
from .asr_service import build_cut_candidates, build_highlights, transcribe_audio
from .llm import vision_describe
from .media import extract_audio, extract_keyframes, extract_thumbnail, image_thumbnail, probe_media


def classify_label(asset: Asset) -> str:
    if asset.user_label:
        return asset.user_label
    ft = asset.file_type
    if ft == "video":
        note = asset.user_note.lower()
        if any(k in note for k in ("口播", "talking", "主讲", "人脸")):
            return "口播视频"
        return "B-roll"
    if ft == "image":
        if "logo" in asset.file_name.lower() or "logo" in asset.user_note.lower():
            return "LOGO"
        return "图片"
    if ft == "audio":
        return "音频"
    return asset.user_label or "素材"


def analyze_project_assets(db: Session, project_id: str, on_step) -> dict:
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    work_dir = OUTPUTS_DIR / project_id / "analysis"
    work_dir.mkdir(parents=True, exist_ok=True)

    talk_asset = None
    for a in assets:
        a.user_label = classify_label(a)
        if a.user_label == "口播视频" and talk_asset is None:
            talk_asset = a

    manifest_assets = []
    asr_data = None

    if talk_asset:
        on_step("提取口播音频", 10)
        audio_path = work_dir / f"{talk_asset.id}.wav"
        extract_audio(Path(talk_asset.file_path), audio_path)
        on_step("Whisper 转录", 25)
        asr_data = transcribe_audio(audio_path, work_dir / "asr")
        on_step("分析口播结构", 40)
        write_json(work_dir / "cut_candidates.json", build_cut_candidates(asr_data["segments"]))
        write_json(work_dir / "highlight_sentences.json", build_highlights(asr_data["segments"]))

    for idx, asset in enumerate(assets):
        p = Path(asset.file_path)
        analysis_dir = work_dir / asset.id
        analysis_dir.mkdir(parents=True, exist_ok=True)
        meta = probe_media(p) if asset.file_type in {"video", "audio"} else {}
        summary = ""
        recommended = []

        if asset.file_type == "video" and asset.id != (talk_asset.id if talk_asset else None):
            on_step("抽帧理解 B-roll", 45 + int(20 * (idx + 1) / max(len(assets), 1)))
            frames = extract_keyframes(p, analysis_dir / "frames")
            if frames:
                summary = vision_describe(db, frames[0], asset.user_note)
            else:
                summary = f"视频素材 {asset.file_name}"
            recommended = ["broll"]
            thumb = extract_thumbnail(p, analysis_dir / "thumb.jpg")
            if thumb:
                asset.thumbnail_path = str(thumb)
        elif asset.file_type == "image":
            on_step("匹配素材备注", 70)
            summary = vision_describe(db, p, asset.user_note)
            recommended = ["cover", "illustration", "logo"] if asset.user_label == "LOGO" else ["broll", "illustration"]
            thumb = image_thumbnail(p, analysis_dir / "thumb.jpg")
            asset.thumbnail_path = str(thumb)
        elif asset.file_type == "audio":
            summary = f"音频素材 {asset.file_name}，备注：{asset.user_note or '无'}"
            recommended = ["bgm", "sfx"]
        elif asset.id == (talk_asset.id if talk_asset else None):
            summary = "主口播视频轨道"
            recommended = ["main_speech_track"]
            thumb = extract_thumbnail(p, analysis_dir / "thumb.jpg", 0.5)
            if thumb:
                asset.thumbnail_path = str(thumb)

        analysis = {
            "asset_id": asset.id,
            "auto_summary": summary,
            "recommended_usage": recommended,
            "meta": meta,
        }
        write_json(analysis_dir / "analysis.json", analysis)
        asset.analysis_json_path = str(analysis_dir / "analysis.json")
        asset.analysis_status = "completed"
        if meta.get("duration"):
            asset.duration = meta["duration"]
        if meta.get("width"):
            asset.width = meta["width"]
            asset.height = meta.get("height")

        manifest_assets.append(
            {
                "asset_id": asset.id,
                "file_path": asset.file_path,
                "type": asset.file_type,
                "user_label": asset.user_label,
                "user_note": asset.user_note,
                "must_use": asset.must_use,
                "duration": asset.duration,
                "resolution": [asset.width, asset.height] if asset.width else None,
                "auto_summary": summary,
                "recommended_usage": recommended,
            }
        )

    on_step("生成剪辑方案", 90)
    manifest = {"project_id": project_id, "assets": manifest_assets, "asr": asr_data}
    write_json(work_dir / "asset_manifest.json", manifest)
    db.commit()
    return manifest
