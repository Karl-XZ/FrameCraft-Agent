#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: scripts/package-deliverables.sh <vertical-preview.mp4> <landscape-preview.mp4>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/deliverables"
VERTICAL_SRC="$1"
LANDSCAPE_SRC="$2"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

probe_has_av() {
  local src="$1"
  local json
  json="$(ffprobe -v error -show_streams -show_format -of json "$src")"
  python3 - "$src" <<'PY' <<<"$json"
import json, sys
src = sys.argv[1]
data = json.load(sys.stdin)
streams = data.get("streams") or []
has_video = any(s.get("codec_type") == "video" for s in streams)
has_audio = any(s.get("codec_type") == "audio" for s in streams)
if not has_video or not has_audio:
    raise SystemExit(f"{src} missing streams: video={has_video} audio={has_audio}")
print(f"OK {src}")
PY
}

make_contact() {
  local src="$1"
  local out="$2"
  ffmpeg -y -i "$src" \
    -vf "fps=1/24,scale=480:-1,tile=2x2:padding=12:margin=12:color=0x0d1321" \
    -frames:v 1 "$out" >/dev/null 2>&1
}

need_cmd ffmpeg
need_cmd ffprobe
need_cmd python3

probe_has_av "$VERTICAL_SRC"
probe_has_av "$LANDSCAPE_SRC"

mkdir -p "$OUT"
cp "$VERTICAL_SRC" "$OUT/mvp-vertical-codex.mp4"
cp "$LANDSCAPE_SRC" "$OUT/mvp-landscape-codex.mp4"

make_contact "$VERTICAL_SRC" "$OUT/mvp-vertical-codex-contact.jpg"
make_contact "$LANDSCAPE_SRC" "$OUT/mvp-landscape-codex-contact.jpg"

echo "Deliverables updated in $OUT"
