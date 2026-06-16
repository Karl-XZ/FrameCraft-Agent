"""FrameCraft 工作区路径绑定：build 脚本在 Agent 内运行时读取环境变量。"""
from __future__ import annotations

import os
from pathlib import Path


def workspace_active() -> bool:
    return bool(os.environ.get("FRAMECRAFT_WF_WORKSPACE"))


def workspace_root(default: Path) -> Path:
    ws = os.environ.get("FRAMECRAFT_WF_WORKSPACE")
    return (Path(ws) / "hyperframes") if ws else default


def input_dir(default: Path) -> Path:
    ws = os.environ.get("FRAMECRAFT_WF_WORKSPACE")
    return (Path(ws) / "input") if ws else default


def talk_video(default: Path) -> Path:
    custom = os.environ.get("FRAMECRAFT_WF_INPUT")
    if custom:
        return Path(custom)
    ws = os.environ.get("FRAMECRAFT_WF_WORKSPACE")
    return (Path(ws) / "input" / "talk.mp4") if ws else default


def student_kit(default: Path) -> Path:
    sk = os.environ.get("FRAMECRAFT_WF_STUDENT_KIT")
    return Path(sk) if sk else default


def duration(default: float) -> float:
    d = os.environ.get("FRAMECRAFT_WF_DUR")
    return float(d) if d else default
