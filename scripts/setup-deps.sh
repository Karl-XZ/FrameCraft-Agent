#!/usr/bin/env bash
# FrameCraft Agent — 单 Codex agent 新后端依赖安装（macOS/Linux）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() {
  printf '\n=== %s ===\n' "$1"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

ensure_node_pm() {
  if command -v npm >/dev/null 2>&1; then
    echo "npm"
    return
  fi
  if command -v bun >/dev/null 2>&1; then
    echo "bun"
    return
  fi
  echo "Neither npm nor bun is available" >&2
  exit 1
}

PM="$(ensure_node_pm)"
need_cmd python3

say "Backend Python venv"
if [[ ! -x backend/venv/bin/python ]]; then
  python3 -m venv backend/venv
fi
backend/venv/bin/python -m pip install -q --upgrade pip
backend/venv/bin/python -m pip install -q -r backend/requirements.txt
PYTHONPATH=backend backend/venv/bin/python -c "import app.main; print('OK single-agent backend deps')"

say "Node / HyperFrames deps"
if [[ "$PM" == "npm" ]]; then
  npm install
  (cd framecraft-agent && npm install)
else
  bun install
  (cd framecraft-agent && bun install)
fi

say "Codex CLI"
if command -v codex >/dev/null 2>&1; then
  codex --version
elif [[ -x /Applications/Codex.app/Contents/Resources/codex ]]; then
  /Applications/Codex.app/Contents/Resources/codex --version
else
  echo "WARN Codex CLI not found. Set CODEX_BIN or install Codex app." >&2
fi

say "Done"
echo "Run scripts/verify-env.sh to check all components."
