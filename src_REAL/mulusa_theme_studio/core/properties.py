"""Changes to one element's properties and styles. Run these only through ``History.apply``.

Every value is checked here, so nothing unsafe or malformed can reach the document no matter
which part of the interface asked for it.
"""
from __future__ import annotations

from typing import Any

from .document import BREAKPOINTS, Document, Node, find_node
from .errors import StudioError
from .styles import StyleError, TONES, check_style, is_safe_url, normalize_color, split_values

WIDTHS = ("content", "narrow", "wide", "full")
VARIANTS = ("primary", "secondary", "ghost")
RATIOS = {"original": None, "1:1": 1.0, "4:3": 4 / 3, "3:2": 1.5, "16:9": 16 / 9, "3:4": .75, "4:5": .8}
SHADOWS = {
    "none": "none",
    "soft": "0 2px 8px rgba(0,0,0,.08)",
    "medium": "0 8px 24px rgba(0,0,0,.14)",
    "strong": "0 18px 48px rgba(0,0,0,.24)",
}
_SIDES = ("top", "right", "bottom", "left")


class PropertyError(StudioError):
    pass


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise PropertyError("That needs to be text.")
    if len(value) > 20_000:
        raise PropertyError("That text is too long.")
    return value


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise PropertyError("That needs to be on or off.")
    return value


def _choice(options: tuple) -> Any:
    def check(value: Any) -> Any:
        if value not in options:
            raise PropertyError(f"'{value}' is not one of the available choices.")
        return value
    return check


def _level(value: Any) -> int:
    if isinstance(value, bool) or value not in (1, 2, 3, 4, 5, 6):
        raise PropertyError("A heading level must be from 1 to 6.")
    return value


