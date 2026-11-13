"""What may contain what. This is the single source of the rules.

The document validator and every edit operation use it directly. The canvas receives
it as data for its drop indicators, and its answer is never trusted: Python checks
again before anything changes.
"""
from __future__ import annotations

CONTENT = frozenset({"heading", "text", "richtext", "image", "gallery", "video", "icon", "button", "link", "faq_item", "contact_form",
                     "illustration", "countdown", "progress"})
LAYOUT = frozenset({"container", "columns", "row"})
ROOT_CHILDREN = frozenset({"section"})  # What a page may hold directly.
# Filled by the publishing system when the site runs. A post field also needs a post around it,
# which validate_document checks: inside a posts list, or on a post template page.
DYNAMIC = frozenset({"query", "post_field"})

CHILD_RULES: dict[str, frozenset[str]] = {
    # Text directly in a section would ignore the content width, so it goes in a container.
    "section": LAYOUT | {"divider", "image", "gallery", "video", "query"},
    "footer": LAYOUT | {"divider"},
    "container": LAYOUT | CONTENT | DYNAMIC | {"divider"},
    "columns": LAYOUT | CONTENT | DYNAMIC,
    "row": frozenset({"container", "row", "post_field"}) | CONTENT,
    "query": frozenset({"container"}),  # The card, repeated once for each post.
}
# Exactly one of each per site, shared by every page: never inserted, moved or deleted.
SHARED_TYPES = frozenset({"header", "footer"})


def can_contain(parent_type: str | None, child_type: str) -> bool:
    """Whether a node type may hold a child type. ``None`` means the page itself."""
    if parent_type is None:
        return child_type in ROOT_CHILDREN
    return child_type in CHILD_RULES.get(parent_type, frozenset())


def is_container(node_type: str) -> bool:
    return node_type in CHILD_RULES


def rules_as_data() -> dict:
    """The rules as plain data, for the canvas's visual feedback."""
    return {"root": sorted(ROOT_CHILDREN), "children": {k: sorted(v) for k, v in CHILD_RULES.items()}}
