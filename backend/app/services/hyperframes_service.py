from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from ..config import CHROME_EXE, NODE_EXE, ROOT
from ..utils import run_cmd, write_json


def _rel_asset(path: str, hf_dir: Path) -> str:
    src = Path(path)
    assets_dir = hf_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / src.name
    if not dest.exists():
        shutil.copy2(src, dest)
    return f"assets/{src.name}"


def generate_hyperframes_project(timeline: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    hf_dir = out_dir / "hyperframes"
    if hf_dir.exists():
        shutil.rmtree(hf_dir)
    hf_dir.mkdir(parents=True)

    project = timeline["project"]
    width = project["width"]
    height = project["height"]
    duration = project["duration"]
    assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}

    clips = []
    for item in timeline.get("items", []):
        itype = item.get("type")
        if itype == "video":
            aid = item.get("asset_id")
            src = assets_by_id.get(aid, {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            clips.append(
                f'<video class="clip" data-start="{item["timeline_start"]:.3f}" '
                f'data-duration="{item["timeline_end"] - item["timeline_start"]:.3f}" '
                f'data-track-index="0" src="{rel}" muted playsinline></video>'
            )
        elif itype == "image":
            aid = item.get("asset_id")
            src = assets_by_id.get(aid, {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            clips.append(
                f'<img class="clip" data-start="{item["timeline_start"]:.3f}" '
                f'data-duration="{item["timeline_end"] - item["timeline_start"]:.3f}" '
                f'data-track-index="1" src="{rel}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.95" />'
            )
        elif itype == "subtitle" or itype == "text":
            text = (item.get("text") or "").replace('"', "&quot;")
            y = "78%" if itype == "subtitle" else "12%"
            size = "42px" if itype == "subtitle" else "56px"
            color = "#fff" if itype == "subtitle" else "#FACC15"
            clips.append(
                f'<div id="cap-{item["id"]}" class="clip" data-start="{item["timeline_start"]:.3f}" '
                f'data-duration="{item["timeline_end"] - item["timeline_start"]:.3f}" data-track-index="2" '
                f'style="position:absolute;left:50%;top:{y};transform:translateX(-50%);color:{color};'
                f'font-size:{size};font-weight:800;text-align:center;width:90%;text-shadow:0 4px 24px #000;">{text}</div>'
            )
        elif itype == "audio":
            aid = item.get("asset_id")
            src = assets_by_id.get(aid, {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            vol = item.get("volume", 0.3)
            clips.append(
                f'<audio data-start="{item["timeline_start"]:.3f}" data-duration="{duration:.3f}" '
                f'data-track-index="3" data-volume="{vol}" src="{rel}"></audio>'
            )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{project.get("name", "FrameCraft")}</title>
  <style>
    html, body {{ margin:0; background:#0D1321; }}
    #stage {{
      position:relative; width:{width}px; height:{height}px; overflow:hidden;
      background: linear-gradient(180deg,#0D1321 0%,#111827 100%);
      font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif;
    }}
    video.clip {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="framecraft" data-start="0" data-width="{width}" data-height="{height}">
    {''.join(clips)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    document.querySelectorAll('[id^="cap-"]').forEach((el, i) => {{
      const start = parseFloat(el.dataset.start || '0');
      tl.from(el, {{ opacity: 0, y: 30, duration: 0.5 }}, start + 0.1);
    }});
    window.__timelines = window.__timelines || {{}};
    window.__timelines.framecraft = tl;
  </script>
</body>
</html>"""
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    write_json(hf_dir / "hyperframes.json", {"composition": "index.html", "fps": project.get("fps", 30)})
    write_json(hf_dir / "meta.json", {"title": project.get("name"), "duration": duration})
    return hf_dir


def render_preview(hf_dir: Path, preview_path: Path, fps: int = 30) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    hf_cli = ROOT / "node_modules" / "hyperframes" / "dist" / "cli.js"
    node = NODE_EXE if NODE_EXE.exists() else "node"
    cmd = [str(node), str(hf_cli), "render", str(hf_dir), "-o", str(preview_path), "--fps", str(fps), "-q", "draft"]
    if CHROME_EXE.exists():
        cmd.extend(["--browser-path", str(CHROME_EXE)])
    result = run_cmd(cmd, cwd=hf_dir)
    if result.returncode != 0 or not preview_path.exists():
        raise RuntimeError(f"HyperFrames render failed: {result.stderr or result.stdout}")


def zip_hyperframes(hf_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in hf_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(hf_dir.parent))
