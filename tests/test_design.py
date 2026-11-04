"""The global design system: tokens, palettes and their effect on rendered pages."""
from __future__ import annotations

import pytest

from mulusa_theme_studio.core import design
from mulusa_theme_studio.core.document import COLOR_TOKENS, validate_document, walk_nodes
from mulusa_theme_studio.core.history import History
from mulusa_theme_studio.core.properties import set_prop, set_style
from mulusa_theme_studio.render.css import tokens_css
from mulusa_theme_studio.render.site import write_site

KNOWN = frozenset({"Inter", "Lora"})


def test_colour_token_reaches_the_stylesheet(template_doc, tmp_path):
    design.set_color(template_doc, "primary", "#123456")
    css = (write_site(template_doc, tmp_path).root / "assets" / "style.css").read_text(encoding="utf-8")
    assert "--mts-primary:#123456" in css


def test_text_on_primary_stays_readable(template_doc):
    for value in ("#000000", "#ffffff", "#ffd400", "#14325c"):
        design.set_color(template_doc, "primary", value)
        colors = template_doc["tokens"]["colors"]
        assert design.contrast_ratio(colors["primary"], colors["on_primary"]) >= 4.5


@pytest.mark.parametrize("name,value", [("primary", "red"), ("primary", "$accent"), ("on_primary", "#000000"), ("bogus", "#000000"), ("text", "#12")])
def test_bad_colours_are_refused(template_doc, name, value):
    with pytest.raises(Exception):
        design.set_color(template_doc, name, value)


@pytest.mark.parametrize("palette", design.BUILTIN_PALETTES, ids=lambda p: p["name"])
def test_builtin_palettes_are_complete_and_readable(template_doc, palette):
    assert len(design.BUILTIN_PALETTES) >= 6
    design.apply_palette(template_doc, palette)
    colors = template_doc["tokens"]["colors"]
    assert set(COLOR_TOKENS) <= set(colors)
    assert design.contrast_ratio(colors["text"], colors["background"]) >= 7
    assert design.contrast_ratio(colors["muted"], colors["background"]) >= 4.5
    assert design.contrast_ratio(colors["text"], colors["surface"]) >= 4.5
    assert design.contrast_ratio(colors["primary"], colors["on_primary"]) >= 4.5
    assert design.contrast_ratio(colors["accent"], colors["on_accent"]) >= 4.5
    assert validate_document(template_doc) == []


def test_custom_palette_is_saved_in_the_document(template_doc):
    count = len(template_doc["palettes"])
    design.set_color(template_doc, "accent", "#ff0066")
    design.save_palette(template_doc, "Mine")
    design.save_palette(template_doc, "Mine")
    assert len(template_doc["palettes"]) == count + 1
    assert template_doc["palettes"][-1]["colors"]["accent"] == "#ff0066"
    with pytest.raises(design.DesignError):
        design.save_palette(template_doc, "  ")


def test_fonts_must_be_bundled(template_doc, tmp_path):
    design.set_font(template_doc, "heading", "Lora", KNOWN)
    assert template_doc["tokens"]["fonts"]["heading"] == "Lora"
    with pytest.raises(design.DesignError):
        design.set_font(template_doc, "heading", "Comic Papyrus", KNOWN)
    site = write_site(template_doc, tmp_path)
    assert list((site.root / "assets" / "fonts").glob("lora*"))
    assert "'Lora'" in (site.root / "assets" / "style.css").read_text(encoding="utf-8")


def test_a_font_on_one_element_is_bundled_with_the_site(template_doc, tmp_path):
    heading = next(n for n in walk_nodes(template_doc["pages"][0]["nodes"]) if n["type"] == "heading")
    set_style(template_doc, heading["id"], "font_family", "Lora")
    site = write_site(template_doc, tmp_path)
    css = (site.root / "assets" / "style.css").read_text(encoding="utf-8")
    assert "font-family:'Lora'" in css and "@font-face{font-family:'Lora'" in css
    assert (site.root / "assets" / "fonts").glob("lora*")


