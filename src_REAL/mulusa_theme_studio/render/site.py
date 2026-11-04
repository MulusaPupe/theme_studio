"""Writes a document as a working website folder.

The canvas, the preview and thumbnails all use this one route, and the static
exporter will too, so what you see while designing is what is exported.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ..core.document import Document, home_page, walk_document
from ..core.structure import rules_as_data
from .css import BREAKPOINT_QUERIES, tokens_css
from .fonts import catalog, font_face_css, font_files
from .html import RenderContext, esc, render_node

BASE_CSS = Path(__file__).with_name("base.css")

EDITOR_JS = Path(__file__).with_name("editor.js")


def editor_script() -> str:
    """Editor only: selection, hover and drag handling. Never written into a preview or export."""
    source = EDITOR_JS.read_text(encoding="utf-8").replace("__MTS_RULES__", json.dumps(rules_as_data()))
    return f"<script>{source}</script>"


@dataclass(frozen=True)
class SiteOutput:
    root: Path
    pages: dict[str, Path]  # page id -> html file
    bodies: dict[str, str] = field(default_factory=dict)  # page id -> body markup, for live updates
    style_href: str = ""
    body_class: str = ""


def page_filename(page: dict) -> str:
    return "index.html" if page.get("home") else f"{page['slug']}.html"


def _all_styles(doc: Document) -> Iterator[dict]:
    for node in walk_document(doc):
        yield node.get("style") or {}
        for override in (node.get("responsive") or {}).values():
            yield (override or {}).get("style") or {}


def _same_file(source: Path, target: Path) -> bool:
    """Project media never changes under one name, so large images are not copied on every edit."""
    if not target.is_file():
        return False
    a, b = source.stat(), target.stat()
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def write_site(doc: Document, out_dir: Path, *, editor: bool = False, project_folder: Path | None = None) -> SiteOutput:
    out_dir = Path(out_dir)
    assets = out_dir / "assets"
    (assets / "fonts").mkdir(parents=True, exist_ok=True)

    bodies: dict[str, str] = {}
    contexts: list[RenderContext] = []
    # All pages share one stylesheet, so shared header and footer rules are collected once.
    rules: list[str] = []
    responsive: dict[str, list[str]] = {k: [] for k in BREAKPOINT_QUERIES}
    used_assets: set[str] = set()
    for index, page in enumerate(doc["pages"]):
        ctx = RenderContext(doc=doc, editor=editor, current_page=page["id"])
        header = render_node(doc["site"]["header"], ctx)
        footer = render_node(doc["site"]["footer"], ctx)
        shared_rules = list(ctx.rules)
        shared_responsive = {k: list(v) for k, v in ctx.responsive.items()}
        main = "".join(render_node(node, ctx) for node in page["nodes"])
        bodies[page["id"]] = f"{header}<main>{main}</main>{footer}"
        if index == 0:
            rules += shared_rules
            for key in responsive:
                responsive[key] += shared_responsive[key]
        rules += ctx.rules[len(shared_rules):]
        for key in responsive:
            responsive[key] += ctx.responsive[key][len(shared_responsive[key]):]
        used_assets |= ctx.used_assets
        contexts.append(ctx)

    fonts = doc["tokens"]["fonts"]
    families = {fonts["heading"], fonts["body"]} | set(fonts.get("extra", []))
    # A font chosen for one element travels with the site, and only then.
    families |= {str(style["font_family"]) for style in _all_styles(doc) if str(style.get("font_family", "")) in catalog()}
    media = "\n".join(
        f"@media {BREAKPOINT_QUERIES[key]}{{{''.join(values)}}}"
        # Tablet before mobile so the narrower rule wins.
        for key, values in responsive.items() if values
    )
    css = "\n".join(
        (font_face_css(families), tokens_css(doc["tokens"]), BASE_CSS.read_text(encoding="utf-8"), "".join(rules), media)
    )
    (assets / "style.css").write_text(css, encoding="utf-8")
    version = hashlib.sha1(css.encode()).hexdigest()[:10]
    for file in font_files(families):
        target = assets / "fonts" / file.name
        if not target.exists():
            shutil.copyfile(file, target)
    if used_assets and project_folder is not None:
        media_dir = assets / "media"
        media_dir.mkdir(exist_ok=True)
        for name in used_assets:
            source = Path(project_folder) / "assets" / name
            target = media_dir / name
            if source.is_file() and not _same_file(source, target):
                shutil.copy2(source, target)

    style = doc["tokens"].get("shape", {}).get("button_style", "solid")
    body_class = f"mts-tone-default mts-btnstyle-{esc(str(style), quote=True)}"
    home = home_page(doc)
    site_name = esc(str(doc["meta"].get("name", "")))
    pages: dict[str, Path] = {}
    for page in doc["pages"]:
        title = site_name if page is home else f"{esc(str(page.get('title', '')))} | {site_name}"
        description = esc(str(doc["meta"].get("description", "")), quote=True)
        script = editor_script() if editor else ""
        document = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><meta name="description" content="{description}">'
            f'<link rel="stylesheet" href="assets/style.css?v={version}"></head>'
            f'<body class="{body_class}">{bodies[page["id"]]}{script}</body></html>'
        )
        path = out_dir / page_filename(page)
        path.write_text(document, encoding="utf-8")
        pages[page["id"]] = path
    return SiteOutput(out_dir, pages, bodies, f"assets/style.css?v={version}", body_class)
