"""HyperFrames 导出与渲染（需求 §8）。

把 unified_timeline.json 生成符合 HyperFrames 约定的 HTML 工程：
- 根 composition 带 data-composition-id / data-width / data-height / data-duration
- 每个 clip 带 class="clip" + data-start + data-duration + data-track-index
- 视频 muted + 独立 <audio> 承载 BGM
- 逐词 karaoke 字幕：caption-group + 每词 <span> + GSAP color 补间
- Hook 大标题 / lower-third / 进度条（persistent-overlay）
- GSAP 时间线注册到 window.__timelines（paused:true）
随后调用 hyperframes CLI 渲染 MP4；lint 未通过则中止渲染并写入 render_log.json。
"""
from __future__ import annotations

import html
import json
import shutil
import zipfile
from pathlib import Path

from ..config import HYPERFRAMES_CLI, NODE_EXE
from ..utils import run_cmd, write_json

QUALITY_MAP = {
    "720p": "draft",
    "720p快速预览": "draft",
    "1080p": "standard",
    "1080p正式导出": "standard",
    "4K旗舰版": "high",
}


def _rel_asset(path: str, hf_dir: Path) -> str:
    src = Path(path)
    assets_dir = hf_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / src.name
    if not dest.exists() and src.exists():
        shutil.copy2(src, dest)
    return f"assets/{src.name}"


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def generate_hyperframes_project(timeline: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    hf_dir = out_dir / "hyperframes"
    if hf_dir.exists():
        shutil.rmtree(hf_dir)
    hf_dir.mkdir(parents=True)

    project = timeline["project"]
    width, height, duration = project["width"], project["height"], project["duration"]
    fps = project.get("fps", 30)
    assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}
    template = (timeline.get("styles") or {}).get("template") or {}
    tokens = template.get("tokens") or {}
    primary = tokens.get("primary", "#38BDF8")
    accent = tokens.get("accent", "#FACC15")
    muted = tokens.get("muted", "#96A2B6")
    kicker = tokens.get("kicker", "FRAMECRAFT · 高级口播")
    stamp = tokens.get("stamp", "AI 重构")
    bg_grad = tokens.get("bg_grad", "linear-gradient(180deg,#07121C 0%,#0D2031 100%)")

    clips: list[str] = []
    audios: list[str] = []
    tweens: list[str] = []
    track_ends: dict[int, float] = {}

    def _norm_span(start: float, end: float) -> tuple[float, float]:
        start = round(float(start), 3)
        dur = max(0.1, round(float(end) - start, 3))
        return start, dur

    def _slot_on_track(track: int, start: float, end: float) -> tuple[float, float]:
        """避免同轨道 clip 浮点边界重叠（lint overlapping_clips_same_track）。"""
        start = round(float(start), 3)
        end = round(float(end), 3)
        last = track_ends.get(track, 0.0)
        if start < last + 0.001:
            start = round(last + 0.001, 3)
        dur = max(0.1, round(end - start, 3))
        track_ends[track] = round(start + dur, 3)
        return start, dur

    for item in timeline.get("items", []):
        itype = item.get("type")
        raw_start = float(item.get("timeline_start", 0))
        raw_end = float(item.get("timeline_end", raw_start + 1))
        start, dur = _norm_span(raw_start, raw_end)
        iid = item["id"]

        if itype == "video":
            src = assets_by_id.get(item.get("asset_id"), {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            track = 0 if item.get("role") == "a_roll" else 1
            start, dur = _slot_on_track(track, raw_start, raw_end)
            anims = item.get("animations") or []
            zoom = ""
            for a in anims:
                if a.get("type") == "scale":
                    tweens.append(
                        f'tl.fromTo("#{iid}", {{scale:{a.get("from",1)}}}, '
                        f'{{scale:{a.get("to",1.06)}, duration:{dur:.3f}, ease:"none"}}, {start:.3f});'
                    )
            if item.get("intro_animation") == "zoom_in":
                tweens.append(
                    f'tl.from("#{iid}", {{scale:1.2, opacity:0, duration:0.4, ease:"power2.out"}}, {start:.3f});'
                )
            clips.append(
                f'<video id="{iid}" class="clip" src="{rel}" muted playsinline '
                f'data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="{track}" '
                f'data-timeline-label="{_esc(item.get("role","video"))}" '
                f'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;{zoom}"></video>'
            )

        elif itype == "image":
            src = assets_by_id.get(item.get("asset_id"), {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            start, dur = _slot_on_track(2, raw_start, raw_end)
            if item.get("intro_animation") == "zoom_in":
                tweens.append(
                    f'tl.from("#{iid}", {{scale:1.2, opacity:0, duration:0.4, ease:"power2.out"}}, {start:.3f});'
                )
            clips.append(
                f'<img id="{iid}" class="clip" src="{rel}" '
                f'data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="2" '
                f'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;" />'
            )

        elif itype == "subtitle":
            start, dur = _slot_on_track(5, raw_start, raw_end)
            clips.append(_karaoke_caption(item, start, dur, tweens))

        elif itype == "text" and item.get("role") == "hook":
            start, dur = _slot_on_track(10, raw_start, raw_end)
            # Hook 面板范式吸收自 student-kit may-shorts-19/scene1-intro（mono kicker + slam + stamp 擦入）
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="10" data-layout-allow-overflow="true" '
                f'style="position:absolute;left:50%;top:16%;transform:translateX(-50%);width:88%;text-align:center;">'
                f'<div id="{iid}-kicker" style="font-family:\'Roboto Mono\',monospace;font-size:{int(height*0.018)}px;'
                f'letter-spacing:.18em;color:{muted};margin-bottom:18px;">{_esc(kicker)}</div>'
                f'<div id="{iid}-slam" style="color:{accent};font-size:{int(height*0.054)}px;font-weight:900;'
                f'line-height:1.12;text-shadow:0 6px 30px rgba(0,0,0,.7);">{_esc(item.get("text",""))}</div>'
                f'<div id="{iid}-stamp" style="display:inline-block;margin-top:16px;padding:6px 18px;'
                f'background:{primary};color:#07121c;font-weight:800;font-size:{int(height*0.018)}px;'
                f'clip-path:inset(0 100% 0 0);">{_esc(stamp)}</div></div>'
            )
            tweens.append(f'tl.from("#{iid}-kicker", {{opacity:0, y:14, duration:0.4, ease:"power2.out"}}, {start:.3f});')
            tweens.append(f'tl.from("#{iid}-slam", {{scale:0.6, opacity:0, duration:0.6, ease:"back.out(1.7)"}}, {start+0.15:.3f});')
            tweens.append(f'tl.to("#{iid}-stamp", {{clipPath:"inset(0 0% 0 0)", duration:0.28, ease:"power3.out"}}, {start+0.7:.3f});')

        elif itype == "text" and item.get("role") == "lower_third":
            start, dur = _slot_on_track(8, raw_start, raw_end)
            title = _esc(item.get("text", ""))
            sub = _esc(item.get("subtitle", ""))
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="8" data-timeline-label="lower-third" '
                f'style="position:absolute;left:6%;bottom:24%;padding:14px 22px;'
                f'background:rgba(13,19,33,.78);border-left:5px solid #38BDF8;border-radius:6px;">'
                f'<div style="font-size:{int(height*0.024)}px;font-weight:800;color:#fff">{title}</div>'
                f'<div style="font-size:{int(height*0.016)}px;color:#94A3B8">{sub}</div></div>'
            )
            tweens.append(f'tl.from("#{iid}", {{x:-140, opacity:0, duration:0.5}}, {start:.3f});')

        elif itype == "text" and item.get("role") == "keyword_pop":
            start, dur = _slot_on_track(11, raw_start, raw_end)
            # 关键词弹出：大字号弹跳，强调色，居中偏上
            color = item.get("color", accent)
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="11" data-layout-allow-overflow="true" '
                f'style="position:absolute;left:50%;top:34%;transform:translate(-50%,-50%);'
                f'color:{color};font-size:{int(height*0.07)}px;font-weight:900;letter-spacing:.02em;'
                f'text-shadow:0 0 24px rgba(0,0,0,.6),2px 2px 0 #07121c;white-space:nowrap;">{_esc(item.get("text",""))}</div>'
            )
            tweens.append(f'tl.from("#{iid}", {{scale:0.2, opacity:0, rotation:-6, duration:0.32, ease:"back.out(2.5)"}}, {start:.3f});')

        elif itype == "text" and item.get("role") == "chapter_card":
            start, dur = _slot_on_track(9, raw_start, raw_end)
            # 章节标题卡：编号 + 标题，整条横幅滑入
            color = item.get("color", primary)
            num = f'{int(item.get("index",1)):02d}'
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="9" data-timeline-label="chapter" '
                f'style="position:absolute;left:8%;top:42%;display:flex;align-items:center;gap:18px;">'
                f'<div style="font-family:\'Roboto Mono\',monospace;font-size:{int(height*0.06)}px;font-weight:700;color:{color};">{num}</div>'
                f'<div style="width:6px;height:{int(height*0.07)}px;background:{color};"></div>'
                f'<div style="font-size:{int(height*0.034)}px;font-weight:900;color:#fff;max-width:62%;">{_esc(item.get("text",""))}</div></div>'
            )
            tweens.append(f'tl.from("#{iid}", {{x:-180, opacity:0, duration:0.5, ease:"power3.out"}}, {start:.3f});')

        elif itype == "text" and item.get("role") == "explainer_card":
            start, dur = _slot_on_track(9, raw_start, raw_end)
            # 图文解释卡：标题 + 正文，半透明卡片缩放淡入
            color = item.get("color", primary)
            body = _esc(item.get("body", ""))
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="9" data-timeline-label="explainer" '
                f'style="position:absolute;left:50%;top:30%;transform:translateX(-50%);width:78%;'
                f'background:rgba(7,18,28,.82);border:1px solid {color}55;border-radius:16px;padding:22px 26px;'
                f'box-shadow:0 18px 50px rgba(0,0,0,.5);">'
                f'<div style="font-size:{int(height*0.026)}px;font-weight:900;color:{color};margin-bottom:10px;">{_esc(item.get("text",""))}</div>'
                f'<div style="font-size:{int(height*0.02)}px;line-height:1.4;color:#D5DEEA;">{body}</div></div>'
            )
            tweens.append(f'tl.from("#{iid}", {{scale:0.86, opacity:0, y:24, duration:0.4, ease:"power3.out"}}, {start:.3f});')

        elif itype == "effect" and item.get("role") == "stat_block":
            start, dur = _slot_on_track(11, raw_start, raw_end)
            # 数字 / 价格 / 对比：大号数字弹入 + 标签
            color = item.get("color", accent)
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="11" data-layout-allow-overflow="true" '
                f'style="position:absolute;right:8%;top:30%;text-align:right;">'
                f'<div id="{iid}-v" style="font-family:\'Roboto Mono\',monospace;font-size:{int(height*0.072)}px;'
                f'font-weight:700;color:{color};text-shadow:0 4px 18px rgba(0,0,0,.6);">{_esc(item.get("value",""))}</div>'
                f'<div style="font-size:{int(height*0.02)}px;color:#D5DEEA;margin-top:4px;">{_esc(item.get("text",""))}</div></div>'
            )
            tweens.append(f'tl.from("#{iid}-v", {{scale:0.4, opacity:0, duration:0.4, ease:"back.out(2)"}}, {start:.3f});')
            tweens.append(f'tl.from("#{iid}", {{x:60, opacity:0, duration:0.35, ease:"power2.out"}}, {start:.3f});')

        elif itype == "effect" and item.get("role") == "annotation":
            start, dur = _slot_on_track(12, raw_start, raw_end)
            # 手绘圈选：SVG 椭圆描边动画（产品截图标注）
            color = item.get("color", accent)
            cw, ch = int(width * 0.5), int(height * 0.18)
            clips.append(
                f'<svg id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="12" data-layout-ignore="true" viewBox="0 0 {cw} {ch}" '
                f'style="position:absolute;left:25%;top:40%;width:{cw}px;height:{ch}px;overflow:visible;">'
                f'<ellipse id="{iid}-e" cx="{cw//2}" cy="{ch//2}" rx="{cw//2-12}" ry="{ch//2-8}" '
                f'fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" '
                f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>'
            )
            tweens.append(f'tl.to("#{iid}-e", {{strokeDashoffset:0, duration:0.5, ease:"power1.inOut"}}, {start:.3f});')

        elif itype == "text" and item.get("role") == "cta":
            start, dur = _slot_on_track(13, raw_start, raw_end)
            # 结尾 CTA 面板
            color = item.get("color", accent)
            pcolor = item.get("primary", primary)
            clips.append(
                f'<div id="{iid}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                f'data-track-index="13" data-layout-allow-overflow="true" '
                f'style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:84%;text-align:center;">'
                f'<div style="font-size:{int(height*0.04)}px;font-weight:900;color:#fff;line-height:1.2;">{_esc(item.get("text",""))}</div>'
                f'<div id="{iid}-btn" style="display:inline-block;margin-top:22px;padding:14px 34px;border-radius:999px;'
                f'background:{pcolor};color:#07121c;font-weight:800;font-size:{int(height*0.024)}px;">立即关注 ▶</div></div>'
            )
            tweens.append(f'tl.from("#{iid}", {{opacity:0, scale:0.8, duration:0.5, ease:"back.out(1.6)"}}, {start:.3f});')
            tweens.append(f'tl.fromTo("#{iid}-btn", {{scale:1}}, {{scale:1.08, duration:0.5, yoyo:true, repeat:3, ease:"sine.inOut"}}, {start+0.5:.3f});')

        elif itype == "shape" and item.get("role") == "progress_bar":
            color = item.get("color", "#EF4444")
            clips.append(
                f'<div id="{iid}" class="clip" data-start="0" data-duration="{duration:.3f}" '
                f'data-timeline-role="persistent-overlay" data-track-index="99" '
                f'data-layout-ignore="true" '
                f'style="position:absolute;left:0;right:0;bottom:0;height:8px;background:rgba(255,255,255,.12);">'
                f'<div id="{iid}-bar" style="height:100%;width:0%;background:{color};"></div></div>'
            )
            tweens.append(
                f'tl.to("#{iid}-bar", {{width:"100%", duration:{duration:.3f}, ease:"none"}}, 0);'
            )

        elif itype == "audio":
            src = assets_by_id.get(item.get("asset_id"), {}).get("file_path")
            if not src:
                continue
            rel = _rel_asset(src, hf_dir)
            adur = min(duration, float(assets_by_id.get(item.get("asset_id"), {}).get("duration") or duration))
            audios.append(
                f'<audio id="{iid}" src="{rel}" data-start="{start:.3f}" '
                f'data-duration="{adur:.3f}" data-track-index="3" data-volume="{item.get("volume",0.25)}"></audio>'
            )

    # 多场景统一 crossfade 过渡：由 timeline.export_settings.transition 控制强度/时长。
    scenes = [s for s in timeline.get("scenes", []) if isinstance(s, dict)]
    transition = ((timeline.get("export_settings") or {}).get("transition") or {})
    t_style = str(transition.get("style") or "crossfade").strip().lower()
    t_opacity = float(transition.get("opacity") or 0.22)
    t_duration = float(transition.get("duration") or 0.18)
    t_opacity = max(0.0, min(0.8, t_opacity))
    t_duration = max(0.05, min(0.8, t_duration))
    boundaries: list[float] = []
    for i in range(len(scenes) - 1):
        try:
            b = float(scenes[i].get("timeline_end", 0))
        except (TypeError, ValueError):
            continue
        if 0.05 < b < float(duration) - 0.05:
            boundaries.append(b)
    if boundaries and t_style == "crossfade":
        clips.append(
            f'<div id="scene-xfade" class="clip" data-start="0" data-duration="{duration:.3f}" '
            f'data-track-index="98" data-layout-ignore="true" '
            f'style="position:absolute;inset:0;background:#000;opacity:0;pointer-events:none;"></div>'
        )
        for b in boundaries:
            t0 = max(0.0, b - t_duration)
            tweens.append(
                f'tl.fromTo("#scene-xfade", {{opacity:0}}, {{opacity:{t_opacity:.3f}, duration:{t_duration:.3f}, ease:"power1.out"}}, {t0:.3f});'
            )
            tweens.append(
                f'tl.to("#scene-xfade", {{opacity:0, duration:{t_duration:.3f}, ease:"power1.in"}}, {t0:.3f});'
            )
            # lint: gsap_exit_missing_hard_kill — 在 exit tween 结束时刻 hard kill
            tweens.append(f'tl.set("#scene-xfade", {{opacity:0}}, {(b + t_duration):.3f});')

    html_doc = _render_html(project, width, height, duration, fps, clips, audios, tweens, bg_grad)
    (hf_dir / "index.html").write_text(html_doc, encoding="utf-8")
    write_json(hf_dir / "meta.json", {"title": project.get("name"), "duration": duration, "fps": fps})
    return hf_dir


