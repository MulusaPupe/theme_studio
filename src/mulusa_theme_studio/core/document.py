"""The universal theme document.

A website is one JSON-compatible dictionary. The editor reads and changes only
this structure, and renderers and exporters translate it. Nothing here knows
about Qt, HTML or any particular platform.

Document shape (schema ``mulusa.theme/2``; ``migrate_document`` reads version 1)::

    meta        name, description, author, version, created, modified, source_template
    tokens      colors, fonts, type, shape, spacing (the global design system)
    palettes    saved colour palettes; type_pairs: saved font combinations
    site        header and footer nodes shared by every page
    navigation  primary: [{id, label, page | url}]
    pages       [{id, slug, title, home, layout, description?, role?, nodes: [node]}]
                role: absent for an ordinary page, or single, archive or not_found for a
                template of content that the publishing system supplies when the site runs.
    media       art (placeholder style), assets: [{id, file, name, kind}]
    reusable    saved components (nodes)

Node shape::

    id, type, name?, props{}, style{}, responsive{tablet|mobile|desktop: {style, props, hidden}}, children[]

Sections are trees of primitive nodes rather than opaque blocks. A "hero" is a
``section`` whose ``props.role`` is ``hero``. That makes every element
selectable, gives an AI assistant precise targets, and maps directly onto
the block structures of content management systems.

Dynamic content is described without naming any platform. A ``query`` holds a source
({kind: "posts", count, order_by, order, categories, follow_page}), display settings and one
card, repeated for each result. A ``post_field`` shows one detail of the current post.
"""
from __future__ import annotations

import copy
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from .structure import can_contain
from .styles import STYLE_PROPERTIES, TONES, is_safe_value

SCHEMA = "mulusa.theme/2"
OLDER_SCHEMAS = ("mulusa.theme/1",)
PAGE_ROLES = {"single": "A single post template", "archive": "A post list template", "not_found": "A page-not-found template"}
PAGE_LAYOUTS = {"default": "Standard: site header and footer", "landing": "Landing: no site header or footer"}
QUERY_SOURCES = ("posts",)  # Pages, search results and products can join later without a new node type.
QUERY_ORDER_BY = ("date", "title", "modified", "random")
POST_FIELDS = ("title", "featured_image", "excerpt", "date", "author", "categories", "tags", "content", "read_more")
QUERY_HIDEABLE = ("featured_image", "excerpt", "date", "author", "categories", "tags", "read_more")
BREAKPOINTS = ("desktop", "tablet", "mobile")
NODE_TYPES = frozenset(
    {
        "section", "container", "columns", "row", "divider", "header", "footer",
        "heading", "text", "richtext", "image", "gallery", "video", "icon",
        "button", "link", "faq_item", "contact_form", "query", "post_field",
        "illustration", "countdown", "progress",
    }
)
CONTAINER_TYPES = frozenset({"section", "container", "columns", "row", "footer", "query"})
COLOR_TOKENS = (
    "primary", "on_primary", "secondary", "accent", "on_accent",
    "background", "surface", "text", "muted", "border",
)
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
Node = dict[str, Any]
Document = dict[str, Any]


def new_id() -> str:
    return "n" + uuid.uuid4().hex[:10]


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def walk_nodes(nodes: list[Node]) -> Iterator[Node]:
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("children", []))


def walk_document(doc: Document) -> Iterator[Node]:
    """Every node in the document: shared header and footer, then each page."""
    for key in ("header", "footer"):
        node = doc.get("site", {}).get(key)
        if node:
            yield from walk_nodes([node])
    for page in doc.get("pages", []):
        yield from walk_nodes(page.get("nodes", []))


def find_node(doc: Document, node_id: str) -> Node | None:
    return next((n for n in walk_document(doc) if n.get("id") == node_id), None)


def home_page(doc: Document) -> dict[str, Any]:
    return next((p for p in doc["pages"] if p.get("home")), doc["pages"][0])


def site_pages(doc: Document) -> list[dict[str, Any]]:
    """The pages a visitor can be linked to, leaving out content templates."""
    return [p for p in doc["pages"] if not p.get("role")]


def migrate_document(doc: Any) -> Any:
    """Brings an older document up to the current schema. Changes nothing else, and is safe to repeat.

    Version 2 adds post lists, post fields, page roles and descriptions, a logo, and ids on menu
    links so each can be edited alone. Only the menu ids need adding to existing data.
    """
    if not isinstance(doc, dict) or doc.get("schema") not in OLDER_SCHEMAS:
        return doc
    navigation = doc.get("navigation")
    items = navigation.get("primary") if isinstance(navigation, dict) else None
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and not item.get("id"):
            item["id"] = new_id()
    doc["schema"] = SCHEMA
    return doc


def find_page(doc: Document, page_id: str) -> dict[str, Any] | None:
    return next((p for p in doc["pages"] if p["id"] == page_id), None)


