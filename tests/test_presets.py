"""The component catalogue: complete trees of primitive nodes, valid wherever they belong."""
from __future__ import annotations

from pathlib import Path

import pytest

from mulusa_theme_studio.components import registry
from mulusa_theme_studio.core.document import NODE_TYPES, validate_document
from mulusa_theme_studio.core.operations import PAGE_PREFIX, check_tree, insert_tree, place_for
from mulusa_theme_studio.render.html import RenderContext, render_node
from mulusa_theme_studio.render.site import write_site

ALL = [c.id for c in registry.catalogue()]
BRIEF = {
    "Structure": {"Section", "Container", "Two columns", "Three columns", "Divider"},
    "Content": {"Heading", "Paragraph", "Image", "Button", "Icon", "Spacer"},
    "Prebuilt sections": {"Hero", "About", "Services", "Features", "Testimonials", "Team", "Pricing", "Statistics", "Portfolio", "Call to action", "Contact", "FAQ"},
}


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def test_catalogue_covers_the_brief():
    for group, labels in BRIEF.items():
        have = {c.label for c in registry.catalogue() if c.group == group}
        assert labels <= have, group
    assert registry.groups() == list(BRIEF)


def test_shared_structures_are_not_droppable():
    assert not {c.node_type for c in registry.catalogue()} & {"header", "footer"}


def test_icons_exist():
    icons = Path(registry.__file__).parents[1] / "resources" / "icons"
    assert all((icons / f"{c.icon}.svg").is_file() for c in registry.catalogue())


def test_a_new_component_can_be_registered_without_touching_the_editor():
    component = registry.register(registry.ComponentDef("test-only", "Test", "Content", "star", "x", lambda: {"id": "a", "type": "divider", "props": {}, "style": {}}))
    try:
        assert registry.get("test-only") is component
    finally:
        registry._REGISTRY.pop("test-only")


@pytest.mark.parametrize("component_id", ALL)
def test_preset_is_a_valid_tree_with_fresh_unique_ids(component_id):
    build = registry.get(component_id).build
    first, second = build(), build()
    check_tree(first)
    ids = [n["id"] for n in walk(first)]
    assert len(ids) == len(set(ids))
    assert not set(ids) & {n["id"] for n in walk(second)}
    assert all(n["type"] in NODE_TYPES for n in walk(first))


@pytest.mark.parametrize("component_id", ALL)
def test_preset_inserts_validly_and_renders(template_doc, component_id, tmp_path):
    doc = template_doc
    tree = registry.get(component_id).build()
    page = doc["pages"][0]
    place = place_for(doc, tree["type"], page["nodes"][0]["children"][0]["id"], page["id"])
    assert place is not None
    node_id = insert_tree(doc, *place, tree)
    assert validate_document(doc) == []
    ctx = RenderContext(doc=doc, editor=True, current_page=page["id"])
    html = render_node(tree, ctx)
    assert f'data-mts-id="{node_id}"' in html
    for node in walk(tree):
        assert f'data-mts-id="{node["id"]}"' in html, node["type"]  # Independently selectable.
    site = write_site(doc, tmp_path / "plain")
    plain = site.pages[page["id"]].read_text(encoding="utf-8")
    assert "data-mts-id" not in plain and "mtsSelect" not in plain and "qwebchannel" not in plain.lower()


def test_hero_is_real_children_not_a_block():
    hero = registry.get("hero").build()
    assert hero["type"] == "section" and hero["props"]["role"] == "hero"
    types = {n["type"] for n in walk(hero)}
    assert {"columns", "container", "heading", "text", "button", "image"} <= types
    assert next(n for n in walk(hero) if n["type"] == "heading")["props"]["level"] == 1


@pytest.mark.parametrize("component_id", ALL)
def test_images_have_alt_text(component_id):
    for node in walk(registry.get(component_id).build()):
        if node["type"] == "image":
            assert node["props"]["alt"].strip()


def test_page_prefix_is_how_the_page_is_named():
    assert PAGE_PREFIX == "page:"
