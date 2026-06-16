"""Quick chat API smoke test."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PROJECT = "proj_27c3fc265ee5"


def call(msg: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/projects/{PROJECT}/chat",
        data=json.dumps({"message": msg, "apply": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    lines: list[str] = []
    health = json.loads(urllib.request.urlopen(f"{BASE}/api/health").read().decode())
    lines.append("health: " + json.dumps(health, ensure_ascii=False))
    for msg in ["你好", "你能做什么", "字幕加上渐显渐隐"]:
        d = call(msg)
        lines.append(f"\n[{msg}]")
        lines.append("  status: " + d["status"])
        lines.append("  content: " + d["content"][:120])
        if d.get("patch"):
            ops = d["patch"].get("operations") or []
            lines.append(f"  patch_ops: {len(ops)}")
    out = Path(__file__).resolve().parents[1] / "chat_e2e_result.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
