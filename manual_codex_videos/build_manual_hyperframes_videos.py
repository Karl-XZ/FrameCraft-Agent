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
OUT_ROOT = ROOT / "manual_codex_videos" / "outputs"
HF_CLI = ROOT / "node_modules" / "hyperframes" / "dist" / "cli.js"
FONT_SOURCE = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
NODE = shutil.which("node") or "node"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

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
        return src
    rows = [src[i : i + width] for i in range(0, len(src), width)]
    return "<br/>".join(esc(row) for row in rows)


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


def clip_duration(item: dict) -> float:
    return max(0.06, float(item["end"]) - float(item["start"]))


def layer_life(kind: str, duration: float) -> str:
    if kind == "subtitle":
        return f"--dur:{duration:.3f}s;animation:subtitleLife var(--dur) linear both;"
    life_name = {
        "hook": "titleLife",
        "sticker": "popLife",
        "bubble": "bubbleLife",
        "comic": "comicLife",
        "burst": "burstLife",
        "notes": "panelLife",
        "loading": "panelLife",
        "thesis": "panelLife",
        "compare": "panelLife",
        "flow": "panelLife",
        "evidence": "panelLife",
        "channel": "panelLife",
    }.get(kind, "panelLife")
    return f"--dur:{duration:.3f}s;animation:{life_name} var(--dur) linear both;"


def highlight_html(text: str, keyword: str) -> str:
    clean = esc(text)
    if not keyword:
        return clean
    return clean.replace(esc(keyword), f'<span class="hl">{esc(keyword)}</span>', 1)


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
    canvas = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), (9, 18, 31))
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
            thumb = im.convert("RGB").resize((thumb_w, thumb_h))
            canvas.paste(thumb, (x, y))
        label = f"{item['id']}  {item['label']}  {item['start']:.2f}-{item['end']:.2f}s"
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label_h), fill=(14, 25, 42))
        draw.text((x + 12, y + thumb_h + 12), label, font=font, fill=(240, 248, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def subtitle_block_html(spec: dict, width: int, height: int, track_index: int) -> str:
    text_html = highlight_html(spec["text"], spec.get("highlight", ""))
    fs = int(height * 0.047)
    duration = max(0.06, spec["end"] - spec["start"] - 0.02)
    return (
        f'<div id="{spec["id"]}" class="clip subtitle" data-start="{spec["start"]:.3f}" '
        f'data-duration="{duration:.3f}" data-track-index="{track_index}" '
        f'style="position:absolute;left:0;right:0;bottom:0;height:26%;padding:0 6% 4.8%;'
        f'display:flex;justify-content:center;align-items:flex-end;{layer_life("subtitle", duration)}">'
        f'<div class="subtitle-card" style="max-width:86%;padding:16px 24px 14px;border-radius:28px;'
        'background:rgba(10,18,26,.58);backdrop-filter:blur(18px);'
        f'font-family:{FONT_STACK};font-size:{fs}px;line-height:1.16;font-weight:900;'
        'color:#F8FAFC;text-align:center;text-shadow:0 2px 14px rgba(0,0,0,.52);">'
        f'{text_html}</div></div>'
    )


def hook_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:7.5%;width:42%;pointer-events:none;{layer_life("hook", clip_duration(block))}">'
        '<div class="motion-hook" style="position:relative;display:block;">'
        f'<div style="display:inline-block;padding:8px 16px;border-radius:999px;'
        'background:rgba(255,255,255,.12);font-size:18px;font-weight:800;color:#C7D2FE;'
        f'font-family:{FONT_STACK};letter-spacing:.08em;">{esc(block.get("eyebrow", ""))}</div>'
        f'<div style="margin-top:16px;font-size:{int(height*0.065)}px;line-height:1.02;'
        'font-weight:900;color:#FACC15;text-shadow:0 6px 18px rgba(0,0,0,.34);'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 12)}</div></div></div>'
    )


def sticker_block(block: dict, height: int) -> str:
    asset = esc(block["asset"])
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 11)}" '
        f'style="position:absolute;left:5.5%;top:26%;width:24%;min-width:320px;pointer-events:none;{layer_life("sticker", clip_duration(block))}">'
        '<div class="motion-sticker" style="display:flex;align-items:center;gap:16px;padding:16px 18px;border-radius:28px;'
        'background:rgba(255,255,255,.94);box-shadow:0 18px 48px rgba(0,0,0,.24);position:relative;overflow:hidden;">'
        f'<img class="emoji-pulse" src="{asset}" alt="" style="width:{int(height*0.12)}px;height:{int(height*0.12)}px;object-fit:contain;flex:0 0 auto;"/>'
        '<div style="min-width:0;">'
        f'<div style="font-size:{int(height*0.028)}px;line-height:1.15;font-weight:900;color:#111827;'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 8)}</div>'
        f'<div style="margin-top:6px;font-size:{int(height*0.018)}px;color:#6B7280;font-weight:800;'
        f'font-family:{FONT_STACK};">{esc(block.get("caption", ""))}</div>'
        '</div></div></div>'
    )


