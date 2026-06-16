from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = ROOT / "uploads"
OUTPUTS_DIR = ROOT / "outputs"
WORKSPACES_DIR = ROOT / "workspaces"
DB_PATH = ROOT / "backend" / "framecraft.db"
LOCAL_PATHS = ROOT / "config" / "local.paths.json"
VECTCUT_DIR = ROOT / "vendor" / "VectCutAPI"
ASR_VENV_PYTHON = ROOT / "vendor" / "asr-venv" / "Scripts" / "python.exe"
RESOURCES_DIR = ROOT / "resources"
WORKFLOWS_DIR = ROOT / "workflows"
TALKING_HEAD_DIR = WORKFLOWS_DIR / "talking-head"
STUDENT_KIT_DIR = RESOURCES_DIR / "hyperframes-student-kit"

for d in (UPLOADS_DIR, OUTPUTS_DIR, WORKSPACES_DIR):
    d.mkdir(parents=True, exist_ok=True)


def load_local_paths() -> dict:
    if LOCAL_PATHS.exists():
        try:
            return json.loads(LOCAL_PATHS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


LOCAL = load_local_paths()
_TOOLS = LOCAL.get("tools", {})
_JY = LOCAL.get("jianying", {})


def _resolve_node_exe() -> Path:
    """Locate node.exe without hardcoding a username."""
    candidates = []
    cfg = _TOOLS.get("node_exe")
    if cfg:
        candidates.append(Path(cfg))
    env = os.getenv("NODE_EXE")
    if env:
        candidates.append(Path(env))
    found = shutil.which("node")
    if found:
        candidates.append(Path(found))
    local_programs = Path(os.getenv("LOCALAPPDATA", "")) / "Programs"
    if local_programs.exists():
        for d in local_programs.glob("node-v*"):
            exe = d / "node.exe"
            if exe.exists():
                candidates.append(exe)
    candidates.append(Path(r"C:\Program Files\nodejs\node.exe"))
    for c in candidates:
        if c and c.exists():
            return c
    return Path("node")


def _resolve_chrome_exe() -> Path:
    cfg = _TOOLS.get("chromium_exe")
    if cfg:
        p = Path(cfg)
        if not p.is_absolute():
            p = ROOT / cfg
        if p.exists():
            return p
    chrome_root = ROOT / "chrome"
    if chrome_root.exists():
        for exe in chrome_root.glob("win64-*/chrome-win64/chrome.exe"):
            return exe
    return Path("")


NODE_EXE = _resolve_node_exe()
CHROME_EXE = _resolve_chrome_exe()
HYPERFRAMES_CLI = ROOT / "node_modules" / "hyperframes" / "dist" / "cli.js"

JIANYING_DRAFT_DIR = Path(
    _JY.get(
        "draft_dir",
        os.getenv("JIANYING_DRAFT_DIR", str(ROOT / "outputs" / "_jianying_inbox")),
    )
)
IS_CAPCUT_ENV = bool(_JY.get("is_capcut_env", False))

# Upload limits (requirements 6.2.2)
MAX_VIDEO_BYTES = 1024 * 1024 * 1024          # 1 GB
MAX_IMAGE_BYTES = 50 * 1024 * 1024            # 50 MB
MAX_AUDIO_BYTES = 200 * 1024 * 1024           # 200 MB
MAX_ASSETS_PER_PROJECT = 30
MAX_PROJECT_TOTAL_BYTES = 3 * 1024 * 1024 * 1024   # 3 GB

# 比赛 Demo 内置 DashScope / Qwen 配置（评委无需手动填 Key）
TEST_LLM_DEFAULTS = {
    "provider": "qwen",
    "api_key": "sk-f4fa1e490f78469eb4433266814d28d2",
    "text_model": "qwen-max",
    "vision_model": "qwen-vl-max",
    "asr_model": "base",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}
