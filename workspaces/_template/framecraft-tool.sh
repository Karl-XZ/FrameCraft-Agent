#!/usr/bin/env bash
# FrameCraft Agent 工具包装器 — 从 workspace 根目录调用
set -euo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$WS/../../backend"
PY="$BACKEND/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$BACKEND/venv/Scripts/python.exe"
fi

cd "$BACKEND"

if [[ -f "$WS/framecraft-env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$WS/framecraft-env.sh"
fi

if [[ ! -x "$PY" && ! -f "$PY" ]]; then
  printf '%s\n' '{"ok": false, "error": "backend venv python not found"}' >&2
  exit 1
fi

"$PY" -m app.services.agent_tools "$@"
