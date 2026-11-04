"""Property edits and their history, with no interface involved."""
from __future__ import annotations

import copy

import pytest

from mulusa_theme_studio.core.document import validate_document, walk_nodes
from mulusa_theme_studio.core.errors import StudioError
from mulusa_theme_studio.core.history import History
from mulusa_theme_studio.core.properties import box_values, clear_overrides, set_background_overlay, set_box_side, set_prop, set_style
from mulusa_theme_studio.core.styles import StyleError, check_style, normalize_color, normalize_length
from mulusa_theme_studio.render.css import declarations


def first(doc, kind):
    return next(n for p in doc["pages"] for n in walk_nodes(p["nodes"]) if n["type"] == kind)


@pytest.mark.parametrize("prop,value,stored", [
    ("font_size", "40", "40px"), ("font_size", "2rem", "2rem"), ("font_size", "clamp(2rem,4vw,3rem)", "clamp(2rem,4vw,3rem)"),
    ("color", "#ABC", "#aabbcc"), ("color", "$primary", "$primary"), ("background", "linear-gradient(90deg,$primary,#000000)", "linear-gradient(90deg,$primary,#000000)"),
    ("opacity", ".5", ".5"), ("font_family", "Inter", "Inter"), ("margin_top", "-12", "-12px"), ("border", "1px solid $c-border", "1px solid $c-border"),
    ("gap", "12px 20px", "12px 20px"), ("padding", "4 8", "4px 8px"), ("object_fit", "contain", "contain"), ("text_align", "center", "center"),
])
def test_good_values_are_normalised(prop, value, stored):
    assert check_style(prop, value) == stored


@pytest.mark.parametrize("prop,value", [
    ("color", "red;}body{display:none"), ("color", "not-a-colour"), ("font_size", "big"), ("font_size", "-4px"),
    ("background", "url(http://evil/x.png)"), ("background_image", "expression(alert(1))"), ("opacity", "2"),
    ("font_family", "<script>"), ("text_align", "sideways"), ("border", "thick"), ("not_a_property", "1"),
    ("object_fit", "explode"), ("width", "calc(1px;}"), ("color", True), ("color", None),
])
def test_bad_values_are_refused(prop, value):
    with pytest.raises(StyleError):
        check_style(prop, value)


def test_every_template_and_preset_style_passes_the_stricter_rules(library):
    from mulusa_theme_studio.components import registry
    from mulusa_theme_studio.core.document import walk_document

    def check(node):
        for style in [node.get("style", {})] + [o.get("style", {}) for o in node.get("responsive", {}).values()]:
            for key, value in style.items():
                check_style(key, value)

    for entry in library.templates:
        for node in walk_document(library.load(entry.id)):
            check(node)
    for component in registry.catalogue():
        for node in walk_nodes([component.build()]):
            check(node)


def test_helpers():
    assert normalize_length("0") == "0" and normalize_length("$gap") == "$gap"
    assert normalize_color("abcdef") == "#abcdef"


def test_update_text_level_and_refuse_bad_props(template_doc):
    heading = first(template_doc, "heading")
    set_prop(template_doc, heading["id"], "text", "New title")
    set_prop(template_doc, heading["id"], "level", 3)
    assert heading["props"]["text"] == "New title" and heading["props"]["level"] == 3
    for key, value in (("level", 9), ("level", True), ("text", 5), ("nonsense", "x"), ("html", "<b>x</b>")):
        with pytest.raises(StudioError):
            set_prop(template_doc, heading["id"], key, value)


def test_links_are_checked(template_doc):
    button = first(template_doc, "button")
    set_prop(template_doc, button["id"], "href", {"page": "about"})
    set_prop(template_doc, button["id"], "href", "https://example.com")
    assert button["props"]["href"] == "https://example.com"
    for bad in ("javascript:alert(1)", {"page": ""}, {"evil": 1}):
        with pytest.raises(StudioError):
            set_prop(template_doc, button["id"], "href", bad)


def test_tones_are_a_closed_list(template_doc):
    section = first(template_doc, "section")
    with pytest.raises(StudioError):
        set_prop(template_doc, section["id"], "tone", "neon")
    section["props"]["tone"] = "neon"
    assert any("tone" in issue for issue in validate_document(template_doc))


def test_a_section_over_a_photo_keeps_the_image_tone(template_doc):
    section = first(template_doc, "section")
    section["props"].update(tone="image", background={"media": {"kind": "placeholder", "seed": "x"}})
    with pytest.raises(StudioError):
        set_prop(template_doc, section["id"], "tone", "default")
    section["props"]["tone"] = "default"
    assert any("image tone" in issue for issue in validate_document(template_doc))


