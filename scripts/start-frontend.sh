#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/framecraft-agent"

HOST="${FRAMECRAFT_FRONTEND_HOST:-0.0.0.0}"
PORT="${FRAMECRAFT_FRONTEND_PORT:-5174}"

if command -v npm >/dev/null 2>&1; then
  exec npm run dev -- --host "$HOST" --port "$PORT"
fi

if command -v bun >/dev/null 2>&1; then
  exec bun run dev -- --host "$HOST" --port "$PORT"
fi

echo "Missing npm or bun" >&2
exit 1
