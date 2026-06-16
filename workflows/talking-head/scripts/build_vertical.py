"""Build 9:16 vertical HyperFrames — cropped face upper-center + motion panel below + captions."""
import json
import shutil
import subprocess
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framecraft_paths import duration, input_dir, talk_video, student_kit, workspace_root

ROOT = workspace_root(Path(__file__).resolve().parents[1])
KIT = student_kit(Path(__file__).resolve().parents[3] / "vendor" / "hyperframes-student-kit") / "video-projects" / "may-shorts-19"
if not KIT.exists():
    KIT = student_kit(Path(__file__).resolve().parents[3] / "_hf_demo" / "hyperframes-student-kit") / "video-projects" / "may-shorts-19"
SHARED = input_dir(Path(r"C:\hf_demo\projects\nov26-short\assets"))
INPUT = talk_video(Path(r"C:\hf_demo\input\nov26-edit.mp4"))

DUR = duration(25.033)
W, H = 1080, 1920
# 口播裁切：原片下半屏评论者（去掉新闻台+德文字幕）
FACE_CROP = "580:720:0:1180"
FACE_W = 900
FACE_BOX_H = 680
FACE_LEFT = (W - FACE_W) // 2
ANIM_H = 720
CONTENT_GAP = 16
# 人物 + 动效整体垂直居中，不为字幕预留底栏
BLOCK_H = FACE_BOX_H + CONTENT_GAP + ANIM_H
BLOCK_TOP = (H - BLOCK_H) // 2
FACE_TOP = BLOCK_TOP
ANIM_TOP = BLOCK_TOP + FACE_BOX_H + CONTENT_GAP
CAP_STAGE_TOP = ANIM_TOP + ANIM_H - 148
LAYOUT_MODE = "pip"

TEXT_BODY = "#f2f6fb"
TEXT_MUTED = "#e0e8f2"
TEXT_ACCENT = "#37bdf8"
TEXT_WARN = "#f09025"

EU_IMP_CN_2024 = 519
EU_IMP_CN_2025 = 559
EU_IMP_CN_YOY = 6.4
CN_EXP_EU_YOY_2024 = 3.0
CN_EXP_US_YOY_2024 = 4.9
BAR_2024_PCT = round(EU_IMP_CN_2024 / EU_IMP_CN_2025 * 100, 1)

SRC_EUROSTAT = "来源：Eurostat，2025-04"
SRC_MIXED = "来源：Eurostat / 海关总署"

_growth = [EU_IMP_CN_YOY, CN_EXP_EU_YOY_2024, CN_EXP_US_YOY_2024]
SCENE2_BAR = [round(v / max(_growth) * 100) for v in _growth]

PANEL = (
    f"position:absolute;top:{ANIM_TOP}px;left:0;width:{W}px;height:{ANIM_H}px;box-sizing:border-box;"
    f"padding:36px 40px 32px;"
    f"background:linear-gradient(180deg,rgba(7,18,28,.94) 0%,rgba(7,18,28,.88) 85%,rgba(7,18,28,.75) 100%);"
    f"border-top:1px solid rgba(55,189,248,.22);"
)
SOURCE_CSS = f"""
      .data-source {{
        position:absolute; left:40px; bottom:24px;
        font-family:"Roboto Mono",monospace; font-size:15px; line-height:1.3;
        color:{TEXT_MUTED}; max-width:900px; opacity:0;
      }}
"""

SCENES = [
    {"id": "vs-scene1-hook", "start": 0.0, "end": 5.67, "dur": 5.67},
    {"id": "vs-scene2-grid", "start": 5.67, "end": 11.74, "dur": 6.07},
    {"id": "vs-scene3-flow", "start": 11.74, "end": 18.5, "dur": 6.76},
    {"id": "vs-scene4-stats", "start": 18.5, "end": 22.8, "dur": 4.3},
    {"id": "vs-scene5-cta", "start": 22.8, "end": DUR, "dur": 2.233},
]