def test_device_override_does_not_touch_the_desktop_style(template_doc):
    heading = first(template_doc, "heading")
    before = copy.deepcopy(heading["style"])
    set_style(template_doc, heading["id"], "font_size", "20", "mobile")
    assert heading["style"] == before and heading["responsive"]["mobile"]["style"]["font_size"] == "20px"
    set_style(template_doc, heading["id"], "font_size", None, "mobile")
    assert "mobile" not in heading.get("responsive", {})


def test_clearing_overrides_keeps_responsive_props(template_doc):
    columns = next(n for n in walk_nodes(template_doc["pages"][0]["nodes"]) if n["type"] == "columns" and n.get("responsive", {}).get("tablet"))
    set_style(template_doc, columns["id"], "gap", "4", "tablet")
    clear_overrides(template_doc, columns["id"], "tablet")
    assert "style" not in columns["responsive"]["tablet"] and "props" in columns["responsive"]["tablet"]


def test_one_side_of_a_shorthand_keeps_the_others(template_doc):
    heading = first(template_doc, "heading")
    heading["style"]["padding"] = "10px 20px"
    assert box_values(heading["style"], "padding") == {"top": "10px", "right": "20px", "bottom": "10px", "left": "20px"}
    set_box_side(template_doc, heading["id"], "padding", "top", "5")
    assert "padding" not in heading["style"]
    assert box_values(heading["style"], "padding") == {"top": "5px", "right": "20px", "bottom": "10px", "left": "20px"}
    css = declarations(heading["style"])
    assert "padding-top:5px" in css and "padding-left:20px" in css


def test_overlay(template_doc):
    section = first(template_doc, "section")
    set_background_overlay(template_doc, section["id"], "#000000", .4)
    assert section["props"]["background"]["overlay"] == "rgba(0,0,0,0.40)"
    set_background_overlay(template_doc, section["id"], "#000000", 0)
    assert "background" not in section["props"]


def test_unsafe_style_in_a_hand_edited_file_fails_validation(template_doc):
    first(template_doc, "heading")["style"]["color"] = "red;}*{display:none"
    assert validate_document(template_doc)
    template_doc_tokens = template_doc["tokens"]
    first(template_doc, "heading")["style"].pop("color")
    template_doc_tokens["shape"]["radius"] = "1px;}*{display:none"
    assert any("unsafe" in issue for issue in validate_document(template_doc))


# History ---------------------------------------------------------------------
def slide(history, node_id, values):
    for value in values:
        history.apply("Size", lambda d, v=value: set_style(d, node_id, "font_size", v), merge=f"size:{node_id}")


def test_a_slider_drag_is_one_undo_step(template_doc):
    history = History(template_doc)
    node = first(template_doc, "heading")
    original = copy.deepcopy(node["style"])
    slide(history, node["id"], range(24, 41))
    assert history.undo_depth == 1 and node["style"]["font_size"] == "40px"
    history.undo()
    assert first(history.document, "heading")["style"] == original
    history.redo()
    assert first(history.document, "heading")["style"]["font_size"] == "40px"


def test_sealing_starts_a_new_step(template_doc):
    history = History(template_doc)
    node = first(template_doc, "heading")
    slide(history, node["id"], [24, 30])
    history.seal()
    slide(history, node["id"], [31, 32])
    assert history.undo_depth == 2
    history.undo()
    assert first(history.document, "heading")["style"]["font_size"] == "30px"


def test_a_different_property_starts_a_new_step(template_doc):
    history = History(template_doc)
    node = first(template_doc, "heading")
    slide(history, node["id"], [24, 30])
    history.apply("Colour", lambda d: set_style(d, node["id"], "color", "#112233"), merge="colour")
    assert history.undo_depth == 2


def test_dragging_back_to_the_start_leaves_nothing_to_undo(template_doc):
    history = History(template_doc)
    node = first(template_doc, "heading")
    original = node["style"].get("font_size", "")
    slide(history, node["id"], ["30"])
    history.apply("Size", lambda d: set_style(d, node["id"], "font_size", original or None), merge=f"size:{node['id']}")
    assert history.undo_depth == 0 and not history.can_undo


def test_failed_change_inside_a_run_rolls_back_only_itself(template_doc):
    history = History(template_doc)
    node = first(template_doc, "heading")
    slide(history, node["id"], [24, 30])
    with pytest.raises(StudioError):
        history.apply("Size", lambda d: set_style(d, node["id"], "font_size", "huge"), merge=f"size:{node['id']}")
    live = first(history.document, "heading")
    assert live["style"]["font_size"] == "30px" and history.undo_depth == 1
