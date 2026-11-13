"""Shared pieces for the import adapters: a blank document, node builders and the import report.

Every adapter produces ordinary universal-document nodes, so imported content is edited,
undone and exported exactly like anything made in the editor.
"""
from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any

from ..core.document import SCHEMA, new_id, now_iso, slugify, validate_document
from ..core.styles import STYLE_PROPERTIES, check_style
from ..core.structure import can_contain

DEFAULT_COLORS = {
    "primary": "#1f3a5f", "on_primary": "#ffffff", "secondary": "#16293f", "accent": "#d9822b", "on_accent": "#ffffff",
    "background": "#ffffff", "surface": "#f3f5f8", "text": "#16202b", "muted": "#55606d", "border": "#d9dee5",
}
DEFAULT_TOKENS = {
    "colors": DEFAULT_COLORS,
    "fonts": {"heading": "Inter", "body": "Inter", "extra": []},
    "type": {"heading_weight": 700, "heading_transform": "none", "heading_tracking": "-0.01em", "heading_line": 1.12, "base": 17, "ratio": 1.28},
    "shape": {"radius": "8px", "button_radius": "8px", "button_style": "solid", "button_transform": "none", "button_tracking": "0", "button_size": ".97rem"},
    "spacing": {"section": "88px", "gap": "28px", "width": "1180px"},
}
ROLE_WORDS = [
    ("hero", ("hero", "banner", "jumbotron", "masthead", "intro", "splash", "cover")),
    ("testimonials", ("testimonial", "review", "quote")),
    ("pricing", ("pricing", "price", "plans")),
    ("faq", ("faq", "question")),
    ("contact", ("contact", "enquir")),
    ("team", ("team", "people", "staff")),
    ("portfolio", ("portfolio", "gallery", "work", "projects", "case")),
    ("statistics", ("stat", "counter", "numbers", "facts")),
    ("services", ("service", "offer")),
    ("features", ("feature", "benefit", "why")),
    ("about", ("about", "story", "who")),
    ("clients", ("client", "partner", "logos", "brands")),
    ("call_to_action", ("cta", "call-to-action", "action", "signup", "subscribe", "newsletter")),
    ("blog", ("blog", "news", "post", "article")),
]


class Report:
    """What an adapter could not carry over. Nothing is dropped without a line here."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.notes: list[str] = []
        self.converted = 0

    def lost(self, what: str, n: int = 1) -> None:
        self.counts[what] += n

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    @property
    def losses(self) -> int:
        return sum(self.counts.values())

    def lines(self) -> list[str]:
        out = [f"{what} ({n})" if n > 1 else what for what, n in self.counts.most_common()]
        return out + self.notes


def node(type_: str, props: dict | None = None, style: dict | None = None, children: list | None = None, name: str = "") -> dict:
    out: dict[str, Any] = {"id": new_id(), "type": type_, "props": props or {}, "style": style or {}}
    if name:
        out["name"] = name
    if type_ in ("section", "container", "columns", "row", "footer", "query"):
        out["children"] = children or []
    return out


def clean_style(raw: dict[str, str], report: Report | None = None) -> dict:
    """Keeps only declarations the editor supports, with safe values."""
    out = {}
    for prop, value in raw.items():
        key = prop.strip().lower().replace("-", "_")
        if key not in STYLE_PROPERTIES:
            if report is not None and not prop.startswith("--"):
                report.lost(f"CSS property '{prop}' is not supported by the editor")
            continue
        try:
            out[key] = check_style(key, str(value).strip())
        except Exception:  # noqa: BLE001 - any refusal means the value is not safe or not understood
            if report is not None:
                report.lost(f"CSS value not carried over for '{prop}'")
    return out


def guess_role(*hints: str) -> str:
    text = " ".join(h for h in hints if h).lower()
    for role, words in ROLE_WORDS:
        if any(w in text for w in words):
            return role
    return "content"


def text_of(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    from html import unescape
    return " ".join(unescape(text).split())


def wrap_for(parent_type: str, child: dict) -> dict:
    """Puts a child in a container when the nesting rules need one (text straight in a section, ...)."""
    if can_contain(parent_type, child["type"]):
        return child
    return node("container", {"width": "content"} if parent_type == "section" else {}, {}, [child])


def section_of(children: list[dict], role: str = "content", style: dict | None = None, name: str = "") -> dict:
    inner = node("container", {"width": "content"}, {"gap": "18px"}, [c if can_contain("container", c["type"]) else node("container", {}, {}, [c]) for c in children])
    return node("section", {"role": role}, style or {}, [inner], name=name or role.replace("_", " ").capitalize())


def blank_document(name: str, *, colors: dict | None = None, fonts: dict | None = None, source: str = "") -> dict:
    tokens = copy.deepcopy(DEFAULT_TOKENS)
    if colors:
        tokens["colors"].update({k: v for k, v in colors.items() if k in tokens["colors"]})
    if fonts:
        tokens["fonts"].update({k: v for k, v in fonts.items() if k in ("heading", "body")})
    footer_text = node("text", {"text": f"© {name}", "muted": True})
    return {
        "schema": SCHEMA,
        "meta": {"name": name, "description": "", "author": "", "version": "1.0.0", "created": now_iso(), "modified": now_iso(),
                 "source_template": source or "import"},
        "tokens": tokens,
        "palettes": [],
        "type_pairs": [],
        "site": {
            "header": node("header", {"brand": name, "layout": "classic"}, {}, name="Site header"),
            "footer": node("footer", {"tone": "default"}, {"padding_block": "40px"}, [node("container", {"width": "content"}, {}, [footer_text])], name="Site footer"),
        },
        "navigation": {"primary": []},
        "pages": [],
        "media": {"art": "mono", "assets": []},
        "reusable": [],
    }


def add_page(doc: dict, title: str, nodes: list[dict], *, home: bool = False, slug: str = "") -> dict:
    taken = {p["slug"] for p in doc["pages"]}
    base = slugify(slug or title) or "page"
    if home:
        base = "home"
    wanted, n = base, 2
    while wanted in taken:
        wanted, n = f"{base}-{n}", n + 1
    page = {"id": wanted, "slug": wanted, "title": title or wanted.title(), "home": home, "layout": "default", "nodes": nodes}
    doc["pages"].append(page)
    return page


def finish(doc: dict) -> list[str]:
    """Makes sure the document is valid: one homepage, no empty pages. Returns any remaining issues."""
    if not doc["pages"]:
        add_page(doc, "Home", [], home=True)
    if not any(p.get("home") for p in doc["pages"]):
        doc["pages"][0]["home"] = True
    for page in doc["pages"]:
        if not page["nodes"]:
            page["nodes"].append(section_of([node("heading", {"text": page["title"], "level": 1})]))
    return validate_document(doc)
