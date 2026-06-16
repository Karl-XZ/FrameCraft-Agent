"""Build 16:9 landscape HyperFrames short with top-half face crop + rich motion graphics."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framecraft_paths import duration, input_dir, student_kit, workspace_root

ROOT = workspace_root(Path(__file__).resolve().parents[1])
KIT6 = student_kit(Path(__file__).resolve().parents[3] / "vendor" / "hyperframes-student-kit") / "video-projects" / "may-shorts-6"
if not KIT6.exists():
    KIT6 = student_kit(Path(__file__).resolve().parents[3] / "_hf_demo" / "hyperframes-student-kit") / "video-projects" / "may-shorts-6"
DUR = duration(25.033)
W, H = 1920, 1080
PANEL_W = 960  # 左侧动效区宽度；右侧 960px 专供口播，互不重叠
PANEL_BG = "#07121c"
CAP_SAFE = 150  # 底部字幕安全区高度（动效不得侵入）
TEXT_BODY = "#f2f6fb"       # 主文案：深色底上用近白
TEXT_MUTED = "#e0e8f2"      # 次要标签：浅灰蓝，深色底可读
TEXT_ACCENT = "#37bdf8"
TEXT_WARN = "#f09025"

# --- 可核实公开数据（标注场景专用）---
EU_IMP_CN_2024 = 519       # 亿欧元，Eurostat 2024 自华进口
EU_IMP_CN_2025 = 559       # 亿欧元，Eurostat 2025 自华进口
EU_IMP_CN_YOY = 6.4        # %，2025 同比 2024（Eurostat）
CN_EXP_EU_YOY_2024 = 3.0   # %，2024 对欧盟出口同比（海关总署，美元计）
CN_EXP_US_YOY_2024 = 4.9   # %，2024 对美国出口同比（海关总署）
BAR_2024_PCT = round(EU_IMP_CN_2024 / EU_IMP_CN_2025 * 100, 1)
BAR_2025_PCT = 100.0

SRC_EUROSTAT = "来源：Eurostat，2025-04"
SRC_GACC = "来源：海关总署，2024"
SRC_MIXED = "来源：Eurostat / 海关总署"

_growth = [EU_IMP_CN_YOY, CN_EXP_EU_YOY_2024, CN_EXP_US_YOY_2024]
_gmax = max(_growth)
SCENE2_BAR = [round(v / _gmax * 100) for v in _growth]

SOURCE_STYLE = f"""
      .data-source {{
        position:absolute; left:24px; bottom:{CAP_SAFE + 6}px; z-index:6;
        font-family:"Roboto Mono",monospace; font-size:17px; line-height:1.35;
        color:{TEXT_MUTED}; letter-spacing:.02em; max-width:900px; opacity:0;
      }}
