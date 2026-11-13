"""HTML and CSS website packages -> universal document.

The page is parsed with the standard library's HTML parser; nothing is rendered or run.
Scripts, inline event handlers and ``javascript:`` links are removed and reported. Each
top-level block of the page body becomes a section; headings, paragraphs, images, links,
buttons, lists, video and forms become the editor's own elements; supported CSS becomes
node styles, with width media queries as tablet and mobile overrides.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from html import escape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from ..core.styles import is_safe_url
from . import css as csslib
from .convert import Report, add_page, blank_document, clean_style, finish, guess_role, node, section_of

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP = {"script", "noscript", "template", "style", "head", "title", "meta", "link", "object", "embed", "canvas", "map"}
INLINE = {"a", "abbr", "b", "strong", "i", "em", "span", "small", "mark", "sub", "sup", "code", "br", "u", "s", "time", "cite", "q", "label", "kbd"}
BLOCKY = {"div", "section", "article", "aside", "main", "header", "footer", "nav", "figure", "ul", "ol", "dl", "table", "form",
          "h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "pre", "address", "hr", "img", "video", "iframe", "picture", "button"}
BUTTON_HINTS = re.compile(r"\b(btn|button|cta|wp-block-button__link)\b", re.I)
GRID_HINTS = re.compile(r"\b(row|grid|columns|cols|col-wrap|cards|features|d-flex|flex|wp-block-columns)\b", re.I)
VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com")

MediaResolver = Callable[[str, str], "dict | None"]   # (src, alt) -> media ref, or None when it cannot be brought in


class Element:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict, parent: "Element | None") -> None:
        self.tag, self.attrs, self.children, self.parent = tag, attrs, [], parent

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def text(self) -> str:
        parts = []
        for child in self.children:
            parts.append(child if isinstance(child, str) else ("\n" if child.tag == "br" else child.text()))
        return " ".join("".join(parts).split())

    def elements(self) -> list["Element"]:
        return [c for c in self.children if isinstance(c, Element)]

    def find(self, tag: str) -> "Element | None":
        for child in self.elements():
            if child.tag == tag:
                return child
            hit = child.find(tag)
            if hit:
                return hit
        return None

    def find_all(self, tag: str) -> list["Element"]:
        out = []
        for child in self.elements():
            if child.tag == tag:
                out.append(child)
            out += child.find_all(tag)
        return out

    def inner_html(self) -> str:
        out = []
        for child in self.children:
            if isinstance(child, str):
                out.append(escape(child, quote=False))
            elif child.tag in SKIP:
                continue
            else:
                attrs = ""
                if child.tag == "a" and is_safe_url(child.attrs.get("href", "")) and not child.attrs.get("href", "").lower().startswith("javascript"):
                    attrs = f' href="{escape(child.attrs["href"])}"'
                out.append(f"<{child.tag}{attrs}>" if child.tag in VOID else f"<{child.tag}{attrs}>{child.inner_html()}</{child.tag}>")
        return "".join(out)


class _Parser(HTMLParser):
    def __init__(self, report: Report) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#root", {}, None)
        self.cur = self.root
        self.report = report
        self.styles: list[str] = []
        self.links: list[str] = []
        self.title = ""
        self._in: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        for key in list(a):
            if key.startswith("on"):
                self.report.lost("Inline event handlers (onclick and similar) removed")
                del a[key]
        if tag == "link" and "stylesheet" in a.get("rel", "").lower() and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self.report.lost("JavaScript removed (never run on import)")
        if tag in ("iframe",) and not any(h in a.get("src", "") for h in VIDEO_HOSTS):
            self.report.lost("Embedded frames (iframe) other than YouTube or Vimeo video")
        if tag == "svg":
            self.report.lost("Inline SVG drawings")
        if tag == "canvas":
            self.report.lost("Canvas drawings")
        el = Element(tag, a, self.cur)
        self.cur.children.append(el)
        if tag not in VOID:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.cur.tag == tag:
            self.cur = self.cur.parent or self.root

    def handle_endtag(self, tag):
        el = self.cur
        while el is not None and el.tag != tag:
            el = el.parent
        if el is not None and el.parent is not None:
            self.cur = el.parent

    def handle_data(self, data):
        if self.cur.tag == "style":
            self.styles.append(data)
        elif self.cur.tag == "title":
            self.title += data
        elif self.cur.tag not in ("script", "noscript", "template"):
            if data.strip() or (self.cur.children and isinstance(self.cur.children[-1], Element)):
                self.cur.children.append(data)


def parse_html(text: str, report: Report) -> _Parser:
    parser = _Parser(report)
    parser.feed(text)
    parser.close()
    return parser


def _strip_php(text: str, report: Report) -> str:
    if "<?" in text:
        report.lost("PHP code removed (never run on import)")
        text = re.sub(r"<\?php.*?(\?>|$)", "", text, flags=re.S)
    return text


class HtmlConverter:
    def __init__(self, report: Report, sheet: csslib.Stylesheet, resolve_media: MediaResolver, page_slugs: dict[str, str]) -> None:
        self.report = report
        self.sheet = sheet
        self.resolve_media = resolve_media
        self.page_slugs = page_slugs        # "about.html" -> "about"
        self.h1_seen = False

    # Styles -------------------------------------------------------------------
    def styles_for(self, el: Element) -> tuple[dict, dict]:
        computed = self.sheet.computed(el)
        inline = csslib.parse_declarations(el.attrs.get("style", ""))
        base = {**computed.get("", {}), **computed.get("desktop", {}), **{k: self.sheet.resolve(v) for k, v in inline.items()}}
        responsive = {}
        for bp in ("tablet", "mobile"):
            over = dict(computed.get(bp, {}))
            if bp == "mobile":
                over.update({k: v for k, v in computed.get("", {}).items() if k in computed.get("desktop", {})})
            if over:
                responsive[bp] = over
        return base, responsive

    def apply_style(self, el: Element, target: dict, skip: tuple[str, ...] = ()) -> dict:
        base, responsive = self.styles_for(el)
        raw = {k: v for k, v in base.items() if k not in skip and not k.startswith(("transition", "animation", "cursor"))}
        if "background" in raw and "url(" in raw["background"]:
            raw.pop("background")
        if "background-image" in raw and "url(" in raw["background-image"]:
            raw.pop("background-image")
        target["style"] = {**target.get("style", {}), **clean_style(raw, self.report)}
        for bp, over in responsive.items():
            cleaned = clean_style({k: v for k, v in over.items() if "url(" not in v}, self.report)
            if cleaned:
                target.setdefault("responsive", {}).setdefault(bp, {})["style"] = cleaned
        return base

    def background_image(self, el: Element) -> str:
        base, _ = self.styles_for(el)
        for key in ("background-image", "background"):
            m = re.search(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", base.get(key, ""))
            if m:
                return m.group(1)
        return ""

    # Links --------------------------------------------------------------------
    def href(self, raw: str):
        raw = (raw or "").strip()
        if not raw or raw.lower().startswith(("javascript:", "data:", "vbscript:")):
            if raw:
                self.report.lost("javascript: links removed")
            return "#"
        path = raw.split("#")[0].split("?")[0]
        name = PurePosixPath(path).name.lower()
        if name in self.page_slugs and not raw.startswith(("http:", "https:")):
            return {"page": self.page_slugs[name]}
        return raw if is_safe_url(raw) else "#"

    # Content ------------------------------------------------------------------
    def is_button(self, el: Element) -> bool:
        return el.tag == "button" or (el.tag == "a" and (BUTTON_HINTS.search(el.attrs.get("class", "")) or el.attrs.get("role") == "button"))

    def has_block_children(self, el: Element) -> bool:
        return any(c.tag in BLOCKY for c in el.elements())

    def convert_children(self, el: Element) -> list[dict]:
        out: list[dict] = []
        inline_run: list = []

        def flush():
            if not inline_run:
                return
            holder = Element("p", {}, el)
            holder.children = list(inline_run)
            inline_run.clear()
            if holder.text():
                out.extend(self.convert(holder))

        for child in el.children:
            if isinstance(child, str) or child.tag in INLINE and not self.is_button(child):
                inline_run.append(child)
                continue
            flush()
            out.extend(self.convert(child))
        flush()
        return out

    def convert(self, el: Element) -> list[dict]:
        tag = el.tag
        if tag in SKIP or tag in ("svg", "canvas", "iframe") and not (tag == "iframe" and any(h in el.attrs.get("src", "") for h in VIDEO_HOSTS)):
            return []
        if el.attrs.get("hidden") is not None and "hidden" in el.attrs or el.attrs.get("aria-hidden") == "true" and not el.text():
            return []
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            if level == 1 and self.h1_seen:
                level = 2
            self.h1_seen = self.h1_seen or level == 1
            text = el.text()
            if not text:
                return []
            n = node("heading", {"text": text, "level": level})
            self.apply_style(el, n)
            self.report.converted += 1
            return [n]
        if tag in ("p", "blockquote", "address", "figcaption", "pre", "label", "span", "small", "dd", "dt"):
            text = el.text()
            if not text:
                return [i for c in el.elements() if c.tag == "img" for i in self.convert(c)]
            imgs = [i for c in el.elements() if c.tag == "img" for i in self.convert(c)]
            buttons = [c for c in el.elements() if self.is_button(c)]
            if buttons and len(buttons) == len(el.elements()):
                return [b for c in buttons for b in self.convert(c)]
            rich = any(isinstance(c, Element) and c.tag in ("a", "strong", "b", "em", "i", "br", "code") for c in el.children)
            n = node("richtext", {"html": f"<p>{el.inner_html().strip()}</p>"}) if rich else node("text", {"text": text})
            self.apply_style(el, n)
            self.report.converted += 1
            return imgs + [n]
        if tag in ("ul", "ol", "dl"):
            if tag == "ul" and el.find("a") and len(el.find_all("li")) and all(li.find("a") for li in el.find_all("li")) and len(el.text()) < 160:
                links = [self._link(a) for a in el.find_all("a")]
                row = node("row", {}, {"gap": "18px", "flex_wrap": "wrap"}, [l for l in links if l])
                return [row] if row["children"] else []
            n = node("richtext", {"html": f"<{tag}>{el.inner_html()}</{tag}>"})
            self.report.converted += 1
            return [n]
        if tag == "table":
            self.report.lost("Tables (kept as text)")
            return [node("text", {"text": el.text()})] if el.text() else []
        if tag == "hr":
            return [node("divider")]
        if tag in ("img", "picture"):
            img = el if tag == "img" else el.find("img")
            if img is None:
                return []
            src = img.attrs.get("src") or img.attrs.get("data-src") or (img.attrs.get("srcset", "").split(" ")[0])
            alt = img.attrs.get("alt", "")
            ref = self.resolve_media(src, alt) if src else None
            if ref is None:
                return []
            n = node("image", {"media": ref, "alt": alt})
            self.apply_style(img, n, skip=("width", "height"))
            self.report.converted += 1
            return [n]
        if tag in ("video", "iframe"):
            src = el.attrs.get("src") or (el.find("source").attrs.get("src") if el.find("source") else "")
            if src.startswith("//"):
                src = "https:" + src
            if not src.startswith("https://"):
                self.report.lost("Local video files (add the video again in the editor)")
                return []
            props = {"url": src, "title": el.attrs.get("title", "Video"), "ratio": 1.78}
            poster = el.attrs.get("poster")
            if poster:
                ref = self.resolve_media(poster, "Video poster")
                if ref:
                    props["poster"] = ref
            self.report.converted += 1
            return [node("video", props)]
        if tag == "form":
            self.report.note("A form was converted to the editor's contact form; its own fields and action were not kept.")
            self.report.converted += 1
            return [node("contact_form", {})]
        if tag in ("button", "a") and self.is_button(el):
            label = el.text()
            if not label:
                return []
            classes = el.attrs.get("class", "")
            variant = "secondary" if re.search(r"outline|secondary|ghost|light", classes) else "primary"
            n = node("button", {"label": label[:80], "href": self.href(el.attrs.get("href", "")), "variant": variant})
            self.report.converted += 1
            return [n]
        if tag == "a":
            if el.find("img") and not el.text():
                return self.convert(el.find("img"))
            if self.has_block_children(el):
                return self.convert_children(el)
            link = self._link(el)
            return [link] if link else []
        if tag in ("input", "select", "textarea"):
            return []
        # Layout: div, section, article, figure, nav, aside, main, li ...
        children = self.convert_children(el)
        if not children:
            return []
        if len(children) == 1 and not self.styles_for(el)[0] and not el.attrs.get("style"):
            return children
        base, _ = self.styles_for(el)
        display = base.get("display", "")
        direction = base.get("flex-direction", "row")
        block_kids = [c for c in el.elements() if c.tag not in INLINE or self.is_button(c)]
        gridish = display in ("grid", "flex", "inline-flex") and not direction.startswith("column") or GRID_HINTS.search(el.attrs.get("class", ""))
        if gridish and len(block_kids) >= 2 and len(children) >= 2 and all(c["type"] in ("container", "image", "button", "link") for c in children):
            if all(c["type"] in ("button", "link") for c in children):
                row = node("row", {}, {"gap": "12px", "flex_wrap": "wrap"}, children)
                return [row]
            count = min(len(children), 4)
            columns = node("columns", {"columns": count}, {}, [c if c["type"] == "container" else node("container", {}, {}, [c]) for c in children])
            columns["responsive"] = {"tablet": {"props": {"columns": min(count, 2)}}, "mobile": {"props": {"columns": 1}}}
            self.apply_style(el, columns, skip=("display", "grid-template-columns", "flex-direction", "flex-wrap"))
            return [columns]
        box = node("container", {}, {}, [c if c["type"] not in ("section",) else c for c in children])
        self.apply_style(el, box, skip=("display",))
        return [box]

    def _link(self, el: Element) -> dict | None:
        label = el.text()
        if not label:
            return None
        self.report.converted += 1
        return node("link", {"label": label[:120], "href": self.href(el.attrs.get("href", ""))})

    # Page structure -----------------------------------------------------------
    def sections(self, body: Element) -> list[dict]:
        main = body.find("main") or body
        blocks = [c for c in main.elements() if c.tag not in ("header", "footer", "nav") or main is not body and c.tag != "nav"]
        if main is body:
            blocks = [c for c in body.elements() if c.tag not in ("header", "footer", "nav", "script", "noscript", "style")]
        # A single wrapper div around everything is unwrapped.
        while len(blocks) == 1 and blocks[0].tag in ("div", "main") and len(blocks[0].elements()) > 1:
            blocks = [c for c in blocks[0].elements() if c.tag not in ("header", "footer", "nav")]
        out = []
        for block in blocks:
            nodes = self.convert(block)
            if not nodes:
                continue
            hint = f"{block.attrs.get('id', '')} {block.attrs.get('class', '')}"
            role = "hero" if not out and (block.find("h1") or block.tag == "header") else guess_role(hint)
            sec = section_of(nodes, role)
            if nodes and len(nodes) == 1 and nodes[0]["type"] == "container":
                sec["children"][0]["children"] = nodes[0]["children"]   # its style is the block's, applied to the section below
            self.apply_style(block, sec, skip=("display", "max-width", "width", "margin", "margin-left", "margin-right"))
            bg = self.background_image(block)
            if bg:
                ref = self.resolve_media(bg, "Background")
                if ref:
                    sec["props"]["background"] = {"media": ref, "overlay": "rgba(0,0,0,0.45)"}
                    sec["props"]["tone"] = "image"
            out.append(sec)
        return out


def header_parts(body: Element, conv: HtmlConverter) -> tuple[str, list[dict]]:
    """The brand and navigation found in the page's header or nav."""
    header = body.find("header") or body.find("nav")
    if header is None:
        return "", []
    brand = ""
    for cand in header.find_all("a")[:3] + [header.find("h1"), header.find("strong")]:
        if cand is None:
            continue
        cls = cand.attrs.get("class", "")
        if re.search(r"logo|brand|site-title|navbar-brand", cls) or cand.tag in ("h1", "strong"):
            brand = cand.text() or (cand.find("img").attrs.get("alt", "") if cand.find("img") else "")
            if brand:
                break
    nav = header.find("nav") or header
    items = []
    for a in nav.find_all("a"):
        label = a.text()
        if not label or label == brand or conv.is_button(a) or len(items) >= 8:
            continue
        target = conv.href(a.attrs.get("href", ""))
        items.append({"label": label[:40], **({"page": target["page"]} if isinstance(target, dict) else {"url": target if isinstance(target, str) and target != "#" else "#"})})
    return brand, items