assets = ROOT / "assets"
comp_dir = ROOT / "compositions"
assets.mkdir(exist_ok=True)
comp_dir.mkdir(exist_ok=True)

transcript_path = assets / "transcript.json"
if not transcript_path.exists():
    ws_transcript = input_dir(Path(r"C:\hf_demo\projects\nov26-short\assets")) / "transcript.json"
    if ws_transcript.exists():
        shutil.copy2(ws_transcript, transcript_path)
transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
seg_js = [
    {"words": [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in s.get("words", [])]}
    for s in transcript["segments"] if s.get("words")
]


def ensure_assets() -> None:
    if not INPUT.exists():
        return
    face_out = assets / "nov26-face-vertical.mp4"
    audio_out = assets / "nov26-vertical-audio.mp4"
    vf = f"crop={FACE_CROP},scale=-1:{FACE_BOX_H}:flags=lanczos,pad={FACE_W}:{FACE_BOX_H}:(ow-iw)/2:(oh-ih)/2:color=0x07121c"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(INPUT), "-t", str(DUR), "-vf", vf,
         "-c:v", "libx264", "-r", "30", "-g", "30", "-keyint_min", "30",
         "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(face_out)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(INPUT), "-t", str(DUR),
         "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(audio_out)],
        check=True, capture_output=True,
    )


def copy_ambient_bg() -> None:
    text = (KIT / "compositions" / "ambient-bg.html").read_text(encoding="utf-8")
    text = text.replace("18.84", str(DUR))
    (comp_dir / "ambient-bg.html").write_text(text, encoding="utf-8")


ensure_assets()
copy_ambient_bg()

cap_style = {"intro": "none", "outro": "none"}
_style_path = assets / "caption_style.json"
if _style_path.exists():
    cap_style.update(json.loads(_style_path.read_text(encoding="utf-8")))
INTRO_FADE = cap_style.get("intro") == "fade"
OUTRO_FADE = cap_style.get("outro") == "fade"
_show_in = (
    'tl.to(wrap,{opacity:1,visibility:"visible",duration:0.28,ease:"power2.out"}, seg.words[0].start-0.05);'
    if INTRO_FADE
    else 'tl.set(wrap,{opacity:1,visibility:"visible"}, seg.words[0].start-0.02);'
)
_hide_out = (
    'tl.to(wrap,{opacity:0,duration:0.22,ease:"power2.in"}, seg.words[seg.words.length-1].end+0.08);'
    if OUTRO_FADE
    else 'tl.set(wrap,{opacity:0,visibility:"hidden"}, seg.words[seg.words.length-1].end+0.12);'
)

