from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import OUTPUTS_DIR
from ..models import Asset
from ..utils import write_json
from .asr_service import build_cut_candidates, build_highlights, transcribe_audio
from .llm import (
    classify_image_usage,
    ocr_image_with_meta,
    vision_describe_with_meta,
    vision_describe_frames_with_meta,
)
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


def _append_warning(warnings: list[dict], code: str, message: str, *, asset_id: str | None = None) -> None:
    item = {"code": code, "message": message}
    if asset_id:
        item["asset_id"] = asset_id
    warnings.append(item)


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
    analysis_warnings: list[dict] = []
    asr_data = None

    if talk_asset:
        on_step("提取口播音频", 10)
        audio_path = work_dir / f"{talk_asset.id}.wav"
        extract_audio(Path(talk_asset.file_path), audio_path)
        on_step("Whisper 转录", 25)
        try:
            asr_data = transcribe_audio(audio_path, work_dir / "asr")
            asr_data["degraded"] = False
            asr_data["degraded_reason"] = None
        except Exception as exc:
            reason = str(exc)[:300]
            on_step(f"ASR 失败：{reason[:80]}", 35)
            asr_data = {
                "language": "",
                "duration": 0,
                "text": "",
                "segments": [],
                "words": [],
                "degraded": True,
                "degraded_reason": reason,
            }
            write_json(work_dir / "asr" / "asr_result.json", asr_data)
            write_json(work_dir / "asr" / "transcript.json", {"text": "", "language": "", "degraded": True})
            write_json(work_dir / "asr" / "word_timestamps.json", [])
            write_json(work_dir / "asr" / "speech_segments.json", [])
            _append_warning(
                analysis_warnings,
                "asr_degraded",
                f"口播转录失败，成片将无逐词字幕。原因：{reason}",
                asset_id=talk_asset.id,
            )
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
        ocr_text = ""
        vision_status = "n/a"
        vision_error = None
        ocr_status = "n/a"
        ocr_error = None

        if asset.file_type == "video" and asset.id != (talk_asset.id if talk_asset else None):
            on_step("抽帧理解 B-roll", 45 + int(20 * (idx + 1) / max(len(assets), 1)))
            frames = extract_keyframes(p, analysis_dir / "frames")
            if frames:
                vis = vision_describe_frames_with_meta(db, frames, asset.user_note)
                summary = vis.text
                vision_status = vis.vision_status
                vision_error = vis.error
            else:
                summary = f"视频素材 {asset.file_name}（未能抽取关键帧）"
                vision_status = "unavailable"
                vision_error = "关键帧抽取失败"
            if vision_status != "vlm":
                _append_warning(
                    analysis_warnings,
                    "vision_degraded",
                    f"素材 {asset.file_name}：{vision_error or '视觉理解已降级'}",
                    asset_id=asset.id,
                )
            recommended = ["broll"]
            thumb = extract_thumbnail(p, analysis_dir / "thumb.jpg")
            if thumb:
                asset.thumbnail_path = str(thumb)
        elif asset.file_type == "image":
            on_step("匹配素材备注", 70 + int(12 * (idx + 1) / max(len(assets), 1)))
            vis = vision_describe_with_meta(db, p, asset.user_note)
            summary = vis.text
            vision_status = vis.vision_status
            vision_error = vis.error
            ocr = ocr_image_with_meta(db, p)
            ocr_text = ocr.text
            ocr_status = ocr.ocr_status
            ocr_error = ocr.error
            if vision_status != "vlm":
                _append_warning(
                    analysis_warnings,
                    "vision_degraded",
                    f"图片 {asset.file_name}：{vision_error or '视觉理解已降级'}",
                    asset_id=asset.id,
                )
            if ocr_status == "failed" and ocr_error:
                _append_warning(
                    analysis_warnings,
                    "ocr_failed",
                    f"图片 {asset.file_name} OCR 失败：{ocr_error}",
                    asset_id=asset.id,
                )
            recommended = classify_image_usage(asset.file_name, asset.user_label, ocr_text, summary)
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
            "ocr_text": ocr_text,
            "vision_status": vision_status,
            "vision_error": vision_error,
            "ocr_status": ocr_status,
            "ocr_error": ocr_error,
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
                "priority": asset.priority,
                "duration": asset.duration,
                "resolution": [asset.width, asset.height] if asset.width else None,
                "auto_summary": summary,
                "recommended_usage": recommended,
                "ocr_text": ocr_text,
                "vision_status": vision_status,
            }
        )

    on_step("匹配素材备注", 88)
    manifest = {
        "project_id": project_id,
        "assets": manifest_assets,
        "asr": asr_data,
        "analysis_warnings": analysis_warnings,
    }
    write_json(work_dir / "asset_manifest.json", manifest)
    db.commit()
    return manifest