def _ratio(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not .1 <= value <= 10:
        raise PropertyError("That aspect ratio is not valid.")
    return float(value)


def _href(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"page"} and isinstance(value["page"], str) and value["page"]:
            return value
        raise PropertyError("That link destination is not valid.")
    text = _text(value).strip()
    if not is_safe_url(text):
        raise PropertyError(f"'{text}' is not a link this editor can use. Start it with https://, mailto: or tel:.")
    return text


def _columns(value: Any) -> Any:
    if isinstance(value, bool):
        raise PropertyError("That is not a column layout.")
    if isinstance(value, int) and 1 <= value <= 12:
        return value
    if isinstance(value, str) and value.strip() and all(p.endswith("fr") for p in split_values(value)):
        return value.strip()
    raise PropertyError("Columns must be a number from 1 to 12.")


def _fields(value: Any) -> list:
    if not isinstance(value, list) or not all(isinstance(f, dict) and isinstance(f.get("label"), str) for f in value):
        raise PropertyError("The form fields are not valid.")
    return value


def _cta(value: Any) -> dict:
    if not isinstance(value, dict):
        raise PropertyError("That call to action is not valid.")
    return {"label": _text(value.get("label", "")), "href": _href(value.get("href", "#"))}


_COMMON = {"aria_label": _text}
PROP_RULES: dict[str, dict[str, Any]] = {
    "heading": {"text": _text, "level": _level},
    "text": {"text": _text, "muted": _flag},
    "richtext": {"html": _text},
    "image": {"alt": _text, "ratio": _ratio},
    "button": {"label": _text, "href": _href, "variant": _choice(VARIANTS), **_COMMON},
    "link": {"label": _text, "href": _href, "arrow": _flag, **_COMMON},
    "icon": {"name": _text, **_COMMON},
    "section": {"tone": _choice(TONES), "anchor": _text},
    "container": {"width": _choice(WIDTHS), "tone": _choice(TONES)},
    "columns": {"columns": _columns, "width": _choice(WIDTHS)},
    "gallery": {"columns": _columns},
    "video": {"url": _href, "title": _text, "ratio": _ratio},
    "faq_item": {"question": _text, "answer": _text, "open": _flag},
    "contact_form": {"submit": _text, "fields": _fields},
    "header": {"brand": _text, "tone": _choice(TONES), "cta": _cta, "sticky": _flag},
    "footer": {"tone": _choice(TONES)},
}


def _node(doc: Document, node_id: str) -> Node:
    node = find_node(doc, node_id)
    if node is None:
        raise PropertyError("That element no longer exists.")
    return node


def set_prop(doc: Document, node_id: str, key: str, value: Any) -> None:
    """Sets a content property. ``None`` removes an optional one."""
    node = _node(doc, node_id)
    rules = PROP_RULES.get(node.get("type"), {})
    if key not in rules:
        raise PropertyError(f"A {node.get('type')} has no property '{key}'.")
    props = node.setdefault("props", {})
    if value is None:
        props.pop(key, None)
        return
    checked = rules[key](value)
    if node["type"] == "section" and key == "tone" and checked != "image" and _has_photo(node):
        raise PropertyError("This section has a background image, so it keeps the image tone to stay readable.")
    props[key] = checked


def _has_photo(section: Node) -> bool:
    background = section.get("props", {}).get("background")
    return isinstance(background, dict) and isinstance(background.get("media"), dict)


def _style_target(node: Node, scope: str) -> dict:
    """Where a style lives: the base style, or one device's override. Others stay untouched."""
    if not scope:
        return node.setdefault("style", {})
    if scope not in BREAKPOINTS:
        raise PropertyError(f"'{scope}' is not a device.")
    return node.setdefault("responsive", {}).setdefault(scope, {}).setdefault("style", {})


def _tidy_override(node: Node, scope: str) -> None:
    if not scope:
        return
    responsive = node.get("responsive", {})
    entry = responsive.get(scope)
    if entry is not None:
        if not entry.get("style"):
            entry.pop("style", None)
        if not entry:
            responsive.pop(scope)
    if not responsive:
        node.pop("responsive", None)


def set_style(doc: Document, node_id: str, prop: str, value: Any, scope: str = "") -> None:
    """Sets or, with ``None``, clears one style, on all devices or as one device's override."""
    node = _node(doc, node_id)
    target = _style_target(node, scope)
    if value is None or value == "":
        target.pop(prop, None)
    else:
        checked = check_style(prop, value)
        # Move it to the end: a later longhand must beat an earlier shorthand.
        target.pop(prop, None)
        target[prop] = checked
    _tidy_override(node, scope)


def _expand(style: dict, family: str) -> None:
    """Replaces padding, padding_block and padding_inline with four sides, keeping how it looks."""
    sides: dict[str, str] = {}
    if family in style:
        parts = split_values(style.pop(family))
        count = len(parts)
        top = parts[0]
        right = parts[1] if count > 1 else top
        bottom = parts[2] if count > 2 else top
        left = parts[3] if count > 3 else right
        sides = dict(zip(_SIDES, (top, right, bottom, left)))
    for suffix, names in (("block", ("top", "bottom")), ("inline", ("left", "right"))):
        key = f"{family}_{suffix}"
        if key in style:
            parts = split_values(style.pop(key))
            sides[names[0]] = parts[0]
            sides[names[1]] = parts[1] if len(parts) > 1 else parts[0]
    for side, value in sides.items():
        style.setdefault(f"{family}_{side}", value)


def box_values(style: dict, family: str) -> dict[str, str]:
    """The four sides as they currently stand, reading shorthands without changing anything."""
    copy = dict(style)
    _expand(copy, family)
    return {side: str(copy.get(f"{family}_{side}", "")) for side in _SIDES}


def set_box_side(doc: Document, node_id: str, family: str, side: str, value: Any, scope: str = "") -> None:
    """One side of margin or padding. The other sides keep the values they showed before."""
    if family not in ("margin", "padding") or side not in _SIDES:
        raise PropertyError("That is not a side of an element.")
    node = _node(doc, node_id)
    target = _style_target(node, scope)
    _expand(target, family)
    _tidy_override(node, scope)
    set_style(doc, node_id, f"{family}_{side}", value, scope)


def clear_overrides(doc: Document, node_id: str, scope: str) -> None:
    node = _node(doc, node_id)
    if scope not in BREAKPOINTS:
        raise PropertyError(f"'{scope}' is not a device.")
    entry = node.get("responsive", {}).get(scope)
    if entry:
        entry.pop("style", None)
    _tidy_override(node, scope)


def compose_border(width: Any, style: str, color: str) -> str:
    return f"{width} {style} {color}"


def parse_border(value: Any) -> tuple[str, str, str]:
    parts = split_values(str(value or ""))
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return "", "none", ""


def set_background_overlay(doc: Document, node_id: str, color: str, strength: float) -> None:
    """A colour wash over a section's background image. Strength 0 removes it."""
    node = _node(doc, node_id)
    if node.get("type") != "section":
        raise PropertyError("Only a section has a background overlay.")
    background = node.setdefault("props", {}).setdefault("background", {})
    if not 0 <= strength <= 1:
        raise PropertyError("Overlay strength must be from 0 to 100%.")
    if strength == 0:
        background.pop("overlay", None)
    else:
        hex_color = normalize_color(color)
        if not hex_color.startswith("#"):
            raise StyleError("An overlay needs a fixed colour.")
        red, green, blue = (int(hex_color[i: i + 2], 16) for i in (1, 3, 5))
        background["overlay"] = f"rgba({red},{green},{blue},{strength:.2f})"
    if not background:
        node["props"].pop("background")