@pytest.mark.parametrize("key,value,expected", [("base", 18, "--mts-body-size:18"), ("body_line", 1.8, "--mts-body-line:1.8"), ("heading_weight", 800, "--mts-heading-weight:800")])
def test_typography_tokens_propagate(template_doc, key, value, expected):
    design.set_type(template_doc, key, value)
    assert expected in tokens_css(template_doc["tokens"])


def test_heading_scale_changes_heading_sizes(template_doc):
    before = tokens_css(template_doc["tokens"])
    design.set_type(template_doc, "ratio", 1.6)
    assert tokens_css(template_doc["tokens"]) != before


@pytest.mark.parametrize("key,value", [("base", 4), ("ratio", 9), ("body_line", "tall"), ("heading_weight", 5000), ("nope", 1)])
def test_bad_typography_is_refused(template_doc, key, value):
    with pytest.raises(design.DesignError):
        design.set_type(template_doc, key, value)


def test_shape_and_spacing_tokens_propagate(template_doc):
    design.set_shape(template_doc, "card_radius", "14")
    design.set_shape(template_doc, "input_radius", "2px")
    design.set_shape(template_doc, "button_radius", "20")
    design.set_spacing(template_doc, "section", "120")
    design.set_spacing(template_doc, "space_m", "30")
    css = tokens_css(template_doc["tokens"])
    for token in ("--mts-card-radius:14px", "--mts-input-radius:2px", "--mts-btn-radius:20px", "--mts-section:120px", "--mts-space-m:30px"):
        assert token in css
    for setter, key in ((design.set_shape, "nope"), (design.set_spacing, "nope")):
        with pytest.raises(design.DesignError):
            setter(template_doc, key, "1px")
    with pytest.raises(Exception):
        design.set_spacing(template_doc, "gap", "lots")


def test_older_projects_get_sensible_defaults(template_doc):
    for key in ("card_radius", "input_radius"):
        template_doc["tokens"]["shape"].pop(key, None)
    css = tokens_css(template_doc["tokens"])
    radius = template_doc["tokens"]["shape"]["radius"]
    assert f"--mts-card-radius:{radius}" in css and "--mts-space-s:12px" in css


def test_elements_using_a_token_follow_it(template_doc, tmp_path):
    heading = next(n for n in walk_nodes(template_doc["pages"][0]["nodes"]) if n["type"] == "heading")
    set_style(template_doc, heading["id"], "color", "$accent")
    css = (write_site(template_doc, tmp_path).root / "assets" / "style.css").read_text(encoding="utf-8")
    assert "color:var(--mts-accent)" in css
    design.set_color(template_doc, "accent", "#00aa55")
    css = (write_site(template_doc, tmp_path).root / "assets" / "style.css").read_text(encoding="utf-8")
    assert "--mts-accent:#00aa55" in css and "color:var(--mts-accent)" in css


@pytest.mark.parametrize("tone", ["default", "surface", "inverse", "primary", "accent", "image"])
def test_section_tone_renders_its_class(template_doc, tone, tmp_path):
    page = template_doc["pages"][0]
    section = page["nodes"][1]
    set_prop(template_doc, section["id"], "tone", tone)
    html = write_site(template_doc, tmp_path).pages[page["id"]].read_text(encoding="utf-8")
    assert f"mts-tone-{tone}" in html


def test_design_edits_undo_exactly(template_doc):
    history = History(template_doc)
    live = history.document
    primary = live["tokens"]["colors"]["primary"]
    on = live["tokens"]["colors"]["on_primary"]
    history.apply("Colour", lambda d: design.set_color(d, "primary", "#ffd400"))
    history.apply("Palette", lambda d: design.apply_palette(d, design.BUILTIN_PALETTES[0]))
    history.undo()
    assert live["tokens"]["colors"]["primary"] == "#ffd400"
    history.undo()
    assert live["tokens"]["colors"]["primary"] == primary and live["tokens"]["colors"]["on_primary"] == on
