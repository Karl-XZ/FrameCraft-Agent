#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/setup-deps.sh
HOST="${FRAMECRAFT_BACKEND_HOST:-0.0.0.0}"
PORT="${FRAMECRAFT_BACKEND_PORT:-8022}"

echo "[FrameCraft] Starting single-Codex-agent backend on http://${HOST}:${PORT}"
PYTHONPATH=backend exec backend/venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
