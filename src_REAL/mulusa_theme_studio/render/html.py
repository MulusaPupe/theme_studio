"""Universal nodes to HTML. Every value from the document is escaped or sanitised."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ..core.document import Document, Node
from ..core.styles import TONES
from .css import BREAKPOINT_QUERIES, column_count, columns_value, declarations
from .placeholders import placeholder_svg

ICON_DIR = Path(__file__).resolve().parents[1] / "resources" / "icons"
_SAFE_URL = re.compile(r"^(https?:|mailto:|tel:|#|[a-zA-Z0-9_./-]+$)", re.I)
_TONES = set(TONES)
_WIDTHS = {"content", "narrow", "wide", "full"}
esc = html.escape


@lru_cache(maxsize=256)
def icon_svg(name: str) -> str:
    safe = re.sub(r"[^a-z0-9-]", "", str(name))
    try:
        svg = (ICON_DIR / f"{safe}.svg").read_text(encoding="utf-8")
    except OSError:
        svg = (ICON_DIR / "square.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r'\s*class="[^"]*"', "", svg)
    svg = re.sub(r'\s*(width|height)="24"', "", svg)
    return re.sub(r"\s+", " ", svg).strip()


class _RichText(HTMLParser):
    """Keeps a short list of harmless tags. Everything else is reduced to its text."""

    ALLOWED = {"p", "strong", "em", "b", "i", "u", "a", "ul", "ol", "li", "br", "h3", "h4", "h5", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag not in self.ALLOWED:
            return
        if tag == "a":
            href = dict(attrs).get("href") or "#"
            self.out.append(f'<a href="{esc(href if _SAFE_URL.match(href) else "#")}">')
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in self.ALLOWED and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(esc(data))


def sanitize_rich_text(source: str) -> str:
    parser = _RichText()
    parser.feed(str(source))
    parser.close()
    return "".join(parser.out)


@dataclass
class RenderContext:
    doc: Document
    editor: bool = False
    current_page: str = ""
    rules: list[str] = field(default_factory=list)
    responsive: dict[str, list[str]] = field(default_factory=lambda: {k: [] for k in BREAKPOINT_QUERIES})
    used_assets: set[str] = field(default_factory=set)

    def page_href(self, page_id: str) -> str:
        for page in self.doc["pages"]:
            if page["id"] == page_id:
                return "index.html" if page.get("home") else f"{page['slug']}.html"
        return "#"

    def href(self, target: Any) -> str:
        if isinstance(target, dict) and target.get("page"):
            return self.page_href(target["page"])
        text = str(target or "#")
        return text if _SAFE_URL.match(text) else "#"

    def media_url(self, ref: dict) -> str:
        if ref.get("kind") == "asset":
            for asset in self.doc["media"].get("assets", []):
                if asset.get("id") == ref.get("id"):
                    name = Path(str(asset.get("file", ""))).name
                    self.used_assets.add(name)
                    return f"assets/media/{name}"
        return placeholder_svg(ref, self.doc["tokens"]["colors"], self.doc["media"].get("art", "gradient"))

    def attrs(self, node: Node, *classes: str) -> str:
        """Class list and editor hook for an element, and registers its CSS."""
        names = [c for c in classes if c]
        cls = f"n-{re.sub(r'[^a-zA-Z0-9_-]', '', str(node.get('id', '')))}"
        written = self._register(node, cls)
        if written:
            names.append(cls)
        out = f' class="{" ".join(names)}"' if names else ""
        if self.editor:
            out += f' data-mts-id="{esc(str(node.get("id", "")), quote=True)}" data-mts-type="{esc(str(node.get("type", "")), quote=True)}"'
        return out

    def _register(self, node: Node, cls: str) -> bool:
        written = False
        base = declarations(node.get("style", {}))
        extra = ""
        props = node.get("props", {})
        if node.get("type") == "columns":
            value = columns_value(props.get("columns", 2))
            if value:
                extra = f"grid-template-columns:{value}"
        if node.get("type") in ("columns", "gallery") and props.get("columns") is not None:
            self._column_defaults(node, cls)
            written = True
        if node.get("type") == "gallery":
            value = columns_value(props.get("columns", 3))
            extra = f"grid-template-columns:{value}" if value else ""
        if props.get("ratio") and node.get("type") in ("image", "video"):
            extra = (extra + ";" if extra else "") + f"aspect-ratio:{float(props['ratio']):.4f}"
        body = ";".join(x for x in (extra, base) if x)
        if body:
            self.rules.append(f".{cls}{{{body}}}")
            written = True
        for point, query_rules in self.responsive.items():
            over = node.get("responsive", {}).get(point) or {}
            parts = []
            if over.get("hidden"):
                parts.append("display:none!important")
            style = declarations(over.get("style", {}))
            if style:
                parts.append(style)
            value = (over.get("props") or {}).get("columns")
            if value is not None:
                track = columns_value(value)
                if track:
                    parts.append(f"grid-template-columns:{track}")
            if parts:
                query_rules.append(f".{cls}{{{';'.join(parts)}}}")
                written = True
        return written

    def _column_defaults(self, node: Node, cls: str) -> None:
        """Columns collapse sensibly unless the design says otherwise for that size."""
        over = node.get("responsive", {})
        count = column_count(node.get("props", {}).get("columns", 2))
        if "columns" not in (over.get("tablet", {}).get("props") or {}) and count >= 4:
            self.responsive["tablet"].append(f".{cls}{{grid-template-columns:repeat(2,minmax(0,1fr))}}")
        if "columns" not in (over.get("mobile", {}).get("props") or {}):
            self.responsive["mobile"].append(f".{cls}{{grid-template-columns:minmax(0,1fr)}}")


def _tone(node: Node) -> str:
    tone = node.get("props", {}).get("tone")
    return f"mts-tone-{tone}" if tone in _TONES else ""


def render_children(node: Node, ctx: RenderContext) -> str:
    return "".join(render_node(child, ctx) for child in node.get("children", []))


def _section(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    tone = _tone(node) or "mts-tone-default"
    background = ""
    bg = props.get("background")
    if isinstance(bg, dict):
        if isinstance(bg.get("media"), dict):
            alt = esc(str(bg.get("alt", "")), quote=True)
            background += f'<img class="mts-bg" src="{esc(ctx.media_url(bg["media"]), quote=True)}" alt="{alt}">'
        overlay = declarations({"background": bg["overlay"]}) if bg.get("overlay") else ""
        if overlay:
            background += f'<span class="mts-bg-overlay" style="{esc(overlay, quote=True)}"></span>'
    anchor = f' id="{esc(str(props["anchor"]), quote=True)}"' if props.get("anchor") else ""
    return f"<section{ctx.attrs(node, 'mts-section', tone)}{anchor}>{background}{render_children(node, ctx)}</section>"


def _container(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    width = props.get("width")
    cls = f"mts-w-{width}" if width in _WIDTHS else ""
    return f"<div{ctx.attrs(node, 'mts-container', cls, _tone(node))}>{render_children(node, ctx)}</div>"


def _columns(node: Node, ctx: RenderContext) -> str:
    width = node.get("props", {}).get("width")
    cls = f"mts-w-{width}" if width in _WIDTHS else ""
    return f"<div{ctx.attrs(node, 'mts-columns', cls)}>{render_children(node, ctx)}</div>"


def _row(node: Node, ctx: RenderContext) -> str:
    return f"<div{ctx.attrs(node, 'mts-row')}>{render_children(node, ctx)}</div>"


def _header(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    layout = props.get("layout", "classic")
    layout = layout if layout in {"classic", "split", "centered", "masthead", "minimal"} else "classic"
    classes = [f"mts-header mts-header-{layout}", _tone(node) or "mts-tone-default"]
    if props.get("sticky"):
        classes.append("mts-header-sticky")
    if props.get("overlay"):
        classes.append("mts-header-overlay")
    if props.get("nav_style") == "caps":
        classes.append("mts-nav-caps")
    items = []
    for item in ctx.doc.get("navigation", {}).get("primary", []):
        target = {"page": item["page"]} if item.get("page") else item.get("url")
        current = ' aria-current="page"' if item.get("page") and item["page"] == ctx.current_page else ""
        items.append(f'<li><a href="{esc(ctx.href(target), quote=True)}"{current}>{esc(str(item.get("label", "")))}</a></li>')
    home = next((p["id"] for p in ctx.doc["pages"] if p.get("home")), "")
    cta = ""
    if isinstance(props.get("cta"), dict) and props["cta"].get("label"):
        cta = (
            f'<a class="mts-btn mts-btn-primary mts-header-cta" href="{esc(ctx.href(props["cta"].get("href")), quote=True)}">'
            f'{esc(str(props["cta"]["label"]))}</a>'
        )
    return (
        f"<header{ctx.attrs(node, *classes)}><div class=\"mts-header-in\">"
        f'<a class="mts-brand" href="{esc(ctx.page_href(home), quote=True)}">{esc(str(props.get("brand", ctx.doc["meta"].get("name", ""))))}</a>'
        '<input class="mts-nav-check" type="checkbox" id="mts-nav" aria-label="Open the menu">'
        '<label class="mts-burger" for="mts-nav" aria-hidden="true"><span></span></label>'
        f'<nav class="mts-nav" aria-label="Main"><ul>{"".join(items)}</ul></nav>{cta}</div></header>'
    )


def _footer(node: Node, ctx: RenderContext) -> str:
    return f"<footer{ctx.attrs(node, 'mts-footer', _tone(node) or 'mts-tone-default')}>{render_children(node, ctx)}</footer>"


def _heading(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    level = props.get("level", 2)
    level = level if level in (1, 2, 3, 4, 5, 6) else 2
    return f"<h{level}{ctx.attrs(node)}>{esc(str(props.get('text', '')))}</h{level}>"


def _text(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    cls = "mts-muted" if props.get("muted") else ""
    return f"<p{ctx.attrs(node, cls)}>{esc(str(props.get('text', '')))}</p>"


def _richtext(node: Node, ctx: RenderContext) -> str:
    return f"<div{ctx.attrs(node, 'mts-richtext')}>{sanitize_rich_text(node.get('props', {}).get('html', ''))}</div>"


def _image(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    media = props.get("media") if isinstance(props.get("media"), dict) else {"kind": "placeholder"}
    alt = esc(str(props.get("alt", media.get("label", ""))), quote=True)
    marker = " data-mts-placeholder" if ctx.editor and media.get("kind") != "asset" else ""
    return f'<img{ctx.attrs(node, "mts-img")}{marker} src="{esc(ctx.media_url(media), quote=True)}" alt="{alt}" loading="lazy">'


def _gallery(node: Node, ctx: RenderContext) -> str:
    items = node.get("props", {}).get("items", [])
    images = "".join(
        f'<img class="mts-img" src="{esc(ctx.media_url(item), quote=True)}" alt="{esc(str(item.get("label", "")), quote=True)}" loading="lazy">'
        for item in items if isinstance(item, dict)
    )
    return f"<div{ctx.attrs(node, 'mts-gallery')}>{images}</div>"


def _video(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    poster = ctx.media_url(props["poster"]) if isinstance(props.get("poster"), dict) else ""
    url = str(props.get("url", ""))
    if re.search(r"\.(mp4|webm)(\?|$)", url, re.I) and _SAFE_URL.match(url):
        return f'<video{ctx.attrs(node, "mts-video")} controls preload="none" poster="{esc(poster, quote=True)}" src="{esc(url, quote=True)}"></video>'
    target = esc(ctx.href(url or "#"), quote=True)
    return (
        f'<a{ctx.attrs(node, "mts-video")} href="{target}" aria-label="{esc(str(props.get("title", "Play video")), quote=True)}">'
        f'<img class="mts-img" style="height:100%" src="{esc(poster, quote=True)}" alt="">'
        '<span class="mts-video-play"><span><svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg></span></span></a>'
    )


def _icon(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    label = f' role="img" aria-label="{esc(str(props["aria_label"]), quote=True)}"' if props.get("aria_label") else ""
    return f"<span{ctx.attrs(node, 'mts-icon')}{label}>{icon_svg(props.get('name', 'star'))}</span>"


def _aria(props: dict) -> str:
    return f' aria-label="{esc(str(props["aria_label"]), quote=True)}"' if props.get("aria_label") else ""


def _button(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    variant = props.get("variant", "primary")
    variant = variant if variant in ("primary", "secondary", "ghost") else "primary"
    return (
        f'<a{ctx.attrs(node, "mts-btn", f"mts-btn-{variant}")} href="{esc(ctx.href(props.get("href")), quote=True)}"{_aria(props)}>'
        f'{esc(str(props.get("label", "")))}</a>'
    )


def _link(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    arrow = icon_svg("arrow-right").replace("<svg", '<svg width="1em" height="1em"') if props.get("arrow") else ""
    return f'<a{ctx.attrs(node, "mts-link")} href="{esc(ctx.href(props.get("href")), quote=True)}"{_aria(props)}>{esc(str(props.get("label", "")))}{arrow}</a>'


def _divider(node: Node, ctx: RenderContext) -> str:
    return f"<hr{ctx.attrs(node, 'mts-divider')}>"


def _faq(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    opened = " open" if props.get("open") else ""
    return (
        f"<details{ctx.attrs(node, 'mts-faq')}{opened}><summary>{esc(str(props.get('question', '')))}</summary>"
        f'<div class="mts-faq-a">{esc(str(props.get("answer", "")))}</div></details>'
    )


def _form(node: Node, ctx: RenderContext) -> str:
    props = node.get("props", {})
    fields = []
    for index, item in enumerate(props.get("fields", [])):
        kind = item.get("type", "text")
        fid = f"f{index}-{re.sub(r'[^a-zA-Z0-9]', '', str(node.get('id', '')))}"
        label = esc(str(item.get("label", "")))
        if kind == "textarea":
            control = f'<textarea id="{fid}" name="{fid}" rows="5"></textarea>'
        else:
            safe_kind = kind if kind in ("text", "email", "tel", "date") else "text"
            control = f'<input id="{fid}" name="{fid}" type="{safe_kind}">'
        fields.append(f'<label class="mts-field" for="{fid}">{label}{control}</label>')
    submit = esc(str(props.get("submit", "Send message")))
    return (
        f'<form{ctx.attrs(node, "mts-form")} action="#" method="post">{"".join(fields)}'
        f'<button class="mts-btn mts-btn-primary" type="submit">{submit}</button></form>'
    )


_RENDERERS = {
    "section": _section, "container": _container, "columns": _columns, "row": _row,
    "header": _header, "footer": _footer, "heading": _heading, "text": _text,
    "richtext": _richtext, "image": _image, "gallery": _gallery, "video": _video,
    "icon": _icon, "button": _button, "link": _link, "divider": _divider,
    "faq_item": _faq, "contact_form": _form,
}


def render_node(node: Node, ctx: RenderContext) -> str:
    renderer = _RENDERERS.get(node.get("type"))
    return renderer(node, ctx) if renderer else ""
