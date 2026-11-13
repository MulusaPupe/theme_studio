"""Putting resources into a project document. Pure document functions; the session runs them through History.

Sections arrive with fresh ids and their images copied into the project (duplicates are
reused), so an inserted section is ordinary content: selectable, editable, undoable, exportable.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..core import media
from ..core.document import Document, walk_nodes
from ..core.operations import clone_tree
from ..core.styles import check_style
from .model import Resource
from .packages import section_trees
from .patterns import GRADIENTS, render_pattern

HEADER_KEYS = ("layout", "tone", "sticky", "mobile_menu", "nav_style", "caps", "rule", "overlay")


def load_sections(resource: Resource) -> tuple[list[dict], list[dict], Path | None]:
    """The section trees a resource inserts, the assets they use and the folder holding those files."""
    if resource.origin == "builtin" and resource.kind in ("section", "header", "footer"):
        data = json.loads(Path(resource.path).read_text(encoding="utf-8"))
        return data.get("nodes", []), [], None
    if resource.kind in ("section", "template"):
        return section_trees(resource)
    raise ValueError(f"'{resource.name}' has no sections to insert.")


def _refs(node: dict):
    props = node.get("props", {})
    for key in ("media", "poster"):
        if isinstance(props.get(key), dict):
            yield props[key]
    if isinstance(props.get("background"), dict) and isinstance(props["background"].get("media"), dict):
        yield props["background"]["media"]
    if node.get("type") == "gallery":
        yield from (i for i in props.get("items", []) if isinstance(i, dict))


def adopt(doc: Document, project_folder: Path, trees: list[dict], assets: list[dict], assets_folder: Path | None) -> list[dict]:
    """Fresh copies of ``trees`` whose images point at assets in this project (copied in when needed)."""
    by_id = {a["id"]: a for a in assets}
    mapping: dict[str, str] = {}
    out = []
    for tree in trees:
        fresh = clone_tree(tree)
        for node in walk_nodes([fresh]):
            for ref in _refs(node):
                if ref.get("kind") != "asset":
                    continue
                old = ref.get("id")
                if old not in mapping:
                    mapping[old] = _bring_in(doc, project_folder, by_id.get(old), assets_folder)
                if mapping[old]:
                    ref["id"] = mapping[old]
                else:   # the file is gone: keep a placeholder rather than a broken image
                    ref.clear()
                    ref.update(media.placeholder_ref(old or "missing", "Image"))
        out.append(fresh)
    return out


def _bring_in(doc: Document, project_folder: Path, asset: dict | None, folder: Path | None) -> str:
    if asset is None or folder is None:
        return ""
    source = folder / Path(asset.get("file", "")).name
    if not source.is_file():
        return ""
    stored = media.store_upload(project_folder, source)
    existing = media.find_duplicate(doc, stored["sha256"])
    if existing:
        media.asset_path(project_folder, stored).unlink(missing_ok=True)
        return existing["id"]
    stored["name"] = asset.get("name", stored["name"])
    media.add_asset(doc, stored)
    return stored["id"]


def apply_header(doc: Document, header: dict) -> None:
    """Takes a header's layout and behaviour; the site's own name and button stay."""
    props = doc["site"]["header"].setdefault("props", {})
    for key in HEADER_KEYS:
        if key in header.get("props", {}):
            props[key] = copy.deepcopy(header["props"][key])
        else:
            props.pop(key, None)
    doc["site"]["header"]["style"] = copy.deepcopy(header.get("style", {}))


def apply_footer(doc: Document, footer: dict, sample_brand: str = "") -> None:
    """Replaces the footer's design. The sample brand name in it becomes the site's own."""
    brand = doc["site"]["header"].get("props", {}).get("brand") or doc["meta"].get("name", "")
    fresh = clone_tree(footer)
    fresh["id"] = doc["site"]["footer"]["id"]
    for node in walk_nodes([fresh]):
        props = node.get("props", {})
        if sample_brand and brand:
            for key in ("text", "label"):
                if isinstance(props.get(key), str) and sample_brand in props[key]:
                    props[key] = props[key].replace(sample_brand, brand)
        href = props.get("href")
        if isinstance(href, dict) and href.get("page") and not any(p["id"] == href["page"] for p in doc["pages"]):
            props["href"] = "#"
    doc["site"]["footer"] = fresh


def apply_gradient(node: dict, key: str) -> None:
    """A gradient replaces any photo behind the section (the photo stays in Media)."""
    media.clear_section_photo(node)
    node.setdefault("style", {})["background"] = check_style("background", GRADIENTS[key]["css"])
    node.setdefault("props", {})["tone"] = "inverse" if key != "surface-fade" else "surface"


def apply_pattern(doc: Document, project_folder: Path, node: dict, key: str) -> str:
    """Draws the pattern in the site's dark colours, adds it as an image and puts it behind the section."""
    colors = doc["tokens"]["colors"]
    target = Path(project_folder) / ".pattern-tmp" / f"pattern-{key}.png"
    render_pattern(key, colors["secondary"], colors["on_primary"], target)
    try:
        stored = media.store_upload(project_folder, target)
    finally:
        target.unlink(missing_ok=True)
    existing = media.find_duplicate(doc, stored["sha256"])
    if existing:
        media.asset_path(project_folder, stored).unlink(missing_ok=True)
        asset_id = existing["id"]
    else:
        stored["name"] = f"Pattern: {key}"
        media.add_asset(doc, stored)
        asset_id = stored["id"]
    media.set_section_photo(doc, node, {"kind": "asset", "id": asset_id})
    node["props"]["background"]["overlay"] = "rgba(0,0,0,0.15)"
    return asset_id
