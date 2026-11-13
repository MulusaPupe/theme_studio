"""Pages, the shared navigation and dynamic content settings. All of these run inside History.apply.

A page can hold an ordinary design, or be a template for content that lives in the
publishing system: ``role`` says which. Links refer to pages by id, so changing a page's
title or address breaks nothing, and deleting a page repoints what linked to it.
"""
from __future__ import annotations

from typing import Any

from .document import (
    PAGE_LAYOUTS, PAGE_ROLES, QUERY_HIDEABLE, QUERY_ORDER_BY, SLUG, Document, Node, find_node, find_page,
    home_page, new_id, site_pages, slugify, walk_document, walk_nodes,
)
from .errors import StudioError
from .media import asset_ref, find_asset
from .operations import clone_tree
from .styles import is_safe_url


class PageError(StudioError):
    pass


def unique_slug(doc: Document, wanted: str, ignore: str = "") -> str:
    base = slugify(wanted) or "page"
    taken = {p["slug"] for p in doc["pages"] if p["id"] != ignore}
    slug, number = base, 2
    while slug in taken:
        slug, number = f"{base}-{number}", number + 1
    return slug


def _clean_title(title: Any) -> str:
    text = str(title or "").strip()
    if not text:
        raise PageError("A page needs a title.")
    if len(text) > 120:
        raise PageError("That title is too long: keep it under 120 characters.")
    return text


def _page(doc: Document, page_id: str) -> dict:
    page = find_page(doc, page_id)
    if page is None:
        raise PageError("That page no longer exists.")
    return page


def create_page(doc: Document, title: str, nodes: list[Node] | None = None, role: str = "", after: str = "") -> str:
    """Adds a page, optionally with ready-made sections, and returns its id."""
    if role and role not in PAGE_ROLES:
        raise PageError(f"Unknown page role '{role}'.")
    if role and any(p.get("role") == role for p in doc["pages"]):
        raise PageError(f"This site already has {PAGE_ROLES[role].lower()}.")
    title = _clean_title(title)
    page = {"id": new_id(), "slug": unique_slug(doc, title), "title": title, "home": False, "layout": "default", "nodes": nodes or []}
    if role:
        page["role"] = role
    position = next((i + 1 for i, p in enumerate(doc["pages"]) if p["id"] == after), len(doc["pages"]))
    doc["pages"].insert(position, page)
    return page["id"]


def rename_page(doc: Document, page_id: str, title: str) -> None:
    _page(doc, page_id)["title"] = _clean_title(title)


def set_slug(doc: Document, page_id: str, slug: str) -> None:
    text = str(slug or "").strip().lower()
    if not SLUG.match(text):
        raise PageError("An address may use only lower-case letters, numbers and single hyphens.")
    if any(p["slug"] == text and p["id"] != page_id for p in doc["pages"]):
        raise PageError(f"Another page already uses the address '{text}'.")
    _page(doc, page_id)["slug"] = text


def set_page_meta(doc: Document, page_id: str, *, description: str | None = None, layout: str | None = None) -> None:
    page = _page(doc, page_id)
    if description is not None:
        if len(description) > 320:
            raise PageError("Keep the page description under 320 characters.")
        if description.strip():
            page["description"] = description.strip()
        else:
            page.pop("description", None)
    if layout is not None:
        if layout not in PAGE_LAYOUTS:
            raise PageError(f"Unknown page layout '{layout}'.")
        page["layout"] = layout


def duplicate_page(doc: Document, page_id: str) -> str:
    """A copy with new ids throughout. It is never the homepage and joins no menu by itself."""
    page = _page(doc, page_id)
    if page.get("role"):
        raise PageError("A content template cannot be copied: a site has one of each.")
    title = _clean_title(f"{page['title']} copy"[:120])
    copy_id = create_page(doc, title, [clone_tree(node) for node in page["nodes"]], after=page_id)
    fresh = find_page(doc, copy_id)
    fresh["layout"] = page.get("layout", "default")
    if page.get("description"):
        fresh["description"] = page["description"]
    return copy_id


def _link_holders(doc: Document) -> list[tuple[dict, str]]:
    found: list[tuple[dict, str]] = []
    for node in walk_document(doc):
        props = node.get("props", {})
        if isinstance(props.get("href"), dict):
            found.append((props, "href"))
        cta = props.get("cta")
        if isinstance(cta, dict) and isinstance(cta.get("href"), dict):
            found.append((cta, "href"))
    return found


def broken_page_links(doc: Document) -> list[str]:
    """Labels of links, in the design or menu, whose page does not exist or cannot be linked to."""
    pages = {p["id"] for p in site_pages(doc)}
    broken = [str(holder.get("label") or "A link") for holder, key in _link_holders(doc) if holder[key].get("page") not in pages]
    broken += [str(item.get("label") or "A menu link") for item in doc["navigation"].get("primary", []) if item.get("page") and item["page"] not in pages]
    return broken


def delete_page(doc: Document, page_id: str) -> int:
    """Removes a page and repoints whatever linked to it. Returns how many links were repointed."""
    page = _page(doc, page_id)
    if page.get("home"):
        raise PageError("The homepage cannot be deleted. Make another page the homepage first.")
    if not page.get("role") and len(site_pages(doc)) <= 1:
        raise PageError("A site needs at least one page.")
    doc["pages"].remove(page)
    home = home_page(doc)["id"]
    nav = doc["navigation"].get("primary", [])
    keep = [item for item in nav if item.get("page") != page_id]
    count = len(nav) - len(keep)
    doc["navigation"]["primary"] = keep
    for holder, key in _link_holders(doc):
        if holder[key].get("page") == page_id:
            holder[key] = {"page": home}
            count += 1
    return count