def _karaoke_caption(item: dict, start: float, dur: float, tweens: list[str]) -> str:
    """逐词 karaoke 字幕。

    吸收自 nateherkai/hyperframes-student-kit `may-shorts-19/compositions/captions.html`
    （MIT, commit a89e704）的三态色彩机：DIM(未读) → ACTIVE(正在读, 放大+强调色) → SPOKEN(已读, 白)。
    """
    iid = item["id"]
    words = item.get("words") or []
    active = item.get("highlight_color", "#38BDF8")   # ACTIVE 强调色
    spoken = item.get("normal_color", "#FFFFFF")      # SPOKEN 已读
    dim = "rgba(255,255,255,0.65)"                     # DIM 未读
    end = start + dur
    # 段落整体淡入（结尾由 data-duration 控制，不做中间场景 exit 动画）
    tweens.append(f'tl.fromTo("#{iid}", {{opacity:0, y:10}}, {{opacity:1, y:0, duration:0.18, ease:"power2.out"}}, {start:.3f});')
    spans = []
    if words:
        for wi, w in enumerate(words):
            wid = f"{iid}-w{wi}"
            spans.append(
                f'<span id="{wid}" style="color:{dim};display:inline-block;transform-origin:center;margin:0 .12em;">{_esc(w["word"])}</span>'
            )
            ws = float(w["start"])
            we = float(w["end"])
            tweens.append(f'tl.set("#{wid}", {{color:"{dim}", scale:1}}, {start:.3f});')
            tweens.append(
                f'tl.to("#{wid}", {{color:"{active}", scale:1.14, duration:0.08, ease:"back.out(3)", overwrite:"auto"}}, {ws:.3f});'
            )
            tweens.append(
                f'tl.to("#{wid}", {{color:"{spoken}", scale:1, duration:0.12, ease:"power2.out", overwrite:"auto"}}, {we:.3f});'
            )
    else:
        spans.append(f'<span style="color:{spoken};">{_esc(item.get("text",""))}</span>')
    # 8 方向描边阴影（ms19 captions 规范；禁用 -webkit-text-stroke）
    stroke = "1px 1px 0 #07121c,-1px 1px 0 #07121c,1px -1px 0 #07121c,-1px -1px 0 #07121c,0 6px 14px rgba(0,0,0,.55)"
    # 字号：可被 set_subtitle_style 的 font_size（剪映单位≈10 默认）调整，预览按 0.5 映射为 vh
    fs_vh = round(float(item.get("font_size", 10.0)) * 0.5, 2)
    font_family = item.get("font")
    family_css = f"font-family:'{font_family}','Noto Sans SC',sans-serif;" if font_family else ""
    return (
        f'<div id="{iid}" class="clip caption-group" data-start="{start:.3f}" data-duration="{dur:.3f}" '
        f'data-track-index="5" data-timeline-label="captions" data-hf-anim="karaoke" '
        f'style="position:absolute;left:50%;bottom:11.5%;transform:translateX(-50%);max-width:87%;'
        f'text-align:center;font-size:{fs_vh}vh;font-weight:900;line-height:1.14;letter-spacing:.01em;{family_css}'
        f'text-shadow:{stroke};">'
        f'{"".join(spans)}</div>'
    )


