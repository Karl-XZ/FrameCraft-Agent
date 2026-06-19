#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== FrameCraft Agent Env Check ==="
echo "Root: $ROOT"
echo

for cmd in python3 git; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "OK  $cmd -> $(command -v "$cmd")"
  else
    echo "MISS $cmd"
  fi
done

if command -v node >/dev/null 2>&1; then
  echo "OK  node $(node --version)"
else
  echo "MISS node"
fi

if command -v npm >/dev/null 2>&1; then
  echo "OK  npm $(npm --version)"
elif command -v bun >/dev/null 2>&1; then
  echo "OK  bun $(bun --version)"
else
  echo "MISS npm/bun"
fi

if [[ -x backend/venv/bin/python ]]; then
  echo "OK  backend venv"
else
  echo "MISS backend venv"
fi

if [[ -f node_modules/hyperframes/dist/cli.js ]]; then
  echo "OK  hyperframes CLI"
elif [[ -f hyperframes-student-kit/node_modules/hyperframes/dist/cli.js ]]; then
  echo "OK  hyperframes CLI (student kit)"
else
  echo "MISS hyperframes CLI"
fi

for cmd in ffmpeg ffprobe; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "OK  $cmd -> $(command -v "$cmd")"
  else
    echo "WARN $cmd"
  fi
done

if command -v codex >/dev/null 2>&1; then
  echo "OK  codex $(codex --version)"
elif [[ -x /Applications/Codex.app/Contents/Resources/codex ]]; then
  echo "OK  codex $(/Applications/Codex.app/Contents/Resources/codex --version)"
else
  echo "MISS codex"
fi

echo
echo "=== Done ==="