def bubble_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 12)}" '
        f'style="position:absolute;left:5.5%;top:49%;width:28%;pointer-events:none;{layer_life("bubble", clip_duration(block))}">'
        '<div class="motion-bubble" style="position:relative;padding:18px 22px;border-radius:26px;background:rgba(255,255,255,.92);'
        'box-shadow:0 18px 40px rgba(0,0,0,.26);">'
        '<div class="bubble-tail" style="position:absolute;left:22px;bottom:-16px;width:32px;height:32px;background:rgba(255,255,255,.92);'
        'clip-path:polygon(0 0,100% 0,0 100%);"></div>'
        f'<div style="font-size:{int(height*0.032)}px;line-height:1.18;font-weight:900;color:#111827;'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 10)}</div>'
        f'<div style="margin-top:8px;font-size:{int(height*0.018)}px;color:#64748B;font-weight:800;'
        f'font-family:{FONT_STACK};">{esc(block.get("caption", ""))}</div>'
        '</div></div>'
    )


def comic_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:18%;width:26%;transform:rotate(-4deg);pointer-events:none;{layer_life("comic", clip_duration(block))}">'
        '<div class="motion-comic" style="padding:14px 18px;border-radius:20px;background:#F8FAFC;border:4px solid #111827;'
        'box-shadow:12px 12px 0 #FACC15,0 20px 40px rgba(0,0,0,.26);">'
        f'<div style="font-size:{int(height*0.03)}px;line-height:1.12;font-weight:900;color:#111827;'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 8)}</div>'
        '</div></div>'
    )


def burst_block(block: dict, height: int) -> str:
    size = int(height * 0.18)
    points = [
        (0.50, 0.00), (0.63, 0.27), (1.00, 0.18), (0.76, 0.50), (1.00, 0.82),
        (0.62, 0.73), (0.50, 1.00), (0.38, 0.73), (0.00, 0.82), (0.24, 0.50),
        (0.00, 0.18), (0.37, 0.27),
    ]
    polygon = " ".join(f"{x*size:.1f},{y*size:.1f}" for x, y in points)
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 12)}" '
        f'style="position:absolute;right:8%;top:12%;width:18%;min-width:220px;pointer-events:none;{layer_life("burst", clip_duration(block))}">'
        f'<svg class="motion-burst" viewBox="0 0 {size} {size}" style="width:100%;height:auto;filter:drop-shadow(0 18px 30px rgba(0,0,0,.24));">'
        f'<polygon class="burst-star" points="{polygon}" fill="#FACC15" stroke="#111827" stroke-width="6"></polygon></svg>'
        f'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;'
        f'font-size:{int(height*0.03)}px;line-height:1.05;font-weight:900;color:#111827;'
        f'font-family:{FONT_STACK};text-align:center;">{wrap_text(block["title"], 5)}</div></div>'
    )


def notes_block(block: dict, height: int) -> str:
    note_html = []
    colors = ["#FEF3C7", "#DBEAFE", "#FCE7F3"]
    rotations = ["-4deg", "3deg", "-2deg"]
    for idx, text in enumerate(block["items"]):
        note_html.append(
            f'<div class="note-wrap" style="--i:{idx};transform:rotate({rotations[idx % len(rotations)]});">'
            '<div class="note-card" style="padding:16px 16px 18px;border-radius:18px;'
            f'background:{colors[idx % len(colors)]};'
            'box-shadow:0 14px 24px rgba(0,0,0,.18);">'
            f'<div style="font-size:{int(height*0.027)}px;line-height:1.14;font-weight:900;color:#111827;'
            f'font-family:{FONT_STACK};">{wrap_text(text, 7)}</div></div></div>'
        )
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:18%;width:30%;pointer-events:none;{layer_life("notes", clip_duration(block))}">'
        f'<div class="motion-notes" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">{"".join(note_html)}</div></div>'
    )


def thesis_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:14%;width:34%;pointer-events:none;{layer_life("thesis", clip_duration(block))}">'
        '<div class="motion-panel thesis-panel" style="padding:20px 22px;border-radius:26px;background:rgba(8,15,24,.86);position:relative;overflow:hidden;'
        'border:1px solid rgba(56,189,248,.34);box-shadow:0 18px 42px rgba(0,0,0,.24);">'
        f'<div style="display:inline-block;padding:7px 14px;border-radius:999px;background:rgba(56,189,248,.16);'
        f'color:#7DD3FC;font-size:{int(height*0.017)}px;font-weight:900;letter-spacing:.05em;'
        f'font-family:{FONT_STACK};">{esc(block.get("eyebrow", ""))}</div>'
        f'<div style="margin-top:14px;font-size:{int(height*0.04)}px;line-height:1.08;font-weight:900;color:#F8FAFC;'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 10)}</div>'
        f'<div style="margin-top:12px;font-size:{int(height*0.02)}px;line-height:1.42;color:#CBD5E1;'
        f'font-family:{FONT_STACK};">{wrap_text(block.get("body", ""), 18)}</div></div></div>'
    )


