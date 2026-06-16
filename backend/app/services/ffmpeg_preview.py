"""已废弃：禁止用于成片预览。

帧造 Agent 要求 preview.mp4 必须由 HyperFrames 渲染（hyperframes_service.render_preview）。
此模块保留仅供历史参考，不得在 job_runner / agent_tools 中调用。
"""
from __future__ import annotations

raise ImportError(
    "ffmpeg_preview 已禁用：成片必须由 Agent 通过 HyperFrames 渲染，禁止 FFmpeg 拼接兜底。"
)
