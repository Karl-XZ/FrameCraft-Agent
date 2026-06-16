from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = "未命名项目"
    aspect_ratio: str = "9:16"
    target_style: str = "modern_talking_head"
    target_duration: int = 60
    output_language: str = "zh"        # zh | en | bilingual
    generate_draft: bool = True
    keep_hyperframes: bool = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    aspect_ratio: str | None = None
    target_style: str | None = None
    target_duration: int | None = None
    output_language: str | None = None
    generate_draft: bool | None = None
    keep_hyperframes: bool | None = None
    status: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    status: str
    aspect_ratio: str
    target_style: str
    target_duration: int
    output_language: str = "zh"
    generate_draft: bool = True
    keep_hyperframes: bool = True
    current_version_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetUpdate(BaseModel):
    user_label: str | None = None
    user_note: str | None = None
    must_use: bool | None = None
    priority: int | None = None


class AssetOut(BaseModel):
    id: str
    project_id: str
    file_name: str
    file_type: str
    mime_type: str
    size: int
    duration: float | None
    width: int | None
    height: int | None
    user_label: str
    user_note: str
    must_use: bool
    priority: int
    analysis_status: str
    thumbnail_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    progress: float
    current_step: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class VersionOut(BaseModel):
    id: str
    project_id: str
    version_number: int
    status: str
    preview_url: str | None = None
    draft_url: str | None = None
    timeline_url: str | None = None
    subtitles_url: str | None = None
    cover_url: str | None = None
    publish_copy_url: str | None = None
    hyperframes_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatIn(BaseModel):
    message: str
    apply: bool = True   # False = 仅生成修改方案供用户确认（接受/撤销）


class ChatOut(BaseModel):
    id: str
    role: str
    content: str
    patch: dict[str, Any] | None = None
    job_id: str | None = None
    status: str = "applied"   # applied | proposed | rejected
    created_at: datetime


class ApplyPatchIn(BaseModel):
    patch: dict[str, Any]


class ModelSettings(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    text_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o-mini"
    asr_model: str = "faster-whisper-base"
    base_url: str = ""


class AnalyzeRequest(BaseModel):
    strategy: str = "complete"   # complete | fast
    platform: str = "douyin"


class GenerateRequest(BaseModel):
    confirm_plan: bool = True
    resolution: str = "1080p"    # 720p | 1080p | 4K旗舰版
    fps: int = 30
    strategy: str = "complete"


class EditPlanOut(BaseModel):
    video_concept: str
    target_duration: int
    style: str
    hook: str
    subtitle_style: str
    bgm_note: str
    scenes: list[dict[str, Any]]
    broll_plan: list[dict[str, Any]]