def convert_site(pages: list[tuple[str, str]], stylesheets: list[str], resolve_media: MediaResolver, name: str, report: Report,
                 assets: list | None = None) -> dict:
    """``pages``: [(file name, html text)], the first being the home page. Returns a document."""
    sheet = csslib.Stylesheet()
    for text in stylesheets:
        csslib.parse(text, report, sheet=sheet)
    slugs = {}
    for i, (filename, _) in enumerate(pages):
        stem = PurePosixPath(filename).stem.lower()
        slugs[PurePosixPath(filename).name.lower()] = "home" if i == 0 else re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or f"page-{i}"
    doc = blank_document(name)
    first_title = ""
    for i, (filename, text) in enumerate(pages):
        parsed = parse_html(_strip_php(text, report), report)
        for chunk in parsed.styles:
            csslib.parse(chunk, report, sheet=sheet)
        body = parsed.root.find("body") or parsed.root
        conv = HtmlConverter(report, sheet, resolve_media, slugs)
        if i == 0:
            brand, items = header_parts(body, conv)
            doc["site"]["header"]["props"]["brand"] = (brand or parsed.title.split("|")[0].split("–")[0].strip() or name)[:60]
            doc["navigation"]["primary"] = [{"id": f"nav{j}", **item} for j, item in enumerate(items)]
            footer = body.find("footer")
            if footer is not None:
                inner = conv.convert_children(footer)
                if inner:
                    doc["site"]["footer"]["children"] = [node("container", {"width": "content"}, {"gap": "14px"}, [c if c["type"] != "section" else c for c in inner])]
            body_style, _ = conv.styles_for(body)
            _tokens_from(doc, body_style, sheet, body)
            first_title = parsed.title
        nodes = conv.sections(body)
        title = (parsed.title.split("|")[0].split("–")[0].strip() or PurePosixPath(filename).stem.replace("-", " ").title())[:60]
        add_page(doc, "Home" if i == 0 else title, nodes, home=i == 0, slug=slugs[PurePosixPath(filename).name.lower()])
    doc["meta"]["description"] = first_title.strip()[:160]
    for item in doc["navigation"]["primary"]:
        if "page" in item and not any(p["id"] == item["page"] for p in doc["pages"]):
            item.pop("page")
            item["url"] = "#"
    if assets is not None:
        doc["media"]["assets"] = assets   # the same list the media resolver fills
    issues = finish(doc)
    if issues:
        report.note("Some content could not be placed: " + "; ".join(issues[:3]))
    return doc


def _tokens_from(doc: dict, body_style: dict, sheet: csslib.Stylesheet, body: Element) -> None:
    """Takes the site's main colours and fonts where the CSS states them plainly."""
    from ..core.styles import normalize_color
    from ..render.fonts import catalog
    colors = doc["tokens"]["colors"]

    def color(value: str) -> str | None:
        try:
            out = normalize_color(value.split()[0] if value else "")
            return out if out.startswith("#") and len(out) == 7 else None
        except Exception:  # noqa: BLE001
            return None

    if (c := color(body_style.get("background-color", body_style.get("background", "")))):
        colors["background"] = c
    if (c := color(body_style.get("color", ""))):
        colors["text"] = c
    for el in body.find_all("a") + body.find_all("button"):
        if BUTTON_HINTS.search(el.attrs.get("class", "")) or el.tag == "button":
            style = sheet.computed(el).get("", {})
            if (c := color(style.get("background-color", style.get("background", "")))):
                colors["primary"] = c
                break
    family = body_style.get("font-family", "").split(",")[0].strip().strip("'\"")
    if family and family in catalog():
        doc["tokens"]["fonts"]["body"] = family
        doc["tokens"]["fonts"]["heading"] = family