def compare_block(block: dict, height: int) -> str:
    rows = []
    for idx, (label, text) in enumerate(block["rows"]):
        rows.append(
            f'<div class="panel-row" style="--i:{idx};display:grid;grid-template-columns:82px 1fr;gap:14px;align-items:start;'
            'padding:12px 0;border-top:1px solid rgba(255,255,255,.08);">'
            f'<div style="display:flex;align-items:center;justify-content:center;padding:6px 8px;border-radius:999px;'
            f'background:rgba(56,189,248,.14);color:#7DD3FC;font-size:{int(height*0.015)}px;font-weight:900;'
            f'font-family:{FONT_STACK};">{esc(label)}</div>'
            f'<div style="font-size:{int(height*0.02)}px;line-height:1.42;color:#F8FAFC;font-weight:800;'
            f'font-family:{FONT_STACK};">{wrap_text(text, 16)}</div></div>'
        )
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:14%;width:38%;pointer-events:none;{layer_life("compare", clip_duration(block))}">'
        '<div class="motion-panel compare-panel" style="padding:18px 22px;border-radius:26px;background:rgba(8,15,24,.88);position:relative;overflow:hidden;'
        'border:1px solid rgba(56,189,248,.28);box-shadow:0 18px 42px rgba(0,0,0,.24);">'
        f'<div style="font-size:{int(height*0.026)}px;font-weight:900;color:#7DD3FC;font-family:{FONT_STACK};">{esc(block["title"])}</div>'
        f'{"".join(rows)}</div></div>'
    )


def flow_block(block: dict, height: int) -> str:
    steps_html = []
    for idx, step in enumerate(block["steps"], start=1):
        steps_html.append(
            f'<div class="flow-step" style="--i:{idx - 1};display:flex;align-items:center;gap:14px;padding:12px 14px;border-radius:18px;'
            'background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);">'
            f'<div style="width:{int(height*0.036)}px;height:{int(height*0.036)}px;border-radius:999px;'
            'display:flex;align-items:center;justify-content:center;background:#38BDF8;color:#07121C;'
            f'font-size:{int(height*0.016)}px;font-weight:900;font-family:{MONO_STACK};">{idx}</div>'
            f'<div style="flex:1;font-size:{int(height*0.02)}px;line-height:1.38;color:#F8FAFC;font-weight:800;'
            f'font-family:{FONT_STACK};">{wrap_text(step, 18)}</div></div>'
        )
        if idx < len(block["steps"]):
            steps_html.append(
                f'<div class="flow-arrow" style="display:flex;justify-content:center;align-items:center;height:{int(height*0.032)}px;'
                'font-size:34px;color:#38BDF8;">↓</div>'
            )
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:14%;width:40%;pointer-events:none;{layer_life("flow", clip_duration(block))}">'
        '<div class="motion-panel flow-panel" style="padding:18px 22px;border-radius:26px;background:rgba(8,15,24,.88);position:relative;overflow:hidden;'
        'border:1px solid rgba(56,189,248,.28);box-shadow:0 18px 42px rgba(0,0,0,.24);">'
        f'<div style="font-size:{int(height*0.026)}px;font-weight:900;color:#7DD3FC;font-family:{FONT_STACK};">{esc(block["title"])}</div>'
        f'<div style="margin-top:12px;display:flex;flex-direction:column;gap:6px;">{"".join(steps_html)}</div></div></div>'
    )


def evidence_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:16%;width:34%;pointer-events:none;{layer_life("evidence", clip_duration(block))}">'
        '<div class="motion-panel evidence-panel" style="padding:18px 22px;border-radius:26px;background:rgba(255,255,255,.95);position:relative;overflow:hidden;'
        'box-shadow:0 18px 42px rgba(0,0,0,.2);border-left:8px solid #0EA5E9;">'
        f'<div style="font-size:{int(height*0.017)}px;font-weight:900;color:#0EA5E9;letter-spacing:.05em;'
        f'font-family:{FONT_STACK};">{esc(block.get("eyebrow", ""))}</div>'
        f'<div style="margin-top:10px;font-size:{int(height*0.033)}px;line-height:1.1;font-weight:900;color:#111827;'
        f'font-family:{FONT_STACK};">{wrap_text(block["title"], 10)}</div>'
        f'<div style="margin-top:12px;font-size:{int(height*0.019)}px;line-height:1.44;color:#334155;'
        f'font-family:{FONT_STACK};">{wrap_text(block.get("body", ""), 17)}</div></div></div>'
    )


