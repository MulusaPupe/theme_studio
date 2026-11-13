"""The bundled font catalogue: @font-face rules and the files a site needs."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parents[1] / "resources" / "fonts"
_FALLBACK = {
    "sans": "system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif",
    "serif": "Georgia,'Times New Roman',serif",
    "mono": "ui-monospace,Menlo,Consolas,monospace",
}


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    return {f["family"]: f for f in json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))}


def font_stack(family: str) -> str:
    """A CSS font-family value. An unknown family still falls back to something sensible."""
    entry = catalog().get(family)
    fallback = _FALLBACK[entry["kind"]] if entry else _FALLBACK["sans"]
    return f"'{family}',{fallback}"


def font_face_css(families: set[str], url_prefix: str = "fonts/") -> str:
    rules = []
    for family in sorted(families):
        entry = catalog().get(family)
        if not entry:
            continue
        for item in entry["files"]:
            rules.append(
                f"@font-face{{font-family:'{family}';font-style:{item['style']};font-weight:{item['weight']};"
                f"font-display:swap;src:url('{url_prefix}{item['file']}') format('woff2')}}"
            )
    return "\n".join(rules)


def font_files(families: set[str]) -> list[Path]:
    files = []
    for family in sorted(families):
        entry = catalog().get(family)
        if entry:
            files += [FONT_DIR / item["file"] for item in entry["files"]]
    return files
