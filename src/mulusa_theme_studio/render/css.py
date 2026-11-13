"""Token and element styles to CSS.

Element styles are a controlled vocabulary, not free CSS: only known properties
are written and values that could escape the rule are dropped. ``$name`` in a value
means the design token ``--mts-name``, which is how a global colour or font change
reaches every element that uses it.
"""
from __future__ import annotations

import re
from typing import Any

from ..core.styles import STYLE_PROPERTIES, is_safe_value
from .fonts import catalog, font_stack

_TOKEN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_-]*)")
_GRID = re.compile(r"^[0-9a-zA-Z.%()\s,-]+$")
BREAKPOINT_QUERIES = {
    "desktop": "(min-width:1025px)",
    "tablet": "(max-width:1024px)",
    "mobile": "(max-width:640px)",
}


def style_value(value: Any) -> str | None:
    text = str(value).strip()
    if not text or not is_safe_value(text):
        return None
    return _TOKEN.sub(lambda m: f"var(--mts-{m.group(1)})", text)


def declarations(style: dict[str, Any]) -> str:
    out = []
    for key, value in style.items():
        if key not in STYLE_PROPERTIES:
            continue
        if key == "font_family" and str(value) in catalog():
            value = font_stack(str(value))  # A bundled family, named plainly in the document.
        css = style_value(value)
        if css is not None:
            out.append(f"{key.replace('_', '-')}:{css}")
    return ";".join(out)


def columns_value(value: Any) -> str | None:
    """A grid-template-columns value from a count or a track list such as '7fr 5fr'."""
    if isinstance(value, int) and value > 0:
        return f"repeat({value},minmax(0,1fr))"
    text = str(value).strip()
    if text.isdigit() and int(text) > 0:
        return f"repeat({int(text)},minmax(0,1fr))"
    return text if text and _GRID.match(text) else None


def column_count(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else len(text.split())


def tokens_css(tokens: dict[str, Any]) -> str:
    colors = tokens["colors"]
    fonts = tokens["fonts"]
    type_ = tokens.get("type", {})
    shape = tokens.get("shape", {})
    spacing = tokens.get("spacing", {})
    base = float(type_.get("base", 17))
    ratio = float(type_.get("ratio", 1.3))
    values = {f"--mts-{name}": value for name, value in colors.items()}
    values.update(
        {
            "--mts-font-heading": font_stack(fonts["heading"]),
            "--mts-font-body": font_stack(fonts["body"]),
            "--mts-body-size": f"{base}px",
            "--mts-heading-weight": type_.get("heading_weight", 700),
            "--mts-heading-transform": type_.get("heading_transform", "none"),
            "--mts-heading-tracking": type_.get("heading_tracking", "-0.01em"),
            "--mts-heading-line": type_.get("heading_line", 1.12),
            "--mts-radius": shape.get("radius", "8px"),
            "--mts-btn-radius": shape.get("button_radius", shape.get("radius", "8px")),
            "--mts-card-radius": shape.get("card_radius", shape.get("radius", "8px")),
            "--mts-input-radius": shape.get("input_radius", shape.get("radius", "8px")),
            "--mts-body-line": type_.get("body_line", 1.65),
            "--mts-space-s": spacing.get("space_s", "12px"),
            "--mts-space-m": spacing.get("space_m", "24px"),
            "--mts-space-l": spacing.get("space_l", "48px"),
            "--mts-btn-border": shape.get("button_border", "1.5px"),
            "--mts-btn-transform": shape.get("button_transform", "none"),
            "--mts-btn-tracking": shape.get("button_tracking", "0"),
            "--mts-btn-size": shape.get("button_size", ".97rem"),
            "--mts-section": spacing.get("section", "96px"),
            "--mts-gap": spacing.get("gap", "28px"),
            "--mts-width": spacing.get("width", "1180px"),
            "--mts-gutter": spacing.get("gutter", "clamp(18px,4.5vw,48px)"),
        }
    )
    for level, power in zip(range(1, 7), (6, 4.6, 3, 1.8, 1, .5)):
        values[f"--mts-h{level}"] = f"{base * ratio ** power:.1f}px"
    body = ";".join(f"{name}:{value}" for name, value in values.items())
    return ":root{" + body + "}"
