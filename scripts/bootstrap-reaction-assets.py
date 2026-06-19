#!/usr/bin/env python3
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path


ASSETS = {
    "laugh_cry": {
        "filename": "1F602.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F602.svg",
    },
    "mind_blown": {
        "filename": "1F92F.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F92F.svg",
    },
    "fire": {
        "filename": "1F525.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F525.svg",
    },
    "hundred": {
        "filename": "1F4AF.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F4AF.svg",
    },
    "clap": {
        "filename": "1F44F.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F44F.svg",
    },
    "party": {
        "filename": "1F389.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F389.svg",
    },
    "collision": {
        "filename": "1F4A5.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F4A5.svg",
    },
    "thinking": {
        "filename": "1F914.svg",
        "url": "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/1F914.svg",
    },
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "resources" / "reaction-assets" / "openmoji"
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    skipped = 0
    for spec in ASSETS.values():
        target = out_dir / spec["filename"]
        if target.exists() and target.stat().st_size > 0:
            skipped += 1
            continue
        with urllib.request.urlopen(spec["url"], timeout=30) as response:
            target.write_bytes(response.read())
        downloaded += 1
        print(f"downloaded {target.name}")
    print(f"done downloaded={downloaded} skipped={skipped} dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