def channel_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 10)}" '
        f'style="position:absolute;left:5.5%;top:16%;width:32%;pointer-events:none;{layer_life("channel", clip_duration(block))}">'
        '<div class="motion-panel channel-panel" style="padding:18px 22px;border-radius:24px;background:rgba(8,15,24,.88);position:relative;overflow:hidden;'
        'border:1px solid rgba(148,163,184,.24);box-shadow:0 18px 42px rgba(0,0,0,.24);">'
        f'<div style="font-size:{int(height*0.017)}px;font-weight:900;color:#94A3B8;letter-spacing:.05em;'
        f'font-family:{FONT_STACK};">{esc(block.get("eyebrow", ""))}</div>'
        f'<div style="margin-top:12px;display:flex;align-items:center;gap:14px;">'
        f'<div style="padding:10px 16px;border-radius:999px;background:#10B981;color:#062C22;'
        f'font-size:{int(height*0.022)}px;font-weight:900;font-family:{FONT_STACK};">{esc(block["title"])}</div>'
        f'<div style="font-size:{int(height*0.02)}px;line-height:1.36;color:#E2E8F0;font-weight:800;'
        f'font-family:{FONT_STACK};">{wrap_text(block.get("body", ""), 12)}</div></div></div></div>'
    )


def loading_block(block: dict, height: int) -> str:
    return (
        f'<div id="{block["id"]}" class="clip" data-start="{block["start"]:.3f}" '
        f'data-duration="{block["end"] - block["start"]:.3f}" data-track-index="{block.get("track", 9)}" '
        f'style="position:absolute;left:5.5%;top:18%;width:28%;pointer-events:none;{layer_life("loading", clip_duration(block))}">'
        '<div class="motion-panel loading-panel" style="display:flex;align-items:center;gap:16px;padding:18px 20px;border-radius:24px;position:relative;overflow:hidden;'
        'background:rgba(8,15,24,.86);border:1px solid rgba(255,255,255,.08);box-shadow:0 18px 40px rgba(0,0,0,.22);">'
        f'<div id="{block["id"]}-spinner" style="width:{int(height*0.05)}px;height:{int(height*0.05)}px;'
        'border-radius:999px;border:5px solid rgba(255,255,255,.14);border-top-color:#FACC15;animation:spin 1.1s linear infinite;"></div>'
        '<div>'
        f'<div style="font-size:{int(height*0.023)}px;font-weight:900;color:#F8FAFC;font-family:{FONT_STACK};">{esc(block["title"])}</div>'
        f'<div style="margin-top:4px;font-size:{int(height*0.017)}px;color:#94A3B8;font-weight:700;font-family:{FONT_STACK};">{esc(block.get("caption", ""))}</div>'
        '</div></div></div>'
    )


def block_html(block: dict, height: int) -> str:
    kind = block["kind"]
    if kind == "hook":
        return hook_block(block, height)
    if kind == "sticker":
        return sticker_block(block, height)
    if kind == "bubble":
        return bubble_block(block, height)
    if kind == "comic":
        return comic_block(block, height)
    if kind == "burst":
        return burst_block(block, height)
    if kind == "notes":
        return notes_block(block, height)
    if kind == "thesis":
        return thesis_block(block, height)
    if kind == "compare":
        return compare_block(block, height)
    if kind == "flow":
        return flow_block(block, height)
    if kind == "evidence":
        return evidence_block(block, height)
    if kind == "channel":
        return channel_block(block, height)
    if kind == "loading":
        return loading_block(block, height)
    raise ValueError(f"unknown block kind {kind}")


def block_tweens(blocks: list[dict]) -> list[str]:
    tweens: list[str] = []
    for block in blocks:
        start = block["start"]
        bid = block["id"]
        kind = block["kind"]
        if kind in {"hook", "thesis", "compare", "flow", "evidence", "channel", "notes", "loading"}:
            tweens.append(
                f'tl.from("#{bid}", {{opacity:0, y:22, scale:0.96, duration:0.42, ease:"power3.out"}}, {start:.3f});'
            )
        elif kind == "bubble":
            tweens.append(
                f'tl.from("#{bid}", {{opacity:0, y:18, scale:0.7, duration:0.32, ease:"back.out(2.1)"}}, {start:.3f});'
            )
        elif kind == "sticker":
            tweens.append(
                f'tl.from("#{bid}", {{opacity:0, x:-16, scale:0.62, duration:0.34, ease:"back.out(2.2)"}}, {start:.3f});'
            )
            tweens.append(
                f'tl.to("#{bid}", {{y:-7, duration:0.6, yoyo:true, repeat:2, ease:"sine.inOut"}}, {(start + 0.18):.3f});'
            )
        elif kind == "comic":
            tweens.append(
                f'tl.from("#{bid}", {{opacity:0, rotation:-10, scale:0.55, duration:0.28, ease:"back.out(2.6)"}}, {start:.3f});'
            )
        elif kind == "burst":
            tweens.append(
                f'tl.from("#{bid}", {{opacity:0, scale:0.18, rotation:-18, duration:0.24, ease:"back.out(2.8)"}}, {start:.3f});'
            )
        if kind == "loading":
            tweens.append(
                f'tl.to("#{bid}-spinner", {{rotation:360, duration:1.1, repeat:2, ease:"none"}}, {start:.3f});'
            )
    return tweens


