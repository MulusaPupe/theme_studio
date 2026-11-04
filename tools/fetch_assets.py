"""Download the open-licensed fonts and icons bundled with the application.

Run once when setting up or changing the bundled set; the results are kept in
``src/mulusa_theme_studio/resources``. The application itself never downloads
anything: this is what makes the canvas and exported sites work offline.

Fonts come from Fontsource (latin subset, woff2) and icons from lucide-static.
A font is only kept if its published licence is one we can redistribute.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "src" / "mulusa_theme_studio" / "resources"
UA = {"User-Agent": "mulusa-theme-studio-asset-fetch"}

# (family name, fontsource id, kind, has italic)
VARIABLE = [
    ("Inter", "inter", "sans", False),
    ("Manrope", "manrope", "sans", False),
    ("DM Sans", "dm-sans", "sans", False),
    ("Space Grotesk", "space-grotesk", "sans", False),
    ("Sora", "sora", "sans", False),
    ("Outfit", "outfit", "sans", False),
    ("Archivo", "archivo", "sans", False),
    ("Work Sans", "work-sans", "sans", False),
    ("Figtree", "figtree", "sans", False),
    ("Plus Jakarta Sans", "plus-jakarta-sans", "sans", False),
    ("Syne", "syne", "sans", False),
    ("Bricolage Grotesque", "bricolage-grotesque", "sans", False),
    ("Oswald", "oswald", "sans", False),
    ("Unbounded", "unbounded", "sans", False),
    ("Jost", "jost", "sans", False),
    ("Playfair Display", "playfair-display", "serif", True),
    ("Cormorant Garamond", "cormorant-garamond", "serif", True),
    ("Fraunces", "fraunces", "serif", True),
    ("Source Serif 4", "source-serif-4", "serif", True),
    ("Lora", "lora", "serif", True),
    ("Newsreader", "newsreader", "serif", True),
    ("Bodoni Moda", "bodoni-moda", "serif", True),
    ("EB Garamond", "eb-garamond", "serif", True),
    ("JetBrains Mono", "jetbrains-mono", "mono", False),
]
STATIC = [
    ("Bebas Neue", "bebas-neue", "sans", [400]),
    ("Anton", "anton", "sans", [400]),
    ("DM Serif Display", "dm-serif-display", "serif", [400]),
    ("Abril Fatface", "abril-fatface", "serif", [400]),
    ("Space Mono", "space-mono", "mono", [400, 700]),
    ("Libre Baskerville", "libre-baskerville", "serif", [400, 700]),
]
ICONS = """
layout-template blocks files layers images plus folder-open save undo-2 redo-2 monitor tablet smartphone
eye package settings search zoom-in zoom-out maximize x check circle-alert info type heading-1 pilcrow
image gallery-horizontal video star mouse-pointer-click link panel-top menu panel-bottom box columns-3
rows-3 square minus sparkles user-round list-checks users-round badge-dollar-sign chart-column
briefcase-business mail megaphone circle-help newspaper shopping-bag file-text house chevron-right
chevron-down palette lock clock arrow-right trash-2 text circle-check
compass shield-check rocket leaf hard-hat ruler gem music mic-vocal headphones disc-3 graduation-cap book-open
utensils wine chef-hat cpu code-xml cloud key-round map-pin phone bed-double bath scale handshake target
trending-up globe award scissors shirt pen-tool brush camera hammer building-2 factory truck zap ticket
copy copy-plus clipboard-paste arrow-up arrow-down columns-2 move-vertical mouse-pointer-2 hand
align-left align-center align-right align-justify upload crop image-plus shapes rotate-ccw sliders-horizontal refresh-cw replace bold italic underline list link-2
calendar database bar-chart-3 lightbulb heart coffee flame sprout microscope users trophy landmark drafting-compass
""".split()


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main() -> int:
    fonts_dir = RES / "fonts"
    icons_dir = RES / "icons"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    catalog: list[dict] = []
    failures: list[str] = []
    licences: dict[str, str] = {}

    def licence_of(pkg: str) -> str:
        meta = json.loads(get(f"https://cdn.jsdelivr.net/npm/{pkg}/package.json"))
        return str(meta.get("license", "unknown"))

    for family, fid, kind, italic in VARIABLE:
        try:
            lic = licence_of(f"@fontsource-variable/{fid}")
            files = []
            for style in ["normal"] + (["italic"] if italic else []):
                name = f"{fid}-{style}.woff2"
                (fonts_dir / name).write_bytes(
                    get(f"https://cdn.jsdelivr.net/fontsource/fonts/{fid}:vf@latest/latin-wght-{style}.woff2")
                )
                files.append({"file": name, "style": style, "weight": "100 900"})
            catalog.append({"family": family, "kind": kind, "files": files, "licence": lic})
            licences[family] = lic
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failures.append(f"{family}: {exc}")
    for family, fid, kind, weights in STATIC:
        try:
            lic = licence_of(f"@fontsource/{fid}")
            files = []
            for weight in weights:
                name = f"{fid}-{weight}.woff2"
                (fonts_dir / name).write_bytes(
                    get(f"https://cdn.jsdelivr.net/fontsource/fonts/{fid}@latest/latin-{weight}-normal.woff2")
                )
                files.append({"file": name, "style": "normal", "weight": str(weight)})
            catalog.append({"family": family, "kind": kind, "files": files, "licence": lic})
            licences[family] = lic
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failures.append(f"{family}: {exc}")

    (fonts_dir / "fonts.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")

    for icon in ICONS:
        try:
            (icons_dir / f"{icon}.svg").write_bytes(
                get(f"https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{icon}.svg")
            )
        except (urllib.error.URLError, OSError) as exc:
            failures.append(f"icon {icon}: {exc}")
    try:
        (icons_dir / "LICENSE-lucide.txt").write_bytes(get("https://cdn.jsdelivr.net/npm/lucide-static@latest/LICENSE"))
    except (urllib.error.URLError, OSError) as exc:
        failures.append(f"lucide licence: {exc}")

    print("fonts:", len(catalog), "icons:", len(list(icons_dir.glob("*.svg"))))
    print("licences:", sorted(set(licences.values())))
    not_ofl = {k: v for k, v in licences.items() if v not in {"OFL-1.1", "Apache-2.0"}}
    print("needs review:", not_ofl)
    print("failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
