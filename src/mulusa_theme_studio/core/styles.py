"""The style vocabulary: which properties an element may set, and which values are safe.

Everything that reaches a stylesheet from the document passes through here, whether it came
from the property editor, a template or a hand-edited project file. ``$name`` is a design token.
"""
from __future__ import annotations

import re
from typing import Any

from .errors import StudioError

STYLE_PROPERTIES = frozenset(
    """
    color background background_color background_image border border_top border_bottom border_left border_right
    border_radius box_shadow opacity outline
    padding padding_top padding_bottom padding_left padding_right padding_block padding_inline
    margin margin_top margin_bottom margin_left margin_right margin_block margin_inline
    width max_width min_width height min_height max_height aspect_ratio
    font_family font_size font_weight font_style line_height letter_spacing text_transform text_align text_decoration
    display flex flex_direction flex_wrap align_items align_self justify_content justify_self gap row_gap column_gap
    grid_column grid_row align_content place_items order
    position top right bottom left z_index transform overflow object_fit object_position
    backdrop_filter
    """.split()
)
TONES = ("default", "surface", "inverse", "primary", "accent", "image")
UNITS = ("px", "rem", "em", "%", "vw", "vh")
_UNSAFE = re.compile(r"[<>{};\\]|url\(|expression|@import", re.I)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_SHORT_HEX = re.compile(r"^#[0-9a-fA-F]{3}$")
_TOKEN = re.compile(r"^\$[a-zA-Z_][a-zA-Z0-9_-]*$")
_FILTERS = re.compile(r"^(?:(?:blur\(\d{1,2}(?:\.\d+)?px\)|saturate\(\d{1,3}%\)|brightness\((?:0|1)?(?:\.\d+)?\))\s*){1,3}$")
_RGBA = re.compile(r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*(0|1|0?\.\d+)\s*)?\)$")
_LENGTH = re.compile(r"^-?(\d+\.?\d*|\.\d+)(px|rem|em|%|vw|vh|ch|fr)$")
_NUMBER = re.compile(r"^-?(\d+\.?\d*|\.\d+)$")
_FUNCTION = re.compile(r"^(clamp|calc|min|max)\([0-9a-zA-Z.%+*/\s,$_()-]+\)$")
_FONT = re.compile(r"^[A-Za-z0-9 $'\",_-]{1,120}$")
_GRADIENT = re.compile(r"^(linear|radial)-gradient\([0-9a-zA-Z.%#\s,$_()-]+\)$")
_SAFE_URL = re.compile(r"^(https?:|mailto:|tel:|#|[a-zA-Z0-9_./-]+$)", re.I)
BORDER_STYLES = ("none", "solid", "dashed", "dotted", "double")
KEYWORDS = {
    "text_align": ("left", "center", "right", "justify", "start", "end"),
    "text_transform": ("none", "uppercase", "lowercase", "capitalize"),
    "text_decoration": ("none", "underline", "line-through", "overline"),
    "font_style": ("normal", "italic"),
    "object_fit": ("cover", "contain", "fill", "none", "scale-down"),
    "align_self": ("auto", "flex-start", "center", "flex-end", "stretch"),
    "align_items": ("flex-start", "center", "flex-end", "stretch", "baseline", "start", "end"),
    "justify_content": ("flex-start", "center", "flex-end", "space-between", "space-around", "space-evenly", "start", "end"),
}
_COLORS = {"color", "background_color"}
_PAINT = {"background", "background_image"}
_LENGTHS = {
    "font_size", "letter_spacing", "width", "max_width", "min_width", "height", "min_height", "max_height",
    "row_gap", "column_gap", "border_radius",
    "padding_top", "padding_bottom", "padding_left", "padding_right",
    "margin_top", "margin_bottom", "margin_left", "margin_right",
}
_AUTO_ALLOWED = {"width", "max_width", "min_width", "height", "min_height", "max_height", "margin_top", "margin_bottom", "margin_left", "margin_right"}
_LENGTH_LISTS = {"gap", "padding", "padding_block", "padding_inline", "margin", "margin_block", "margin_inline"}
_BORDERS = {"border", "border_top", "border_bottom", "border_left", "border_right", "outline"}


class StyleError(StudioError):
    """A value that cannot be used. The message is written for the person using the app."""


def is_safe_value(value: Any) -> bool:
    return not _UNSAFE.search(str(value))


def is_safe_url(value: Any) -> bool:
    return bool(_SAFE_URL.match(str(value)))


def is_color(value: Any) -> bool:
    text = str(value).strip()
    return bool(_HEX.match(text) or _SHORT_HEX.match(text) or _TOKEN.match(text) or _RGBA.match(text) or text in ("transparent", "currentColor", "inherit"))


