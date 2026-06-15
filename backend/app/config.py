from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = ROOT / "uploads"
OUTPUTS_DIR = ROOT / "outputs"
WORKSPACES_DIR = ROOT / "workspaces"
DB_PATH = ROOT / "backend" / "framecraft.db"
LOCAL_PATHS = ROOT / "config" / "local.paths.json"
VECTCUT_DIR = ROOT / "vendor" / "VectCutAPI"
ASR_VENV_PYTHON = ROOT / "vendor" / "asr-venv" / "Scripts" / "python.exe"
NODE_EXE = Path(
    r"C:\Users\ZHOU\AppData\Local\Programs\node-v22.20.0-win-x64\node.exe"
)
HYPERFRAMES_CLI = ROOT / "node_modules" / "hyperframes" / "dist" / "cli.js"
CHROME_EXE = ROOT / "chrome" / "win64-149.0.7827.115" / "chrome-win64" / "chrome.exe"

for d in (UPLOADS_DIR, OUTPUTS_DIR, WORKSPACES_DIR):
    d.mkdir(parents=True, exist_ok=True)


def load_local_paths() -> dict:
    if LOCAL_PATHS.exists():
        return json.loads(LOCAL_PATHS.read_text(encoding="utf-8"))
    return {}


LOCAL = load_local_paths()
JIANYING_DRAFT_DIR = Path(
    LOCAL.get("jianying", {}).get(
        "draft_dir",
        r"C:\Users\ZHOU\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft",
    )
)
