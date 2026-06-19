#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "manual_codex_videos" / "outputs_redesign_v2"
HF_CLI = ROOT / "node_modules" / "hyperframes" / "dist" / "cli.js"
FONT_SOURCE = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
NODE = shutil.which("node") or "node"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

FONT_FAMILY = "CodexCN"
FONT_STACK = f'"{FONT_FAMILY}",Arial,sans-serif'
MONO_STACK = "Menlo,Consolas,monospace"


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def must_run(cmd: list[str], *, cwd: Path | None = None) -> None:
    result = run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "command failed")


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def wrap_text(text: str, width: int) -> str:
    src = (text or "").strip()
    if len(src) <= width:
        return esc(src)
    return "<br/>".join(esc(src[i : i + width]) for i in range(0, len(src), width))


def normalize_video(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    must_run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(src),
            "-an",
            "-vf",
            "fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-g",
            "30",
            "-keyint_min",
            "30",
            "-sc_threshold",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )


def extract_audio(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    must_run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def extract_frame(video_path: Path, second: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    must_run(
        [
            FFMPEG,
            "-y",
            "-ss",
            f"{second:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
    )


def midpoint(start: float, end: float) -> float:
    return round((start + end) / 2.0, 3)


def render_contact_sheet(frame_specs: list[dict], qa_dir: Path, out_path: Path) -> None:
    paths = [qa_dir / f"{item['id']}.jpg" for item in frame_specs]
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    thumb_w = 520
    thumb_h = 292
    label_h = 52
    cols = 2
    rows = math.ceil(len(existing) / cols)
    canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (8, 16, 27))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for idx, item in enumerate(frame_specs):
        path = qa_dir / f"{item['id']}.jpg"
        if not path.exists():
            continue
        r = idx // cols
        c = idx % cols
        x = c * thumb_w
        y = r * (thumb_h + label_h)
        with Image.open(path) as im:
            canvas.paste(im.convert("RGB").resize((thumb_w, thumb_h)), (x, y))
        label = f"{item['id']}  {item['kind']}  {item['start']:.2f}-{item['end']:.2f}s"
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill=(12, 25, 42))
        draw.text((x + 12, y + thumb_h + 12), label, font=font, fill=(235, 244, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def subtitle_html(sub: dict, height: int, track_index: int, layout: str) -> str:
    width = "78%" if layout == "right" else "86%"
    left = "0"
    right = "0"
    bottom = "52px" if layout == "right" else "0"
    fs = 42 if layout == "right" else int(height * 0.047)
    duration = max(0.08, float(sub["end"]) - float(sub["start"]) - 0.02)
    text = esc(sub["text"])
    hot = esc(sub.get("highlight", ""))
    if hot:
        text = text.replace(hot, f'<span class="caption-hot">{hot}</span>', 1)
    return (
        f'<div id="{sub["id"]}" class="clip caption-layer" data-start="{sub["start"]:.3f}" '
        f'data-duration="{duration:.3f}" data-track-index="{track_index}" '
        f'style="position:absolute;left:{left};right:{right};bottom:{bottom};height:190px;'
        'display:flex;align-items:flex-end;justify-content:center;pointer-events:none;">'
        f'<div class="caption-card" style="max-width:{width};font-size:{fs}px;">{text}</div></div>'
    )


def block_shell(block: dict, inner: str) -> str:
    style = block["style"]
    return (
        f'<div id="{block["id"]}" class="clip overlay-block block-{block["kind"]}" '
        f'data-start="{block["start"]:.3f}" data-duration="{block["end"] - block["start"]:.3f}" '
        f'data-track-index="{block.get("track", 20)}" style="{style}">{inner}</div>'
    )


def meter_block(block: dict) -> str:
    chips = "".join(f'<span class="chip">{esc(item)}</span>' for item in block.get("chips", []))
    inner = (
        '<div class="meter-card glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="big-title">{wrap_text(block["title"], block.get("wrap", 8))}</div>'
        '<div class="meter-face"><div class="meter-arc"></div><div class="needle"></div><div class="meter-dot"></div></div>'
        f'<div class="chip-row">{chips}</div>'
        '</div>'
    )
    return block_shell(block, inner)


def chat_block(block: dict) -> str:
    bubbles = []
    for idx, item in enumerate(block["items"]):
        bubbles.append(f'<div class="chat-bubble" style="--i:{idx}">{wrap_text(item, 12)}</div>')
    inner = (
        '<div class="chat-stack">'
        f'<div class="eyebrow dark">{esc(block.get("eyebrow", ""))}</div>'
        + "".join(bubbles)
        + '</div>'
    )
    return block_shell(block, inner)


def reaction_block(block: dict) -> str:
    asset = esc(block.get("asset", "assets/1F602.svg"))
    labels = "".join(f'<span>{esc(item)}</span>' for item in block.get("labels", []))
    inner = (
        '<div class="reaction-stage">'
        '<div class="orbit-ring ring-a"></div><div class="orbit-ring ring-b"></div>'
        f'<img class="reaction-emoji" src="{asset}" alt="" />'
        f'<div class="reaction-title">{wrap_text(block["title"], 5)}</div>'
        f'<div class="reaction-labels">{labels}</div>'
        '</div>'
    )
    return block_shell(block, inner)


def loader_block(block: dict) -> str:
    dots = "".join('<i></i>' for _ in range(5))
    inner = (
        '<div class="loader-card glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="loader-title">{wrap_text(block["title"], 9)}</div>'
        f'<div class="loader-dots">{dots}</div>'
        '<div class="loader-bar"><b></b></div>'
        '</div>'
    )
    return block_shell(block, inner)


def storyboard_block(block: dict) -> str:
    cards = []
    for idx, item in enumerate(block["items"]):
        cards.append(f'<div class="story-card" style="--i:{idx}"><b>{idx + 1}</b><span>{wrap_text(item, 7)}</span></div>')
    inner = '<div class="storyboard">' + "".join(cards) + '</div>'
    return block_shell(block, inner)


def impact_word_block(block: dict) -> str:
    words = "".join(f'<span>{esc(word)}</span>' for word in block["words"])
    inner = (
        '<div class="impact-wrap">'
        f'<div class="impact-words">{words}</div>'
        f'<div class="impact-note">{esc(block.get("note", ""))}</div>'
        '</div>'
    )
    return block_shell(block, inner)


def flow_block(block: dict) -> str:
    parts = []
    for idx, item in enumerate(block["items"]):
        parts.append(
            f'<div class="flow-node" style="--i:{idx}">'
            f'<b>{idx + 1}</b><span>{wrap_text(item, block.get("wrap", 9))}</span></div>'
        )
        if idx < len(block["items"]) - 1:
            parts.append(f'<div class="flow-line line-{idx}" style="--i:{idx}"></div>')
    direction = block.get("direction", "vertical")
    inner = (
        f'<div class="flow-board {direction} glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="flow-title">{wrap_text(block["title"], block.get("title_wrap", 10))}</div>'
        '<div class="flow-map">'
        + "".join(parts)
        + '</div>'
        f'<div class="flow-result">{wrap_text(block.get("result", ""), 14)}</div>'
        '</div>'
    )
    return block_shell(block, inner)


def compare_block(block: dict) -> str:
    rows = []
    for idx, row in enumerate(block["rows"]):
        rows.append(
            f'<div class="compare-row" style="--i:{idx}">'
            f'<b>{esc(row[0])}</b><span>{wrap_text(row[1], 15)}</span></div>'
        )
    inner = (
        '<div class="compare-board glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="flow-title">{wrap_text(block["title"], 10)}</div>'
        '<div class="compare-rows">'
        + "".join(rows)
        + '</div><div class="scan-line"></div></div>'
    )
    return block_shell(block, inner)


def timeline_block(block: dict) -> str:
    marks = []
    for idx, row in enumerate(block["items"]):
        marks.append(
            f'<div class="timeline-mark" style="--i:{idx}"><b>{esc(row[0])}</b><span>{wrap_text(row[1], 10)}</span></div>'
        )
    inner = (
        '<div class="timeline-board glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="flow-title">{wrap_text(block["title"], 9)}</div>'
        '<div class="timeline-rail"><em></em></div>'
        '<div class="timeline-marks">'
        + "".join(marks)
        + '</div></div>'
    )
    return block_shell(block, inner)


def channel_block(block: dict) -> str:
    inner = (
        '<div class="channel-board glass-card"><i class="shine"></i>'
        f'<div class="eyebrow">{esc(block.get("eyebrow", ""))}</div>'
        f'<div class="channel-pill">{esc(block["title"])}</div>'
        f'<div class="channel-text">{wrap_text(block.get("body", ""), 13)}</div>'
        '<div class="channel-switch"><i></i><i></i><i></i></div>'
        '</div>'
    )
    return block_shell(block, inner)


def block_html(block: dict) -> str:
    kind = block["kind"]
    if kind == "meter":
        return meter_block(block)
    if kind == "chat":
        return chat_block(block)
    if kind == "reaction":
        return reaction_block(block)
    if kind == "loader":
        return loader_block(block)
    if kind == "storyboard":
        return storyboard_block(block)
    if kind == "impact":
        return impact_word_block(block)
    if kind == "flow":
        return flow_block(block)
    if kind == "compare":
        return compare_block(block)
    if kind == "timeline":
        return timeline_block(block)
    if kind == "channel":
        return channel_block(block)
    raise ValueError(f"unknown block kind {kind}")


def build_css(width: int, height: int, layout: str) -> str:
    return f"""
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background: #05070c;
    }}
    @font-face {{
      font-family: "{FONT_FAMILY}";
      src: url("assets/ArialUnicode.ttf") format("truetype");
      font-display: swap;
    }}
    #stage {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      color: #f7fafc;
      font-family: {FONT_STACK};
      background:
        radial-gradient(circle at 12% 18%, rgba(45, 212, 191, .18), transparent 26%),
        radial-gradient(circle at 82% 74%, rgba(250, 204, 21, .13), transparent 24%),
        linear-gradient(135deg, #070a12 0%, #111827 48%, #05070c 100%);
    }}
    .grid-bg {{
      position: absolute;
      inset: 0;
      opacity: .22;
      background-image:
        linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px);
      background-size: 70px 70px;
      transform: perspective(900px) rotateX(58deg) translateY(160px);
      transform-origin: center bottom;
    }}
    .grain {{
      position:absolute;
      inset:0;
      opacity:.16;
      background-image:
        radial-gradient(circle at 1px 1px, rgba(255,255,255,.18) 1px, transparent 1px),
        radial-gradient(circle at 3px 4px, rgba(255,255,255,.10) 1px, transparent 1px);
      background-size: 7px 7px, 11px 11px;
      mix-blend-mode: screen;
      pointer-events:none;
    }}
    .vignette {{
      position:absolute;
      inset:0;
      background: radial-gradient(ellipse at center, transparent 35%, rgba(2,4,8,.62) 92%);
      pointer-events:none;
    }}
    .sweep {{
      position:absolute;
      top:-10%;
      left:-30%;
      width:28%;
      height:120%;
      transform:skewX(-18deg);
      background:linear-gradient(90deg,transparent,rgba(255,255,255,.14),transparent);
      opacity:.5;
      pointer-events:none;
    }}
    #video-shell {{
      position:absolute;
      border:1px solid rgba(255,255,255,.18);
      background:#02040a;
      overflow:hidden;
      box-shadow:0 30px 90px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.16);
      z-index:2;
    }}
    #main-video {{
      position:absolute;
      inset:0;
      width:100%;
      height:100%;
      object-fit:cover;
    }}
    .video-full #video-shell {{ inset:0; border-radius:0; border:0; }}
    .video-right #video-shell {{
      right:70px;
      top:136px;
      width:900px;
      height:506px;
      border-radius:30px;
    }}
    .full-left-scrim {{
      position:absolute;
      left:0;
      top:0;
      width:50%;
      height:100%;
      background:linear-gradient(90deg, rgba(2,6,13,.86), rgba(2,6,13,.35) 70%, transparent);
      pointer-events:none;
    }}
    .bottom-scrim {{
      position:absolute;
      left:0;
      right:0;
      bottom:0;
      height:32%;
      background:linear-gradient(180deg, transparent, rgba(2,6,13,.88));
      pointer-events:none;
    }}
    .right-stage-label {{
      position:absolute;
      left:72px;
      top:58px;
      font-family:{MONO_STACK};
      font-size:15px;
      letter-spacing:.26em;
      color:rgba(165,243,252,.72);
    }}
    .right-ambient {{
      position:absolute;
      left:32px;
      top:72px;
      width:860px;
      height:744px;
      border-radius:42px;
      overflow:hidden;
      pointer-events:none;
      z-index:1;
      background:
        radial-gradient(circle at 18% 18%, rgba(45,212,191,.24), transparent 32%),
        radial-gradient(circle at 72% 62%, rgba(250,204,21,.16), transparent 34%),
        linear-gradient(135deg, rgba(15,23,42,.32), rgba(15,23,42,.04));
      border:1px solid rgba(255,255,255,.045);
      box-shadow:inset 0 0 90px rgba(103,232,249,.08);
    }}
    .right-ambient .orb {{
      position:absolute;
      border-radius:50%;
      border:1px solid rgba(103,232,249,.18);
      box-shadow:0 0 44px rgba(45,212,191,.12);
    }}
    .right-ambient .orb-a {{ left:56px; top:66px; width:270px; height:270px; }}
    .right-ambient .orb-b {{ right:64px; bottom:72px; width:360px; height:360px; border-color:rgba(250,204,21,.14); }}
    .right-ambient .scan {{
      position:absolute;
      left:-280px;
      width:260px;
      height:100%;
      background:linear-gradient(90deg, transparent, rgba(255,255,255,.075), transparent);
      transform:skewX(-18deg);
    }}
    .caption-card {{
      padding: 16px 24px 15px;
      border-radius: 26px;
      background: rgba(7, 12, 20, .66);
      border: 1px solid rgba(255,255,255,.12);
      backdrop-filter: blur(18px) saturate(1.12);
      color:#f8fafc;
      font-weight:900;
      line-height:1.12;
      text-align:center;
      text-shadow:0 4px 18px rgba(0,0,0,.50);
      opacity:0;
      transform:translateY(18px) scale(.985);
      filter:blur(6px);
    }}
    .caption-hot {{ color:#facc15; }}
    .overlay-block {{
      pointer-events:none;
      opacity:0;
      transform-origin:50% 50%;
      filter:blur(7px);
      z-index:4;
    }}
    .glass-card {{
      position:relative;
      overflow:hidden;
      border:1px solid rgba(255,255,255,.13);
      background:linear-gradient(135deg, rgba(12,20,33,.86), rgba(8,13,22,.62));
      backdrop-filter:blur(18px) saturate(1.18);
      box-shadow:0 24px 70px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.14);
    }}
    .glass-card > .shine {{
      position:absolute;
      top:-30%;
      left:-40%;
      width:32%;
      height:160%;
      background:linear-gradient(90deg, transparent, rgba(255,255,255,.23), transparent);
      transform:skewX(-18deg);
      opacity:.75;
      pointer-events:none;
    }}
    .glass-card > *:not(.shine) {{
      position:relative;
      z-index:1;
    }}
    .eyebrow {{
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding:7px 12px;
      border-radius:999px;
      background:rgba(45,212,191,.12);
      color:#67e8f9;
      font-size:15px;
      font-weight:900;
      letter-spacing:.10em;
    }}
    .eyebrow.dark {{ background:rgba(15,23,42,.66); color:#facc15; }}
    .big-title {{
      margin-top:14px;
      font-size:52px;
      line-height:.98;
      font-weight:900;
      color:#facc15;
      text-shadow:0 10px 30px rgba(0,0,0,.25);
    }}
    .meter-card {{ width:420px; padding:22px 24px 24px; border-radius:26px; }}
    .meter-face {{ position:relative; height:120px; margin-top:8px; }}
    .meter-arc {{
      position:absolute; left:36px; right:36px; bottom:4px; height:86px;
      border:12px solid rgba(250,204,21,.22); border-bottom:0; border-radius:140px 140px 0 0;
    }}
    .needle {{
      position:absolute; left:50%; bottom:8px; width:7px; height:88px; border-radius:999px;
      background:#facc15; transform-origin:50% 100%; transform:translateX(-50%) rotate(-55deg);
      box-shadow:0 0 22px rgba(250,204,21,.68);
    }}
    .meter-dot {{ position:absolute; left:50%; bottom:0; width:22px; height:22px; margin-left:-11px; border-radius:50%; background:#f8fafc; }}
    .chip-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:4px; }}
    .chip {{ padding:7px 11px; border-radius:999px; background:rgba(255,255,255,.09); color:#e2e8f0; font-size:16px; font-weight:800; }}
    .chat-stack {{ display:flex; flex-direction:column; gap:12px; align-items:flex-start; }}
    .chat-bubble {{
      max-width:420px; padding:15px 18px; border-radius:22px;
      background:rgba(255,255,255,.94); color:#111827; font-size:30px; line-height:1.08; font-weight:900;
      box-shadow:0 18px 46px rgba(0,0,0,.30);
      transform-origin:0 100%;
      opacity:0;
    }}
    .reaction-stage {{ position:relative; width:310px; height:300px; }}
    .orbit-ring {{ position:absolute; inset:35px; border-radius:50%; border:3px dashed rgba(250,204,21,.45); }}
    .ring-b {{ inset:18px; border-color:rgba(45,212,191,.34); }}
    .reaction-emoji {{ position:absolute; left:72px; top:52px; width:160px; height:160px; object-fit:contain; }}
    .reaction-title {{ position:absolute; left:34px; right:34px; top:196px; color:#111827; background:#facc15; padding:12px 14px; border-radius:18px; text-align:center; font-size:32px; line-height:1; font-weight:900; box-shadow:0 12px 30px rgba(0,0,0,.24); }}
    .reaction-labels {{ position:absolute; top:0; right:0; display:flex; flex-direction:column; gap:8px; }}
    .reaction-labels span {{ padding:7px 11px; border-radius:999px; color:#f8fafc; background:rgba(15,23,42,.82); font-size:15px; font-weight:900; }}
    .loader-card {{ width:430px; padding:22px; border-radius:26px; }}
    .loader-title {{ margin-top:12px; color:#f8fafc; font-size:34px; line-height:1.08; font-weight:900; }}
    .loader-dots {{ display:flex; gap:12px; margin-top:22px; }}
    .loader-dots i {{ width:18px; height:18px; border-radius:50%; background:#facc15; opacity:.25; }}
    .loader-bar {{ margin-top:18px; height:10px; border-radius:999px; background:rgba(255,255,255,.10); overflow:hidden; }}
    .loader-bar b {{ display:block; height:100%; width:0%; border-radius:999px; background:linear-gradient(90deg,#facc15,#2dd4bf); }}
    .storyboard {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; width:560px; }}
    .story-card {{ padding:18px; min-height:130px; border-radius:20px; background:#f8fafc; color:#111827; box-shadow:0 16px 36px rgba(0,0,0,.22); transform:rotate(-2deg); opacity:0; }}
    .story-card:nth-child(2) {{ transform:rotate(3deg); background:#dcfce7; }}
    .story-card:nth-child(3) {{ transform:rotate(-1deg); background:#fef3c7; }}
    .story-card b {{ display:block; color:#0ea5e9; font-size:18px; }}
    .story-card span {{ display:block; margin-top:8px; font-size:28px; line-height:1.03; font-weight:900; }}
    .impact-words {{ display:flex; flex-direction:column; align-items:flex-start; gap:4px; }}
    .impact-words span {{ font-size:76px; line-height:.92; font-weight:900; color:#f8fafc; text-shadow:0 0 26px rgba(45,212,191,.34); opacity:0; }}
    .impact-note {{ margin-top:16px; color:#facc15; font-size:24px; font-weight:900; }}
    .flow-board, .compare-board, .timeline-board, .channel-board {{ padding:22px 24px; border-radius:28px; }}
    .flow-title {{ margin-top:12px; font-size:34px; line-height:1.06; font-weight:900; color:#f8fafc; }}
    .flow-map {{ position:relative; margin-top:18px; display:flex; gap:18px; }}
    .flow-board.vertical .flow-map {{ flex-direction:column; }}
    .flow-node {{ position:relative; display:flex; align-items:center; gap:12px; min-height:54px; padding:11px 13px; border-radius:16px; background:rgba(255,255,255,.075); border:1px solid rgba(255,255,255,.08); opacity:0; }}
    .flow-node b {{ width:30px; height:30px; flex:0 0 auto; border-radius:50%; display:grid; place-items:center; color:#07121c; background:#67e8f9; font-family:{MONO_STACK}; font-size:14px; font-weight:900; }}
    .flow-node span {{ color:#e2e8f0; font-size:20px; line-height:1.2; font-weight:800; }}
    .flow-line {{ position:relative; width:3px; height:22px; margin-left:28px; margin-top:-18px; margin-bottom:-18px; background:#67e8f9; transform-origin:50% 0%; transform:scaleY(0); box-shadow:0 0 20px rgba(103,232,249,.7); }}
    .flow-board.horizontal .flow-line {{ position:absolute; top:126px; height:3px; width:42px; margin:0; transform-origin:0 50%; transform:scaleX(0); }}
    .flow-board.horizontal .line-0 {{ left:152px; }}
    .flow-board.horizontal .line-1 {{ left:330px; }}
    .flow-result {{ margin-top:16px; color:#facc15; font-size:22px; line-height:1.25; font-weight:900; opacity:0; }}
    .compare-rows {{ margin-top:16px; display:flex; flex-direction:column; gap:10px; }}
    .compare-row {{ display:grid; grid-template-columns:72px 1fr; gap:12px; align-items:start; padding:11px 0; border-top:1px solid rgba(255,255,255,.08); opacity:0; }}
    .compare-row b {{ color:#67e8f9; font-size:18px; }}
    .compare-row span {{ color:#e2e8f0; font-size:20px; line-height:1.25; font-weight:800; }}
    .scan-line {{ position:absolute; left:0; top:0; width:100%; height:3px; background:linear-gradient(90deg,transparent,#facc15,transparent); opacity:0; }}
    .timeline-rail {{ position:relative; height:6px; margin:26px 4px 18px; background:rgba(255,255,255,.10); border-radius:999px; overflow:hidden; }}
    .timeline-rail em {{ display:block; height:100%; width:0%; background:linear-gradient(90deg,#67e8f9,#facc15); border-radius:999px; }}
    .timeline-marks {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .timeline-mark {{ opacity:0; padding:12px 10px; border-radius:16px; background:rgba(255,255,255,.07); }}
    .timeline-mark b {{ display:block; color:#67e8f9; font-size:17px; }}
    .timeline-mark span {{ display:block; margin-top:5px; color:#e2e8f0; font-size:18px; line-height:1.2; font-weight:800; }}
    .channel-pill {{ display:inline-flex; margin-top:16px; padding:12px 20px; border-radius:999px; background:#22c55e; color:#052e1b; font-size:32px; line-height:1; font-weight:900; }}
    .channel-text {{ margin-top:14px; color:#e2e8f0; font-size:22px; line-height:1.3; font-weight:800; }}
    .channel-switch {{ display:flex; gap:8px; margin-top:18px; }}
    .channel-switch i {{ width:38px; height:10px; border-radius:999px; background:rgba(34,197,94,.22); }}
    .channel-switch i:nth-child(2) {{ background:#22c55e; }}
    .video-right .meter-card {{
      width:100%;
      padding:28px 32px 30px;
      border-radius:32px;
    }}
    .video-right .big-title {{ font-size:62px; }}
    .video-right .meter-face {{ height:148px; }}
    .video-right .meter-arc {{ left:48px; right:48px; height:106px; border-width:14px; }}
    .video-right .needle {{ height:108px; }}
    .video-right .chip {{ font-size:19px; padding:9px 14px; }}
    .video-right .flow-board,
    .video-right .compare-board,
    .video-right .timeline-board,
    .video-right .channel-board {{
      padding:30px 34px;
      border-radius:34px;
    }}
    .video-right .flow-board.vertical {{ min-height:430px; }}
    .video-right .flow-board.horizontal {{ min-height:270px; }}
    .video-right .compare-board {{ min-height:390px; }}
    .video-right .timeline-board {{ min-height:350px; }}
    .video-right .channel-board {{ min-height:390px; }}
    .video-right .flow-title {{ font-size:44px; }}
    .video-right .flow-map {{ gap:22px; }}
    .video-right .flow-node {{
      min-height:70px;
      padding:15px 17px;
      border-radius:20px;
    }}
    .video-right .flow-node b {{
      width:38px;
      height:38px;
      font-size:17px;
    }}
    .video-right .flow-node span {{ font-size:25px; }}
    .video-right .flow-result {{ font-size:27px; }}
    .video-right .flow-board.horizontal .flow-map {{
      align-items:center;
      gap:12px;
    }}
    .video-right .flow-board.horizontal .flow-node {{ flex:1 1 0; }}
    .video-right .flow-board.horizontal .flow-line {{
      position:relative;
      top:auto;
      left:auto;
      flex:0 0 58px;
      width:58px;
      height:4px;
      margin:0 -3px;
      transform-origin:0 50%;
    }}
    .video-right .compare-row {{
      grid-template-columns:96px 1fr;
      padding:15px 0;
    }}
    .video-right .compare-row b {{ font-size:23px; }}
    .video-right .compare-row span {{ font-size:25px; }}
    .video-right .timeline-rail {{ height:8px; margin:34px 4px 24px; }}
    .video-right .timeline-marks {{ gap:16px; }}
    .video-right .timeline-mark {{ padding:18px 16px; }}
    .video-right .timeline-mark b {{ font-size:22px; }}
    .video-right .timeline-mark span {{ font-size:23px; }}
    .video-right .storyboard {{
      width:100%;
      gap:18px;
    }}
    .video-right .story-card {{
      min-height:165px;
      padding:24px;
    }}
    .video-right .story-card b {{ font-size:22px; }}
    .video-right .story-card span {{ font-size:35px; }}
    .video-right .impact-words span {{ font-size:98px; }}
    .video-right .impact-note {{ font-size:29px; }}
    .video-right .channel-pill {{ font-size:42px; padding:15px 26px; }}
    .video-right .channel-text {{ font-size:28px; }}
    .video-right .channel-switch i {{ width:54px; height:13px; }}
    .caption-layer {{ z-index:8; }}
    """


def build_script(spec: dict) -> str:
    duration = float(spec["duration"])
    blocks = json.dumps(spec["blocks"], ensure_ascii=False)
    subtitles = json.dumps(spec["subtitles"], ensure_ascii=False)
    return f"""
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true, defaults: {{ ease: "power3.out", overwrite: "auto" }} }});
    const DURATION = {duration:.3f};
    const blocks = {blocks};
    const subtitles = {subtitles};

    tl.to(".grid-bg", {{ backgroundPosition: "140px 210px", duration: DURATION, ease: "none" }}, 0);
    tl.fromTo(".sweep", {{ x: -560, opacity: 0 }}, {{ x: 2440, opacity: .55, duration: 2.2, ease: "power2.inOut", repeat: Math.max(0, Math.floor(DURATION / 4)) }}, .4);
    tl.fromTo("#video-shell", {{ scale: {0.992 if spec["layout"] == "right" else 1.0} }}, {{ scale: {1.012 if spec["layout"] == "right" else 1.028}, duration: DURATION, ease: "none" }}, 0);
    if (document.querySelector(".right-ambient")) {{
      tl.to(".right-ambient .orb-a", {{ rotation: 360, scale: 1.08, duration: DURATION, ease: "none" }}, 0);
      tl.to(".right-ambient .orb-b", {{ rotation: -260, scale: .96, duration: DURATION, ease: "none" }}, 0);
      tl.fromTo(".right-ambient .scan", {{ x: 0, opacity: .2 }}, {{ x: 1160, opacity: .68, duration: 3.6, ease: "power2.inOut", repeat: Math.max(0, Math.floor(DURATION / 4)) }}, .2);
    }}

    function outAt(end, dur = .32) {{
      return Math.max(0, end - dur);
    }}

    subtitles.forEach((s) => {{
      const id = "#" + s.id + " .caption-card";
      const start = s.start;
      const end = s.end - .02;
      const fade = Math.min(.24, Math.max(.08, (end - start) * .28));
      tl.fromTo(id, {{ opacity: 0, y: 18, scale: .985, filter: "blur(6px)" }}, {{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: fade, ease: "power2.out" }}, start);
      tl.to(id, {{ opacity: 0, y: -12, scale: .995, filter: "blur(4px)", duration: fade, ease: "power2.in" }}, Math.max(start + fade, end - fade));
      tl.fromTo("#" + s.id + " .caption-hot", {{ color: "#facc15" }}, {{ color: "#ffffff", duration: .18, repeat: 1, yoyo: true }}, start + fade + .05);
    }});

    blocks.forEach((b) => {{
      const root = "#" + b.id;
      const dur = b.end - b.start;
      const exitAt = outAt(b.end);
      tl.fromTo(root,
        {{ opacity: 0, y: 26, scale: .96, filter: "blur(9px)" }},
        {{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: .42, ease: "power3.out" }},
        b.start
      );
      tl.to(root, {{ opacity: 0, y: -24, scale: .982, filter: "blur(8px)", duration: .32, ease: "power2.in" }}, exitAt);
      const shine = gsap.utils.toArray(root + " .shine");
      if (shine.length) {{
        tl.fromTo(shine, {{ x: -180 }}, {{ x: 820, duration: 1.15, ease: "power2.inOut" }}, b.start + .22);
      }}

      if (b.kind === "meter") {{
        tl.fromTo(root + " .big-title", {{ x: -34, opacity: 0 }}, {{ x: 0, opacity: 1, duration: .42 }}, b.start + .12);
        tl.fromTo(root + " .needle", {{ rotation: -58 }}, {{ rotation: 48, duration: Math.min(1.35, dur - .6), ease: "elastic.out(1, .55)" }}, b.start + .36);
        tl.fromTo(root + " .chip", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: .28, stagger: .09 }}, b.start + .64);
        tl.to(root + " .meter-card", {{ y: -6, duration: .7, repeat: Math.max(0, Math.floor(dur / 1.4) - 1), yoyo: true, ease: "sine.inOut" }}, b.start + .9);
      }}
      if (b.kind === "chat") {{
        tl.fromTo(root + " .chat-bubble", {{ opacity: 0, x: -36, scale: .82, rotation: -2 }}, {{ opacity: 1, x: 0, scale: 1, rotation: 0, duration: .38, stagger: .22, ease: "back.out(1.8)" }}, b.start + .16);
        tl.to(root + " .chat-bubble", {{ y: -4, duration: .55, repeat: Math.max(0, Math.floor(dur / 1.1) - 1), yoyo: true, stagger: .08, ease: "sine.inOut" }}, b.start + 1.0);
      }}
      if (b.kind === "reaction") {{
        tl.fromTo(root + " .reaction-emoji", {{ opacity: 0, scale: .25, rotation: -30 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: .42, ease: "back.out(2.2)" }}, b.start + .12);
        tl.fromTo(root + " .orbit-ring", {{ opacity: 0, scale: .55, rotation: -35 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: .56, stagger: .1 }}, b.start + .22);
        tl.fromTo(root + " .reaction-title", {{ opacity: 0, y: 30, scale: .75 }}, {{ opacity: 1, y: 0, scale: 1, duration: .36, ease: "back.out(2)" }}, b.start + .48);
        tl.fromTo(root + " .reaction-labels span", {{ opacity: 0, x: 24 }}, {{ opacity: 1, x: 0, duration: .22, stagger: .11 }}, b.start + .68);
        tl.to(root + " .reaction-emoji", {{ y: -10, rotation: 5, duration: .62, repeat: Math.max(0, Math.floor(dur / 1.24) - 1), yoyo: true, ease: "sine.inOut" }}, b.start + .86);
        tl.to(root + " .ring-a", {{ rotation: 90, duration: Math.max(.8, dur - .5), ease: "none" }}, b.start + .3);
        tl.to(root + " .ring-b", {{ rotation: -120, duration: Math.max(.8, dur - .5), ease: "none" }}, b.start + .3);
      }}
      if (b.kind === "loader") {{
        tl.fromTo(root + " .loader-title", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: .35 }}, b.start + .12);
        tl.fromTo(root + " .loader-dots i", {{ opacity: .2, scale: .55 }}, {{ opacity: 1, scale: 1.15, duration: .24, stagger: .13, repeat: Math.max(1, Math.floor(dur / .8)), yoyo: true }}, b.start + .42);
        tl.fromTo(root + " .loader-bar b", {{ width: "0%" }}, {{ width: "100%", duration: Math.max(.5, dur - .8), ease: "none" }}, b.start + .55);
      }}
      if (b.kind === "storyboard") {{
        tl.fromTo(root + " .story-card", {{ opacity: 0, y: 42, scale: .72, rotation: -8 }}, {{ opacity: 1, y: 0, scale: 1, rotation: 0, duration: .46, stagger: .2, ease: "back.out(1.7)" }}, b.start + .16);
        tl.to(root + " .story-card", {{ y: -7, duration: .72, repeat: Math.max(0, Math.floor(dur / 1.44) - 1), yoyo: true, stagger: .08, ease: "sine.inOut" }}, b.start + 1.05);
      }}
      if (b.kind === "impact") {{
        tl.fromTo(root + " .impact-words span", {{ opacity: 0, x: -80, scale: .72 }}, {{ opacity: 1, x: 0, scale: 1, duration: .32, stagger: .16, ease: "expo.out" }}, b.start + .14);
        tl.fromTo(root + " .impact-note", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: .28 }}, b.start + .78);
        tl.to(root + " .impact-words span", {{ x: 10, duration: .7, repeat: Math.max(0, Math.floor(dur / 1.4) - 1), yoyo: true, stagger: .05, ease: "sine.inOut" }}, b.start + 1.05);
      }}
      if (b.kind === "flow") {{
        const nodes = gsap.utils.toArray(root + " .flow-node");
        const lines = gsap.utils.toArray(root + " .flow-line");
        const step = Math.min(1.18, Math.max(.52, (dur - 2.2) / Math.max(1, nodes.length + lines.length)));
        let cursor = b.start + .32;
        nodes.forEach((node, i) => {{
          tl.fromTo(node, {{ opacity: 0, x: -38, scale: .82 }}, {{ opacity: 1, x: 0, scale: 1, duration: Math.min(.46, step * .62), ease: "back.out(1.55)" }}, cursor);
          tl.fromTo(node.querySelector("b"), {{ scale: .45 }}, {{ scale: 1.12, duration: Math.min(.28, step * .42), repeat: 1, yoyo: true, ease: "power2.out" }}, cursor + Math.min(.22, step * .32));
          if (lines[i]) {{
            tl.fromTo(lines[i], {{ scaleY: 0, scaleX: 0, opacity: .3 }}, {{ scaleY: 1, scaleX: 1, opacity: 1, duration: Math.min(.42, step * .58), ease: "power2.out" }}, cursor + step * .72);
          }}
          cursor += step;
        }});
        tl.fromTo(root + " .flow-result", {{ opacity: 0, y: 18, scale: .9 }}, {{ opacity: 1, y: 0, scale: 1, duration: .42, ease: "back.out(1.8)" }}, Math.min(b.end - .92, cursor + .2));
        tl.to(root + " .flow-node b", {{ boxShadow: "0 0 28px rgba(103,232,249,.75)", duration: .38, repeat: Math.max(1, Math.floor(dur / 1.25)), yoyo: true, stagger: .18 }}, b.start + 1.05);
      }}
      if (b.kind === "compare") {{
        tl.fromTo(root + " .compare-row", {{ opacity: 0, x: -28 }}, {{ opacity: 1, x: 0, duration: .32, stagger: .24 }}, b.start + .22);
        tl.fromTo(root + " .scan-line", {{ opacity: 0, y: 0 }}, {{ opacity: .9, y: 230, duration: Math.max(.8, dur - 1.0), ease: "none" }}, b.start + .7);
      }}
      if (b.kind === "timeline") {{
        tl.fromTo(root + " .timeline-rail em", {{ width: "0%" }}, {{ width: "100%", duration: Math.max(.7, dur - 1.0), ease: "none" }}, b.start + .28);
        tl.fromTo(root + " .timeline-mark", {{ opacity: 0, y: 28, scale: .86 }}, {{ opacity: 1, y: 0, scale: 1, duration: .38, stagger: .44, ease: "back.out(1.5)" }}, b.start + .42);
        tl.to(root + " .timeline-mark", {{ y: -5, duration: .8, repeat: Math.max(0, Math.floor(dur / 1.6) - 1), yoyo: true, stagger: .12, ease: "sine.inOut" }}, b.start + 1.7);
      }}
      if (b.kind === "channel") {{
        tl.fromTo(root + " .channel-pill", {{ opacity: 0, scale: .5, x: -36 }}, {{ opacity: 1, scale: 1, x: 0, duration: .38, ease: "back.out(2)" }}, b.start + .18);
        tl.fromTo(root + " .channel-text", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: .32 }}, b.start + .52);
        tl.fromTo(root + " .channel-switch i", {{ opacity: .2, scaleX: .45 }}, {{ opacity: 1, scaleX: 1, duration: .24, stagger: .12, repeat: Math.max(1, Math.floor(dur / 1.0)), yoyo: true }}, b.start + .86);
      }}
    }});

    tl.set("#timeline-end", {{ opacity: 0 }}, DURATION);
    window.__timelines["main"] = tl;
    """


def build_html(spec: dict) -> str:
    width, height = 1920, 1080
    layout_class = "video-right" if spec["layout"] == "right" else "video-full"
    clips = [
        '<div class="grid-bg"></div>',
        '<div class="sweep"></div>',
        f'<div id="video-shell"><video id="main-video" class="clip" data-start="0" data-duration="{spec["duration"]:.3f}" '
        f'data-track-index="1" src="assets/main.video.mp4" muted playsinline '
        f'style="object-position:{spec["video_position"]};transform:scale({spec.get("video_scale", 1.0)});'
        f'transform-origin:{spec.get("video_origin", spec["video_position"])};"></video></div>',
    ]
    if spec["layout"] == "full":
        clips.extend(['<div class="full-left-scrim"></div>', '<div class="bottom-scrim"></div>'])
    else:
        clips.append('<div class="right-ambient"><i class="orb orb-a"></i><i class="orb orb-b"></i><b class="scan"></b></div>')
        if spec.get("stage_label"):
            clips.append(f'<div class="right-stage-label">{esc(spec["stage_label"])}</div>')
    clips.extend(block_html(block) for block in spec["blocks"])
    for idx, sub in enumerate(spec["subtitles"], start=1):
        clips.append(subtitle_html(sub, height, 70 + idx, spec["layout"]))
    clips.extend(['<div class="grain"></div>', '<div class="vignette"></div>', '<div id="timeline-end" style="position:absolute;left:-10px;top:-10px;width:1px;height:1px;opacity:0;"></div>'])
    audios = [
        f'<audio id="main-audio" src="assets/main.audio.wav" data-start="0" data-duration="{spec["duration"]:.3f}" data-track-index="4"></audio>'
    ]
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <link rel="icon" href="data:," />
  <title>{esc(spec["title"])}</title>
  <style>{build_css(width, height, spec["layout"])}</style>
</head>
<body class="{layout_class}">
  <div id="stage" data-composition-id="main" data-start="0" data-duration="{spec["duration"]:.3f}" data-width="{width}" data-height="{height}">
    {''.join(clips)}
    {''.join(audios)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>{build_script(spec)}</script>
</body>
</html>
"""


def funny_subtitles() -> list[dict]:
    return [
        {"id": "sub_01", "start": 0.00, "end": 1.32, "text": "每个礼拜我都要上片了", "highlight": "上片"},
        {"id": "sub_02", "start": 1.32, "end": 2.36, "text": "这样不行啦", "highlight": "不行"},
        {"id": "sub_03", "start": 2.36, "end": 4.54, "text": "可不可以麻烦你们老板赶快审一下嘛", "highlight": "赶快"},
        {"id": "sub_04", "start": 4.54, "end": 6.02, "text": "我真的这个部分", "highlight": "真的"},
        {"id": "sub_05", "start": 6.02, "end": 7.28, "text": "我真的不敢吹啊", "highlight": "不敢"},
        {"id": "sub_06", "start": 7.28, "end": 8.24, "text": "我就怕被骂", "highlight": "被骂"},
        {"id": "sub_07", "start": 11.58, "end": 12.14, "text": "天啊", "highlight": "天啊"},
        {"id": "sub_08", "start": 12.14, "end": 13.76, "text": "下礼拜我影片怎么办啦", "highlight": "怎么办"},
        {"id": "sub_09", "start": 13.76, "end": 14.96, "text": "想不出题材了啦", "highlight": "题材"},
        {"id": "sub_10", "start": 15.56, "end": 15.92, "text": "等一下", "highlight": "等一下"},
        {"id": "sub_11", "start": 16.50, "end": 17.22, "text": "题材", "highlight": "题材"},
    ]


def opinion_subtitles() -> list[dict]:
    return [
        {"id": "sub_01", "start": 0.14, "end": 5.92, "text": "那么就会被限流，不放量了，就会第一波。", "highlight": "限流"},
        {"id": "sub_02", "start": 7.54, "end": 16.54, "text": "如果我不在题目里提到罗永浩，改个标题，可能就不会被限流了。", "highlight": "罗永浩"},
        {"id": "sub_03", "start": 17.18, "end": 23.74, "text": "不放量会差很多，但我就是故意在标题里提一下罗永浩。", "highlight": "故意"},
        {"id": "sub_04", "start": 23.74, "end": 33.52, "text": "就是要试验一下，是不是真的会被限流，结果果然又被限流了。", "highlight": "试验"},
        {"id": "sub_05", "start": 34.98, "end": 49.44, "text": "同一天里，也有人发了类似视频，也是围绕另一个健康话题。", "highlight": "同一天"},
        {"id": "sub_06", "start": 49.44, "end": 54.84, "text": "他的那条视频，是放在微信。", "highlight": "微信"},
    ]


def create_specs() -> list[dict]:
    funny_source = ROOT / "temp_sources" / "online_batch_funny_v4" / "clipped" / "paUwYVvK6DY_00340_00560.mp4"
    opinion_source = ROOT / "temp_sources" / "online_batch_opinion_v1" / "clipped" / "7ZVqBwcXydU_00850_01400.mp4"
    return [
        {
            "id": "funny_fullscreen_v2",
            "title": "每周上片人的真实崩溃-全屏新版",
            "source_video": funny_source,
            "duration": 22.0,
            "layout": "full",
            "stage_label": "",
            "video_position": "46% 44%",
            "video_scale": 2.0,
            "video_origin": "46% 44%",
            "subtitles": funny_subtitles(),
            "blocks": [
                {"id": "ff_meter", "kind": "meter", "start": 0.00, "end": 2.20, "track": 20, "style": "position:absolute;left:56px;top:58px;width:430px;", "eyebrow": "本周进度", "title": "上片压力拉满", "chips": ["每周更新", "快审一下", "先别骂"]},
                {"id": "ff_chat", "kind": "chat", "start": 2.25, "end": 5.40, "track": 21, "style": "position:absolute;right:92px;top:122px;width:440px;", "eyebrow": "临时求救", "items": ["老板快审一下", "真的不是不想交稿", "题材它先跑路了"]},
                {"id": "ff_reaction", "kind": "reaction", "start": 5.45, "end": 8.90, "track": 22, "style": "position:absolute;right:122px;top:236px;width:330px;height:320px;", "asset": "assets/1F602.svg", "title": "怕被骂", "labels": ["不敢吹", "保命中"]},
                {"id": "ff_loader", "kind": "loader", "start": 8.95, "end": 11.70, "track": 23, "style": "position:absolute;left:72px;top:126px;width:450px;", "eyebrow": "灵感系统", "title": "正在加载下周题材"},
                {"id": "ff_story", "kind": "storyboard", "start": 12.00, "end": 16.25, "track": 24, "style": "position:absolute;left:54px;top:160px;width:590px;", "items": ["下周拍什么", "先别骂我", "快来点灵感"]},
                {"id": "ff_impact", "kind": "impact", "start": 16.35, "end": 21.60, "track": 25, "style": "position:absolute;left:70px;top:122px;width:560px;", "words": ["题材", "出现", "一下"], "note": "这一秒真的救命"},
            ],
        },
        {
            "id": "funny_right_v2",
            "title": "每周上片人的真实崩溃-居右新版",
            "source_video": funny_source,
            "duration": 22.0,
            "layout": "right",
            "stage_label": "",
            "video_position": "56% 44%",
            "video_scale": 2.25,
            "video_origin": "56% 44%",
            "subtitles": funny_subtitles(),
            "blocks": [
                {"id": "fr_meter", "kind": "meter", "start": 0.00, "end": 3.20, "track": 20, "style": "position:absolute;left:48px;top:92px;width:820px;", "eyebrow": "创作警报", "title": "本周选题库存告急", "chips": ["上片", "审稿", "压力"]},
                {"id": "fr_flow", "kind": "flow", "start": 3.40, "end": 8.35, "track": 21, "style": "position:absolute;left:48px;top:326px;width:830px;", "eyebrow": "崩溃路径", "title": "一个创作者的内心流程", "items": ["想到选题", "担心被骂", "重新想题材"], "result": "循环一整天", "direction": "horizontal", "wrap": 6},
                {"id": "fr_story", "kind": "storyboard", "start": 11.85, "end": 16.40, "track": 22, "style": "position:absolute;left:48px;top:118px;width:830px;", "items": ["下周主题", "观众反应", "自我怀疑"]},
                {"id": "fr_impact", "kind": "impact", "start": 16.45, "end": 21.80, "track": 23, "style": "position:absolute;left:58px;top:314px;width:820px;", "words": ["题材", "救场"], "note": "突然想到的那一秒，像开灯"},
            ],
        },
        {
            "id": "opinion_fullscreen_v2",
            "title": "限流观点拆解-全屏新版",
            "source_video": opinion_source,
            "duration": 55.0,
            "layout": "full",
            "stage_label": "",
            "video_position": "56% 50%",
            "subtitles": opinion_subtitles(),
            "blocks": [
                {"id": "of_hook", "kind": "impact", "start": 0.20, "end": 6.20, "track": 20, "style": "position:absolute;left:64px;top:72px;width:610px;", "words": ["名字", "限流", "实验"], "note": "先把变量摆出来"},
                {"id": "of_flow1", "kind": "flow", "start": 7.40, "end": 16.70, "track": 21, "style": "position:absolute;left:64px;top:120px;width:620px;", "eyebrow": "标题假设", "title": "标题里的名字，可能先触发分发判断", "items": ["标题出现名字", "进入第一轮判断", "分发被收紧"], "result": "不是结论，是一次可观察的假设", "direction": "vertical", "wrap": 10},
                {"id": "of_compare", "kind": "compare", "start": 17.10, "end": 23.65, "track": 22, "style": "position:absolute;left:64px;top:116px;width:640px;", "eyebrow": "对照组", "title": "同一内容，不同标题", "rows": [["版本一", "不提名字：可能正常进入推荐"], ["版本二", "提到名字：观察是否立刻收紧"], ["差异", "播放量变化才是这次观察的重点"]]},
                {"id": "of_flow2", "kind": "flow", "start": 23.80, "end": 34.00, "track": 23, "style": "position:absolute;left:64px;top:112px;width:660px;", "eyebrow": "实验路径", "title": "不是一句话总结，而是三步验证", "items": ["先改标题", "保持观点不变", "观察分发反馈", "结果再次被限流"], "result": "每一步都会影响结果", "direction": "vertical", "wrap": 9},
                {"id": "of_time", "kind": "timeline", "start": 35.00, "end": 49.20, "track": 24, "style": "position:absolute;left:64px;top:132px;width:660px;", "eyebrow": "补充样本", "title": "同一天的相近话题", "items": [["同一天", "有人也发类似内容"], ["相近话题", "围绕健康信息讨论"], ["不同平台", "分发环境可能改变结果"]]},
                {"id": "of_channel", "kind": "channel", "start": 49.40, "end": 54.80, "track": 25, "style": "position:absolute;left:64px;top:160px;width:560px;", "eyebrow": "渠道变量", "title": "微信", "body": "换一个发布场，结果可能完全不同。"},
            ],
        },
        {
            "id": "opinion_right_v2",
            "title": "限流观点拆解-居右新版",
            "source_video": opinion_source,
            "duration": 55.0,
            "layout": "right",
            "stage_label": "",
            "video_position": "56% 50%",
            "subtitles": opinion_subtitles(),
            "blocks": [
                {"id": "or_flow1", "kind": "flow", "start": 0.20, "end": 12.20, "track": 20, "style": "position:absolute;left:48px;top:86px;width:830px;", "eyebrow": "核心变量", "title": "名字进入标题之后", "items": ["标题变量", "平台初筛", "推荐放量", "限流反馈"], "result": "一层一层看清变化", "direction": "vertical", "wrap": 8},
                {"id": "or_compare", "kind": "compare", "start": 12.50, "end": 24.00, "track": 21, "style": "position:absolute;left:48px;top:88px;width:840px;", "eyebrow": "对照观察", "title": "标题写法对分发的影响", "rows": [["版本一", "不提名字，保留原观点"], ["版本二", "标题里加入特定名字"], ["观察", "看第一波放量是否变化"]]},
                {"id": "or_flow2", "kind": "flow", "start": 24.20, "end": 34.20, "track": 22, "style": "position:absolute;left:48px;top:288px;width:840px;", "eyebrow": "验证过程", "title": "故意触发，再看反馈", "items": ["改标题", "发出视频", "等待推荐", "记录结果"], "result": "反馈再次指向限流", "direction": "horizontal", "wrap": 6},
                {"id": "or_time", "kind": "timeline", "start": 35.00, "end": 49.30, "track": 23, "style": "position:absolute;left:48px;top:98px;width:840px;", "eyebrow": "旁证", "title": "同一天，不同发布场", "items": [["样本", "相近健康话题"], ["时间", "同一天出现"], ["渠道", "微信发布"]]},
                {"id": "or_channel", "kind": "channel", "start": 49.45, "end": 54.80, "track": 24, "style": "position:absolute;left:48px;top:132px;width:800px;", "eyebrow": "最终变量", "title": "渠道差异", "body": "讨论平台分发时，发布场本身也要进入判断。"},
            ],
        },
    ]


def write_project(spec: dict) -> dict:
    project_dir = OUT_ROOT / spec["id"]
    hf_dir = project_dir / "hyperframes"
    assets_dir = hf_dir / "assets"
    qa_dir = project_dir / "qa_frames"
    for path in (project_dir, hf_dir, assets_dir, qa_dir):
        path.mkdir(parents=True, exist_ok=True)

    normalize_video(spec["source_video"], assets_dir / "main.video.mp4")
    extract_audio(spec["source_video"], assets_dir / "main.audio.wav")
    if not FONT_SOURCE.exists():
        raise RuntimeError(f"missing font source: {FONT_SOURCE}")
    shutil.copyfile(FONT_SOURCE, assets_dir / "ArialUnicode.ttf")

    for block in spec["blocks"]:
        if block["kind"] == "reaction":
            source_asset = ROOT / "resources" / "reaction-assets" / "openmoji" / Path(block.get("asset", "assets/1F602.svg")).name
            shutil.copyfile(source_asset, assets_dir / source_asset.name)
            block["asset"] = f"assets/{source_asset.name}"

    (hf_dir / "index.html").write_text(build_html(spec), encoding="utf-8")
    (hf_dir / "meta.json").write_text(
        json.dumps({"title": spec["title"], "duration": spec["duration"], "fps": 30}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lint = run([NODE, str(HF_CLI), "lint", str(hf_dir)], cwd=hf_dir)
    (project_dir / "lint.log").write_text((lint.stdout or "") + (lint.stderr or ""), encoding="utf-8")
    if lint.returncode != 0:
        raise RuntimeError(f"lint failed for {spec['id']}")

    preview_path = project_dir / "preview.mp4"
    render = run(
        [NODE, str(HF_CLI), "render", str(hf_dir), "-o", str(preview_path), "--fps", "30", "-q", "standard"],
        cwd=hf_dir,
    )
    (project_dir / "render.log").write_text((render.stdout or "") + (render.stderr or ""), encoding="utf-8")
    if render.returncode != 0 or not preview_path.exists():
        raise RuntimeError(f"render failed for {spec['id']}")

    qa_specs = []
    for block in spec["blocks"]:
        frame_path = qa_dir / f'{block["id"]}.jpg'
        extract_frame(preview_path, midpoint(block["start"], block["end"]), frame_path)
        qa_specs.append(
            {
                "id": block["id"],
                "kind": block["kind"],
                "start": block["start"],
                "end": block["end"],
                "frame": str(frame_path),
            }
        )
    render_contact_sheet(qa_specs, qa_dir, project_dir / "qa_contact_sheet.jpg")
    summary = {
        "id": spec["id"],
        "title": spec["title"],
        "layout": spec["layout"],
        "source_video": str(spec["source_video"]),
        "preview_path": str(preview_path),
        "hyperframes_dir": str(hf_dir),
        "qa_contact_sheet": str(project_dir / "qa_contact_sheet.jpg"),
        "blocks": qa_specs,
    }
    (project_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = [write_project(spec) for spec in create_specs()]
    (OUT_ROOT / "manual_codex_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
