"""Build FULLSCREEN 1920x1080 dual-rail HyperFrames project with GSAP animations."""
import json
import shutil
import subprocess
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framecraft_paths import duration, input_dir, talk_video, workspace_root

ROOT = workspace_root(Path(__file__).resolve().parents[1])
SHARED = input_dir(Path(r"C:\hf_demo\projects\nov26-short\assets"))
INPUT = talk_video(Path(r"C:\hf_demo\input\nov26-edit.mp4"))

DUR = duration(25.033)
W, H = 1920, 1080
RAIL_W = 320
CAP_SAFE = 150

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
SRC_GACC = "来源：海关总署，2024"
SRC_MIXED = "来源：Eurostat / 海关总署"

_growth = [EU_IMP_CN_YOY, CN_EXP_EU_YOY_2024, CN_EXP_US_YOY_2024]
SCENE2_BAR = [round(v / max(_growth) * 100) for v in _growth]

RAIL_L = (
    f"position:absolute;left:0;top:0;width:{RAIL_W}px;height:{H}px;box-sizing:border-box;"
    f"padding:56px 10px {CAP_SAFE + 20}px 16px;"
    f"background:linear-gradient(90deg,rgba(5,11,19,.92) 0%,rgba(5,11,19,.72) 78%,rgba(5,11,19,0) 100%);"
)
RAIL_R = (
    f"position:absolute;right:0;top:0;width:{RAIL_W}px;height:{H}px;box-sizing:border-box;"
    f"padding:56px 16px {CAP_SAFE + 20}px 10px;text-align:right;"
    f"background:linear-gradient(270deg,rgba(5,11,19,.92) 0%,rgba(5,11,19,.72) 78%,rgba(5,11,19,0) 100%);"
)
SOURCE_CSS = f"""
      .data-source {{
        position:absolute; left:12px; bottom:{CAP_SAFE + 2}px;
        font-family:"Roboto Mono",monospace; font-size:14px; line-height:1.3;
        color:{TEXT_MUTED}; max-width:{RAIL_W - 24}px; opacity:0;
      }}
"""

SCENES = [
    {"id": "fs-scene1-hook", "start": 0.0, "end": 5.67, "dur": 5.67},
    {"id": "fs-scene2-grid", "start": 5.67, "end": 11.74, "dur": 6.07},
    {"id": "fs-scene3-flow", "start": 11.74, "end": 18.5, "dur": 6.76},
    {"id": "fs-scene4-stats", "start": 18.5, "end": 22.8, "dur": 4.3},
    {"id": "fs-scene5-cta", "start": 22.8, "end": DUR, "dur": 2.233},
]

assets = ROOT / "assets"
comp_dir = ROOT / "compositions"
assets.mkdir(exist_ok=True)
comp_dir.mkdir(exist_ok=True)

shutil.copy2(SHARED / "transcript.json", assets / "transcript.json")
transcript = json.loads((assets / "transcript.json").read_text(encoding="utf-8"))
seg_js = [
    {"words": [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in s.get("words", [])]}
    for s in transcript["segments"] if s.get("words")
]


def ensure_fullscreen_video() -> None:
    """16:9 cover crop; prefer tight face-clean, fallback edit clip."""
    out = assets / "nov26-fullscreen.mp4"
    face = SHARED / "nov26-face-clean.mp4"
    src = face if face.exists() else (INPUT if INPUT.exists() else None)
    if not src:
        return
    y_crop = "0.38" if face.exists() else "0.58"
    vf = (
        f"scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080:(iw-1920)/2:(ih-1080)*{y_crop},setsar=1"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-t", str(DUR),
         "-vf", vf, "-c:v", "libx264", "-r", "30", "-g", "30", "-keyint_min", "30",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", str(out)],
        check=True, capture_output=True,
    )


ensure_fullscreen_video()

