"""Every structural edit to the universal document, validated.

These functions change the document they are given, so they must only be run through
``History.apply``, which restores the document if one of them raises. A place to insert
is a ``parent_ref``: a node id, or ``page:<id>`` for the top level of a page.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .document import NODE_TYPES, Document, Node, find_page, new_id, walk_document, walk_nodes
from .errors import StudioError
from .structure import SHARED_TYPES, can_contain, is_container

PAGE_PREFIX = "page:"
MAX_TREE_NODES = 2000
MAX_TREE_DEPTH = 40


class EditError(StudioError):
    """An edit was refused. The message is shown to the person as it is."""


@dataclass(frozen=True)
class Location:
    siblings: list[Node]
    index: int
    parent: Node | None
    page: dict | None


def type_name(node_type: str | None) -> str:
    """A type in words, with its article: "a page", "an image", "a faq item"."""
    if node_type is None:
        return "a page"
    name = str(node_type).replace("_", " ")
    return f"{'an' if name[0] in 'aeiou' else 'a'} {name}"


def locate(doc: Document, node_id: str) -> Location | None:
    """Where a node sits. Shared header and footer have no siblings to move among."""
    def search(nodes: list[Node], parent: Node | None, page: dict | None) -> Location | None:
        for index, node in enumerate(nodes):
            if node.get("id") == node_id:
                return Location(nodes, index, parent, page)
            found = search(node.get("children", []), node, page)
            if found:
                return found
        return None

    for page in doc.get("pages", []):
        found = search(page.get("nodes", []), None, page)
        if found:
            return found
    for key in ("header", "footer"):
        shared = doc.get("site", {}).get(key)
        if shared:
            found = search([shared], None, None)
            if found:
                return found
    return None


def ancestors(doc: Document, node_id: str) -> list[Node]:
    """The chain of nodes from the outermost down to the node itself. Empty if not found."""
    def search(nodes: list[Node], trail: list[Node]) -> list[Node]:
        for node in nodes:
            path = trail + [node]
            if node.get("id") == node_id:
                return path
            found = search(node.get("children", []), path)
            if found:
                return found
        return []

    site = doc.get("site", {})
    roots = [n for n in (site.get("header"), site.get("footer")) if n]
    for nodes in [roots] + [p.get("nodes", []) for p in doc.get("pages", [])]:
        found = search(nodes, [])
        if found:
            return found
    return []


def _resolve_parent(doc: Document, parent_ref: Any) -> tuple[list[Node], str | None, Node | None]:
    if not isinstance(parent_ref, str) or not parent_ref:
        raise EditError("That is not a valid place to insert.")
    if parent_ref.startswith(PAGE_PREFIX):
        page = find_page(doc, parent_ref[len(PAGE_PREFIX):])
        if page is None:
            raise EditError("That page no longer exists.")
        return page["nodes"], None, None
    for node in walk_document(doc):
        if node.get("id") == parent_ref:
            if not is_container(node.get("type")):
                raise EditError(f"{type_name(node.get('type')).capitalize()} cannot contain other elements.")
            return node.setdefault("children", []), node.get("type"), node
    raise EditError("That element no longer exists.")


def _check_index(index: Any, length: int) -> None:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= length:
        raise EditError("That position is not valid.")


def check_tree(tree: Any) -> None:
    """A tree must be well formed before it can enter a document."""
    seen: set[str] = set()

    def visit(node: Any, depth: int) -> None:
        if not isinstance(node, dict):
            raise EditError("The element data is malformed.")
        if depth > MAX_TREE_DEPTH:
            raise EditError("The element is nested too deeply.")
        kind = node.get("type")
        if kind not in NODE_TYPES:
            raise EditError(f"Unknown element type '{kind}'.")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise EditError("The element has a missing or repeated id.")
        seen.add(node_id)
        if len(seen) > MAX_TREE_NODES:
            raise EditError("The element is too large.")
        for key in ("props", "style"):
            if not isinstance(node.get(key, {}), dict):
                raise EditError("The element data is malformed.")
        children = node.get("children", [])
        if not isinstance(children, list):
            raise EditError("The element data is malformed.")
        for child in children:
            if isinstance(child, dict) and not can_contain(kind, child.get("type")):
                raise EditError(f"{type_name(kind).capitalize()} cannot contain {type_name(child.get('type'))}.")
            visit(child, depth + 1)

    visit(tree, 0)


def clone_tree(tree: Node) -> Node:
    """A deep copy in which the node and every descendant have new ids."""
    fresh = copy.deepcopy(tree)
    for node in walk_nodes([fresh]):
        node["id"] = new_id()
        node.get("props", {}).pop("anchor", None)  # A page anchor must stay unique.
    return fresh


def _demote_extra_h1(doc: Document, page: dict | None, tree: Node) -> None:
    """A page has one main heading, so an inserted h1 becomes h2 if one exists. Its look is kept."""
    if page is None:
        return
    has_h1 = any(n.get("type") == "heading" and n.get("props", {}).get("level") == 1 for n in walk_nodes(page["nodes"]))
    if not has_h1:
        return
    for node in walk_nodes([tree]):
        if node.get("type") == "heading" and node.get("props", {}).get("level") == 1:
            node["props"]["level"] = 2


def _page_of(doc: Document, parent_ref: str) -> dict | None:
    if parent_ref.startswith(PAGE_PREFIX):
        return find_page(doc, parent_ref[len(PAGE_PREFIX):])
    location = locate(doc, parent_ref)
    return location.page if location else None


def insert_tree(doc: Document, parent_ref: str, index: int, tree: Node) -> str:
    """Inserts a complete tree. Returns its id."""
    check_tree(tree)
    siblings, parent_type, _ = _resolve_parent(doc, parent_ref)
    if not can_contain(parent_type, tree["type"]):
        raise EditError(f"{type_name(tree['type']).capitalize()} cannot go inside {type_name(parent_type)}.")
    _check_index(index, len(siblings))
    existing = {n.get("id") for n in walk_document(doc)}
    if existing & {n["id"] for n in walk_nodes([tree])}:
        raise EditError("That element is already in the document.")
    _demote_extra_h1(doc, _page_of(doc, parent_ref), tree)
    siblings.insert(index, tree)
    return tree["id"]


def _movable(doc: Document, node_id: Any) -> Location:
    location = locate(doc, node_id) if isinstance(node_id, str) else None
    if location is None:
        raise EditError("That element no longer exists.")
    if location.siblings[location.index].get("type") in SHARED_TYPES:
        kind = location.siblings[location.index]["type"]
        raise EditError(f"The {kind} is shared by every page, so it stays where it is.")
    return location


def move_node(doc: Document, node_id: str, parent_ref: str, index: int) -> None:
    """Moves a node. ``index`` is its target position counted before the node is lifted out."""
    source = _movable(doc, node_id)
    node = source.siblings[source.index]
    siblings, parent_type, parent = _resolve_parent(doc, parent_ref)
    if parent is not None and any(n.get("id") == parent.get("id") for n in walk_nodes([node])):
        raise EditError("An element cannot be moved inside itself.")
    if not can_contain(parent_type, node["type"]):
        raise EditError(f"{type_name(node['type']).capitalize()} cannot go inside {type_name(parent_type)}.")
    _check_index(index, len(siblings))
    if siblings is source.siblings and source.index < index:
        index -= 1
    source.siblings.pop(source.index)
    siblings.insert(index, node)


def shift_node(doc: Document, node_id: str, step: int) -> None:
    """Moves a node up (-1) or down (+1) among its siblings."""
    location = _movable(doc, node_id)
    target = location.index + step
    if not 0 <= target < len(location.siblings):
        raise EditError("It is already at the " + ("top." if step < 0 else "bottom."))
    location.siblings.insert(target, location.siblings.pop(location.index))


def duplicate_node(doc: Document, node_id: str) -> str:
    """Places a copy, with entirely new ids, straight after the original. Returns the new id."""
    location = _movable(doc, node_id)
    copy_ = clone_tree(location.siblings[location.index])
    _demote_extra_h1(doc, location.page, copy_)
    location.siblings.insert(location.index + 1, copy_)
    return copy_["id"]


def delete_node(doc: Document, node_id: str) -> str:
    """Removes a node and everything inside it. Returns the id that should be selected next."""
    location = _movable(doc, node_id)
    location.siblings.pop(location.index)
    if location.index < len(location.siblings):
        return location.siblings[location.index]["id"]
    if location.siblings:
        return location.siblings[-1]["id"]
    return location.parent["id"] if location.parent else ""


def place_for(doc: Document, node_type: str, selected_id: str, page_id: str) -> tuple[str, int] | None:
    """The natural place for a new element when none was pointed at, such as on paste.

    After the selection if it may sit there, else inside the selection, else after the nearest
    ancestor that allows it, else at the end of the page. None if nowhere fits.
    """
    chain = ancestors(doc, selected_id) if selected_id else []
    if chain:
        selected = chain[-1]
        location = locate(doc, selected_id)
        if selected.get("type") not in SHARED_TYPES:
            parent_type = location.parent.get("type") if location.parent else None
            if can_contain(parent_type, node_type):
                ref = location.parent["id"] if location.parent else f"{PAGE_PREFIX}{location.page['id']}"
                return ref, location.index + 1
        if can_contain(selected.get("type"), node_type):
            return selected["id"], len(selected.get("children", []))
        for node, inner in zip(reversed(chain[:-1]), reversed(chain[1:])):
            if can_contain(node.get("type"), node_type):
                children = node.get("children", [])
                position = next((i for i, c in enumerate(children) if c.get("id") == inner.get("id")), len(children) - 1)
                return node["id"], position + 1
    page = find_page(doc, page_id)
    if page is not None and can_contain(None, node_type):
        return f"{PAGE_PREFIX}{page_id}", len(page["nodes"])
    return None