def normalize_color(value: Any) -> str:
    text = str(value).strip()
    if text and text[0] != "#" and re.fullmatch(r"[0-9a-fA-F]{6}", text):
        text = f"#{text}"
    if not is_color(text):
        raise StyleError(f"'{text}' is not a colour. Use a value like #1a2b3c, or choose a site colour.")
    if _SHORT_HEX.match(text):
        text = "#" + "".join(c * 2 for c in text[1:])
    return text.lower() if text.startswith("#") else text


def normalize_length(value: Any, *, auto: bool = False, negative: bool = True) -> str:
    """'24' becomes '24px'. Tokens and clamp() are kept; anything else is refused."""
    text = str(value).strip().lower() if not str(value).strip().startswith("$") else str(value).strip()
    if _NUMBER.match(text):
        text = "0" if float(text) == 0 else f"{text}px"
    if text == "inherit" or (auto and text == "auto"):
        return text
    if _TOKEN.match(text) or _FUNCTION.match(text) or text == "0":
        return text
    if _LENGTH.match(text):
        if not negative and text.startswith("-"):
            raise StyleError("That value cannot be negative.")
        return text
    raise StyleError(f"'{value}' is not a size. Try a number such as 24, or 2rem or 50%.")


def split_values(text: str) -> list[str]:
    """Splits on spaces outside brackets, so 'clamp(1px, 2vw, 3px) 0' is two values."""
    parts, depth, current = [], 0, ""
    for char in str(text).strip():
        depth += (char == "(") - (char == ")")
        if char.isspace() and depth == 0:
            if current:
                parts.append(current)
            current = ""
        else:
            current += char
    return parts + [current] if current else parts


def check_style(prop: str, value: Any) -> str:
    """Returns the value to store, or raises StyleError. An element can never hold an unsafe style."""
    if prop not in STYLE_PROPERTIES:
        raise StyleError(f"'{prop}' is not a style this editor can set.")
    if isinstance(value, bool) or value is None:
        raise StyleError(f"That is not a valid value for {prop.replace('_', ' ')}.")
    text = str(value).strip()
    if not text:
        raise StyleError(f"{prop.replace('_', ' ').capitalize()} cannot be empty.")
    if not is_safe_value(text):
        raise StyleError(f"That value contains characters that are not allowed in {prop.replace('_', ' ')}.")
    if prop in _COLORS:
        return normalize_color(text)
    if prop in _PAINT:
        if _GRADIENT.match(text) or text == "none":
            return text
        return normalize_color(text)
    if prop in KEYWORDS:
        if text not in KEYWORDS[prop]:
            raise StyleError(f"'{text}' is not a valid choice for {prop.replace('_', ' ')}.")
        return text
    if prop in _LENGTHS:
        return normalize_length(text, auto=prop in _AUTO_ALLOWED, negative=prop not in ("border_radius", "row_gap", "column_gap", "font_size", "width", "height", "max_width", "min_width", "min_height", "max_height", "padding_top", "padding_bottom", "padding_left", "padding_right"))
    if prop in _LENGTH_LISTS:
        parts = split_values(text)
        if not 1 <= len(parts) <= 4:
            raise StyleError(f"'{text}' is not a valid value for {prop.replace('_', ' ')}.")
        return " ".join(normalize_length(part, auto=True) for part in parts)
    if prop == "opacity":
        return _number(text, 0, 1, "Opacity")
    if prop == "font_weight":
        if text.startswith("$") or text == "inherit":
            return text
        return _number(text, 1, 1000, "Font weight")
    if prop == "line_height":
        if _NUMBER.match(text):
            return _number(text, .5, 5, "Line height")
        return normalize_length(text, negative=False)
    if prop == "font_family":
        if not _FONT.match(text):
            raise StyleError("That is not a font name.")
        return text
    if prop == "backdrop_filter":
        if text != "none" and not _FILTERS.match(text):
            raise StyleError("A glass effect is a blur such as blur(14px), optionally with saturate(140%).")
        return text
    if prop in _BORDERS:
        parts = split_values(text)
        if text != "none" and not (len(parts) == 3 and parts[1] in BORDER_STYLES and is_color(parts[2])):
            raise StyleError("A border needs a width, a style and a colour.")
        return text
    return text  # Layout properties the editor does not expose. is_safe_value has already checked them.


def _number(text: str, low: float, high: float, name: str) -> str:
    if not _NUMBER.match(text) or not low <= float(text) <= high:
        raise StyleError(f"{name} must be a number from {low:g} to {high:g}.")
    return text