def _render_html(project, width, height, duration, fps, clips, audios, tweens, bg_grad="linear-gradient(180deg,#07121C 0%,#0D2031 100%)") -> str:
    tween_js = "\n    ".join(tweens)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{_esc(project.get("name", "FrameCraft"))}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Roboto+Mono:wght@500&family=Noto+Sans+SC:wght@700;900&display=swap" rel="stylesheet" />
  <style>
    html, body {{ margin:0; padding:0; width:{width}px; height:{height}px; overflow:hidden; background:#07121C; }}
    /* 配色/字体范式吸收自 student-kit AIS tokens（数值参考，非品牌资产） */
    #stage {{
      position:relative; width:{width}px; height:{height}px; overflow:hidden;
      background: {bg_grad};
      font-family:"Montserrat","Noto Sans SC","Microsoft YaHei",sans-serif;
    }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="main" data-start="0" data-duration="{duration:.3f}"
       data-width="{width}" data-height="{height}">
    {''.join(clips)}
    {''.join(audios)}
  </div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true }});
    {tween_js}
    window.__timelines["main"] = tl;
  </script>
</body>
</html>"""


def lint_project(hf_dir: Path) -> tuple[bool, str]:
    node = str(NODE_EXE) if NODE_EXE.exists() else "node"
    if not HYPERFRAMES_CLI.exists():
        return False, "HyperFrames CLI 未安装，无法执行 lint"
    result = run_cmd([node, str(HYPERFRAMES_CLI), "lint", str(hf_dir)], cwd=hf_dir)
    ok = result.returncode == 0
    return ok, (result.stdout or "") + (result.stderr or "")


def lint_hyperframes(version_dir: Path) -> tuple[bool, str]:
    """仅执行 HyperFrames lint，不渲染。"""
    hf_dir = version_dir / "hyperframes"
    if not (hf_dir / "index.html").is_file():
        return False, "hyperframes/index.html 不存在"
    lint_ok, lint_out = lint_project(hf_dir)
    write_json(version_dir / "render_log.json", {
        "lint_ok": lint_ok,
        "lint_output": (lint_out or "")[:8000],
    })
    return lint_ok, lint_out or ""


def render_preview(hf_dir: Path, preview_path: Path, fps: int = 30, quality: str = "draft") -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if not HYPERFRAMES_CLI.exists():
        raise RuntimeError("HyperFrames CLI 未安装")
    version_dir = hf_dir.parent
    lint_ok, lint_out = lint_project(hf_dir)
    render_log = {
        "lint_ok": lint_ok,
        "lint_output": (lint_out or "")[:8000],
    }
    write_json(version_dir / "render_log.json", render_log)
    if not lint_ok:
        raise RuntimeError(f"HyperFrames lint 未通过，已中止渲染：{(lint_out or '')[:800]}")
    node = str(NODE_EXE) if NODE_EXE.exists() else "node"
    q = QUALITY_MAP.get(quality, quality if quality in {"draft", "standard", "high"} else "draft")
    cmd = [
        node, str(HYPERFRAMES_CLI), "render", str(hf_dir),
        "-o", str(preview_path), "--fps", str(fps), "-q", q,
    ]
    result = run_cmd(cmd, cwd=hf_dir)
    render_log["render_ok"] = result.returncode == 0 and preview_path.exists()
    render_log["render_stderr"] = (result.stderr or "")[:4000]
    render_log["render_stdout"] = (result.stdout or "")[:4000]
    write_json(version_dir / "render_log.json", render_log)
    if result.returncode != 0 or not preview_path.exists():
        raise RuntimeError(f"HyperFrames render failed: {result.stderr or result.stdout}")


def zip_hyperframes(hf_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in hf_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(hf_dir.parent))
