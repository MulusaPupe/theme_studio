"""The universal document to native blocks. This is the only place that decides the mapping.

Each element becomes the closest core block. Values the block editor can show in its own
sidebar become native attributes; the rest go into the theme's stylesheet under the element's
class, so the design and every device override survive exactly.

URLs and media are written as tokens, because the same markup is resolved in two ways: to PHP
in a pattern file, or to real ids and addresses when the content plugin imports a page.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from html import escape as esc
from html.parser import HTMLParser
from typing import Any

from ...core.document import Document, Node, find_page, home_page
from ...render.css import BREAKPOINT_QUERIES, column_count, columns_value, declarations
from ...render.html import AMBIENTS, countdown_inner, icon_svg, illustration_markup, progress_inner, sanitize_rich_text
from ...render.placeholders import placeholder_svg
from .blocks import Block, classes

_SAFE_URL = re.compile(r"^(https?:|mailto:|tel:|#)", re.I)
_PALETTE = {"primary", "on_primary", "secondary", "accent", "on_accent", "background", "surface", "text", "muted", "border"}
_PLAIN_VALUE = re.compile(r"^[^$]*$")
_LENGTH = re.compile(r"^-?\d*\.?\d+(px|rem|em|%|vw|vh)?$")
_HIDDEN_WIDTHS = {"content", "narrow", "wide", "full"}
_TONES = {"default", "surface", "inverse", "primary", "accent", "image"}
_TYPOGRAPHY = {
    "font_size": "fontSize", "line_height": "lineHeight", "font_weight": "fontWeight", "letter_spacing": "letterSpacing",
    "text_transform": "textTransform", "font_style": "fontStyle", "text_decoration": "textDecoration",
}
_INLINE_NAME = {
    "font_size": "font-size", "line_height": "line-height", "font_weight": "font-weight", "letter_spacing": "letter-spacing",
    "text_transform": "text-transform", "font_style": "font-style", "text_decoration": "text-decoration",
}
_SIDES = ("top", "right", "bottom", "left")
_IMG_PROPS = {"object_fit", "object_position", "border_radius", "aspect_ratio", "height", "box_shadow", "border", "opacity", "max_height", "min_height"}
_BUTTON_LAYOUT = {"align_self", "justify_self", "margin", "margin_top", "margin_bottom", "margin_left", "margin_right", "margin_block", "margin_inline", "width", "max_width", "min_width", "flex", "grid_column", "grid_row", "order"}
NATIVE_TEXT_TYPES = {"heading", "text"}


def css_slug(name: str) -> str:
    return name.replace("_", "-")


def _hex(value: str) -> str:
    return base64.b16encode(value.encode("utf-8")).decode("ascii").lower()


@dataclass
class Tokens:
    """Stand-ins for what is only known once the site runs. The nonce keeps document text from forging one."""

    nonce: str

    def _make(self, kind: str, value: str) -> str:
        return f"__MTS{self.nonce}_{kind}_{_hex(value)}__"

    def page(self, page_id: str) -> str:
        return self._make("page", page_id)

    def image(self, file: str) -> str:
        return self._make("image", file)

    def image_id(self, file: str) -> str:
        return self._make("imageid", file)

    def theme_file(self, path: str) -> str:
        return self._make("themefile", path)

    def terms(self, slugs: list[str]) -> str:
        return self._make("terms", ",".join(slugs))

    @property
    def pattern(self) -> re.Pattern[str]:
        return re.compile(rf"__MTS{self.nonce}_([a-z]+)_([0-9a-f]*)__")

    @staticmethod
    def decode(value: str) -> str:
        return base64.b16decode(value.upper()).decode("utf-8") if value else ""


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fallbacks: dict[str, int] = field(default_factory=dict)

    def fallback(self, kind: str) -> None:
        self.fallbacks[kind] = self.fallbacks.get(kind, 0) + 1


@dataclass
class Assets:
    """Everything the theme must carry. Only what the design uses is collected."""

    images: set[str] = field(default_factory=set)  # Project media file names.
    placeholders: dict[str, str] = field(default_factory=dict)  # Theme file name -> SVG text.


class Translator:
    def __init__(self, doc: Document, tokens: Tokens, *, in_content: bool = False, report: Report | None = None, assets: Assets | None = None, rules: "Rules | None" = None) -> None:
        self.doc = doc
        self.tokens = tokens
        self.in_content = in_content  # Imported pages get media library ids; theme files use theme URLs.
        self.report = report or Report()
        self.assets = assets or Assets()
        self.rules = rules or Rules()
        self.hide: frozenset[str] = frozenset()
        self.query_count = 0

    # Addresses ---------------------------------------------------------------
    def href(self, target: Any) -> str:
        if isinstance(target, dict) and target.get("page"):
            page = find_page(self.doc, target["page"])
            if page is None or page.get("role"):
                self.report.warnings.append("A link pointed to a page that is not in this site, so it now goes to the homepage.")
                page = home_page(self.doc)
            return self.tokens.page(page["id"])
        text = str(target or "#").strip()
        if _SAFE_URL.match(text):
            return text
        match = re.fullmatch(r"([a-z0-9-]+)\.html", text)
        if match:
            page = next((p for p in self.doc["pages"] if p["slug"] == match.group(1) or (p.get("home") and match.group(1) == "index")), None)
            if page:
                return self.tokens.page(page["id"])
        self.report.warnings.append(f"The link address '{text[:60]}' cannot be used on the website and was changed to #.")
        return "#"

    def media(self, ref: Any) -> tuple[str, str]:
        """The image address, and the file name if it will be in the media library."""
        ref = ref if isinstance(ref, dict) else {"kind": "placeholder"}
        if ref.get("kind") == "asset":
            for asset in self.doc["media"].get("assets", []):
                if asset.get("id") == ref.get("id"):
                    name = str(asset.get("file", ""))
                    self.assets.images.add(name)
                    return (self.tokens.image(name), name) if self.in_content else (self.tokens.theme_file(f"assets/images/{name}"), "")
            self.report.errors.append(f"An image refers to a file that is not in the project ({ref.get('id')}).")
        uri = placeholder_svg(ref, self.doc["tokens"]["colors"], self.doc["media"].get("art", "gradient"))
        from urllib.parse import unquote

        svg = unquote(uri.split(",", 1)[1])
        name = f"placeholder-{_short_hash(svg)}.svg"
        self.assets.placeholders[name] = svg
        return self.tokens.theme_file(f"assets/images/{name}"), ""

    # Styles ------------------------------------------------------------------
    def _native(self, node: Node, kind: str) -> tuple[dict, list[str], list[str], dict]:
        """Splits a node's style: (block attributes, classes, inline CSS, what goes to the stylesheet)."""
        style = dict(node.get("style") or {})
        attrs: dict[str, Any] = {}
        names: list[str] = []
        inline: list[str] = []
        native: dict[str, dict] = {}
        for prop, attr_key, css_name, class_suffix, native_key in (
            ("color", "textColor", "color", "color", "text"),
            ("background", "backgroundColor", "background-color", "background-color", "background"),
        ):
            value = str(style.get(prop, ""))
            token = value[1:] if value.startswith("$") else ""
            if token in _PALETTE:
                attrs[attr_key] = css_slug(token)
                names += [f"has-{css_slug(token)}-{class_suffix}", "has-text-color" if prop == "color" else "has-background"]
                style.pop(prop)
            elif re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                native.setdefault("color", {})[native_key] = value
                names.append("has-text-color" if prop == "color" else "has-background")
                inline.append(f"{css_name}:{value}")
                style.pop(prop)
        if kind in NATIVE_TEXT_TYPES or kind == "group":
            for prop, attr in _TYPOGRAPHY.items():
                value = str(style.get(prop, ""))
                if value and _PLAIN_VALUE.match(value) and value != "inherit":
                    native.setdefault("typography", {})[attr] = value
                    inline.append(f"{_INLINE_NAME[prop]}:{value}")
                    style.pop(prop)
        for family, group in (("padding", "padding"), ("margin", "margin")):
            sides = {side: str(style[f"{family}_{side}"]) for side in _SIDES if f"{family}_{side}" in style}
            usable = {side: value for side, value in sides.items() if _LENGTH.match(value)}
            if usable:
                native.setdefault("spacing", {})[group] = usable
                for side, value in usable.items():
                    inline.append(f"{family}-{side}:{value}")
                    style.pop(f"{family}_{side}")
        if native:
            attrs["style"] = native
        return attrs, names, inline, style

    def _class_for(self, node: Node) -> str:
        return "n-" + re.sub(r"[^a-zA-Z0-9_-]", "", str(node.get("id", "")))

    def _register(self, node: Node, style: dict, *, extra: str = "") -> str:
        cls = self._class_for(node)
        self.rules.add(cls, style, extra, "", node)
        return cls

    # Blocks ------------------------------------------------------------------
    def nodes(self, nodes: list[Node]) -> list[Block]:
        out: list[Block] = []
        for node in nodes:
            out += self.node(node)
        return _merge_buttons(out)

    def node(self, node: Node) -> list[Block]:
        handler = getattr(self, f"_{node.get('type')}", None)
        if handler is None:
            self.report.errors.append(f"The element type '{node.get('type')}' has no translation, so it cannot be exported.")
            return []
        return handler(node)

    def _group(self, node: Node, base: str, *, tag: str = "div", align: str = "", layout: dict | None = None, extra_css: str = "", extra_classes: str = "", inner: list[Block] | None = None, name: str = "core/group", wrapper: str = "wp-block-group") -> Block:
        attrs, names, inline, style = self._native(node, "group")
        cls = self._register(node, style, extra=extra_css)
        props = node.get("props", {})
        tone = props.get("tone")
        tone_class = f"mts-tone-{tone}" if tone in _TONES else ""
        class_name = classes(base, tone_class, extra_classes, cls)
        if name == "core/group":
            if tag != "div":
                attrs["tagName"] = tag
            attrs["layout"] = layout or {"type": "default"}
        if align:
            attrs["align"] = align
        attrs["className"] = class_name
        if props.get("anchor"):
            attrs["anchor"] = str(props["anchor"])
        all_classes = classes(wrapper, f"align{align}" if align else "", class_name, *names)
        anchor = f' id="{esc(str(props["anchor"]), quote=True)}"' if props.get("anchor") else ""
        style_attr = f' style="{esc(";".join(inline), quote=True)}"' if inline else ""
        children = inner if inner is not None else self.nodes(node.get("children", []))
        return Block(name, attrs, f'<{tag}{anchor} class="{all_classes}"{style_attr}>', children, f"</{tag}>")

    def _section(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        background = props.get("background") if isinstance(props.get("background"), dict) else {}
        if isinstance(background.get("media"), dict):
            return [self._cover(node, background)]
        tone = props.get("tone") if props.get("tone") in _TONES else "default"
        extra = "" if props.get("tone") in _TONES else f"mts-tone-{tone}"
        inner = None
        if props.get("ambient") in AMBIENTS:
            ambient = Block("core/html", {}, f'<span class="mts-ambient mts-ambient-{props["ambient"]}" aria-hidden="true"></span>')
            inner = [ambient, *self.nodes(node.get("children", []))]
        return [self._group(node, "mts-section", tag="section", align="full", extra_classes=extra, inner=inner)]

    def _cover(self, node: Node, background: dict) -> Block:
        url, library_file = self.media(background["media"])
        overlay = str(background.get("overlay", ""))
        match = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", overlay)
        color, ratio = "#000000", 0
        if match:
            color = "#{:02x}{:02x}{:02x}".format(*(int(match.group(i)) for i in (1, 2, 3)))
            ratio = round(float(match.group(4)) * 100)
        elif overlay:
            self.report.warnings.append("A section's overlay is not a plain colour, so it was left to the stylesheet.")
        style = dict(node.get("style") or {})
        cls = self._register(node, style)
        class_name = classes("mts-section", "mts-tone-image", cls)
        alt = esc(str(background.get("alt", "")), quote=True)
        attrs: dict[str, Any] = {"url": url, "alt": str(background.get("alt", "")), "dimRatio": ratio, "customOverlayColor": color, "isUserOverlayColor": True, "isDark": True, "tagName": "section", "align": "full", "className": class_name}
        image_class = "wp-block-cover__image-background"
        if library_file:
            token = self.tokens.image_id(library_file)
            attrs["id"] = token
            image_class += f" wp-image-{token}"
        # Gutenberg's save() adds both classes whenever dimRatio is set, 0 included.
        dim_classes = classes("wp-block-cover__background", f"has-background-dim-{10 * round(ratio / 10)}", "has-background-dim")
        before = (
            f'<section class="wp-block-cover alignfull is-dark {class_name}">'
            f'<img class="{image_class}" alt="{alt}" src="{esc(url, quote=True)}" data-object-fit="cover"/>'
            f'<span aria-hidden="true" class="{dim_classes}" style="background-color:{color}"></span>'
            '<div class="wp-block-cover__inner-container">'
        )
        children = self.nodes(node.get("children", []))
        if props_ambient := (node.get("props") or {}).get("ambient"):
            self.report.warnings.append(f"The '{props_ambient}' ambient background is not exported on a section with a photo; the photo is kept.")
        return Block("core/cover", attrs, before, children, "</div></section>")

    def _container(self, node: Node) -> list[Block]:
        style = node.get("style") or {}
        if not node.get("children") and set(style) == {"height"} and _LENGTH.match(str(style["height"])):
            return [self._spacer(node, str(style["height"]))]
        width = node.get("props", {}).get("width")
        cls = f"mts-w-{width}" if width in _HIDDEN_WIDTHS else ""
        return [self._group(node, "mts-container", extra_classes=cls)]

    def _spacer(self, node: Node, height: str) -> Block:
        self.report.fallback("spacer")
        return Block("core/spacer", {"height": height}, f'<div style="height:{esc(height, quote=True)}" aria-hidden="true" class="wp-block-spacer">', [], "</div>")

    def _row(self, node: Node) -> list[Block]:
        return [self._group(node, "mts-row", layout={"type": "flex", "flexWrap": "wrap"})]

    def _columns(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        attrs, names, inline, style = self._native(node, "columns")
        align = {k: style.pop(k) for k in ("align_items",) if k in style}
        extra = ""
        value = columns_value(props.get("columns", 2))
        if value:
            extra = f"grid-template-columns:{value}"
        cls = self._class_for(node)
        self.rules.add(cls, style, extra, "", node)
        self.rules.column_defaults(cls, node)
        if align:
            self.rules.base.append(f"{self.rules.selector(cls)}{{align-items:{align['align_items']}!important}}")  # Core forces this one.
        width = props.get("width")
        width_class = f"mts-w-{width}" if width in _HIDDEN_WIDTHS else ""
        class_name = classes("mts-columns", width_class, cls)
        attrs["className"] = class_name
        children = []
        for child in node.get("children", []):
            children.append(self._column(child))
        style_attr = f' style="{esc(";".join(inline), quote=True)}"' if inline else ""
        return [Block("core/columns", attrs, f'<div class="{classes("wp-block-columns", class_name, *names)}"{style_attr}>', children, "</div>")]

    def _column(self, child: Node) -> Block:
        if child.get("type") == "container" and child.get("children"):
            width = child.get("props", {}).get("width")
            extra = f"mts-w-{width}" if width in _HIDDEN_WIDTHS else ""
            return self._group(child, "mts-container", extra_classes=extra, name="core/column", wrapper="wp-block-column")
        inner = self.node(child)
        return Block("core/column", {"className": "mts-container"}, '<div class="wp-block-column mts-container">', _merge_buttons(inner), "</div>")

    def _footer(self, node: Node) -> list[Block]:
        props = dict(node.get("props", {}))
        tone = props.get("tone") if props.get("tone") in _TONES else ""
        extra = "" if tone else "mts-tone-default"
        return [self._group(node, "mts-footer", extra_classes=extra)]

    def _header(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        layout = props.get("layout", "classic")
        layout = layout if layout in {"classic", "split", "centered", "masthead", "minimal"} else "classic"
        extras = [f"mts-header-{layout}"]
        if props.get("tone") not in _TONES:
            extras.append("mts-tone-default")
        if props.get("sticky"):
            extras.append("mts-header-sticky")
        if props.get("overlay"):
            extras.append("mts-header-overlay")
        if props.get("nav_style") == "caps":
            extras.append("mts-nav-caps")
        inner: list[Block] = []
        if isinstance(props.get("logo"), dict):
            inner.append(Block("core/site-logo", {"width": 44, "className": "mts-wp-logo"}))
        inner.append(Block("core/site-title", {"level": 0, "className": "mts-brand"}))
        inner.append(self._navigation(props))
        cta = props.get("cta")
        if isinstance(cta, dict) and cta.get("label"):
            inner.append(_button_set([_button_block(str(cta["label"]), self.href(cta.get("href")), "mts-wp-btn mts-wp-btn-primary")], "mts-header-cta"))
        holder = Block("core/group", {"className": "mts-header-in", "layout": {"type": "default"}}, '<div class="wp-block-group mts-header-in">', inner, "</div>")
        return [self._group(node, "mts-header", extra_classes=" ".join(extras), inner=[holder])]

    def _navigation(self, props: dict) -> Block:
        overlay = "never" if props.get("mobile_menu") == "inline" else "mobile"
        attrs = {"overlayMenu": overlay, "overlayBackgroundColor": "background", "overlayTextColor": "text", "className": "mts-wp-nav", "layout": {"type": "flex", "setCascadingProperties": True, "justifyContent": "right"}}
        links = []
        for item in self.doc.get("navigation", {}).get("primary", []):
            target = {"page": item["page"]} if item.get("page") else item.get("url")
            links.append(Block("core/navigation-link", {"label": str(item.get("label", "")), "url": self.href(target), "kind": "custom", "isTopLevelLink": True}))
        if not links:
            self.report.warnings.append("The site menu is empty, so the header shows no links.")
        block = Block("core/navigation", attrs, "", links, "")
        return block

    def _heading(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        level = props.get("level", 2)
        level = level if level in (1, 2, 3, 4, 5, 6) else 2
        attrs, names, inline, style = self._native(node, "heading")
        align = style.pop("text_align", None)
        if align in ("left", "center", "right"):
            attrs["textAlign"] = align
            names.append(f"has-text-align-{align}")
        elif align:
            style["text_align"] = align
        cls = self._register(node, style)
        attrs.update(level=level, className=cls)
        style_attr = f' style="{esc(";".join(inline), quote=True)}"' if inline else ""
        return [Block("core/heading", attrs, f'<h{level} class="{classes("wp-block-heading", cls, *names)}"{style_attr}>{esc(str(props.get("text", "")), quote=False)}</h{level}>')]

    def _paragraph_block(self, node: Node, content: str, base: str = "") -> Block:
        attrs, names, inline, style = self._native(node, "text")
        align = style.pop("text_align", None)
        if align in ("left", "center", "right"):
            attrs["align"] = align
            names.append(f"has-text-align-{align}")
        elif align:
            style["text_align"] = align
        cls = self._register(node, style)
        class_name = classes(base, cls)
        attrs["className"] = class_name
        style_attr = f' style="{esc(";".join(inline), quote=True)}"' if inline else ""
        return Block("core/paragraph", attrs, f'<p class="{classes(class_name, *names)}"{style_attr}>{content}</p>')

    def _text(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        return [self._paragraph_block(node, esc(str(props.get("text", "")), quote=False), "mts-muted" if props.get("muted") else "")]

    def _link(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        arrow = " mts-link-arrow" if props.get("arrow") else ""
        href = esc(self.href(props.get("href")), quote=True)
        return [self._paragraph_block(node, f'<a href="{href}">{esc(str(props.get("label", "")), quote=False)}</a>', f"mts-link{arrow}")]

    def _richtext(self, node: Node) -> list[Block]:
        html = sanitize_rich_text(node.get("props", {}).get("html", ""))
        html = re.sub(r'href="([^"]*)"', lambda m: f'href="{esc(self.href(_unescape(m.group(1))), quote=True)}"', html)
        return [self._group(node, "mts-richtext", inner=rich_text_blocks(html))]

    def _image_block(self, ref: Any, alt: str, class_name: str = "", attrs_extra: dict | None = None) -> Block:
        url, library_file = self.media(ref)
        attrs: dict[str, Any] = {"sizeSlug": "full", "linkDestination": "none"}
        image_class = ""
        if library_file:
            token = self.tokens.image_id(library_file)
            attrs["id"] = token
            image_class = f' class="wp-image-{token}"'
        if class_name:
            attrs["className"] = class_name
        attrs.update(attrs_extra or {})
        return Block("core/image", attrs, f'<figure class="{classes("wp-block-image", "size-full", class_name)}"><img src="{esc(url, quote=True)}" alt="{esc(alt, quote=True)}"{image_class}/></figure>')

    def _image(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        media = props.get("media") if isinstance(props.get("media"), dict) else {"kind": "placeholder"}
        style = dict(node.get("style") or {})
        image = {key: style.pop(key) for key in list(style) if key in _IMG_PROPS}
        extra = ""
        if props.get("ratio"):
            extra = f"aspect-ratio:{float(props['ratio']):.4f}"
        cls = self._class_for(node)
        self.rules.add(cls, style, "", "", node)
        self.rules.add(cls, image, extra, " img", None)
        return [self._image_block(media, str(props.get("alt", media.get("label", ""))), classes("mts-image", cls))]

    def _gallery(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        items = [item for item in props.get("items", []) if isinstance(item, dict)]
        count = column_count(props.get("columns", 3)) or 3
        value = columns_value(props.get("columns", 3))
        cls = self._class_for(node)
        self.rules.add(cls, dict(node.get("style") or {}), f"grid-template-columns:{value}" if value else "", "", node)
        self.rules.column_defaults(cls, node)
        class_name = classes("mts-gallery", cls)
        inner = [self._image_block(item, str(item.get("label", ""))) for item in items]
        return [Block("core/gallery", {"columns": count, "linkTo": "none", "sizeSlug": "full", "className": class_name}, f'<figure class="wp-block-gallery has-nested-images columns-{count} is-cropped {class_name}">', inner, "</figure>")]

    def _video(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        url = str(props.get("url", "")).strip()
        cls = self._register(node, dict(node.get("style") or {}))
        if re.search(r"\.(mp4|webm)(\?|$)", url, re.I) and _SAFE_URL.match(url):
            return [Block("core/video", {"className": cls}, f'<figure class="wp-block-video {cls}"><video controls src="{esc(url, quote=True)}"></video></figure>')]
        provider = re.search(r"(youtube|youtu\.be|vimeo)", url, re.I)
        if provider and _SAFE_URL.match(url):
            slug = "vimeo" if "vimeo" in url.lower() else "youtube"
            return [Block("core/embed", {"url": url, "type": "video", "providerNameSlug": slug, "responsive": True, "className": f"wp-embed-aspect-16-9 wp-has-aspect-ratio {cls}"}, f'<figure class="wp-block-embed is-type-video is-provider-{slug} wp-block-embed-{slug} wp-embed-aspect-16-9 wp-has-aspect-ratio {cls}"><div class="wp-block-embed__wrapper">\n{esc(url, quote=False)}\n</div></figure>')]
        self.report.warnings.append(f"Video '{str(props.get('title') or 'untitled')[:40]}' has no playable address, so its poster image is shown instead. Add a video link to fix this.")
        self.report.fallback("video-as-image")
        return [self._image_block(props.get("poster"), str(props.get("title", "")), classes("mts-image", cls))]

    def _icon(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        cls = self._register(node, dict(node.get("style") or {}))
        self.report.fallback("icon-as-html")
        label = f' role="img" aria-label="{esc(str(props["aria_label"]), quote=True)}"' if props.get("aria_label") else ' aria-hidden="true"'
        return [Block("core/html", {}, f'<span class="mts-icon {cls}"{label}>{icon_svg(props.get("name", "star"))}</span>')]

    def _illustration(self, node: Node) -> list[Block]:
        cls = self._register(node, dict(node.get("style") or {}))
        still, svg = illustration_markup(node.get("props", {}))
        return [Block("core/html", {}, f'<div class="mts-illus{still} {cls}">{svg}</div>')]

    def _countdown(self, node: Node) -> list[Block]:
        cls = self._register(node, dict(node.get("style") or {}))
        inner, iso, done = countdown_inner(node.get("props", {}))
        return [Block("core/html", {}, f'<div class="mts-countdown {cls}" data-mts-countdown="{esc(iso, quote=True)}" data-done="{esc(done, quote=True)}" role="timer">{inner}</div>')]

    def _progress(self, node: Node) -> list[Block]:
        cls = self._register(node, dict(node.get("style") or {}))
        inner, kind, aria = progress_inner(node.get("props", {}))
        return [Block("core/html", {}, f'<div class="mts-progress {kind} {cls}" {aria}>{inner}</div>')]

    def _button(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        variant = props.get("variant", "primary")
        variant = variant if variant in ("primary", "secondary", "ghost") else "primary"
        style = dict(node.get("style") or {})
        layout = {key: style.pop(key) for key in list(style) if key in _BUTTON_LAYOUT}
        cls = self._class_for(node)
        self.rules.add(cls, style, "", " .wp-block-button__link", node)
        wrap = ""
        if layout:
            wrap = f"{cls}-w"
            self.rules.add(wrap, layout, "", "", None)
        if props.get("aria_label"):
            self.report.warnings.append(f"Button '{str(props.get('label'))[:30]}': the accessible label cannot be kept in the button block, so its visible text is used.")
        return [_button_set([_button_block(str(props.get("label", "")), self.href(props.get("href")), classes("mts-wp-btn", f"mts-wp-btn-{variant}", cls))], wrap)]

    def _divider(self, node: Node) -> list[Block]:
        cls = self._register(node, dict(node.get("style") or {}))
        class_name = classes("mts-divider", cls)
        return [Block("core/separator", {"className": class_name}, f'<hr class="wp-block-separator has-alpha-channel-opacity {class_name}"/>')]

    def _faq_item(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        cls = self._register(node, dict(node.get("style") or {}))
        class_name = classes("mts-faq", cls)
        attrs: dict[str, Any] = {"className": class_name}
        opened = ""
        if props.get("open"):
            attrs["showContent"] = True
            opened = " open"
        answer = Block("core/paragraph", {"className": "mts-faq-a"}, f'<p class="mts-faq-a">{esc(str(props.get("answer", "")), quote=False)}</p>')
        return [Block("core/details", attrs, f'<details class="wp-block-details {class_name}"{opened}><summary>{esc(str(props.get("question", "")), quote=False)}</summary>', [answer], "</details>")]

    def _contact_form(self, node: Node) -> list[Block]:
        cls = self._register(node, dict(node.get("style") or {}))
        self.report.fallback("form-as-shortcode")
        self.rules.forms[str(node.get("id"))] = {"class": cls, "submit": str(node.get("props", {}).get("submit", "Send message")), "fields": [
            {"label": str(item.get("label", "")), "type": item.get("type", "text") if item.get("type") in ("text", "email", "tel", "date", "textarea") else "text"}
            for item in node.get("props", {}).get("fields", []) if isinstance(item, dict)
        ]}
        identifier = re.sub(r"[^a-zA-Z0-9_-]", "", str(node.get("id")))
        return [Block("core/shortcode", {}, f'[mulusa_form id="{identifier}"]')]

    # Dynamic content ---------------------------------------------------------
    def _query(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        source = props.get("source") or {}
        self.query_count += 1
        is_list = props.get("layout") == "list"
        columns = 1 if is_list else props.get("columns", 3)
        columns = columns if isinstance(columns, int) and 1 <= columns <= 6 else 3
        order_by = {"date": "date", "title": "title", "modified": "modified", "random": "rand"}.get(source.get("order_by", "date"), "date")
        count = source.get("count", 3)
        query: dict[str, Any] = {
            "perPage": count if isinstance(count, int) and 1 <= count <= 24 else 3, "pages": 0, "offset": 0, "postType": "post",
            "order": "asc" if source.get("order") == "asc" else "desc", "orderBy": order_by, "author": "", "search": "", "exclude": [], "sticky": "",
            "inherit": bool(source.get("follow_page")),
        }
        slugs = [str(item) for item in source.get("categories") or []]
        if slugs:
            query["taxQuery"] = {"category": [self.tokens.terms(slugs)]}
        cls = self._class_for(node)
        style = dict(node.get("style") or {})
        self.rules.add(cls, style, "", "", node)
        self.rules.query_tracks(cls, columns)
        side = " mts-query-img-left" if props.get("image_position") == "left" else ""
        class_name = f"mts-query{side} {cls}"
        outer, self.hide = self.hide, frozenset(props.get("hide") or ())
        card = self.nodes(node.get("children", []))
        self.hide = outer
        template = Block("core/post-template", {"layout": {"type": "grid", "columnCount": columns}}, "", card, "")
        inner = [template]
        if props.get("pagination"):
            inner.append(Block("core/query-pagination", {"layout": {"type": "flex", "justifyContent": "space-between"}}, "", [Block("core/query-pagination-previous"), Block("core/query-pagination-numbers"), Block("core/query-pagination-next")], ""))
        empty = str(props.get("empty_text") or "No posts yet.")
        inner.append(Block("core/query-no-results", {}, "", [Block("core/paragraph", {}, f"<p>{esc(empty, quote=False)}</p>")], ""))
        return [Block("core/query", {"queryId": self.query_count, "query": query, "className": class_name}, f'<div class="wp-block-query {class_name}">', inner, "</div>")]

    def _post_field(self, node: Node) -> list[Block]:
        props = node.get("props", {})
        name = props.get("field")
        if name in self.hide:
            return []
        attrs_common = {"className": self._register(node, dict(node.get("style") or {}))}
        if name == "title":
            level = props.get("level", 3)
            attrs = {"level": level if level in (1, 2, 3, 4, 5, 6) else 3, **attrs_common}
            if props.get("link"):
                attrs["isLink"] = True
            return [Block("core/post-title", attrs)]
        if name == "featured_image":
            attrs = dict(attrs_common)
            if props.get("link"):
                attrs["isLink"] = True
            if props.get("ratio"):
                attrs["aspectRatio"] = _ratio_text(float(props["ratio"]))
            return [Block("core/post-featured-image", attrs)]
        if name == "excerpt":
            attrs = {"moreText": "", **attrs_common}
            if isinstance(props.get("words"), int):
                attrs["excerptLength"] = props["words"]
            return [Block("core/post-excerpt", attrs)]
        if name == "date":
            return [Block("core/post-date", attrs_common)]
        if name == "author":
            return [Block("core/post-author-name", attrs_common)]
        if name == "categories":
            return [Block("core/post-terms", {"term": "category", **attrs_common})]
        if name == "tags":
            return [Block("core/post-terms", {"term": "post_tag", **attrs_common})]
        if name == "content":
            return [Block("core/post-content", {"layout": {"type": "default"}, **attrs_common})]
        if name == "read_more":
            return [Block("core/read-more", {"content": str(props.get("label") or "Read more"), **attrs_common})]
        self.report.errors.append(f"Unknown post detail '{name}'.")
        return []


def _short_hash(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _unescape(text: str) -> str:
    from html import unescape

    return unescape(text)


def _ratio_text(value: float) -> str:
    known = {1.0: "1", 1.5: "3/2", 1.3333: "4/3", 1.7778: "16/9", .75: "3/4", .6667: "2/3", .5625: "9/16"}
    for ratio, text in known.items():
        if abs(ratio - value) < .01:
            return text
    return f"{value:.3f}"


def _button_block(label: str, href: str, class_name: str) -> Block:
    return Block("core/button", {"className": class_name}, f'<div class="wp-block-button {class_name}"><a class="wp-block-button__link wp-element-button" href="{esc(href, quote=True)}">{esc(label, quote=False)}</a></div>')


def _button_set(buttons: list[Block], class_name: str = "") -> Block:
    attrs = {"className": class_name} if class_name else {}
    return Block("core/buttons", attrs, f'<div class="{classes("wp-block-buttons", class_name)}">', buttons, "</div>")


def _merge_buttons(blocks: list[Block]) -> list[Block]:
    """Neighbouring plain buttons share one set, as a person using the editor would have them."""
    out: list[Block] = []
    for block in blocks:
        if block.name == "core/buttons" and not block.attrs and out and out[-1].name == "core/buttons" and not out[-1].attrs:
            out[-1].inner += block.inner
        else:
            out.append(block)
    return out


class _Splitter(HTMLParser):
    """Divides sanitised rich text into its top-level elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[tuple[str, str]] = []
        self.depth = 0
        self.current = ""
        self.tag = ""

    def handle_starttag(self, tag, attrs):
        text = self.get_starttag_text() or f"<{tag}>"
        if self.depth == 0 and tag in ("p", "ul", "ol", "h3", "h4", "h5", "blockquote"):
            self._flush()
            self.tag, self.current = tag, ""
            self.depth = 1
            return
        if self.depth:
            self.depth += tag != "br"
        self.current += text

    def handle_endtag(self, tag):
        if tag == "br":
            return
        if self.depth == 1 and tag == self.tag:
            self.parts.append((self.tag, self.current))
            self.tag, self.current, self.depth = "", "", 0
            return
        if self.depth:
            self.depth -= 1
        self.current += f"</{tag}>"

    def handle_data(self, data):
        self.current += data

    def handle_entityref(self, name):
        self.current += f"&{name};"

    def handle_charref(self, name):
        self.current += f"&#{name};"

    def _flush(self):
        if self.current.strip():
            self.parts.append(("p", self.current))
        self.current = ""

    def finish(self):
        self.close()
        if self.current.strip():
            self.parts.append((self.tag or "p", self.current))
        self.current = ""
        return self.parts


def _paragraph(content: str) -> Block:
    return Block("core/paragraph", {}, f"<p>{content}</p>")


def rich_text_blocks(html: str) -> list[Block]:
    parser = _Splitter()
    parser.feed(html)
    blocks: list[Block] = []
    for tag, content in parser.finish():
        if tag == "p":
            blocks.append(_paragraph(content))
        elif tag in ("h3", "h4", "h5"):
            level = int(tag[1])
            blocks.append(Block("core/heading", {"level": level}, f'<h{level} class="wp-block-heading">{content}</h{level}>'))
        elif tag in ("ul", "ol"):
            items = [Block("core/list-item", {}, f"<li>{item}</li>") for item in re.findall(r"<li>(.*?)</li>", content, flags=re.S)]
            attrs = {"ordered": True} if tag == "ol" else {}
            blocks.append(Block("core/list", attrs, f'<{tag} class="wp-block-list">', items, f"</{tag}>"))
        elif tag == "blockquote":
            blocks.append(Block("core/quote", {}, '<blockquote class="wp-block-quote">', [_paragraph(re.sub(r"</?p>", "", content))], "</blockquote>"))
    return blocks


class Rules:
    """The theme's element stylesheet. Selectors are raised above core's, and device overrides above inline styles."""

    def __init__(self) -> None:
        self.base: list[str] = []
        self.responsive: dict[str, list[str]] = {key: [] for key in BREAKPOINT_QUERIES}
        self.forms: dict[str, dict] = {}
        self._seen: set[str] = set()

    @staticmethod
    def selector(cls: str) -> str:
        return f".{cls}.{cls}.{cls}"

    def add(self, cls: str, style: dict, extra: str = "", suffix: str = "", node: Node | None = None) -> None:
        body = ";".join(part for part in (extra, declarations(style)) if part)
        selector = self.selector(cls) + suffix
        if body:
            rule = f"{selector}{{{body}}}"
            if rule not in self._seen:
                self._seen.add(rule)
                self.base.append(rule)
        if node is None:
            return
        for point, rules in self.responsive.items():
            over = (node.get("responsive") or {}).get(point) or {}
            parts: list[str] = []
            if over.get("hidden"):
                parts.append("display:none")
            css = declarations(over.get("style") or {})
            if css:
                parts += css.split(";")
            track = (over.get("props") or {}).get("columns")
            if track is not None and columns_value(track):
                parts.append(f"grid-template-columns:{columns_value(track)}")
            if parts:
                # !important because the block editor stores some values as inline styles.
                rule = f"{self.selector(cls)}{{{';'.join(p + '!important' for p in parts)}}}"
                if rule not in self._seen:
                    self._seen.add(rule)
                    rules.append(rule)

    def column_defaults(self, cls: str, node: Node) -> None:
        over = node.get("responsive") or {}
        count = column_count(node.get("props", {}).get("columns", 2))
        if "columns" not in ((over.get("tablet") or {}).get("props") or {}) and count >= 4:
            self.responsive["tablet"].append(f"{self.selector(cls)}{{grid-template-columns:repeat(2,minmax(0,1fr))!important}}")
        if "columns" not in ((over.get("mobile") or {}).get("props") or {}):
            # A phone also matches the tablet rule, and overrides there are !important, so this must be too.
            self.responsive["mobile"].append(f"{self.selector(cls)}{{grid-template-columns:minmax(0,1fr)!important}}")

    def query_tracks(self, cls: str, columns: int) -> None:
        selector = f"{self.selector(cls)} .wp-block-post-template"
        self.base.append(f"{selector}{{grid-template-columns:repeat({columns},minmax(0,1fr))}}")
        self.responsive["tablet"].append(f"{selector}{{grid-template-columns:repeat({min(columns, 2)},minmax(0,1fr))}}")
        self.responsive["mobile"].append(f"{selector}{{grid-template-columns:minmax(0,1fr)}}")

    def css(self) -> str:
        media = "\n".join(f"@media {BREAKPOINT_QUERIES[key]}{{{''.join(values)}}}" for key, values in self.responsive.items() if values)
        return "".join(self.base) + "\n" + media