"""
PANEL_STYLE = (
    f"position:absolute;top:0;left:0;width:{PANEL_W}px;height:{H}px;"
    f"background:{PANEL_BG};box-sizing:border-box;overflow:hidden;"
    f"padding-bottom:{CAP_SAFE}px;"
)

_transcript_path = input_dir(ROOT / "assets") / "transcript.json"
if not _transcript_path.exists():
    _transcript_path = ROOT / "assets" / "transcript.json"
transcript = json.loads(_transcript_path.read_text(encoding="utf-8"))
segments = transcript["segments"]

SCENES = [
    {"id": "scene1-hook", "start": 0.0, "end": 5.67},
    {"id": "scene2-grid", "start": 5.67, "end": 11.74},
    {"id": "scene3-flow", "start": 11.74, "end": 18.5},
    {"id": "scene4-stats", "start": 18.5, "end": 22.8},
    {"id": "scene5-cta", "start": 22.8, "end": DUR},
]

comp_dir = ROOT / "compositions"
comp_dir.mkdir(exist_ok=True)

# --- ambient-bg (landscape, from may-shorts-6) ---
amb = (KIT6 / "compositions" / "ambient-bg.html").read_text(encoding="utf-8")
amb = amb.replace("19.5", str(DUR)).replace("1920", str(W)).replace("1080", str(H))
(comp_dir / "ambient-bg.html").write_text(amb, encoding="utf-8")

# --- captions 16:9 ---
seg_js = [{"words": [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in s.get("words", [])]} for s in segments if s.get("words")]
captions_html = f"""<template id="captions-template">
  <div data-composition-id="captions" data-start="0" data-width="{W}" data-height="{H}" data-duration="{DUR}">
    <div class="cap-backdrop"></div>
    <div class="cap-stage" id="cap-stage"></div>
    <style>
      [data-composition-id="captions"] {{ position:absolute; inset:0; pointer-events:none; z-index:30; }}
      [data-composition-id="captions"] .cap-backdrop {{
        position:absolute; left:0; right:0; bottom:0; height:{CAP_SAFE + 40}px;
        background:linear-gradient(180deg,transparent 0%,rgba(5,11,19,.72) 45%,rgba(5,11,19,.92) 100%);
        pointer-events:none;
      }}
      [data-composition-id="captions"] .cap-stage {{
        position:absolute; left:0; right:0; bottom:88px; height:0; z-index:2;
      }}
      [data-composition-id="captions"] .cap-line-wrap {{
        position:absolute; left:0; right:0; bottom:0;
        display:flex; justify-content:center; align-items:flex-end;
        padding:0 64px; opacity:0; visibility:hidden;
      }}
      [data-composition-id="captions"] .cap-line {{
        display:inline-block; max-width:1680px; text-align:center;
        font-family:"Noto Sans SC","Montserrat",sans-serif; font-weight:900; font-size:52px;
        line-height:1.18; color:#fff;
        text-shadow:-3px -3px 0 #07121c,3px -3px 0 #07121c,-3px 3px 0 #07121c,3px 3px 0 #07121c,
          -4px 0 0 #07121c,4px 0 0 #07121c,0 -4px 0 #07121c,0 4px 0 #07121c,
          0 8px 24px rgba(0,0,0,.75);
      }}
      [data-composition-id="captions"] .cap-word {{ display:inline-block; transform-origin:center; padding:0 .05em; }}
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
          const wrap = document.createElement("div"); wrap.className="cap-line-wrap"; wrap.id="cap-line-"+si;
          const line = document.createElement("div"); line.className="cap-line";
          seg.words.forEach((w, wi) => {{
            const span = document.createElement("span"); span.className="cap-word"; span.textContent=w.word;
            span.style.color=DIM; line.appendChild(span);
            if (wi < seg.words.length-1) line.appendChild(document.createTextNode(" "));
            const accent = hot.has(w.word.replace(/[，。！？]/g,"")) ? WARN : ACTIVE;
            tl.set(wrap,{{opacity:1,visibility:"visible"}}, w.start-0.02);
            tl.to(span,{{color:accent,scale:1.12,duration:.09,ease:"back.out(2.5)"}}, w.start);
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
</template>
"""
(comp_dir / "captions.html").write_text(captions_html, encoding="utf-8")

# --- scene 1: EU import growth hook (real data) ---
(comp_dir / "scene1-hook.html").write_text(f"""<template id="scene1-hook-template">
  <div data-composition-id="scene1-hook" data-start="0" data-width="{W}" data-height="{H}" data-duration="5.67">
    <div class="panel">
      <div class="label" id="label">欧盟自华进口 · 2025同比</div>
      <div class="big"><span class="sign" id="sign">+</span><span class="counter" id="counter">0</span><span class="plus" id="plus">%</span></div>
      <div class="stamp" id="stamp"><span>2025年进口约{EU_IMP_CN_2025}0亿欧元</span><span class="ul" id="ul"></span></div>
      <div class="ticks" id="ticks">
        <div class="tick"></div><div class="tick"></div><div class="tick"></div><div class="tick"></div>
      </div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <style>
      [data-composition-id="scene1-hook"] {{ position:absolute; inset:0; }}
      [data-composition-id="scene1-hook"] .panel {{
        {PANEL_STYLE}
        display:flex; flex-direction:column; justify-content:center; gap:18px; padding:80px 90px;
        font-family:"Noto Sans SC","Montserrat",sans-serif;
        background:linear-gradient(135deg,{PANEL_BG} 0%,#0d2031 100%);
      }}
      {SOURCE_STYLE}
      [data-composition-id="scene1-hook"] .label {{ font-family:"Roboto Mono",monospace; font-size:38px; letter-spacing:.16em; color:{TEXT_MUTED}; opacity:0; }}
      [data-composition-id="scene1-hook"] .big {{ display:flex; align-items:baseline; gap:4px; font-weight:900; font-size:280px; color:#37bdf8;
        text-shadow:0 0 60px rgba(55,189,248,.45); line-height:.9; }}
      [data-composition-id="scene1-hook"] .sign {{ font-size:140px; color:{TEXT_WARN}; opacity:0; }}
      [data-composition-id="scene1-hook"] .plus {{ font-size:160px; color:#f09025; opacity:0; transform:scale(0); }}
      [data-composition-id="scene1-hook"] .stamp {{ position:relative; font-size:44px; font-weight:700; color:#fff; clip-path:inset(0 100% 0 0); }}
      [data-composition-id="scene1-hook"] .ul {{ position:absolute; left:0; bottom:-8px; height:4px; width:100%; background:#37bdf8; transform:scaleX(0); transform-origin:left; }}
      [data-composition-id="scene1-hook"] .ticks {{ display:flex; gap:12px; margin-top:12px; }}
      [data-composition-id="scene1-hook"] .tick {{ width:4px; height:48px; background:#37bdf8; opacity:0; transform:scaleY(0); transform-origin:bottom; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="scene1-hook"] '; const tl=gsap.timeline({{paused:true}});
        const target={EU_IMP_CN_YOY}; const c={{val:0}}; const el=document.querySelector(S+'.counter');
        tl.to(S+'.label',{{opacity:1,duration:.32,ease:'power2.out'}},0.08);
        tl.to(S+'.sign',{{opacity:1,duration:.2}},0.3);
        tl.to(c,{{val:target,duration:1.1,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent=c.val.toFixed(1);}}}},0.35);
        tl.to(S+'.plus',{{opacity:1,scale:1,duration:.28,ease:'back.out(3)'}},1.35);
        tl.to(S+'.stamp',{{clipPath:'inset(0 0% 0 0)',duration:.55,ease:'power4.out'}},1.55);
        tl.to(S+'.ul',{{scaleX:1,duration:.4,ease:'power2.inOut'}},2.0);
        tl.to(S+'.tick',{{opacity:1,scaleY:1,duration:.22,stagger:.08,ease:'power2.out'}},2.2);
        tl.to(S+'#src',{{opacity:1,duration:.35}},2.4);
        tl.set({{}},{{}},5.67);
        window.__timelines=window.__timelines||{{}}; window.__timelines['scene1-hook']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 2: trade growth comparison (real YoY data) ---
(comp_dir / "scene2-grid.html").write_text(f"""<template id="scene2-grid-template">
  <div data-composition-id="scene2-grid" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.07">
    <div class="panel">
      <div class="hdr" id="hdr">出口增速对比（同比）</div>
      <div class="grid">
        <div class="card" id="c1"><div class="flag">🇪🇺</div><div class="name">欧盟自华进口</div><div class="bar"><div class="fill" id="f1"></div></div><div class="val" id="v1">0</div></div>
        <div class="card" id="c2"><div class="flag">🇨🇳</div><div class="name">中国对欧出口</div><div class="bar"><div class="fill" id="f2"></div></div><div class="val" id="v2">0</div></div>
        <div class="card" id="c3"><div class="flag">🇺🇸</div><div class="name">中国对美出口</div><div class="bar"><div class="fill" id="f3"></div></div><div class="val" id="v3">0</div></div>
      </div>
      <div class="ticker" id="ticker">EU +{EU_IMP_CN_YOY}% · CN→EU +{CN_EXP_EU_YOY_2024}% · CN→US +{CN_EXP_US_YOY_2024}%</div>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <style>
      [data-composition-id="scene2-grid"] {{ position:absolute; inset:0; }}
      [data-composition-id="scene2-grid"] .panel {{
        {PANEL_STYLE} padding:70px 80px;
        background:linear-gradient(160deg,{PANEL_BG},#0d2031);
        font-family:"Noto Sans SC","Montserrat",sans-serif;
      }}
      {SOURCE_STYLE}
      [data-composition-id="scene2-grid"] .hdr {{ font-size:44px; font-weight:900; color:#37bdf8; opacity:0; letter-spacing:.06em; margin-bottom:36px; }}
      [data-composition-id="scene2-grid"] .grid {{ display:flex; flex-direction:column; gap:28px; }}
      [data-composition-id="scene2-grid"] .card {{
        display:grid; grid-template-columns:72px 200px 1fr 100px; align-items:center; gap:16px;
        padding:22px 24px; border:1px solid rgba(55,189,248,.25); border-radius:12px;
        background:rgba(15,32,51,.6); opacity:0; transform:translateX(-40px);
      }}
      [data-composition-id="scene2-grid"] .flag {{ font-size:40px; }}
      [data-composition-id="scene2-grid"] .name {{ font-size:32px; font-weight:700; color:{TEXT_BODY}; }}
      [data-composition-id="scene2-grid"] .bar {{ height:12px; background:rgba(255,255,255,.08); border-radius:6px; overflow:hidden; }}
      [data-composition-id="scene2-grid"] .fill {{ height:100%; width:0; background:linear-gradient(90deg,#37bdf8,#f09025); }}
      [data-composition-id="scene2-grid"] .val {{ font-family:"Roboto Mono",monospace; font-size:32px; color:#f09025; }}
      [data-composition-id="scene2-grid"] .ticker {{
        position:absolute; top:520px; left:80px; font-family:"Roboto Mono",monospace; font-size:22px;
        color:{TEXT_BODY}; letter-spacing:.2em; white-space:nowrap; opacity:0;
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="scene2-grid"] '; const tl=gsap.timeline({{paused:true}});
        const nums=[
          {{el:'#v1',t:{EU_IMP_CN_YOY},f:'#f1',bar:{SCENE2_BAR[0]}}},
          {{el:'#v2',t:{CN_EXP_EU_YOY_2024},f:'#f2',bar:{SCENE2_BAR[1]}}},
          {{el:'#v3',t:{CN_EXP_US_YOY_2024},f:'#f3',bar:{SCENE2_BAR[2]}}}
        ];
        tl.to(S+'#hdr',{{opacity:1,y:0,duration:.4,ease:'power2.out'}},0.1);
        tl.to(S+'.card',{{opacity:1,x:0,duration:.45,stagger:.18,ease:'power3.out'}},0.35);
        nums.forEach((n,i)=>{{
          const o={{v:0}}; const el=document.querySelector(S+n.el);
          tl.to(o,{{v:n.t,duration:.9,ease:'power2.out',onUpdate:()=>{{if(el)el.textContent='+'+o.v.toFixed(1)+'%';}}}},0.7+i*0.25);
          tl.to(S+n.f,{{width:n.bar+'%',duration:.9,ease:'power2.out'}},0.7+i*0.25);
        }});
        tl.to(S+'#c2',{{boxShadow:'0 0 40px rgba(240,144,37,.45)',borderColor:'#f09025',duration:.3}},2.8);
        tl.to(S+'#ticker',{{opacity:1,duration:.3}},1.2);
        tl.to(S+'#src',{{opacity:1,duration:.35}},2.0);
        tl.set({{}},{{}},6.07);
        window.__timelines=window.__timelines||{{}}; window.__timelines['scene2-grid']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 3: supply-chain flow (unified SVG) ---
(comp_dir / "scene3-flow.html").write_text(f"""<template id="scene3-flow-template">
  <div data-composition-id="scene3-flow" data-start="0" data-width="{W}" data-height="{H}" data-duration="6.76">
    <div class="panel">
      <div class="title" id="title">贸易战 → 供应链重组</div>
      <svg class="diagram" viewBox="0 0 860 560" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arrow-blue" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6 Z" fill="#37bdf8"/>
          </marker>
          <marker id="arrow-orange" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6 Z" fill="#f09025"/>
          </marker>
        </defs>
        <path id="path-us-eu" d="M248,416 H312" stroke="#37bdf8" stroke-width="5" fill="none"
          stroke-dasharray="70" stroke-dashoffset="70" marker-end="url(#arrow-blue)"/>
        <path id="path-eu-up" d="M412,372 V176" stroke="#f09025" stroke-width="5" fill="none"
          stroke-dasharray="200" stroke-dashoffset="200" marker-end="url(#arrow-orange)"/>
        <g id="node-us" opacity="0" transform="translate(48,372) scale(0.7)">
          <rect width="200" height="88" rx="14" fill="#0f2033" stroke="#37bdf8" stroke-width="2.5"/>
          <text x="100" y="54" text-anchor="middle" fill="#ffffff" font-size="30" font-weight="700"
            font-family="'Noto Sans SC','Montserrat',sans-serif">美国关税</text>
        </g>
        <g id="node-eu" opacity="0" transform="translate(312,372) scale(0.7)">
          <rect width="200" height="88" rx="14" fill="#0f2033" stroke="#f09025" stroke-width="2.5"/>
          <text x="100" y="54" text-anchor="middle" fill="#ffffff" font-size="30" font-weight="700"
            font-family="'Noto Sans SC','Montserrat',sans-serif">中欧贸易</text>
        </g>
        <g id="node-export" opacity="0" transform="translate(312,88) scale(0.7)">
          <rect width="200" height="88" rx="14" fill="#0f2033" stroke="#37bdf8" stroke-width="2.5"/>
          <text x="100" y="54" text-anchor="middle" fill="#ffffff" font-size="30" font-weight="700"
            font-family="'Noto Sans SC','Montserrat',sans-serif">出口激增</text>
        </g>
        <circle id="pulse" cx="412" cy="274" r="0" fill="none" stroke="#f09025" stroke-width="3" opacity="0"/>
      </svg>
      <div class="legend" id="legend">2025自华进口 +{EU_IMP_CN_YOY}% · 2024对欧出口 +{CN_EXP_EU_YOY_2024}%</div>
      <div class="data-source" id="src">{SRC_MIXED}</div>
    </div>
    <style>
      [data-composition-id="scene3-flow"] {{ position:absolute; inset:0; }}
      [data-composition-id="scene3-flow"] .panel {{
        {PANEL_STYLE}
        background:linear-gradient(135deg,{PANEL_BG},#0a1828);
      }}
      {SOURCE_STYLE}
      [data-composition-id="scene3-flow"] .title {{
        position:absolute; top:72px; left:72px; font-size:46px; font-weight:900; color:#fff; opacity:0;
        font-family:"Noto Sans SC","Montserrat",sans-serif;
      }}
      [data-composition-id="scene3-flow"] .diagram {{
        position:absolute; top:150px; left:48px; width:864px; height:560px; overflow:visible;
      }}
      [data-composition-id="scene3-flow"] .legend {{
        position:absolute; top:700px; left:72px; font-family:"Roboto Mono",monospace;
        font-size:22px; color:{TEXT_BODY}; letter-spacing:.04em; opacity:0;
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="scene3-flow"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#title',{{opacity:1,duration:.4,ease:'power2.out'}},0.1);
        tl.to(S+'#node-us',{{opacity:1,attr:{{transform:'translate(48,372) scale(1)'}},duration:.4,ease:'back.out(2)'}},0.35);
        tl.to(S+'#path-us-eu',{{strokeDashoffset:0,duration:.55,ease:'power2.inOut'}},0.55);
        tl.to(S+'#node-eu',{{opacity:1,attr:{{transform:'translate(312,372) scale(1)'}},duration:.4,ease:'back.out(2)'}},0.75);
        tl.to(S+'#path-eu-up',{{strokeDashoffset:0,duration:.6,ease:'power2.inOut'}},1.05);
        tl.to(S+'#node-export',{{opacity:1,attr:{{transform:'translate(312,88) scale(1)'}},duration:.45,ease:'elastic.out(1,.55)'}},1.35);
        tl.to(S+'#pulse',{{opacity:1,attr:{{r:36}},duration:.9,ease:'power2.out'}},1.7);
        tl.to(S+'#pulse',{{opacity:0,duration:.4}},2.5);
        tl.to(S+'#legend',{{opacity:1,duration:.35}},1.9);
        tl.to(S+'#src',{{opacity:1,duration:.35}},2.1);
        tl.set({{}},{{}},6.76);
        window.__timelines=window.__timelines||{{}}; window.__timelines['scene3-flow']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 4: EU import volume + YoY (real data) ---
(comp_dir / "scene4-stats.html").write_text(f"""<template id="scene4-stats-template">
  <div data-composition-id="scene4-stats" data-start="0" data-width="{W}" data-height="{H}" data-duration="4.3">
    <div class="panel">
      <div class="kicker" id="kicker">欧盟自华进口额</div>
      <div class="stat-wrap">
        <div class="sign" id="sign">+</div>
        <div class="stat" id="stat">{EU_IMP_CN_YOY}%</div>
      </div>
      <div class="bars">
        <div class="row"><span>2024</span><div class="track"><div class="fill" id="b1"></div></div><span id="p1">€{EU_IMP_CN_2024}B</span></div>
        <div class="row"><span>2025</span><div class="track"><div class="fill hot" id="b2"></div></div><span id="p2">€{EU_IMP_CN_2025}B</span></div>
      </div>
      <div class="slam" id="slam">2025同比 +{EU_IMP_CN_YOY}%</div>
      <div class="data-source" id="src">{SRC_EUROSTAT}</div>
    </div>
    <style>
      [data-composition-id="scene4-stats"] {{ position:absolute; inset:0; }}
      [data-composition-id="scene4-stats"] .panel {{
        {PANEL_STYLE} padding:70px 80px;
        background:linear-gradient(160deg,{PANEL_BG},#0d2031);
        font-family:"Noto Sans SC","Montserrat",sans-serif;
      }}
      {SOURCE_STYLE}
      [data-composition-id="scene4-stats"] .kicker {{ font-family:"Roboto Mono",monospace; font-size:32px; color:{TEXT_MUTED}; opacity:0; letter-spacing:.14em; }}
      [data-composition-id="scene4-stats"] .stat-wrap {{ position:relative; height:220px; margin:20px 0; display:flex; align-items:baseline; gap:8px; }}
      [data-composition-id="scene4-stats"] .sign {{ font-weight:900; font-size:120px; color:{TEXT_WARN}; opacity:0; line-height:1; }}
      [data-composition-id="scene4-stats"] .stat {{
        font-weight:900; font-size:200px; line-height:1; opacity:0; color:#f09025; transform:scale(.5);
      }}
      [data-composition-id="scene4-stats"] .bars {{ display:flex; flex-direction:column; gap:20px; margin-top:16px; }}
      [data-composition-id="scene4-stats"] .row {{ display:grid; grid-template-columns:80px 1fr 120px; align-items:center; gap:16px; font-size:28px; color:{TEXT_BODY}; opacity:0; }}
      [data-composition-id="scene4-stats"] .row span:last-child {{ color:{TEXT_WARN}; font-family:"Roboto Mono",monospace; font-weight:700; font-size:26px; }}
      [data-composition-id="scene4-stats"] .track {{ height:28px; background:rgba(255,255,255,.08); border-radius:6px; overflow:hidden; }}
      [data-composition-id="scene4-stats"] .fill {{ height:100%; width:0; background:#37bdf8; }}
      [data-composition-id="scene4-stats"] .fill.hot {{ background:linear-gradient(90deg,#f09025,#ff6b35); }}
      [data-composition-id="scene4-stats"] .slam {{
        margin-top:28px; font-size:48px; font-weight:900; color:#fff; clip-path:inset(0 100% 0 0);
        text-shadow:0 0 30px rgba(240,144,37,.5);
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="scene4-stats"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'#kicker',{{opacity:1,duration:.3}},0.08);
        tl.to(S+'#sign',{{opacity:1,duration:.2}},0.3);
        tl.to(S+'#stat',{{opacity:1,scale:1,duration:.55,ease:'elastic.out(1,.55)'}},0.35);
        tl.to(S+'.row',{{opacity:1,duration:.3,stagger:.15}},0.9);
        tl.to(S+'#b1',{{width:'{BAR_2024_PCT}%',duration:.7,ease:'power2.out'}},1.0);
        tl.to(S+'#b2',{{width:'{BAR_2025_PCT}%',duration:.85,ease:'power3.out'}},1.2);
        tl.to(S+'#slam',{{clipPath:'inset(0 0% 0 0)',duration:.5,ease:'power4.out'}},1.85);
        tl.to(S+'#src',{{opacity:1,duration:.35}},2.1);
        tl.set({{}},{{}},4.3);
        window.__timelines=window.__timelines||{{}}; window.__timelines['scene4-stats']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- scene 5: CTA outro ---
(comp_dir / "scene5-cta.html").write_text(f"""<template id="scene5-cta-template">
  <div data-composition-id="scene5-cta" data-start="0" data-width="{W}" data-height="{H}" data-duration="2.233">
    <div class="panel">
      <div class="lockup" id="lockup">
        <div class="eyebrow" id="eyebrow">欧洲各国</div>
        <div class="headline" id="headline">开始行动</div>
        <div class="cta-bar" id="bar"></div>
        <div class="sub" id="sub">关注 · 持续跟进贸易变局</div>
      </div>
      <div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
    </div>
    <style>
      [data-composition-id="scene5-cta"] {{ position:absolute; inset:0; }}
      [data-composition-id="scene5-cta"] .panel {{
        {PANEL_STYLE}
        display:flex; align-items:center; justify-content:center;
        background:radial-gradient(ellipse at 40% 50%,#0f2033,{PANEL_BG});
        font-family:"Noto Sans SC","Montserrat",sans-serif;
      }}
      [data-composition-id="scene5-cta"] .lockup {{ text-align:center; opacity:0; transform:scale(.92); }}
      [data-composition-id="scene5-cta"] .eyebrow {{ font-family:"Roboto Mono",monospace; font-size:36px; color:{TEXT_MUTED}; letter-spacing:.2em; }}
      [data-composition-id="scene5-cta"] .headline {{ font-size:120px; font-weight:900; color:#37bdf8; margin:12px 0;
        text-shadow:0 0 50px rgba(55,189,248,.4); }}
      [data-composition-id="scene5-cta"] .cta-bar {{ height:6px; width:0; margin:0 auto 20px; background:linear-gradient(90deg,#37bdf8,#f09025); }}
      [data-composition-id="scene5-cta"] .sub {{ font-size:40px; color:#fff; opacity:0; }}
      [data-composition-id="scene5-cta"] .corner {{ position:absolute; width:48px; height:48px; border:3px solid #37bdf8; opacity:0; }}
      [data-composition-id="scene5-cta"] .tl {{ top:60px; left:60px; border-right:none; border-bottom:none; }}
      [data-composition-id="scene5-cta"] .tr {{ top:60px; right:60px; border-left:none; border-bottom:none; }}
      [data-composition-id="scene5-cta"] .bl {{ bottom:60px; left:60px; border-right:none; border-top:none; }}
      [data-composition-id="scene5-cta"] .br {{ bottom:60px; right:60px; border-left:none; border-top:none; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <script>
      (function(){{
        const S='[data-composition-id="scene5-cta"] '; const tl=gsap.timeline({{paused:true}});
        tl.to(S+'.corner',{{opacity:1,duration:.25,stagger:.06}},0.05);
        tl.to(S+'#lockup',{{opacity:1,scale:1,duration:.45,ease:'back.out(1.4)'}},0.15);
        tl.to(S+'#bar',{{width:480,duration:.4,ease:'power2.inOut'}},0.55);
        tl.to(S+'#sub',{{opacity:1,duration:.35}},0.75);
        tl.to(S+'#headline',{{scale:1.04,duration:1.2,ease:'none'}},0.5);
        tl.set({{}},{{}},2.233);
        window.__timelines=window.__timelines||{{}}; window.__timelines['scene5-cta']=tl;
      }})();
    </script>
  </div>
</template>""", encoding="utf-8")

# --- index.html 16:9 ---
scene_layers = []
for sc in SCENES:
    dur = round(sc["end"] - sc["start"], 3)
    scene_layers.append(f"""
      <div class="scene-layer" data-composition-id="{sc['id']}"
        data-composition-src="compositions/{sc['id']}.html"
        data-start="{sc['start']}" data-duration="{dur}"
        data-track-index="3" data-width="{W}" data-height="{H}"></div>""")

index_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width={W}, height={H}" />
  <title>nov26-short 16:9 v2</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Noto+Sans+SC:wght@700;900&family=Roboto+Mono:wght@500&display=block" rel="stylesheet" />
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html,body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; background:#050b13; }}
    #face-slot {{
      position:absolute; left:{PANEL_W}px; top:0; width:{PANEL_W}px; height:{H}px;
      overflow:hidden; z-index:2; background:#050b13;
    }}
    #face-wrapper {{
      position:absolute; top:0; left:0; width:1080px; height:1080px;
      transform-origin:0 0; will-change:transform;
    }}
    #face-video {{
      display:block; width:100%; height:100%; object-fit:cover; object-position:center 18%;
      filter:contrast(1.08) saturate(1.06) brightness(0.98); transform-origin:center center;
    }}
    #face-wrapper::after {{
      content:""; position:absolute; inset:0; pointer-events:none;
      background:radial-gradient(ellipse at 50% 42%,transparent 52%,rgba(5,11,19,.45) 88%,rgba(5,11,19,.75) 100%);
    }}
    #split-line {{
      position:absolute; left:{PANEL_W}px; top:0; width:3px; height:{H}px; z-index:15;
      background:linear-gradient(180deg,transparent,rgba(55,189,248,.55) 20%,rgba(55,189,248,.55) 80%,transparent);
      box-shadow:0 0 18px rgba(55,189,248,.35);
    }}
    .scene-layer {{ position:absolute; top:0; left:0; width:{W}px; height:{H}px; z-index:10; pointer-events:none; }}
    #captions-layer {{ z-index:30; }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}"
       data-width="{W}" data-height="{H}">
    <div id="ambient-bg" class="scene-layer" style="z-index:0;"
      data-composition-id="ambient-bg" data-composition-src="compositions/ambient-bg.html"
      data-start="0" data-duration="{DUR}" data-track-index="0" data-width="{W}" data-height="{H}"></div>

    <div id="face-slot">
      <div id="face-wrapper">
        <video id="face-video" data-start="0" data-duration="{DUR}" data-track-index="1"
          src="assets/nov26-face-clean.mp4" muted playsinline></video>
      </div>
    </div>

    <audio id="face-audio" data-start="0" data-duration="{DUR}" data-track-index="2"
      data-volume="1" src="assets/nov26-face-clean.mp4"></audio>

    {"".join(scene_layers)}

    <div id="split-line"></div>

    <div id="captions-layer" class="scene-layer"
      data-composition-id="captions" data-composition-src="compositions/captions.html"
      data-start="0" data-duration="{DUR}" data-track-index="4" data-width="{W}" data-height="{H}"></div>
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const mainTl = gsap.timeline({{ paused: true }});
    const SIDE = {{ x: -60, y: 0, scale: 1.0 }};
    mainTl.set("#face-wrapper", SIDE, 0);
    mainTl.to("#face-video", {{ scale: 1.05, duration: {DUR}, ease: "none" }}, 0);
    mainTl.set({{}}, {{}}, {DUR});
    window.__timelines["main"] = mainTl;
  </script>
</body>
</html>
"""
(ROOT / "index.html").write_text(index_html, encoding="utf-8")
(ROOT / "meta.json").write_text(json.dumps({"id": "nov26-short", "name": "nov26-short-landscape", "width": W, "height": H, "fps": 30}, indent=2), encoding="utf-8")
print("landscape build ok", W, "x", H)