def media_refs(doc: Document) -> Iterator[dict[str, Any]]:
    """Every media reference used by the document."""
    for node in walk_document(doc):
        props = node.get("props", {})
        for key in ("media", "poster", "logo"):
            if isinstance(props.get(key), dict):
                yield props[key]
        background = props.get("background")
        if isinstance(background, dict) and isinstance(background.get("media"), dict):
            yield background["media"]
        for item in props.get("items", []) if node.get("type") == "gallery" else []:
            if isinstance(item, dict):
                yield item


_TYPE_NAMES = {"text": "Paragraph", "richtext": "Rich text", "faq_item": "FAQ item", "contact_form": "Contact form", "progress": "Progress bar"}


def type_label(node: Node) -> str:
    """The kind of element, in plain words."""
    kind = str(node.get("type", "node"))
    return _TYPE_NAMES.get(kind, kind.replace("_", " ").title())


def describe_node(node: Node) -> str:
    """A line for the hierarchy, such as 'Section: Hero' or 'Heading: Our work'."""
    kind = type_label(node)
    label = node_label(node)
    return kind if label == kind else (label if node.get("name") else f"{kind}: {label}")


def node_label(node: Node) -> str:
    """A short human name for layers and the status bar."""
    if node.get("name"):
        return node["name"]
    props = node.get("props", {})
    if props.get("role"):
        return str(props["role"]).replace("_", " ").title()
    for key in ("text", "label", "question", "alt", "brand"):
        if props.get(key):
            text = str(props[key])
            return text if len(text) <= 32 else text[:31] + "…"
    return str(node.get("type", "node")).replace("_", " ").title()


def instantiate_template(template_doc: Document, *, name: str, author: str = "") -> Document:
    """A new project document from a template. The template itself is untouched."""
    doc = copy.deepcopy(template_doc)
    stamp = now_iso()
    source = doc.get("meta", {}).get("id", "")
    doc["meta"] = {
        "name": name,
        "description": doc.get("meta", {}).get("description", ""),
        "author": author,
        "version": "1.0.0",
        "created": stamp,
        "modified": stamp,
        "source_template": source,
    }
    return doc


def validate_document(doc: Any) -> list[str]:
    """Problems that would make a document unsafe to edit. Empty means valid."""
    if not isinstance(doc, dict):
        return ["The project data is not a JSON object."]
    issues: list[str] = []
    if doc.get("schema") != SCHEMA and doc.get("schema") not in OLDER_SCHEMAS:  # Version 2 only added to version 1.
        issues.append(f"Unsupported format '{doc.get('schema')}'; this version reads '{SCHEMA}'.")
        return issues
    for key, kind in (("meta", dict), ("tokens", dict), ("site", dict), ("navigation", dict), ("media", dict), ("pages", list)):
        if not isinstance(doc.get(key), kind):
            issues.append(f"Section '{key}' is missing or has the wrong type.")
    if issues:
        return issues

    tokens = doc["tokens"]
    colors = tokens.get("colors", {})
    for name in COLOR_TOKENS:
        if not HEX_COLOR.match(str(colors.get(name, ""))):
            issues.append(f"Colour token '{name}' must be a #rrggbb value (found {colors.get(name)!r}).")
    for name in ("heading", "body"):
        if not tokens.get("fonts", {}).get(name):
            issues.append(f"Font token '{name}' is missing.")
    for group in ("type", "shape", "spacing"):
        if not isinstance(tokens.get(group), dict):
            issues.append(f"Token group '{group}' is missing.")

    pages = doc["pages"]
    if not pages:
        issues.append("The project has no pages.")
    homes = [p for p in pages if isinstance(p, dict) and p.get("home")]
    if any(isinstance(p, dict) and p.get("home") and p.get("role") for p in pages):
        issues.append("A content template cannot be the homepage.")
    roles: set[str] = set()
    for page in pages:
        role = page.get("role") if isinstance(page, dict) else None
        if role is not None and role not in PAGE_ROLES:
            issues.append(f"Unknown page role '{role}'.")
        if role is not None and role in roles:
            issues.append(f"Only one page can have the role '{role}'.")
        roles.add(role)
        if isinstance(page, dict) and page.get("layout", "default") not in PAGE_LAYOUTS:
            issues.append(f"Page '{page.get('title')}' has an unknown layout '{page.get('layout')}'.")
    if len(homes) != 1:
        issues.append(f"Exactly one page must be the homepage (found {len(homes)}).")
    seen_pages: set[str] = set()
    seen_slugs: set[str] = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("nodes"), list):
            issues.append("A page entry is malformed.")
            continue
        if page.get("id") in seen_pages:
            issues.append(f"Duplicate page id '{page.get('id')}'.")
        seen_pages.add(page.get("id"))
        slug = str(page.get("slug", ""))
        if not SLUG.match(slug):
            issues.append(f"Page '{page.get('title')}' has an invalid address '{slug}'.")
        if slug in seen_slugs:
            issues.append(f"Two pages use the address '{slug}'.")
        seen_slugs.add(slug)

    for key in ("header", "footer"):
        if not isinstance(doc["site"].get(key), dict):
            issues.append(f"The shared {key} is missing.")
    seen_nodes: set[str] = set()
    for node in _safe_walk(doc, issues):
        node_id = node.get("id")
        if not node_id:
            issues.append(f"A '{node.get('type')}' element has no id.")
        elif node_id in seen_nodes:
            issues.append(f"Duplicate element id '{node_id}'.")
        seen_nodes.add(node_id)
        if node.get("type") not in NODE_TYPES:
            issues.append(f"Unknown element type '{node.get('type')}' ({node_id}).")
    if not issues:
        issues += _structure_issues(doc)

    for item in doc["navigation"].get("primary", []):
        if item.get("page") and item["page"] not in seen_pages:
            issues.append(f"Navigation link '{item.get('label')}' points to a missing page.")
    assets = {a.get("id") for a in doc["media"].get("assets", [])}
    for asset in doc["media"].get("assets", []):
        name = str(asset.get("file", ""))
        if not name or "/" in name or "\\" in name or name.startswith("."):
            issues.append(f"A media asset has an unsafe file name '{name}'.")
    for group in ("type", "shape", "spacing"):
        for key, value in (tokens.get(group) or {}).items():
            if not is_safe_value(value):
                issues.append(f"Design setting '{key}' has an unsafe value.")
    if not issues:
        issues += _style_issues(doc)
    if not issues:
        issues += _dynamic_issues(doc)
    if not issues:
        for ref in media_refs(doc):
            if ref.get("kind") == "asset" and ref.get("id") not in assets:
                issues.append(f"An image refers to a missing media asset '{ref.get('id')}'.")
            elif ref.get("kind") not in ("asset", "placeholder"):
                issues.append(f"Unknown media kind '{ref.get('kind')}'.")
    return issues


