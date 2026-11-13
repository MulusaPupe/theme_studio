"""The global design system: colours, fonts, shape and spacing. Run these through ``History.apply``.

Elements refer to tokens (``$primary``), so changing a token here changes every element using it.
"""
from __future__ import annotations

import copy
from typing import Any

from .document import COLOR_TOKENS, Document, HEX_COLOR
from .errors import StudioError
from .styles import normalize_color, normalize_length

EDITABLE_COLORS = ("primary", "secondary", "accent", "background", "surface", "text", "muted", "border")
SHAPE_TOKENS = {"radius": "Default corners", "button_radius": "Button corners", "card_radius": "Card corners", "input_radius": "Input corners"}
SPACING_TOKENS = {
    "section": "Section spacing", "gap": "Element gap", "width": "Content width",
    "space_s": "Small space", "space_m": "Medium space", "space_l": "Large space",
}
SPACE_DEFAULTS = {"space_s": "12px", "space_m": "24px", "space_l": "48px"}
WHITE, INK = "#ffffff", "#111318"


class DesignError(StudioError):
    pass


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    red, green, blue = (int(color[i: i + 2], 16) for i in (1, 3, 5))
    return .2126 * _channel(red) + .7152 * _channel(green) + .0722 * _channel(blue)


def contrast_ratio(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


def readable_on(background: str) -> str:
    """Whichever of white or near-black reads better on this colour."""
    return WHITE if contrast_ratio(WHITE, background) >= contrast_ratio(INK, background) else INK


def _palette(name: str, primary: str, secondary: str, accent: str, background: str, surface: str, text: str, muted: str, border: str) -> dict:
    return {
        "name": name,
        "colors": {
            "primary": primary, "on_primary": readable_on(primary), "secondary": secondary,
            "accent": accent, "on_accent": readable_on(accent), "background": background,
            "surface": surface, "text": text, "muted": muted, "border": border,
        },
    }


BUILTIN_PALETTES = (
    _palette("Harbour", "#14325c", "#1f6f8b", "#d97a2b", "#ffffff", "#f3f6f9", "#14233b", "#566172", "#d8dee6"),
    _palette("Forest", "#1f4d3a", "#2f6f55", "#c98a2c", "#fbfaf5", "#eef0e6", "#1b2a22", "#57655c", "#d9dccd"),
    _palette("Terracotta", "#a4452c", "#6b3a2a", "#e0a458", "#fdf8f3", "#f5ebe0", "#2c1a14", "#6f5a50", "#e6d8c9"),
    _palette("Graphite", "#22262e", "#454c58", "#ffb703", "#ffffff", "#f2f3f5", "#16181d", "#5a606b", "#dcdfe4"),
    _palette("Orchid", "#5b2a86", "#8e4585", "#e8618c", "#fffbfe", "#f6eff7", "#241530", "#655a70", "#e5dbe9"),
    _palette("Midnight", "#7aa7ff", "#a78bfa", "#ffd166", "#0e1320", "#182033", "#eef1f8", "#a9b2c6", "#2b3550"),
    _palette("Ember", "#ff7849", "#ffb454", "#6ee7b7", "#141110", "#211c1a", "#f6efe9", "#b8ada5", "#3a322e"),
    _palette("Sand & Sea", "#0f766e", "#155e75", "#d9a441", "#fffdf8", "#f4efe3", "#17302d", "#5b6b68", "#e1dac8"),
)


def set_color(doc: Document, name: str, value: Any) -> None:
    if name not in EDITABLE_COLORS:
        raise DesignError(f"'{name}' is not a site colour.")
    color = normalize_color(value)
    if not HEX_COLOR.match(color):
        raise DesignError("A site colour must be a fixed colour, such as #1a2b3c.")
    colors = doc["tokens"]["colors"]
    colors[name] = color
    # Text on these two colours is worked out, so tones stay readable whatever is chosen.
    if name == "primary":
        colors["on_primary"] = readable_on(color)
    elif name == "accent":
        colors["on_accent"] = readable_on(color)


def apply_palette(doc: Document, palette: dict) -> None:
    colors = palette.get("colors") if isinstance(palette, dict) else None
    if not isinstance(colors, dict) or any(not HEX_COLOR.match(str(colors.get(k, ""))) for k in COLOR_TOKENS):
        raise DesignError("That palette is incomplete.")
    doc["tokens"]["colors"].update({k: str(colors[k]).lower() for k in COLOR_TOKENS})


def save_palette(doc: Document, name: str) -> None:
    name = str(name).strip()
    if not name:
        raise DesignError("Give the palette a name.")
    palettes = doc.setdefault("palettes", [])
    entry = {"name": name[:60], "colors": copy.deepcopy(doc["tokens"]["colors"])}
    for index, existing in enumerate(palettes):
        if existing.get("name") == entry["name"]:
            palettes[index] = entry
            return
    palettes.append(entry)


def set_font(doc: Document, role: str, family: Any, known: set[str] | frozenset[str]) -> None:
    if role not in ("heading", "body"):
        raise DesignError(f"'{role}' is not a font role.")
    if family not in known:
        raise DesignError(f"'{family}' is not in the bundled font library.")
    doc["tokens"]["fonts"][role] = family


_TYPE_RANGES = {
    "base": (12, 24, "Base font size"), "ratio": (1.05, 1.7, "Heading scale"),
    "body_line": (1.1, 2.4, "Body line height"), "heading_weight": (100, 900, "Heading weight"),
}


def set_type(doc: Document, key: str, value: Any) -> None:
    if key not in _TYPE_RANGES:
        raise DesignError(f"'{key}' is not a typography setting.")
    low, high, name = _TYPE_RANGES[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise DesignError(f"{name} must be from {low:g} to {high:g}.")
    doc["tokens"]["type"][key] = value


def _token_length(value: Any) -> str:
    text = normalize_length(value, negative=False)
    if text.startswith("$"):
        raise DesignError("A site setting needs a fixed size.")
    return text


def set_shape(doc: Document, key: str, value: Any) -> None:
    if key not in SHAPE_TOKENS:
        raise DesignError(f"'{key}' is not a shape setting.")
    doc["tokens"]["shape"][key] = _token_length(value)


def set_spacing(doc: Document, key: str, value: Any) -> None:
    if key not in SPACING_TOKENS:
        raise DesignError(f"'{key}' is not a spacing setting.")
    doc["tokens"]["spacing"][key] = _token_length(value)