def subtitle_tweens(subtitles: list[dict]) -> list[str]:
    tweens: list[str] = []
    for sub in subtitles:
        start = sub["start"]
        sid = sub["id"]
        tweens.append(
            f'tl.from("#{sid}", {{opacity:0, y:8, duration:0.18, ease:"power2.out"}}, {start:.3f});'
        )
    return tweens


def progress_bar(duration: float) -> str:
    return (
        f'<div id="progress-wrap" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="99" '
        'style="position:absolute;left:0;right:0;bottom:0;height:8px;background:rgba(255,255,255,.14);">'
        f'<div id="progress-bar" style="height:100%;width:0%;background:#FACC15;animation:progressFill {duration:.3f}s linear forwards;"></div></div>'
    )


def build_html(spec: dict, width: int, height: int, duration: float) -> str:
    blocks = spec["blocks"]
    subtitles = spec["subtitles"]
    clips: list[str] = []
    clips.append(
        f'<video id="main-video" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="1" '
        f'src="assets/main.video.mp4" playsinline muted style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:{spec["video_position"]};"></video>'
    )
    clips.append(
        '<div id="left-scrim" class="clip" data-start="0" data-duration="{dur}" data-track-index="2" '
        'style="position:absolute;left:0;top:0;width:46%;height:100%;background:linear-gradient(90deg,rgba(5,10,18,.82),rgba(5,10,18,.42) 58%,rgba(5,10,18,0) 100%);"></div>'.format(dur=f"{duration:.3f}")
    )
    clips.append(
        '<div id="bottom-scrim" class="clip" data-start="0" data-duration="{dur}" data-track-index="3" '
        'style="position:absolute;left:0;bottom:0;width:100%;height:34%;background:linear-gradient(180deg,rgba(5,10,18,0),rgba(5,10,18,.22) 24%,rgba(5,10,18,.78) 72%,rgba(5,10,18,.95) 100%);"></div>'.format(dur=f"{duration:.3f}")
    )
    for idx, sub in enumerate(subtitles, start=1):
        clips.append(subtitle_block_html(sub, width, height, 50 + idx))
    for block in blocks:
        clips.append(block_html(block, height))
    clips.append(progress_bar(duration))
    audios = [
        f'<audio id="main-audio" src="assets/main.audio.wav" data-start="0" data-duration="{duration:.3f}" data-track-index="4"></audio>'
    ]
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{esc(spec["title"])}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background: #050A12;
    }}
    @font-face {{
      font-family: "{FONT_FAMILY}";
      src: url("assets/ArialUnicode.ttf") format("truetype");
      font-display: swap;
    }}
    @keyframes subtitleLife {{
      0% {{ opacity: 0; transform: translateY(12px) scale(.98); filter: blur(3px); }}
      10% {{ opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }}
      82% {{ opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }}
      100% {{ opacity: 0; transform: translateY(-10px) scale(.99); filter: blur(2px); }}
    }}
    @keyframes titleLife {{
      0% {{ opacity: 0; clip-path: inset(0 100% 0 0); filter: blur(5px); }}
      16% {{ opacity: 1; clip-path: inset(0 0 0 0); filter: blur(0); }}
      82% {{ opacity: 1; clip-path: inset(0 0 0 0); filter: blur(0); }}
      100% {{ opacity: 0; clip-path: inset(0 0 0 100%); filter: blur(4px); }}
    }}
    @keyframes panelLife {{
      0% {{ opacity: 0; clip-path: inset(14% 0 14% 0 round 26px); filter: blur(8px); }}
      13% {{ opacity: 1; clip-path: inset(0 0 0 0 round 26px); filter: blur(0); }}
      84% {{ opacity: 1; clip-path: inset(0 0 0 0 round 26px); filter: blur(0); }}
      100% {{ opacity: 0; clip-path: inset(9% 0 9% 0 round 26px); filter: blur(7px); }}
    }}
    @keyframes popLife {{
      0% {{ opacity: 0; clip-path: circle(0% at 18% 45%); filter: blur(4px); }}
      18% {{ opacity: 1; clip-path: circle(135% at 18% 45%); filter: blur(0); }}
      84% {{ opacity: 1; clip-path: circle(135% at 18% 45%); filter: blur(0); }}
      100% {{ opacity: 0; clip-path: circle(0% at 18% 45%); filter: blur(4px); }}
    }}
    @keyframes bubbleLife {{
      0% {{ opacity: 0; clip-path: ellipse(0% 0% at 12% 80%); filter: blur(4px); }}
      16% {{ opacity: 1; clip-path: ellipse(130% 130% at 12% 80%); filter: blur(0); }}
      84% {{ opacity: 1; clip-path: ellipse(130% 130% at 12% 80%); filter: blur(0); }}
      100% {{ opacity: 0; clip-path: ellipse(0% 0% at 12% 80%); filter: blur(4px); }}
    }}
    @keyframes comicLife {{
      0% {{ opacity: 0; clip-path: polygon(50% 50%,50% 50%,50% 50%,50% 50%); filter: blur(3px); }}
      16% {{ opacity: 1; clip-path: polygon(0 0,100% 0,100% 100%,0 100%); filter: blur(0); }}
      84% {{ opacity: 1; clip-path: polygon(0 0,100% 0,100% 100%,0 100%); filter: blur(0); }}
      100% {{ opacity: 0; clip-path: polygon(50% 0,100% 50%,50% 100%,0 50%); filter: blur(3px); }}
    }}
    @keyframes burstLife {{
      0% {{ opacity: 0; filter: blur(3px) saturate(.6); }}
      12% {{ opacity: 1; filter: blur(0) saturate(1.12); }}
      82% {{ opacity: 1; filter: blur(0) saturate(1.12); }}
      100% {{ opacity: 0; filter: blur(3px) saturate(.7); }}
    }}
    @keyframes hookDrift {{
      0%,100% {{ transform: translate3d(0,0,0); }}
      50% {{ transform: translate3d(10px,-8px,0); }}
    }}
    @keyframes stickerWiggle {{
      0%,100% {{ transform: translateY(0) rotate(-1.2deg); }}
      35% {{ transform: translateY(-9px) rotate(1.8deg); }}
      70% {{ transform: translateY(2px) rotate(-.8deg); }}
    }}
    @keyframes emojiPulse {{
      0%,100% {{ transform: scale(1) rotate(0deg); }}
      45% {{ transform: scale(1.12) rotate(-5deg); }}
      70% {{ transform: scale(.98) rotate(4deg); }}
    }}
    @keyframes bubbleBreath {{
      0%,100% {{ transform: translateY(0) scale(1); }}
      50% {{ transform: translateY(-5px) scale(1.025); }}
    }}
    @keyframes comicJitter {{
      0%,100% {{ transform: translate(0,0) rotate(0deg); }}
      28% {{ transform: translate(4px,-3px) rotate(1.4deg); }}
      56% {{ transform: translate(-3px,2px) rotate(-1deg); }}
    }}
    @keyframes burstPulse {{
      0%,100% {{ transform: scale(1) rotate(0deg); }}
      45% {{ transform: scale(1.12) rotate(6deg); }}
      70% {{ transform: scale(.96) rotate(-3deg); }}
    }}
    @keyframes panelFloat {{
      0%,100% {{ transform: translateY(0); box-shadow: 0 18px 42px rgba(0,0,0,.24); }}
      50% {{ transform: translateY(-6px); box-shadow: 0 25px 54px rgba(0,0,0,.30); }}
    }}
    @keyframes rowPulse {{
      0% {{ opacity: .38; transform: translateX(-10px); }}
      22% {{ opacity: 1; transform: translateX(0); }}
      100% {{ opacity: 1; transform: translateX(0); }}
    }}
    @keyframes noteFloat {{
      0%,100% {{ transform: translateY(0) scale(1); }}
      50% {{ transform: translateY(-8px) scale(1.025); }}
    }}
    @keyframes arrowFlow {{
      0%,100% {{ transform: translateY(-2px); opacity: .55; }}
      50% {{ transform: translateY(5px); opacity: 1; }}
    }}
    @keyframes cardSweep {{
      0% {{ transform: translateX(-130%) skewX(-18deg); opacity: 0; }}
      35% {{ opacity: .72; }}
      70% {{ opacity: .18; }}
      100% {{ transform: translateX(170%) skewX(-18deg); opacity: 0; }}
    }}
    @keyframes spin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
    @keyframes progressFill {{
      from {{ width: 0%; }}
      to {{ width: 100%; }}
    }}
    #stage {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background: #050A12;
      font-family: {FONT_STACK};
    }}
    .subtitle .hl {{
      color: #FACC15;
    }}
    .subtitle-card {{
      animation: subtitleCardBreath 1.35s ease-in-out infinite alternate;
    }}
    @keyframes subtitleCardBreath {{
      from {{ box-shadow: 0 8px 26px rgba(0,0,0,.18); }}
      to {{ box-shadow: 0 12px 38px rgba(250,204,21,.18); }}
    }}
    .motion-hook {{
      animation: hookDrift 2.9s ease-in-out infinite;
    }}
    .motion-hook::after,
    .motion-sticker::after,
    .motion-panel::after {{
      content: "";
      position: absolute;
      top: -20%;
      left: 0;
      width: 30%;
      height: 140%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.25), transparent);
      animation: cardSweep 2.6s ease-in-out infinite;
      pointer-events: none;
    }}
    .motion-sticker {{
      animation: stickerWiggle 1.28s ease-in-out infinite;
    }}
    .emoji-pulse {{
      animation: emojiPulse 1.05s ease-in-out infinite;
      transform-origin: 50% 80%;
    }}
    .motion-bubble {{
      animation: bubbleBreath 1.15s ease-in-out infinite;
      transform-origin: 12% 100%;
    }}
    .bubble-tail {{
      animation: arrowFlow .82s ease-in-out infinite;
    }}
    .motion-comic {{
      animation: comicJitter .74s steps(2, end) infinite;
    }}
    .motion-burst {{
      animation: burstPulse .78s ease-in-out infinite;
      transform-origin: 50% 50%;
    }}
    .burst-star {{
      animation: burstPulse .92s ease-in-out infinite reverse;
      transform-origin: 50% 50%;
    }}
    .motion-panel {{
      animation: panelFloat 2.45s ease-in-out infinite;
    }}
    .motion-panel::after {{
      background: linear-gradient(90deg, transparent, rgba(125,211,252,.22), transparent);
      animation-duration: 3.15s;
    }}
    .panel-row,
    .flow-step {{
      animation: rowPulse .78s ease-out both;
      animation-delay: calc(.16s + var(--i) * .18s);
    }}
    .flow-arrow {{
      animation: arrowFlow .9s ease-in-out infinite;
    }}
    .note-wrap {{
      animation: rowPulse .55s ease-out both;
      animation-delay: calc(.08s + var(--i) * .15s);
    }}
    .note-card {{
      animation: noteFloat 1.4s ease-in-out infinite;
      animation-delay: calc(var(--i) * -.22s);
    }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="{width}" data-height="{height}">
    {''.join(clips)}
    {''.join(audios)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true }});
    tl.set({{}}, {{}}, {duration:.3f});
    window.__timelines["main"] = tl;
  </script>