# --- captions ---
(comp_dir / "captions.html").write_text(f"""<template id="captions-template">
  <div data-composition-id="captions" data-start="0" data-width="{W}" data-height="{H}" data-duration="{DUR}">
    <div class="cap-stage" id="cap-stage"></div>
    <style>
      [data-composition-id="captions"] {{ position:absolute; inset:0; pointer-events:none; z-index:30; }}
      [data-composition-id="captions"] .cap-stage {{
        position:absolute; left:0; right:0; top:{CAP_STAGE_TOP}px; height:0;
      }}
      [data-composition-id="captions"] .cap-line-wrap {{
        position:absolute; left:0; right:0; bottom:0; display:flex; justify-content:center;
        padding:0 32px; opacity:0; visibility:hidden;
      }}
      [data-composition-id="captions"] .cap-line {{
        display:inline-block; max-width:920px; text-align:center;
        font-family:"Noto Sans SC","Montserrat",sans-serif; font-weight:900; font-size:48px;
        line-height:1.18; color:#fff;
        text-shadow:-2px -2px 0 #07121c,2px 2px 0 #07121c,0 6px 18px rgba(0,0,0,.82);
      }}
      [data-composition-id="captions"] .cap-word {{ display:inline-block; transform-origin:center; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function () {{
        const SEGMENTS = {json.dumps(seg_js, ensure_ascii=False)};
        const DIM="rgba(255,255,255,0.78)", ACTIVE="{TEXT_ACCENT}", WARN="{TEXT_WARN}", SPOKEN="{TEXT_BODY}";
        const hot = new Set(["成倍","增长","贸易战","歐盟","出口"]);
        const stage = document.querySelector('[data-composition-id="captions"] #cap-stage');
        if (!stage) return;
        const tl = gsap.timeline({{ paused: true }});
        SEGMENTS.forEach((seg) => {{
          const wrap = document.createElement("div"); wrap.className="cap-line-wrap";
          const line = document.createElement("div"); line.className="cap-line";
          seg.words.forEach((w, wi) => {{
            const span = document.createElement("span"); span.className="cap-word"; span.textContent=w.word;
            span.style.color=DIM; line.appendChild(span);
            if (wi < seg.words.length-1) line.appendChild(document.createTextNode(" "));
            const accent = hot.has(w.word.replace(/[，。！？]/g,"")) ? WARN : ACTIVE;
            {_show_in}
            tl.to(span,{{color:accent,scale:1.1,duration:.09,ease:"back.out(2.5)"}}, w.start);
            tl.to(span,{{color:SPOKEN,scale:1,duration:.08}}, w.end);
          }});
          wrap.appendChild(line); stage.appendChild(wrap);
          {_hide_out}
        }});
        tl.set({{}},{{}}, {DUR});
        window.__timelines=window.__timelines||{{}}; window.__timelines["captions"]=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 1: title slide + counter slam ---
(comp_dir / "vs-scene1-hook.html").write_text(f"""<template id="vs-scene1-hook-template">
  <div data-composition-id="vs-scene1-hook" data-start="0" data-width="{W}" data-height="{H}" data-duration="5.67">
    <div class="panel">
      <div class="left">
        <div class="lbl" id="lbl">欧盟自华进口</div>
        <div class="sub" id="sub">2025 同比</div>
        <div class="note" id="note">进口约 {EU_IMP_CN_2025}0 亿欧元</div>
      </div>
      <div class="right">
        <div class="tag" id="tag">YoY</div>
        <div class="pct-wrap">
          <span class="sign">+</span><span class="num" id="num">0.0</span><span class="unit">%</span>
        </div>
      </div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <style>
      [data-composition-id="vs-scene1-hook"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="vs-scene1-hook"] .panel {{ {PANEL} font-family:"Noto Sans SC",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="vs-scene1-hook"] .left {{ position:absolute; left:40px; top:48px; width:400px; }}
      [data-composition-id="vs-scene1-hook"] .right {{ position:absolute; right:40px; top:36px; text-align:right; font-family:"Montserrat",sans-serif; }}
      [data-composition-id="vs-scene1-hook"] .lbl {{ font-size:38px; font-weight:900; color:{TEXT_BODY}; opacity:0; transform:translateX(-48px); }}
      [data-composition-id="vs-scene1-hook"] .sub {{ margin-top:8px; font-size:28px; color:{TEXT_ACCENT}; opacity:0; }}
      [data-composition-id="vs-scene1-hook"] .note {{ margin-top:16px; font-size:22px; color:{TEXT_MUTED}; opacity:0; clip-path:inset(0 100% 0 0); }}
      [data-composition-id="vs-scene1-hook"] .tag {{ font-size:20px; letter-spacing:.18em; color:{TEXT_MUTED}; opacity:0; }}
      [data-composition-id="vs-scene1-hook"] .pct-wrap {{ margin-top:12px; opacity:0; transform:scale(.45); }}
      [data-composition-id="vs-scene1-hook"] .sign {{ font-size:56px; font-weight:900; color:{TEXT_WARN}; }}
      [data-composition-id="vs-scene1-hook"] .num {{ font-size:100px; font-weight:900; color:{TEXT_ACCENT}; line-height:1; }}
      [data-composition-id="vs-scene1-hook"] .unit {{ font-size:48px; font-weight:900; color:{TEXT_WARN}; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="vs-scene1-hook"] '; const tl=gsap.timeline({{paused:true}});
        const c={{v:0}}; const el=document.querySelector(S+'#num');
        tl.to(S+'#lbl',{{opacity:1,x:0,duration:.45,ease:'power3.out'}},0.12);
        tl.to(S+'#sub',{{opacity:1,duration:.35}},0.38);
        tl.to(S+'#tag',{{opacity:1,duration:.3}},0.42);
        tl.to(S+'.pct-wrap',{{opacity:1,scale:1,duration:.55,ease:'elastic.out(1,.55)'}},0.52);
        tl.to(c,{{v:{EU_IMP_CN_YOY},duration:.95,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent=c.v.toFixed(1);}}}},0.58);
        tl.to(S+'#note',{{opacity:1,clipPath:'inset(0 0% 0 0)',duration:.5,ease:'power4.out'}},1.65);
        tl.to(S+'#src',{{opacity:1,duration:.3}},2.05);
        tl.set({{}},{{}},5.67);
        window.__timelines=window.__timelines||{{}}; window.__timelines['vs-scene1-hook']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 2: three metric rows ---
(comp_dir / "vs-scene2-grid.html").write_text(f"""<template id="vs-scene2-grid-template">
  <div data-composition-id="vs-scene2-grid" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.07">
    <div class="panel">
      <div class="hdr" id="hdr">全球出口增速对比</div>
      <div class="row" id="r1">
        <div class="nm">🇪🇺 欧盟自华进口</div>
        <div class="val" id="v1">+0.0%</div>
        <div class="track"><div class="fill" id="f1"></div></div>
      </div>
      <div class="row" id="r2">
        <div class="nm">🇨🇳 对欧出口</div>
        <div class="val hot" id="v2">+0.0%</div>
        <div class="track"><div class="fill hot" id="f2"></div></div>
      </div>
      <div class="row" id="r3">
        <div class="nm">🇺🇸 对美出口</div>
        <div class="val" id="v3">+0.0%</div>
        <div class="track"><div class="fill" id="f3"></div></div>
      </div>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <style>
      [data-composition-id="vs-scene2-grid"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="vs-scene2-grid"] .panel {{ {PANEL} font-family:"Noto Sans SC",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="vs-scene2-grid"] .hdr {{ font-size:32px; font-weight:800; color:{TEXT_ACCENT}; opacity:0; margin-bottom:18px; }}
      [data-composition-id="vs-scene2-grid"] .row {{
        background:rgba(11,22,35,.55); border:1px solid rgba(55,189,248,.28); border-radius:14px;
        padding:14px 20px; margin-bottom:12px; opacity:0; transform:translateY(28px);
      }}
      [data-composition-id="vs-scene2-grid"] .nm {{ font-size:24px; font-weight:700; color:{TEXT_BODY}; }}
      [data-composition-id="vs-scene2-grid"] .val {{ font-family:"Roboto Mono",monospace; font-size:34px; font-weight:700; color:{TEXT_ACCENT}; margin:6px 0; opacity:0; }}
      [data-composition-id="vs-scene2-grid"] .val.hot {{ color:{TEXT_WARN}; }}
      [data-composition-id="vs-scene2-grid"] .track {{ height:14px; background:rgba(255,255,255,.12); border-radius:7px; overflow:hidden; }}
      [data-composition-id="vs-scene2-grid"] .fill {{ height:100%; width:0; background:linear-gradient(90deg,{TEXT_ACCENT},#77d4ff); }}
      [data-composition-id="vs-scene2-grid"] .fill.hot {{ background:linear-gradient(90deg,{TEXT_WARN},#ff6b35); }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="vs-scene2-grid"] '; const tl=gsap.timeline({{paused:true}});
        const rows=[
          {{row:'#r1',v:'#v1',f:'#f1',t:{EU_IMP_CN_YOY},w:{SCENE2_BAR[0]}}},
          {{row:'#r2',v:'#v2',f:'#f2',t:{CN_EXP_EU_YOY_2024},w:{SCENE2_BAR[1]}}},
          {{row:'#r3',v:'#v3',f:'#f3',t:{CN_EXP_US_YOY_2024},w:{SCENE2_BAR[2]}}}
        ];
        tl.to(S+'#hdr',{{opacity:1,duration:.35}},0.1);
        rows.forEach((r,i)=>{{
          const o={{v:0}}; const el=document.querySelector(S+r.v);
          tl.to(S+r.row,{{opacity:1,y:0,duration:.4,ease:'power3.out'}},0.35+i*0.35);
          tl.to(S+r.v,{{opacity:1,duration:.2}},0.55+i*0.35);
          tl.to(o,{{v:r.t,duration:.8,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent='+'+o.v.toFixed(1)+'%';}}}},0.6+i*0.35);
          tl.to(S+r.f,{{width:r.w+'%',duration:.75,ease:'power2.out'}},0.6+i*0.35);
        }});
        tl.to(S+'#r2',{{boxShadow:'0 0 28px rgba(240,144,37,.45)',borderColor:'#f09025',duration:.3}},2.6);
        tl.to(S+'#src',{{opacity:1,duration:.3}},1.9);
        tl.set({{}},{{}},6.07);
        window.__timelines=window.__timelines||{{}}; window.__timelines['vs-scene2-grid']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 3: horizontal SVG flow + chips ---
(comp_dir / "vs-scene3-flow.html").write_text(f"""<template id="vs-scene3-flow-template">
  <div data-composition-id="vs-scene3-flow" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.76">
    <div class="panel">
      <div class="ttl" id="ttl">供应链重组</div>
      <svg class="flow" viewBox="0 0 920 120" xmlns="http://www.w3.org/2000/svg">
        <path id="p1" d="M280,60 H380" stroke="#37bdf8" stroke-width="4" fill="none" stroke-dasharray="100" stroke-dashoffset="100"/>
        <path id="p2" d="M540,60 H640" stroke="#f09025" stroke-width="4" fill="none" stroke-dasharray="100" stroke-dashoffset="100"/>
        <g id="n1" opacity="0" transform="translate(40,20) scale(.75)">
          <rect width="240" height="80" rx="12" fill="#0f2033" stroke="#37bdf8" stroke-width="2"/>
          <text x="120" y="50" text-anchor="middle" fill="#fff" font-size="26" font-family="Noto Sans SC">美国关税</text>
        </g>
        <g id="n2" opacity="0" transform="translate(300,20) scale(.75)">
          <rect width="240" height="80" rx="12" fill="#0f2033" stroke="#f09025" stroke-width="2"/>
          <text x="120" y="50" text-anchor="middle" fill="#fff" font-size="26" font-family="Noto Sans SC">中欧贸易</text>
        </g>
        <g id="n3" opacity="0" transform="translate(560,20) scale(.75)">
          <rect width="240" height="80" rx="12" fill="#0f2033" stroke="#37bdf8" stroke-width="2"/>
          <text x="120" y="50" text-anchor="middle" fill="#fff" font-size="26" font-family="Noto Sans SC">出口放量</text>
        </g>
      </svg>
      <div class="chips">
        <div class="chip" id="c1">EU进口 +{EU_IMP_CN_YOY}%</div>
        <div class="chip" id="c2">对欧 +{CN_EXP_EU_YOY_2024}%</div>
        <div class="chip" id="c3">对美 +{CN_EXP_US_YOY_2024}%</div>
      </div>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <style>
      [data-composition-id="vs-scene3-flow"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="vs-scene3-flow"] .panel {{ {PANEL} font-family:"Noto Sans SC",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="vs-scene3-flow"] .ttl {{ font-size:34px; font-weight:900; color:{TEXT_BODY}; opacity:0; margin-bottom:12px; }}
      [data-composition-id="vs-scene3-flow"] .flow {{ width:920px; height:100px; margin:4px auto 18px; display:block; }}
      [data-composition-id="vs-scene3-flow"] .chips {{ display:flex; gap:14px; justify-content:center; flex-wrap:wrap; }}
      [data-composition-id="vs-scene3-flow"] .chip {{
        font-family:"Roboto Mono",monospace; font-size:22px; color:{TEXT_BODY};
        padding:14px 20px; background:rgba(11,22,35,.6); border-radius:12px;
        border-bottom:3px solid {TEXT_ACCENT}; opacity:0; transform:translateY(24px);
      }}
      [data-composition-id="vs-scene3-flow"] .chip:nth-child(2) {{ border-bottom-color:{TEXT_WARN}; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="vs-scene3-flow"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#ttl',{{opacity:1,duration:.35}},0.1);
        tl.to(S+'#n1',{{opacity:1,attr:{{transform:'translate(40,20) scale(1)'}},duration:.35,ease:'back.out(2)'}},0.35);
        tl.to(S+'#p1',{{strokeDashoffset:0,duration:.45,ease:'power2.inOut'}},0.55);
        tl.to(S+'#n2',{{opacity:1,attr:{{transform:'translate(300,20) scale(1)'}},duration:.35,ease:'back.out(2)'}},0.7);
        tl.to(S+'#p2',{{strokeDashoffset:0,duration:.45,ease:'power2.inOut'}},0.9);
        tl.to(S+'#n3',{{opacity:1,attr:{{transform:'translate(560,20) scale(1)'}},duration:.4,ease:'elastic.out(1,.55)'}},1.05);
        ['#c1','#c2','#c3'].forEach((id,i)=>{{
          tl.to(S+id,{{opacity:1,y:0,duration:.35,ease:'power3.out'}},1.35+i*0.22);
        }});
        tl.to(S+'#src',{{opacity:1,duration:.3}},2.1);
        tl.set({{}},{{}},6.76);
        window.__timelines=window.__timelines||{{}}; window.__timelines['vs-scene3-flow']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 4: +6.4% + euro bars ---
(comp_dir / "vs-scene4-stats.html").write_text(f"""<template id="vs-scene4-stats-template">
  <div data-composition-id="vs-scene4-stats" data-start="0" data-width="{W}" data-height="{H}" data-duration="4.3">
    <div class="panel">
      <div class="k" id="k">欧盟自华进口</div>
      <div class="big" id="big">+{EU_IMP_CN_YOY}%</div>
      <div class="bars">
        <div class="bar-row" id="br1">
          <span class="yr">2024</span>
          <div class="track"><div class="fill" id="b1"></div></div>
          <span class="amt" id="a1">€0B</span>
        </div>
        <div class="bar-row" id="br2">
          <span class="yr">2025</span>
          <div class="track"><div class="fill hot" id="b2"></div></div>
          <span class="amt warn" id="a2">€0B</span>
        </div>
      </div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <style>
      [data-composition-id="vs-scene4-stats"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="vs-scene4-stats"] .panel {{ {PANEL} font-family:"Noto Sans SC",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="vs-scene4-stats"] .k {{ font-size:32px; color:{TEXT_MUTED}; opacity:0; text-align:center; }}
      [data-composition-id="vs-scene4-stats"] .big {{ font-size:92px; font-weight:900; color:{TEXT_WARN}; text-align:center; opacity:0; transform:scale(.4); margin:8px 0 28px; }}
      [data-composition-id="vs-scene4-stats"] .bar-row {{ display:grid; grid-template-columns:72px 1fr 88px; align-items:center; gap:16px; margin-bottom:20px; opacity:0; }}
      [data-composition-id="vs-scene4-stats"] .yr {{ font-size:24px; color:{TEXT_BODY}; font-family:"Roboto Mono",monospace; }}
      [data-composition-id="vs-scene4-stats"] .track {{ height:18px; background:rgba(255,255,255,.12); border-radius:9px; overflow:hidden; }}
      [data-composition-id="vs-scene4-stats"] .fill {{ height:100%; width:0; background:{TEXT_ACCENT}; }}
      [data-composition-id="vs-scene4-stats"] .fill.hot {{ background:linear-gradient(90deg,{TEXT_WARN},#ff6b35); }}
      [data-composition-id="vs-scene4-stats"] .amt {{ font-family:"Roboto Mono",monospace; font-size:24px; font-weight:700; color:{TEXT_ACCENT}; text-align:right; }}
      [data-composition-id="vs-scene4-stats"] .amt.warn {{ color:{TEXT_WARN}; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="vs-scene4-stats"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#k',{{opacity:1,duration:.25}},0.08);
        tl.to(S+'#big',{{opacity:1,scale:1,duration:.55,ease:'elastic.out(1,.55)'}},0.22);
        tl.to(S+'#br1',{{opacity:1,duration:.3}},0.88);
        tl.to(S+'#b1',{{width:'{BAR_2024_PCT}%',duration:.65,ease:'power2.out'}},0.92);
        tl.set(S+'#a1',{{textContent:'€{EU_IMP_CN_2024}B'}},0.92);
        tl.to(S+'#br2',{{opacity:1,duration:.3}},1.22);
        tl.to(S+'#b2',{{width:'100%',duration:.7,ease:'power3.out'}},1.28);
        tl.set(S+'#a2',{{textContent:'€{EU_IMP_CN_2025}B'}},1.28);
        tl.to(S+'#src',{{opacity:1,duration:.3}},1.85);
        tl.set({{}},{{}},4.3);
        window.__timelines=window.__timelines||{{}}; window.__timelines['vs-scene4-stats']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 5: CTA ---
(comp_dir / "vs-scene5-cta.html").write_text(f"""<template id="vs-scene5-cta-template">
  <div data-composition-id="vs-scene5-cta" data-start="0" data-width="{W}" data-height="{H}" data-duration="2.233">
    <div class="panel">
      <div class="ey" id="ey">欧洲各国</div>
      <div class="hd" id="hd">开始行动</div>
      <div class="sub" id="sub">持续跟进贸易变局</div>
      <div class="ln" id="ln"></div>
    </div>
    <style>
      [data-composition-id="vs-scene5-cta"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="vs-scene5-cta"] .panel {{ {PANEL} font-family:"Noto Sans SC",sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }}
      [data-composition-id="vs-scene5-cta"] .ey {{ font-size:36px; font-weight:800; color:{TEXT_MUTED}; opacity:0; transform:translateY(-20px); }}
      [data-composition-id="vs-scene5-cta"] .hd {{ font-size:76px; font-weight:900; color:{TEXT_ACCENT}; opacity:0; transform:scale(.65); margin-top:12px; text-shadow:0 0 48px rgba(55,189,248,.35); }}
      [data-composition-id="vs-scene5-cta"] .sub {{ margin-top:18px; font-size:28px; color:{TEXT_BODY}; opacity:0; }}
      [data-composition-id="vs-scene5-cta"] .ln {{ height:4px; width:0; margin-top:28px; background:linear-gradient(90deg,{TEXT_ACCENT},{TEXT_WARN}); }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="vs-scene5-cta"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#ey',{{opacity:1,y:0,duration:.35,ease:'power3.out'}},0.08);
        tl.to(S+'#hd',{{opacity:1,scale:1,duration:.5,ease:'back.out(1.6)'}},0.22);
        tl.to(S+'#sub',{{opacity:1,duration:.3}},0.62);
        tl.to(S+'#ln',{{width:320,duration:.45,ease:'power2.inOut'}},0.45);
        tl.to(S+'#hd',{{scale:1.04,duration:1.1,ease:'none'}},0.5);
        tl.set({{}},{{}},2.233);
        window.__timelines=window.__timelines||{{}}; window.__timelines['vs-scene5-cta']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

scene_layers = []
for sc in SCENES:
    scene_layers.append(f"""
      <div class="scene-layer" data-composition-id="{sc['id']}"
        data-composition-src="compositions/{sc['id']}.html"
        data-start="{sc['start']}" data-duration="{sc['dur']}"
        data-track-index="3" data-width="{W}" data-height="{H}"></div>""")

(ROOT / "index.html").write_text(f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width={W}, height={H}" />
  <title>nov26-vertical 9:16 pip</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Noto+Sans+SC:wght@700;900&family=Roboto+Mono:wght@500&display=block" rel="stylesheet" />
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html,body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; background:#07121c; }}
    #canvas-bg {{
      position:absolute; inset:0; z-index:0;
      background:radial-gradient(ellipse 90% 55% at 50% 50%,#0f2033 0%,#07121c 55%,#050b13 100%);
    }}
    #ambient-bg {{ z-index:1; opacity:.55; }}
    #face-slot {{
      position:absolute; top:{FACE_TOP}px; left:{FACE_LEFT}px;
      width:{FACE_W}px; height:{FACE_BOX_H}px; z-index:5;
      border-radius:20px; overflow:hidden;
      box-shadow:0 16px 48px rgba(0,0,0,.55),0 0 0 1px rgba(55,189,248,.15);
      transform-origin:center center;
      background:#07121c;
    }}
    #face-video {{
      display:block; width:100%; height:100%; object-fit:contain; object-position:center center;
      filter:contrast(1.05) saturate(1.05);
    }}
    #face-slot::after {{
      content:""; position:absolute; inset:0; pointer-events:none;
      background:linear-gradient(180deg,transparent 70%,rgba(7,18,28,.35) 100%);
    }}
    .scene-layer {{ position:absolute; top:0; left:0; width:{W}px; height:{H}px; pointer-events:none; z-index:10; }}
    #captions-layer {{ z-index:30; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}"
       data-width="{W}" data-height="{H}">
    <div id="canvas-bg"></div>
    <div id="ambient-bg" class="scene-layer"
      data-composition-id="ambient-bg" data-composition-src="compositions/ambient-bg.html"
      data-start="0" data-duration="{DUR}" data-track-index="6" data-width="{W}" data-height="{H}"></div>

    <div id="face-slot">
      <video id="face-video" data-start="0" data-duration="{DUR}" data-track-index="1"
        src="assets/nov26-face-vertical.mp4" muted playsinline></video>
    </div>

    <audio id="face-audio" data-start="0" data-duration="{DUR}" data-track-index="4"
      data-volume="1" src="assets/nov26-vertical-audio.mp4"></audio>

    {"".join(scene_layers)}

    <div id="captions-layer" class="scene-layer"
      data-composition-id="captions" data-composition-src="compositions/captions.html"
      data-start="0" data-duration="{DUR}" data-track-index="2" data-width="{W}" data-height="{H}"></div>
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const mainTl = gsap.timeline({{ paused: true }});
    mainTl.to("#face-slot", {{ scale: 1.022, duration: {DUR}, ease: "none" }}, 0);
    mainTl.set({{}}, {{}}, {DUR});
    window.__timelines["main"] = mainTl;
  </script>
</body>
</html>""", encoding="utf-8")

(ROOT / "meta.json").write_text(json.dumps({
    "id": "nov26-vertical", "name": "nov26-vertical-portrait",
    "width": W, "height": H, "fps": 30,
}, indent=2), encoding="utf-8")

(ROOT / "hyperframes.json").write_text(json.dumps({
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
}, indent=2), encoding="utf-8")

(ROOT / "package.json").write_text(json.dumps({
    "name": "nov26-vertical",
    "private": True,
    "type": "module",
    "scripts": {
        "dev": "npx --yes hyperframes@0.6.99 preview",
        "render": "npx --yes hyperframes@0.6.99 render",
    },
}, indent=2), encoding="utf-8")

print("vertical build ok", W, "x", H, "mode", LAYOUT_MODE, "block_top", BLOCK_TOP, "face", FACE_W, "x", FACE_BOX_H, "anim", ANIM_H)