# --- captions ---
(comp_dir / "captions.html").write_text(f"""<template id="captions-template">
  <div data-composition-id="captions" data-start="0" data-width="{W}" data-height="{H}" data-duration="{DUR}">
    <div class="cap-backdrop"></div>
    <div class="cap-stage" id="cap-stage"></div>
    <style>
      [data-composition-id="captions"] {{ position:absolute; inset:0; pointer-events:none; z-index:30; }}
      [data-composition-id="captions"] .cap-backdrop {{
        position:absolute; left:0; right:0; bottom:0; height:{CAP_SAFE + 40}px;
        background:linear-gradient(180deg,transparent 0%,rgba(5,11,19,.72) 45%,rgba(5,11,19,.92) 100%);
      }}
      [data-composition-id="captions"] .cap-stage {{ position:absolute; left:0; right:0; bottom:88px; height:0; }}
      [data-composition-id="captions"] .cap-line-wrap {{
        position:absolute; left:0; right:0; bottom:0; display:flex; justify-content:center;
        padding:0 64px; opacity:0; visibility:hidden;
      }}
      [data-composition-id="captions"] .cap-line {{
        display:inline-block; max-width:1280px; text-align:center;
        font-family:"Noto Sans SC","Montserrat",sans-serif; font-weight:900; font-size:50px;
        line-height:1.18; color:#fff;
        text-shadow:-3px -3px 0 #07121c,3px 3px 0 #07121c,0 8px 24px rgba(0,0,0,.75);
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
        SEGMENTS.forEach((seg, si) => {{
          const wrap = document.createElement("div"); wrap.className="cap-line-wrap";
          const line = document.createElement("div"); line.className="cap-line";
          seg.words.forEach((w, wi) => {{
            const span = document.createElement("span"); span.className="cap-word"; span.textContent=w.word;
            span.style.color=DIM; line.appendChild(span);
            if (wi < seg.words.length-1) line.appendChild(document.createTextNode(" "));
            const accent = hot.has(w.word.replace(/[，。！？]/g,"")) ? WARN : ACTIVE;
            tl.set(wrap,{{opacity:1,visibility:"visible"}}, w.start-0.02);
            tl.to(span,{{color:accent,scale:1.1,duration:.09,ease:"back.out(2.5)"}}, w.start);
            tl.to(span,{{color:SPOKEN,scale:1,duration:.08}}, w.end);
          }});
          wrap.appendChild(line); stage.appendChild(wrap);
          tl.set(wrap,{{opacity:0,visibility:"hidden"}}, seg.words[seg.words.length-1].end+0.12);
        }});
        tl.set({{}},{{}}, {DUR});
        window.__timelines=window.__timelines||{{}}; window.__timelines["captions"]=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 1: left label slide + right counter slam ---
(comp_dir / "fs-scene1-hook.html").write_text(f"""<template id="fs-scene1-hook-template">
  <div data-composition-id="fs-scene1-hook" data-start="0" data-width="{W}" data-height="{H}" data-duration="5.67">
    <div class="rail-left">
      <div class="lbl" id="lbl">欧盟自华进口</div>
      <div class="sub" id="sub">2025同比</div>
      <div class="note" id="note">进口约{EU_IMP_CN_2025}0亿欧元</div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <div class="rail-right">
      <div class="tag" id="tag">YoY</div>
      <div class="pct-wrap">
        <span class="sign" id="sign">+</span><span class="num" id="num">0.0</span><span class="unit" id="unit">%</span>
      </div>
    </div>
    <style>
      [data-composition-id="fs-scene1-hook"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="fs-scene1-hook"] .rail-left {{ {RAIL_L} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene1-hook"] .rail-right {{ {RAIL_R} font-family:"Montserrat",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="fs-scene1-hook"] .lbl {{ font-size:30px; font-weight:800; color:{TEXT_BODY}; opacity:0; transform:translateX(-36px); }}
      [data-composition-id="fs-scene1-hook"] .sub {{ margin-top:8px; font-size:26px; color:{TEXT_ACCENT}; opacity:0; }}
      [data-composition-id="fs-scene1-hook"] .note {{ margin-top:20px; font-size:18px; color:{TEXT_MUTED}; opacity:0; clip-path:inset(0 100% 0 0); }}
      [data-composition-id="fs-scene1-hook"] .tag {{ font-size:18px; letter-spacing:.2em; color:{TEXT_MUTED}; opacity:0; }}
      [data-composition-id="fs-scene1-hook"] .pct-wrap {{ margin-top:12px; opacity:0; transform:scale(.5); }}
      [data-composition-id="fs-scene1-hook"] .sign {{ font-size:52px; font-weight:900; color:{TEXT_WARN}; }}
      [data-composition-id="fs-scene1-hook"] .num {{ font-size:88px; font-weight:900; color:{TEXT_ACCENT}; line-height:1; }}
      [data-composition-id="fs-scene1-hook"] .unit {{ font-size:44px; font-weight:900; color:{TEXT_WARN}; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="fs-scene1-hook"] '; const tl=gsap.timeline({{paused:true}});
        const c={{v:0}}; const el=document.querySelector(S+'#num');
        tl.to(S+'.rail-left',{{opacity:1,duration:.25}},0);
        tl.to(S+'.rail-right',{{opacity:1,duration:.25}},0);
        tl.to(S+'#lbl',{{opacity:1,x:0,duration:.4,ease:'power3.out'}},0.1);
        tl.to(S+'#sub',{{opacity:1,duration:.3}},0.35);
        tl.to(S+'#tag',{{opacity:1,duration:.25}},0.4);
        tl.to(S+'.pct-wrap',{{opacity:1,scale:1,duration:.5,ease:'elastic.out(1,.55)'}},0.5);
        tl.to(c,{{v:{EU_IMP_CN_YOY},duration:.9,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent=c.v.toFixed(1);}}}},0.55);
        tl.to(S+'#note',{{opacity:1,clipPath:'inset(0 0% 0 0)',duration:.45,ease:'power4.out'}},1.6);
        tl.to(S+'#src',{{opacity:1,duration:.3}},2.0);
        tl.set({{}},{{}},5.67);
        window.__timelines=window.__timelines||{{}}; window.__timelines['fs-scene1-hook']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 2: left EU bar + right CN/US cards stagger ---
(comp_dir / "fs-scene2-grid.html").write_text(f"""<template id="fs-scene2-grid-template">
  <div data-composition-id="fs-scene2-grid" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.07">
    <div class="rail-left">
      <div class="hdr" id="hdr">🇪🇺 欧盟自华进口</div>
      <div class="val" id="v1">+0.0%</div>
      <div class="track"><div class="fill" id="f1"></div></div>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <div class="rail-right">
      <div class="card" id="c2">
        <div class="nm">🇨🇳 对欧出口</div>
        <div class="val" id="v2">+0.0%</div>
        <div class="track"><div class="fill hot" id="f2"></div></div>
      </div>
      <div class="card" id="c3">
        <div class="nm">🇺🇸 对美出口</div>
        <div class="val" id="v3">+0.0%</div>
        <div class="track"><div class="fill" id="f3"></div></div>
      </div>
    </div>
    <style>
      [data-composition-id="fs-scene2-grid"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="fs-scene2-grid"] .rail-left {{ {RAIL_L} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene2-grid"] .rail-right {{ {RAIL_R} font-family:"Noto Sans SC",sans-serif; }}
      {SOURCE_CSS}
      [data-composition-id="fs-scene2-grid"] .hdr {{ font-size:24px; font-weight:800; color:{TEXT_ACCENT}; opacity:0; }}
      [data-composition-id="fs-scene2-grid"] .val {{ font-family:"Roboto Mono",monospace; font-size:36px; font-weight:700; color:{TEXT_WARN}; margin:10px 0; opacity:0; }}
      [data-composition-id="fs-scene2-grid"] .track {{ height:14px; background:rgba(255,255,255,.12); border-radius:7px; overflow:hidden; }}
      [data-composition-id="fs-scene2-grid"] .fill {{ height:100%; width:0; background:linear-gradient(90deg,{TEXT_ACCENT},#77d4ff); }}
      [data-composition-id="fs-scene2-grid"] .fill.hot {{ background:linear-gradient(90deg,{TEXT_WARN},#ff6b35); }}
      [data-composition-id="fs-scene2-grid"] .card {{
        background:rgba(11,22,35,.65); border:1px solid rgba(55,189,248,.3); border-radius:12px;
        padding:14px 12px; margin-bottom:14px; opacity:0; transform:translateX(40px);
      }}
      [data-composition-id="fs-scene2-grid"] .nm {{ font-size:20px; font-weight:700; color:{TEXT_BODY}; text-align:right; }}
      [data-composition-id="fs-scene2-grid"] .rail-right .val {{ font-size:28px; text-align:right; }}
      [data-composition-id="fs-scene2-grid"] .rail-right .track {{ margin-top:8px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="fs-scene2-grid"] '; const tl=gsap.timeline({{paused:true}});
        const rows=[
          {{v:'#v1',f:'#f1',t:{EU_IMP_CN_YOY},w:{SCENE2_BAR[0]}}},
          {{v:'#v2',f:'#f2',t:{CN_EXP_EU_YOY_2024},w:{SCENE2_BAR[1]}}},
          {{v:'#v3',f:'#f3',t:{CN_EXP_US_YOY_2024},w:{SCENE2_BAR[2]}}}
        ];
        tl.to(S+'#hdr',{{opacity:1,duration:.35}},0.1);
        tl.to(S+'#c2',{{opacity:1,x:0,duration:.4,ease:'power3.out'}},0.3);
        tl.to(S+'#c3',{{opacity:1,x:0,duration:.4,ease:'power3.out'}},0.5);
        rows.forEach((r,i)=>{{
          const o={{v:0}}; const el=document.querySelector(S+r.v);
          tl.to(S+r.v,{{opacity:1,duration:.2}},0.55+i*0.2);
          tl.to(o,{{v:r.t,duration:.75,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent='+'+o.v.toFixed(1)+'%';}}}},0.6+i*0.2);
          tl.to(S+r.f,{{width:r.w+'%',duration:.75,ease:'power2.out'}},0.6+i*0.2);
        }});
        tl.to(S+'#c2',{{boxShadow:'0 0 24px rgba(240,144,37,.5)',borderColor:'#f09025',duration:.25}},2.5);
        tl.to(S+'#src',{{opacity:1,duration:.3}},1.8);
        tl.set({{}},{{}},6.07);
        window.__timelines=window.__timelines||{{}}; window.__timelines['fs-scene2-grid']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 3: left vertical SVG flow + right stagger bullets ---
(comp_dir / "fs-scene3-flow.html").write_text(f"""<template id="fs-scene3-flow-template">
  <div data-composition-id="fs-scene3-flow" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.76">
    <div class="rail-left">
      <div class="ttl" id="ttl">供应链重组</div>
      <svg class="flow" viewBox="0 0 240 420" xmlns="http://www.w3.org/2000/svg">
        <path id="p1" d="M120,92 V148" stroke="#37bdf8" stroke-width="4" fill="none" stroke-dasharray="60" stroke-dashoffset="60"/>
        <path id="p2" d="M120,220 V276" stroke="#f09025" stroke-width="4" fill="none" stroke-dasharray="60" stroke-dashoffset="60"/>
        <g id="n1" opacity="0" transform="translate(20,20) scale(.8)">
          <rect width="200" height="56" rx="10" fill="#0f2033" stroke="#37bdf8" stroke-width="2"/>
          <text x="100" y="36" text-anchor="middle" fill="#fff" font-size="22" font-family="Noto Sans SC">美国关税</text>
        </g>
        <g id="n2" opacity="0" transform="translate(20,148) scale(.8)">
          <rect width="200" height="56" rx="10" fill="#0f2033" stroke="#f09025" stroke-width="2"/>
          <text x="100" y="36" text-anchor="middle" fill="#fff" font-size="22" font-family="Noto Sans SC">中欧贸易</text>
        </g>
        <g id="n3" opacity="0" transform="translate(20,276) scale(.8)">
          <rect width="200" height="56" rx="10" fill="#0f2033" stroke="#37bdf8" stroke-width="2"/>
          <text x="100" y="36" text-anchor="middle" fill="#fff" font-size="22" font-family="Noto Sans SC">出口放量</text>
        </g>
      </svg>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <div class="rail-right">
      <div class="b" id="b1">EU进口 +{EU_IMP_CN_YOY}%</div>
      <div class="b" id="b2">对欧出口 +{CN_EXP_EU_YOY_2024}%</div>
      <div class="b" id="b3">对美出口 +{CN_EXP_US_YOY_2024}%</div>
    </div>
    <style>
      [data-composition-id="fs-scene3-flow"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="fs-scene3-flow"] .rail-left {{ {RAIL_L} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene3-flow"] .rail-right {{ {RAIL_R} font-family:"Roboto Mono",monospace; }}
      {SOURCE_CSS}
      [data-composition-id="fs-scene3-flow"] .ttl {{ font-size:26px; font-weight:800; color:{TEXT_BODY}; opacity:0; margin-bottom:8px; }}
      [data-composition-id="fs-scene3-flow"] .flow {{ width:240px; height:380px; }}
      [data-composition-id="fs-scene3-flow"] .b {{
        font-size:20px; color:{TEXT_BODY}; padding:12px 10px; margin-bottom:10px;
        background:rgba(11,22,35,.55); border-radius:10px; border-right:3px solid {TEXT_ACCENT};
        opacity:0; transform:translateX(32px);
      }}
      [data-composition-id="fs-scene3-flow"] .b:nth-child(2) {{ border-right-color:{TEXT_WARN}; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="fs-scene3-flow"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#ttl',{{opacity:1,duration:.35}},0.1);
        tl.to(S+'#n1',{{opacity:1,attr:{{transform:'translate(20,20) scale(1)'}},duration:.35,ease:'back.out(2)'}},0.3);
        tl.to(S+'#p1',{{strokeDashoffset:0,duration:.45,ease:'power2.inOut'}},0.5);
        tl.to(S+'#n2',{{opacity:1,attr:{{transform:'translate(20,148) scale(1)'}},duration:.35,ease:'back.out(2)'}},0.65);
        tl.to(S+'#p2',{{strokeDashoffset:0,duration:.45,ease:'power2.inOut'}},0.85);
        tl.to(S+'#n3',{{opacity:1,attr:{{transform:'translate(20,276) scale(1)'}},duration:.4,ease:'elastic.out(1,.55)'}},1.0);
        tl.to(S+'#b1',{{opacity:1,x:0,duration:.35,ease:'power3.out'}},1.2);
        tl.to(S+'#b2',{{opacity:1,x:0,duration:.35,ease:'power3.out'}},1.45);
        tl.to(S+'#b3',{{opacity:1,x:0,duration:.35,ease:'power3.out'}},1.7);
        tl.to(S+'#src',{{opacity:1,duration:.3}},2.0);
        tl.set({{}},{{}},6.76);
        window.__timelines=window.__timelines||{{}}; window.__timelines['fs-scene3-flow']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 4: left +6.4% slam, right € bars ---
(comp_dir / "fs-scene4-stats.html").write_text(f"""<template id="fs-scene4-stats-template">
  <div data-composition-id="fs-scene4-stats" data-start="0" data-width="{W}" data-height="{H}" data-duration="4.3">
    <div class="rail-left">
      <div class="k" id="k">欧盟自华进口</div>
      <div class="big" id="big">+{EU_IMP_CN_YOY}%</div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <div class="rail-right">
      <div class="row" id="r1"><span>2024</span><span class="amt" id="a1">€0B</span></div>
      <div class="track"><div class="fill" id="b1"></div></div>
      <div class="row" id="r2"><span>2025</span><span class="amt warn" id="a2">€0B</span></div>
      <div class="track"><div class="fill hot" id="b2"></div></div>
    </div>
    <style>
      [data-composition-id="fs-scene4-stats"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="fs-scene4-stats"] .rail-left {{ {RAIL_L} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene4-stats"] .rail-right {{ {RAIL_R} font-family:"Roboto Mono",monospace; }}
      {SOURCE_CSS}
      [data-composition-id="fs-scene4-stats"] .k {{ font-size:22px; color:{TEXT_MUTED}; opacity:0; }}
      [data-composition-id="fs-scene4-stats"] .big {{ font-size:72px; font-weight:900; color:{TEXT_WARN}; opacity:0; transform:scale(.4); margin-top:8px; }}
      [data-composition-id="fs-scene4-stats"] .row {{ display:flex; justify-content:space-between; font-size:20px; color:{TEXT_BODY}; opacity:0; margin-top:14px; }}
      [data-composition-id="fs-scene4-stats"] .amt {{ font-weight:700; color:{TEXT_ACCENT}; }}
      [data-composition-id="fs-scene4-stats"] .amt.warn {{ color:{TEXT_WARN}; }}
      [data-composition-id="fs-scene4-stats"] .track {{ height:16px; background:rgba(255,255,255,.12); border-radius:8px; overflow:hidden; margin-top:6px; }}
      [data-composition-id="fs-scene4-stats"] .fill {{ height:100%; width:0; background:{TEXT_ACCENT}; }}
      [data-composition-id="fs-scene4-stats"] .fill.hot {{ background:linear-gradient(90deg,{TEXT_WARN},#ff6b35); }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="fs-scene4-stats"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#k',{{opacity:1,duration:.25}},0.08);
        tl.to(S+'#big',{{opacity:1,scale:1,duration:.55,ease:'elastic.out(1,.55)'}},0.25);
        tl.to(S+'#r1',{{opacity:1,duration:.25}},0.85);
        tl.to(S+'#b1',{{width:'{BAR_2024_PCT}%',duration:.65,ease:'power2.out'}},0.9);
        tl.set(S+'#a1',{{textContent:'€{EU_IMP_CN_2024}B'}},0.9);
        tl.to(S+'#r2',{{opacity:1,duration:.25}},1.2);
        tl.to(S+'#b2',{{width:'100%',duration:.7,ease:'power3.out'}},1.25);
        tl.set(S+'#a2',{{textContent:'€{EU_IMP_CN_2025}B'}},1.25);
        tl.to(S+'#src',{{opacity:1,duration:.3}},1.8);
        tl.set({{}},{{}},4.3);
        window.__timelines=window.__timelines||{{}}; window.__timelines['fs-scene4-stats']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 5: split CTA ---
(comp_dir / "fs-scene5-cta.html").write_text(f"""<template id="fs-scene5-cta-template">
  <div data-composition-id="fs-scene5-cta" data-start="0" data-width="{W}" data-height="{H}" data-duration="2.233">
    <div class="rail-left">
      <div class="ey" id="ey">欧洲各国</div>
      <div class="ln" id="ln"></div>
    </div>
    <div class="rail-right">
      <div class="hd" id="hd">开始行动</div>
      <div class="sub" id="sub">持续跟进贸易变局</div>
    </div>
    <style>
      [data-composition-id="fs-scene5-cta"] {{ position:absolute; inset:0; pointer-events:none; }}
      [data-composition-id="fs-scene5-cta"] .rail-left {{ {RAIL_L} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene5-cta"] .rail-right {{ {RAIL_R} font-family:"Noto Sans SC",sans-serif; }}
      [data-composition-id="fs-scene5-cta"] .ey {{ font-size:32px; font-weight:800; color:{TEXT_MUTED}; opacity:0; transform:translateX(-24px); }}
      [data-composition-id="fs-scene5-cta"] .ln {{ height:4px; width:0; margin-top:16px; background:linear-gradient(90deg,{TEXT_ACCENT},{TEXT_WARN}); }}
      [data-composition-id="fs-scene5-cta"] .hd {{ font-size:56px; font-weight:900; color:{TEXT_ACCENT}; opacity:0; transform:scale(.7); text-shadow:0 0 40px rgba(55,189,248,.4); }}
      [data-composition-id="fs-scene5-cta"] .sub {{ margin-top:12px; font-size:22px; color:{TEXT_BODY}; opacity:0; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="fs-scene5-cta"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#ey',{{opacity:1,x:0,duration:.35,ease:'power3.out'}},0.08);
        tl.to(S+'#ln',{{width:180,duration:.4,ease:'power2.inOut'}},0.35);
        tl.to(S+'#hd',{{opacity:1,scale:1,duration:.45,ease:'back.out(1.6)'}},0.25);
        tl.to(S+'#sub',{{opacity:1,duration:.3}},0.65);
        tl.to(S+'#hd',{{scale:1.04,duration:1.2,ease:'none'}},0.5);
        tl.set({{}},{{}},2.233);
        window.__timelines=window.__timelines||{{}}; window.__timelines['fs-scene5-cta']=tl;
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
  <title>nov26-fullscreen 16:9</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Noto+Sans+SC:wght@700;900&family=Roboto+Mono:wght@500&display=block" rel="stylesheet" />
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html,body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; background:#050b13; }}
    #fullscreen-video {{
      position:absolute; top:0; left:0; width:{W}px; height:{H}px;
      object-fit:cover; object-position:center 38%; z-index:1; transform-origin:center center;
    }}
    .scene-layer {{ position:absolute; top:0; left:0; width:{W}px; height:{H}px; z-index:10; pointer-events:none; }}
    #captions-layer {{ z-index:30; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}"
       data-width="{W}" data-height="{H}">
    <video id="fullscreen-video" data-start="0" data-duration="{DUR}" data-track-index="1"
      src="assets/nov26-fullscreen.mp4" muted playsinline></video>
    <audio id="fullscreen-audio" data-start="0" data-duration="{DUR}" data-track-index="2"
      data-volume="1" src="assets/nov26-fullscreen.mp4"></audio>
    {"".join(scene_layers)}
    <div id="captions-layer" class="scene-layer"
      data-composition-id="captions" data-composition-src="compositions/captions.html"
      data-start="0" data-duration="{DUR}" data-track-index="4" data-width="{W}" data-height="{H}"></div>
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const mainTl = gsap.timeline({{ paused: true }});
    mainTl.to("#fullscreen-video", {{ scale: 1.04, duration: {DUR}, ease: "none" }}, 0);
    mainTl.set({{}}, {{}}, {DUR});
    window.__timelines["main"] = mainTl;
  </script>
</body>
</html>""", encoding="utf-8")

(ROOT / "meta.json").write_text(json.dumps({
    "id": "nov26-fullscreen", "name": "nov26-fullscreen-landscape",
    "width": W, "height": H, "fps": 30,
}, indent=2), encoding="utf-8")

print("fullscreen build ok", W, "x", H)