def move_page(doc: Document, page_id: str, step: int) -> None:
    page = _page(doc, page_id)
    pages = doc["pages"]
    index = pages.index(page)
    target = index + step
    if not 0 <= target < len(pages):
        raise PageError("That page is already at the end of the list.")
    pages.insert(target, pages.pop(index))


def set_home(doc: Document, page_id: str) -> None:
    page = _page(doc, page_id)
    if page.get("role"):
        raise PageError("A content template cannot be the homepage.")
    for other in doc["pages"]:
        other["home"] = False
    page["home"] = True


# Navigation ------------------------------------------------------------------
def _menu(doc: Document) -> list[dict]:
    return doc["navigation"].setdefault("primary", [])


def _item(doc: Document, item_id: str) -> dict:
    for item in _menu(doc):
        if item.get("id") == item_id:
            return item
    raise PageError("That menu link no longer exists.")


def _destination(doc: Document, target: Any) -> dict:
    if isinstance(target, dict) and target.get("page"):
        page = find_page(doc, target["page"])
        if page is None or page.get("role"):
            raise PageError("A menu link must point to an existing page.")
        return {"page": page["id"]}
    text = str((target or {}).get("url", "") if isinstance(target, dict) else target or "").strip()
    if not text or not is_safe_url(text):
        raise PageError("That link address is not valid. Use https://, mailto:, tel: or #.")
    return {"url": text}


def add_nav_item(doc: Document, label: str, target: Any, index: int = -1) -> str:
    text = str(label or "").strip()
    if not text:
        raise PageError("A menu link needs a label.")
    item = {"id": new_id(), "label": text, **_destination(doc, target)}
    menu = _menu(doc)
    menu.insert(index if 0 <= index <= len(menu) else len(menu), item)
    return item["id"]


def update_nav_item(doc: Document, item_id: str, *, label: str | None = None, target: Any = None) -> None:
    item = _item(doc, item_id)
    if label is not None:
        text = str(label).strip()
        if not text:
            raise PageError("A menu link needs a label.")
        item["label"] = text
    if target is not None:
        destination = _destination(doc, target)
        item.pop("page", None)
        item.pop("url", None)
        item.update(destination)


def remove_nav_item(doc: Document, item_id: str) -> None:
    _menu(doc).remove(_item(doc, item_id))


def move_nav_item(doc: Document, item_id: str, step: int) -> None:
    menu = _menu(doc)
    item = _item(doc, item_id)
    index = menu.index(item)
    target = index + step
    if not 0 <= target < len(menu):
        raise PageError("That link is already at the end of the menu.")
    menu.insert(target, menu.pop(index))


def set_header_logo(doc: Document, asset_id: str) -> None:
    """Shows an uploaded image as the site logo. An empty id goes back to the site name alone."""
    props = doc["site"]["header"]["props"]
    if not asset_id:
        props.pop("logo", None)
        return
    asset = find_asset(doc, asset_id)
    if asset is None:
        raise PageError("That image is no longer in the project.")
    props["logo"] = asset_ref(asset)


# Dynamic content ------------------------------------------------------------
def set_query(doc: Document, node_id: str, **changes: Any) -> None:
    """Changes what a posts list shows. Every value is checked, so a bad one cannot reach an export."""
    node = find_node(doc, node_id)
    if node is None or node.get("type") != "query":
        raise PageError("That element is not a posts list.")
    props = node["props"]
    source = props.setdefault("source", {"kind": "posts"})
    for key, value in changes.items():
        if key == "count":
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 24:
                raise PageError("A posts list shows between 1 and 24 posts.")
            source["count"] = value
        elif key == "order_by":
            if value not in QUERY_ORDER_BY:
                raise PageError(f"Unknown sort order '{value}'.")
            source["order_by"] = value
        elif key == "order":
            if value not in ("asc", "desc"):
                raise PageError("Posts are sorted ascending or descending.")
            source["order"] = value
        elif key == "categories":
            names = [slugify(str(item)) for item in value if slugify(str(item))] if isinstance(value, (list, tuple)) else None
            if names is None:
                raise PageError("Categories must be a list of names.")
            source["categories"] = names
        elif key == "follow_page":
            source["follow_page"] = bool(value)
        elif key == "layout":
            if value not in ("grid", "list"):
                raise PageError("A posts list is a grid or a list.")
            props["layout"] = value
        elif key == "columns":
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 6:
                raise PageError("A posts grid has between 1 and 6 columns.")
            props["columns"] = value
        elif key == "image_position":
            if value not in ("top", "left"):
                raise PageError("The image goes above or beside the text.")
            props["image_position"] = value
        elif key == "pagination":
            props["pagination"] = bool(value)
        elif key == "empty_text":
            props["empty_text"] = str(value)[:200]
        elif key == "hide":
            fields = [item for item in value if item in QUERY_HIDEABLE] if isinstance(value, (list, tuple)) else None
            if fields is None or len(fields) != len(value):
                raise PageError("Only known post details can be hidden.")
            props["hide"] = fields
        else:
            raise PageError(f"A posts list has no setting '{key}'.")


def post_fields_in(nodes: list[Node]) -> set[str]:
    return {n["props"].get("field") for n in walk_nodes(nodes) if n.get("type") == "post_field"}