</body>
</html>
"""


def create_spec() -> list[dict]:
    assets = ROOT / "resources" / "reaction-assets" / "openmoji"
    return [
        {
            "id": "funny_manual_codex",
            "title": "每周上片人的真实崩溃",
            "source_video": ROOT / "temp_sources" / "online_batch_funny_v4" / "clipped" / "paUwYVvK6DY_00340_00560.mp4",
            "duration": 22.0,
            "video_position": "58% 50%",
            "subtitles": [
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
            ],
            "blocks": [
                {"id": "blk_funny_hook", "kind": "hook", "start": 0.00, "end": 2.20, "eyebrow": "搞笑口播", "title": "每周上片人的真实崩溃"},
                {
                    "id": "blk_funny_sticker_1",
                    "kind": "sticker",
                    "track": 11,
                    "start": 1.45,
                    "end": 3.85,
                    "asset": "assets/1F602.svg",
                    "title": "先别骂",
                    "caption": "灵感还没跟上",
                },
                {
                    "id": "blk_funny_bubble_1",
                    "kind": "bubble",
                    "track": 12,
                    "start": 2.45,
                    "end": 4.90,
                    "title": "真的不是不想交稿",
                    "caption": "是题材先跑路了",
                },
                {
                    "id": "blk_funny_comic",
                    "kind": "comic",
                    "start": 4.60,
                    "end": 6.95,
                    "title": "我真的不敢乱吹",
                },
                {
                    "id": "blk_funny_burst",
                    "kind": "burst",
                    "start": 6.85,
                    "end": 8.90,
                    "title": "怕被骂",
                },
                {
                    "id": "blk_funny_loading",
                    "kind": "loading",
                    "start": 8.85,
                    "end": 11.55,
                    "title": "灵感加载中…",
                    "caption": "请给下周题材一点时间",
                },
                {
                    "id": "blk_funny_notes",
                    "kind": "notes",
                    "start": 12.00,
                    "end": 16.30,
                    "items": ["下周拍什么", "先别骂我", "快来点灵感"],
                },
                {
                    "id": "blk_funny_sticker_2",
                    "kind": "sticker",
                    "track": 11,
                    "start": 12.35,
                    "end": 14.75,
                    "asset": "assets/1F914.svg",
                    "title": "题材呢？",
                    "caption": "真的想不出来了",
                },
            ],
        },
        {
            "id": "opinion_manual_codex",
            "title": "为什么一提某个名字就更容易被限流？",
            "source_video": ROOT / "temp_sources" / "online_batch_opinion_v1" / "clipped" / "7ZVqBwcXydU_00850_01400.mp4",
            "duration": 55.0,
            "video_position": "56% 50%",
            "subtitles": [
                {"id": "sub_01", "start": 0.14, "end": 5.92, "text": "那么就会被限流，不放量了，就会第一波。", "highlight": "限流"},
                {"id": "sub_02", "start": 7.54, "end": 16.54, "text": "如果我不在题目里提到罗永浩，改个标题，可能就不会被限流了。", "highlight": "罗永浩"},
                {"id": "sub_03", "start": 17.18, "end": 23.74, "text": "不放量会差很多，但我就是故意在标题里提一下罗永浩。", "highlight": "故意"},
                {"id": "sub_04", "start": 23.74, "end": 33.52, "text": "就是要试验一下，是不是真的会被限流，结果果然又被限流了。", "highlight": "试验"},
                {"id": "sub_05", "start": 34.98, "end": 49.44, "text": "同一天里，也有人发了类似视频，也是围绕另一个健康话题。", "highlight": "同一天"},
                {"id": "sub_06", "start": 49.44, "end": 54.84, "text": "他的那条视频，是放在微信。", "highlight": "微信"},
            ],
            "blocks": [
                {
                    "id": "blk_op_hook",
                    "kind": "hook",
                    "start": 0.20,
                    "end": 5.60,
                    "eyebrow": "观点评论",
                    "title": "为什么一提名字，就更容易被限流？",
                },
                {
                    "id": "blk_op_thesis",
                    "kind": "thesis",
                    "start": 7.60,
                    "end": 11.60,
                    "eyebrow": "核心判断",
                    "title": "改标题也许能避开第一波限流",
                    "body": "不是内容突然变差，而是标题里的触发词，可能先改变平台的分发判断。",
                },
                {
                    "id": "blk_op_compare",
                    "kind": "compare",
                    "start": 17.20,
                    "end": 21.90,
                    "title": "观点拆解",
                    "rows": [
                        ("前提", "不放量的时候，播放差距会非常明显"),
                        ("动作", "标题里故意提一下特定名字"),
                        ("结果", "就是想看看分发会不会立刻变化"),
                    ],
                },
                {
                    "id": "blk_op_flow",
                    "kind": "flow",
                    "start": 23.85,
                    "end": 28.80,
                    "title": "试验路径",
                    "steps": [
                        "先改标题，保留原本观点",
                        "再观察平台是不是立刻收紧分发",
                        "最后验证：结果果然又被限流",
                    ],
                },
                {
                    "id": "blk_op_evidence",
                    "kind": "evidence",
                    "start": 35.05,
                    "end": 40.60,
                    "eyebrow": "补充案例",
                    "title": "同一天，也有人讲了相近话题",
                    "body": "说明单条视频的波动，不一定只由观点本身决定，分发环境和标题策略也在起作用。",
                },
                {
                    "id": "blk_op_channel",
                    "kind": "channel",
                    "start": 49.55,
                    "end": 53.60,
                    "eyebrow": "传播路径",
                    "title": "微信",
                    "body": "同样的话题，换个平台分发，结果就可能完全不同。",
                },
            ],
        },
    ]


def write_project(spec: dict) -> dict:
    width, height = 1920, 1080
    project_dir = OUT_ROOT / spec["id"]
    hf_dir = project_dir / "hyperframes"
    assets_dir = hf_dir / "assets"
    qa_dir = project_dir / "qa_frames"
    for path in (project_dir, hf_dir, assets_dir, qa_dir):
        path.mkdir(parents=True, exist_ok=True)

    normalized_video = assets_dir / "main.video.mp4"
    normalized_audio = assets_dir / "main.audio.wav"
    normalize_video(spec["source_video"], normalized_video)
    extract_audio(spec["source_video"], normalized_audio)
    if not FONT_SOURCE.exists():
        raise RuntimeError(f"missing font source: {FONT_SOURCE}")
    shutil.copyfile(FONT_SOURCE, assets_dir / "ArialUnicode.ttf")

    # Copy sticker assets used by this spec.
    for block in spec["blocks"]:
        if block["kind"] == "sticker":
            source_asset = ROOT / "resources" / "reaction-assets" / "openmoji" / Path(block["asset"]).name
            shutil.copyfile(source_asset, assets_dir / source_asset.name)
            block["asset"] = f"assets/{source_asset.name}"

    html_doc = build_html(spec, width, height, spec["duration"])
    (hf_dir / "index.html").write_text(html_doc, encoding="utf-8")
    (hf_dir / "meta.json").write_text(json.dumps({"title": spec["title"], "duration": spec["duration"], "fps": 30}, ensure_ascii=False, indent=2), encoding="utf-8")

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
        shot_time = midpoint(block["start"], block["end"])
        frame_path = qa_dir / f'{block["id"]}.jpg'
        extract_frame(preview_path, shot_time, frame_path)
        qa_specs.append(
            {
                "id": block["id"],
                "label": block["kind"],
                "start": block["start"],
                "end": block["end"],
                "frame": str(frame_path),
            }
        )
    render_contact_sheet(qa_specs, qa_dir, project_dir / "qa_contact_sheet.jpg")

    summary = {
        "id": spec["id"],
        "title": spec["title"],
        "source_video": str(spec["source_video"]),
        "preview_path": str(preview_path),
        "hyperframes_dir": str(hf_dir),
        "qa_dir": str(qa_dir),
        "qa_contact_sheet": str(project_dir / "qa_contact_sheet.jpg"),
        "blocks": qa_specs,
    }
    (project_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = [write_project(spec) for spec in create_spec()]
    (OUT_ROOT / "manual_codex_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