def _dynamic_issues(doc: Document) -> list[str]:
    """A posts list must be readable by every exporter, and a post field needs a post to show."""
    issues: list[str] = []

    def visit(node: Node, has_post: bool) -> None:
        kind = node.get("type")
        props = node.get("props", {})
        if kind == "post_field":
            if props.get("field") not in POST_FIELDS:
                issues.append(f"Unknown post detail '{props.get('field')}'.")
            if not has_post:
                issues.append(f"A post {props.get('field')} sits outside a posts list, so it has no post to show.")
        if kind == "query":
            source = props.get("source")
            if not isinstance(source, dict) or source.get("kind") not in QUERY_SOURCES:
                issues.append("A posts list has an unknown content source.")
            if len(node.get("children", [])) != 1:
                issues.append("A posts list must hold exactly one card.")
            has_post = True
        for child in node.get("children", []):
            visit(child, has_post)

    for key in ("header", "footer"):
        visit(doc["site"][key], False)
    for page in doc["pages"]:
        for node in page.get("nodes", []):
            visit(node, page.get("role") == "single")
    return issues


def _style_issues(doc: Document) -> list[str]:
    """Tones are a closed list, a section over a photo keeps the image tone, and no unsafe style gets in."""
    issues: list[str] = []
    for node in walk_document(doc):
        props = node.get("props", {})
        tone = props.get("tone")
        if tone is not None and tone not in TONES:
            issues.append(f"Unknown tone '{tone}' on a {node.get('type')}.")
        background = props.get("background")
        if node.get("type") == "section" and isinstance(background, dict) and isinstance(background.get("media"), dict) and tone != "image":
            issues.append("A section with a background image must use the image tone.")
        styles = [node.get("style") or {}] + [(o or {}).get("style") or {} for o in (node.get("responsive") or {}).values()]
        for style in styles:
            for key, value in style.items():
                if key not in STYLE_PROPERTIES or not is_safe_value(value):
                    issues.append(f"Unsafe style '{key}' on a {node.get('type')}.")
    return issues


def _structure_issues(doc: Document) -> list[str]:
    """Every parent and child pairing must be one the structure rules allow."""
    issues: list[str] = []

    def visit(node: Node) -> None:
        for child in node.get("children", []):
            if not can_contain(node.get("type"), child.get("type")):
                issues.append(f"A {node.get('type')} cannot contain a {child.get('type')} ({child.get('id')}).")
            visit(child)

    for key, kind in (("header", "header"), ("footer", "footer")):
        if doc["site"][key].get("type") != kind:
            issues.append(f"The shared {key} has the wrong type.")
        visit(doc["site"][key])
    for page in doc["pages"]:
        for node in page.get("nodes", []):
            if not can_contain(None, node.get("type")):
                issues.append(f"Page '{page.get('title')}' cannot hold a {node.get('type')} at its top level.")
            visit(node)
    return issues


def _safe_walk(doc: Document, issues: list[str]) -> Iterator[Node]:
    def visit(node: Any) -> Iterator[Node]:
        if not isinstance(node, dict) or not isinstance(node.get("children", []), list):
            issues.append("An element is malformed.")
            return
        yield node
        for child in node.get("children", []):
            yield from visit(child)

    for key in ("header", "footer"):
        if isinstance(doc["site"].get(key), dict):
            yield from visit(doc["site"][key])
    for page in doc["pages"]:
        if isinstance(page, dict) and isinstance(page.get("nodes"), list):
            for node in page["nodes"]:
                yield from visit(node)
