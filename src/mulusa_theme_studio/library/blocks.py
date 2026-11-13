"""WordPress block markup (patterns, block theme templates) -> universal document nodes.

Block markup is HTML with ``<!-- wp:name {json} -->`` delimiters. The delimiters are parsed
into a block tree; each core block that has an equivalent becomes the editor's own element,
and every other block is named in the import report. PHP in pattern files is never run: the
translation calls patterns use for their text are read for their string, anything else is removed.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .convert import Report, clean_style, node, text_of, wrap_for
from .html_import import Element, HtmlConverter, parse_html

_DELIM = re.compile(r"<!--\s+(/)?wp:([a-z][a-z0-9_-]*(?:/[a-z][a-z0-9_-]*)?)\s+(\{.*?\}\s+)?(/)?-->", re.S)
_TRANSLATE = re.compile(r"<\?php\s+(?:echo\s+)?(?:esc_html_e|esc_attr_e|_e|esc_html__|esc_attr__|__|esc_html_x|_x)\s*\(\s*'((?:[^'\\]|\\.)*)'[^?]*\?>", re.S)
_URI = re.compile(r"<\?php\s+echo\s+esc_url\(\s*get_(?:template|stylesheet)_directory_uri\(\)\s*\)\s*;?\s*\?>", re.S)
THEME_URI = "theme-root:"   # stands for the theme folder in converted image paths

MediaResolver = Callable[[str, str], "dict | None"]


@dataclass
class Block:
    name: str
    attrs: dict
    inner: list = field(default_factory=list)   # str chunks and Blocks, in order

    @property
    def blocks(self) -> list["Block"]:
        return [b for b in self.inner if isinstance(b, Block)]

    @property
    def html(self) -> str:
        return "".join(i if isinstance(i, str) else i.html for i in self.inner)

    @property
    def own_html(self) -> str:
        return "".join(i for i in self.inner if isinstance(i, str))


def strip_php(text: str, report: Report) -> str:
    """Pattern PHP: translation calls become their text, theme URLs a marker, the rest is removed."""
    text = _URI.sub(THEME_URI, text)
    text = _TRANSLATE.sub(lambda m: m.group(1).replace("\\'", "'"), text)
    if "<?" in text:
        report.lost("PHP code in patterns removed (never run on import)")
        text = re.sub(r"<\?php.*?(\?>|$)", "", text, flags=re.S)
    return text


def parse_blocks(markup: str) -> list[Block]:
    root = Block("#root", {})
    stack = [root]
    pos = 0
    for m in _DELIM.finditer(markup):
        if m.start() > pos:
            stack[-1].inner.append(markup[pos:m.start()])
        pos = m.end()
        closing, name, raw, selfclose = m.group(1), m.group(2), m.group(3), m.group(4)
        name = name if "/" in name else f"core/{name}"
        try:
            attrs = json.loads(raw) if raw else {}
        except ValueError:
            attrs = {}
        if closing:
            if len(stack) > 1 and stack[-1].name == name:
                done = stack.pop()
                stack[-1].inner.append(done)
            continue
        block = Block(name, attrs if isinstance(attrs, dict) else {})
        if selfclose:
            stack[-1].inner.append(block)
        else:
            stack.append(block)
    if pos < len(markup):
        stack[-1].inner.append(markup[pos:])
    while len(stack) > 1:  # unclosed blocks are closed at the end
        done = stack.pop()
        stack[-1].inner.append(done)
    return root.blocks if root.blocks else ([Block("core/html", {}, [markup])] if markup.strip() else [])


class BlockConverter:
    def __init__(self, report: Report, resolve_media: MediaResolver, palette: dict[str, str] | None = None,
                 patterns: dict[str, str] | None = None) -> None:
        self.report = report
        self.resolve_media = resolve_media
        self.palette = palette or {}      # slug -> hex, from theme.json
        self.patterns = patterns or {}    # slug -> markup, for core/pattern references
        self._html = HtmlConverter(report, _empty_sheet(), resolve_media, {})
        self._depth = 0

    # Attributes -> style ------------------------------------------------------------
    def colour(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("var:preset|color|"):
            value = value.rsplit("|", 1)[1]
        return self.palette.get(value) or (value if value.startswith("#") else None)

    def style_of(self, attrs: dict) -> dict:
        raw: dict[str, str] = {}
        style = attrs.get("style") or {}
        spacing = style.get("spacing") or {}
        for side, value in (spacing.get("padding") or {}).items() if isinstance(spacing.get("padding"), dict) else []:
            raw[f"padding-{side}"] = _preset_length(value)
        for side, value in (spacing.get("margin") or {}).items() if isinstance(spacing.get("margin"), dict) else []:
            if side in ("top", "bottom"):
                raw[f"margin-{side}"] = _preset_length(value)
        if spacing.get("blockGap") and isinstance(spacing["blockGap"], str):
            raw["gap"] = _preset_length(spacing["blockGap"])
        color = style.get("color") or {}
        if (c := self.colour(color.get("background") or attrs.get("backgroundColor"))):
            raw["background-color"] = c
        if (c := self.colour(color.get("text") or attrs.get("textColor"))):
            raw["color"] = c
        if color.get("gradient"):
            raw["background"] = color["gradient"]
        typo = style.get("typography") or {}
        for key, css in (("fontSize", "font-size"), ("fontWeight", "font-weight"), ("lineHeight", "line-height"),
                         ("letterSpacing", "letter-spacing"), ("textTransform", "text-transform")):
            if typo.get(key):
                raw[css] = _preset_length(str(typo[key]))
        border = style.get("border") or {}
        if border.get("radius") and isinstance(border["radius"], str):
            raw["border-radius"] = border["radius"]
        if attrs.get("textAlign") or attrs.get("align") in ("center", "left", "right"):
            raw["text-align"] = attrs.get("textAlign") or attrs["align"]
        if attrs.get("minHeight"):
            raw["min-height"] = f"{attrs['minHeight']}{attrs.get('minHeightUnit', 'px')}"
        return clean_style(raw, self.report)

    # Blocks -------------------------------------------------------------------
    def convert_many(self, blocks: list[Block]) -> list[dict]:
        out = []
        for b in blocks:
            out.extend(self.convert(b))
        return out

    def convert(self, b: Block) -> list[dict]:
        name = b.name
        handler = getattr(self, "b_" + name.split("/")[-1].replace("-", "_"), None) if name.startswith("core/") else None
        if handler is None:
            if b.blocks:
                self.report.lost(f"Block '{name}' (its inner blocks were kept)")
                return self.convert_many(b.blocks)
            self.report.lost(f"Block '{name}'")
            return []
        made = handler(b)
        self.report.converted += bool(made)
        return made

    def _html_nodes(self, html: str) -> list[dict]:
        parsed = parse_html(html, self.report)
        return self._html.convert_children(parsed.root)

    def b_heading(self, b):
        text = text_of(b.own_html)
        if not text:
            return []
        n = node("heading", {"text": text, "level": int(b.attrs.get("level", 2))}, self.style_of(b.attrs))
        return [n]

    def b_paragraph(self, b):
        html = b.own_html.strip()
        inner = re.sub(r"^<p[^>]*>|</p>$", "", html, flags=re.S).strip()
        if not text_of(inner):
            return []
        rich = re.search(r"<(a|strong|em|b|i|br|code)\b", inner)
        n = node("richtext", {"html": f"<p>{inner}</p>"}) if rich else node("text", {"text": text_of(inner)})
        n["style"] = self.style_of(b.attrs)
        return [n]

    def b_list(self, b):
        html = b.html.strip()
        return [node("richtext", {"html": re.sub(r"<!--.*?-->", "", html, flags=re.S)})] if text_of(html) else []

    def b_quote(self, b):
        return [node("text", {"text": text_of(b.html)}, self.style_of(b.attrs))] if text_of(b.html) else []

    b_pullquote = b_quote
    b_verse = b_quote
    b_preformatted = b_quote
    b_code = b_quote

    def b_separator(self, b):
        return [node("divider")]

    def b_spacer(self, b):
        return []   # spacing comes from the design system's gaps

    def b_image(self, b):
        m = re.search(r"<img[^>]*src=\"([^\"]+)\"", b.html)
        if not m:
            return []
        alt_m = re.search(r"alt=\"([^\"]*)\"", b.html)
        alt = alt_m.group(1) if alt_m else ""
        ref = self.resolve_media(m.group(1), alt)
        return [node("image", {"media": ref, "alt": alt})] if ref else []

    def b_gallery(self, b):
        items = []
        for m in re.finditer(r"<img[^>]*src=\"([^\"]+)\"", b.html):
            ref = self.resolve_media(m.group(1), "")
            if ref:
                items.append(ref)
        if not items:
            return []
        return [node("gallery", {"items": items, "columns": int(b.attrs.get("columns", 3))}, {"gap": "10px"})]

    def b_buttons(self, b):
        buttons = self.convert_many(b.blocks)
        return [node("row", {}, {"gap": "12px", "flex_wrap": "wrap"}, buttons)] if buttons else []

    def b_button(self, b):
        m = re.search(r"<a[^>]*?(?:href=\"([^\"]*)\")?[^>]*>(.*?)</a>", b.html, re.S)
        label = text_of(m.group(2) if m else b.html)
        if not label:
            return []
        href = self._html.href(m.group(1) if m and m.group(1) else "#")
        variant = "secondary" if "is-style-outline" in (b.attrs.get("className") or "") else "primary"
        return [node("button", {"label": label[:80], "href": href, "variant": variant})]

    def b_columns(self, b):
        cols = [c for c in (self.b_column(x)[0] for x in b.blocks if x.name == "core/column") if c["children"]]
        if not cols:
            return []
        n = node("columns", {"columns": min(len(cols), 4)}, self.style_of(b.attrs), cols)
        n["responsive"] = {"tablet": {"props": {"columns": min(len(cols), 2)}}, "mobile": {"props": {"columns": 1}}}
        return [n]

    def b_column(self, b):
        kids = [wrap_for("container", c) for c in self.convert_many(b.blocks)]
        return [node("container", {}, {"gap": "14px", **self.style_of(b.attrs)}, kids)]

    def b_group(self, b):
        kids = [wrap_for("container", c) for c in self.convert_many(b.blocks)]
        if not kids:
            return []
        layout = (b.attrs.get("layout") or {}).get("type")
        if layout == "flex" and (b.attrs.get("layout") or {}).get("orientation") != "vertical" and all(k["type"] in ("button", "link", "heading", "text", "image", "icon") for k in kids):
            return [node("row", {}, {"gap": "14px", "flex_wrap": "wrap", **self.style_of(b.attrs)}, kids)]
        return [node("container", {}, {"gap": "16px", **self.style_of(b.attrs)}, kids)]

    b_row = b_group
    b_stack = b_group

    def b_cover(self, b):
        kids = self.convert_many(b.blocks)
        n = node("container", {"tone": "inverse"}, {"gap": "16px", "padding": "48px", **self.style_of(b.attrs)}, [wrap_for("container", k) for k in kids])
        url = b.attrs.get("url")
        if url:
            ref = self.resolve_media(url, b.attrs.get("alt", ""))
            if ref:
                n["_background"] = {"media": ref, "overlay": f"rgba(0,0,0,{min(0.9, (b.attrs.get('dimRatio', 50) or 0) / 100):.2f})"}
        return [n]

    def b_media_text(self, b):
        img = None
        if b.attrs.get("mediaUrl"):
            ref = self.resolve_media(b.attrs["mediaUrl"], b.attrs.get("mediaAlt", ""))
            img = node("image", {"media": ref, "alt": b.attrs.get("mediaAlt", "")}) if ref else None
        text = node("container", {}, {"gap": "14px", "justify_content": "center"}, [wrap_for("container", k) for k in self.convert_many(b.blocks)])
        parts = [node("container", {}, {}, [img])] if img else []
        parts = parts + [text] if b.attrs.get("mediaPosition") != "right" else [text] + parts
        n = node("columns", {"columns": len(parts)}, {"align_items": "center"}, parts)
        n["responsive"] = {"mobile": {"props": {"columns": 1}}}
        return [n]

    def b_video(self, b):
        m = re.search(r"src=\"(https://[^\"]+)\"", b.html)
        return [node("video", {"url": m.group(1), "title": "Video", "ratio": 1.78})] if m else []

    def b_embed(self, b):
        url = b.attrs.get("url", "")
        if any(h in url for h in ("youtube.com", "youtu.be", "vimeo.com")):
            return [node("video", {"url": url, "title": "Video", "ratio": 1.78})]
        self.report.lost("Embeds other than YouTube or Vimeo")
        return []

    def b_details(self, b):
        m = re.search(r"<summary>(.*?)</summary>", b.html, re.S)
        question = text_of(m.group(1)) if m else "Question"
        answer = text_of(re.sub(r"<summary>.*?</summary>", "", b.html, flags=re.S))
        return [node("faq_item", {"question": question, "answer": answer})]

    def b_html(self, b):
        nodes = self._html_nodes(b.html)
        if not nodes:
            self.report.lost("Custom HTML block")
        return nodes

    def b_freeform(self, b):
        return self._html_nodes(b.html)

    def b_pattern(self, b):
        slug = b.attrs.get("slug", "")
        markup = self.patterns.get(slug) or self.patterns.get(slug.split("/")[-1])
        if markup is None or self._depth > 4:
            self.report.lost(f"Pattern reference '{slug}' (pattern file not in the package)")
            return []
        self._depth += 1
        try:
            return self.convert_many(parse_blocks(markup))
        finally:
            self._depth -= 1

    def b_site_title(self, b):
        return []   # the header carries the site name

    def b_social_links(self, b):
        links = []
        for s in b.blocks:
            url = s.attrs.get("url")
            if url:
                links.append(node("link", {"label": s.attrs.get("label") or s.attrs.get("service", "Link").title(), "href": self._html.href(url)}))
        return [node("row", {}, {"gap": "14px"}, links)] if links else []

    # Content the publishing system fills at run time.
    def _dynamic(self, b):
        self.report.lost(f"Dynamic block '{b.name}' (rebuild with the editor's post lists and post fields)")
        return []

    b_query = b_post_template = b_post_title = b_post_content = b_post_excerpt = b_post_date = _dynamic
    b_post_featured_image = b_template_part = b_navigation = b_search = b_comments = b_query_pagination = _dynamic
    b_site_logo = b_site_tagline = b_loginout = b_archives = b_categories = b_latest_posts = _dynamic

    # Top level ----------------------------------------------------------------
    SECTIONISH = {"core/group", "core/cover", "core/columns", "core/media-text", "core/pattern"}

    def top_level(self, blocks: list[Block], depth: int = 0) -> list[Block]:
        """Pattern references are expanded and page-wide wrappers (a <main> group) unwrapped, so each
        visible band of the page becomes its own section."""
        out: list[Block] = []
        for b in blocks:
            if b.name == "core/pattern" and depth < 4:
                slug = b.attrs.get("slug", "")
                markup = self.patterns.get(slug) or self.patterns.get(slug.split("/")[-1])
                if markup is not None:
                    expanded = self.top_level(parse_blocks(markup), depth + 1)
                    for e in expanded:
                        e.attrs.setdefault("_hint", slug.split("/")[-1])
                    out += expanded
                    continue
            kids = b.blocks
            wrapper = b.name == "core/group" and (b.attrs.get("tagName") == "main" or
                      len(blocks) == 1 and sum(k.name in self.SECTIONISH for k in kids) >= 2)
            if wrapper and depth < 4:
                out += self.top_level(kids, depth + 1)
            else:
                out.append(b)
        return out

    def sections(self, blocks: list[Block], role_hint: str = "") -> list[dict]:
        """Each top-level block becomes one section."""
        from .convert import guess_role, section_of
        out = []
        for i, b in enumerate(self.top_level(blocks)):
            nodes = self.convert(b)
            if not nodes:
                continue
            hint = f"{role_hint} {b.attrs.get('_hint', '')} {b.attrs.get('className', '')} {b.attrs.get('metadata', {}).get('name', '') if isinstance(b.attrs.get('metadata'), dict) else ''}"
            has_h1 = any(n["type"] == "heading" and n["props"].get("level") == 1 for n in _walk(nodes))
            role = "hero" if (not out and (has_h1 or b.name == "core/cover")) else guess_role(hint)
            if len(nodes) == 1 and nodes[0]["type"] == "container":
                outer = nodes[0]
                bg = outer.pop("_background", None)
                sec = section_of(outer["children"], role)
                style = {k: v for k, v in outer["style"].items() if k.startswith(("padding_top", "padding_bottom", "background", "color", "min_height"))}
                sec["style"].update(style)
                sec["children"][0]["style"].update({k: v for k, v in outer["style"].items() if k not in style})
                if bg:
                    sec["props"]["background"] = bg
                    sec["props"]["tone"] = "image"
                elif outer["props"].get("tone"):
                    sec["props"]["tone"] = outer["props"]["tone"]
            else:
                sec = section_of(nodes, role)
            for n in _walk([sec]):
                n.pop("_background", None)
            out.append(sec)
        return out


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children", []))


def _preset_length(value: str) -> str:
    """'var:preset|spacing|40' -> a length the editor accepts."""
    if isinstance(value, str) and value.startswith("var:preset|spacing|"):
        step = value.rsplit("|", 1)[1]
        table = {"10": "8px", "20": "12px", "30": "20px", "40": "32px", "50": "48px", "60": "64px", "70": "88px", "80": "120px"}
        return table.get(step, "24px")
    if isinstance(value, str) and value.startswith("var:preset|font-size|"):
        return {"small": ".9rem", "medium": "1.05rem", "large": "1.4rem", "x-large": "2rem", "xx-large": "2.8rem"}.get(value.rsplit("|", 1)[1], "1rem")
    return str(value)


def _empty_sheet():
    from .css import Stylesheet
    return Stylesheet()


def element_text(el: Element) -> str:
    return el.text()
