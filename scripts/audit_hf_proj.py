from pathlib import Path
import json

root = Path(r"E:\备份\20250313\work\new work\新建文件夹\新建文件夹\新建文件夹\cursor\outputs\proj_22f471a0c8cb")
for ver in sorted(root.glob("ver_*")):
    print(f"=== {ver.name} ===")
    tl = ver / "unified_timeline.json"
    hf = ver / "hyperframes"
    print(f"  timeline: {tl.exists()} ({tl.stat().st_size if tl.exists() else 0} bytes)")
    if not hf.exists():
        print("  hyperframes: MISSING")
        continue
    files = [f for f in hf.rglob("*") if f.is_file()]
    print(f"  hyperframes files: {len(files)}")
    for f in sorted(files):
        print(f"    {f.relative_to(hf)}  {f.stat().st_size}")
    idx = hf / "index.html"
    if idx.exists():
        t = idx.read_text(encoding="utf-8")
        print("  index checks:", {
            "composition": "data-composition-id" in t,
            "timelines": "__timelines" in t,
            "gsap": "gsap" in t,
            "clips": 'class="clip"' in t,
            "duration": "data-duration" in t,
            "lines": t.count("\n") + 1,
        })
    rl = ver / "render_log.json"
    if rl.exists():
        j = json.loads(rl.read_text(encoding="utf-8"))
        lo = j.get("lint_output") or ""
        warns = lo.count("⚠") + lo.count("warning")
        print("  render_log:", {
            "lint_ok": j.get("lint_ok"),
            "render_ok": j.get("render_ok"),
            "warn_count": warns,
        })
        print("  lint_head:", lo[:180].replace("\n", " "))
    pv = ver / "preview.mp4"
    print(f"  preview.mp4: {pv.exists()} ({pv.stat().st_size if pv.exists() else 0} bytes)")
