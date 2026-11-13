"""Fifty-five templates, and proof that they are valid, readable and genuinely different."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import combinations

import pytest
from PIL import Image

from mulusa_theme_studio.core.document import media_refs, validate_document, walk_document
from mulusa_theme_studio.core.errors import TemplateError
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.render.css import STYLE_PROPERTIES
from mulusa_theme_studio.render.fonts import catalog

LIB = TemplateLibrary()
DOCS = {t.id: json.loads(t.file.read_text(encoding="utf-8")) for t in LIB.templates}
EXPECTED = {"corporate", "fashion", "music", "art", "news", "construction", "education", "hospitality", "technology", "real_estate"}
STARTERS = {"personal", "healthcare", "community", "automotive", "shop"}   # one starter each, added with the resource library


def _lum(c):
    def f(v):
        s = v / 255
        return s / 12.92 if s <= .03928 else ((s + .055) / 1.055) ** 2.4

    return .2126 * f(int(c[1:3], 16)) + .7152 * f(int(c[3:5], 16)) + .0722 * f(int(c[5:7], 16))


def ratio(a, b):
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + .05) / (y + .05)


def home_layout(doc):
    """The order of section roles plus each section's structure: the layout's fingerprint."""
    def shape(node):
        return (node["type"], node["props"].get("columns"), tuple(shape(c) for c in node.get("children", [])))

    return tuple((n["props"].get("role"), shape(n)) for n in doc["pages"][0]["nodes"])


def test_sixty_nine_templates_in_sixteen_categories():
    counts = Counter(t.category for t in LIB.templates)
    assert set(counts) == EXPECTED | STARTERS | {"onepage"} and len(LIB.templates) == 69
    assert {counts[c] for c in EXPECTED} == {5} and {counts[c] for c in STARTERS} == {1} and counts["onepage"] == 14
    assert LIB.problems == []


def test_named_examples_from_the_brief_exist():
    names = {t.name for t in LIB.templates}
    assert {"Corporate Classic", "Modern Consulting", "Executive Minimal", "Professional Agency", "Corporate Dark",
            "Luxury Editorial", "Modern Boutique", "Streetwear", "Minimal Fashion", "Fashion Magazine",
            "Artist Portfolio", "Record Label", "Concert and Events", "Music Magazine", "DJ and Producer"} <= names


SITES = {i: d for i, d in DOCS.items() if not i.startswith("onepage/")}    # full websites
ONEPAGE = {i: d for i, d in DOCS.items() if i.startswith("onepage/")}     # launch, maintenance and one-page templates


@pytest.mark.parametrize("tid", sorted(SITES))
def test_each_template_is_valid_and_complete(tid):
    doc = DOCS[tid]
    assert validate_document(doc) == []
    assert [p["id"] for p in doc["pages"]] == ["home", "about", "services", "portfolio", "blog", "contact"]
    assert all(p["nodes"] for p in doc["pages"])
    assert len(doc["navigation"]["primary"]) == 5
    for name in (doc["tokens"]["fonts"]["heading"], doc["tokens"]["fonts"]["body"], *doc["tokens"]["fonts"]["extra"]):
        assert name in catalog(), name


@pytest.mark.parametrize("tid", sorted(DOCS))
def test_images_are_placeholder_references_never_embedded(tid):
    refs = list(media_refs(DOCS[tid]))
    assert (refs or tid in ONEPAGE) and all(r["kind"] == "placeholder" for r in refs)
    assert "data:image" not in json.dumps(DOCS[tid])


@pytest.mark.parametrize("tid", sorted(DOCS))
def test_text_is_readable(tid):
    c = DOCS[tid]["tokens"]["colors"]
    assert ratio(c["text"], c["background"]) >= 7, "body text"
    assert ratio(c["muted"], c["background"]) >= 4.5, "muted text"
    assert ratio(c["muted"], c["surface"]) >= 4.5, "muted on surface"
    assert ratio(c["on_primary"], c["primary"]) >= 4.5, "button text"
    assert ratio(c["on_accent"], c["accent"]) >= 4.5, "accent text"


@pytest.mark.parametrize("tid", sorted(DOCS))
def test_styles_only_use_known_properties(tid):
    for node in walk_document(DOCS[tid]):
        unknown = set(node.get("style", {})) - STYLE_PROPERTIES
        for over in node.get("responsive", {}).values():
            unknown |= set(over.get("style", {})) - STYLE_PROPERTIES
        assert not unknown, (node["id"], unknown)


@pytest.mark.parametrize("tid", sorted(DOCS))
def test_every_section_over_a_photo_uses_the_image_tone(tid):
    for node in walk_document(DOCS[tid]):
        if isinstance(node["props"].get("background"), dict):
            assert node["props"].get("tone") == "image", node["id"]


def test_no_two_templates_share_a_home_layout():
    layouts = Counter(home_layout(d) for d in SITES.values())
    assert max(layouts.values()) == 1


def _living(doc) -> tuple:
    """What makes a one-page template look like itself: its drawing, its background motion and its parts."""
    nodes = list(walk_document(doc))
    return (tuple(n["props"]["name"] for n in nodes if n["type"] == "illustration"),
            tuple(n["props"].get("ambient", "") for n in nodes if n["type"] == "section"),
            home_layout(doc))


@pytest.mark.parametrize("tid", sorted(ONEPAGE))
def test_each_one_page_template_is_a_valid_single_living_page(tid):
    doc = ONEPAGE[tid]
    assert validate_document(doc) == []
    assert [p["id"] for p in doc["pages"]] == ["home"] and doc["pages"][0]["nodes"]
    types = {n["type"] for n in walk_document(doc)}
    assert types & {"illustration", "countdown", "progress"}, "a one-page template has a living element"
    assert any(n["props"].get("ambient") for n in walk_document(doc) if n["type"] == "section") or "illustration" in types
    for name in (doc["tokens"]["fonts"]["heading"], doc["tokens"]["fonts"]["body"], *doc["tokens"]["fonts"]["extra"]):
        assert name in catalog(), name


def test_one_page_templates_cover_many_trades_and_each_looks_different():
    looks = Counter(_living(d) for d in ONEPAGE.values())
    assert max(looks.values()) == 1
    drawings = {name for d in ONEPAGE.values() for name in _living(d)[0]}
    assert len(drawings) >= 10
    assert {"music", "ict", "security", "construction", "maintenance"} <= {w for i in ONEPAGE for w in i.split("/")[1].split("-")}


def test_no_two_templates_share_a_palette_or_font_and_palette_identity():
    palettes = Counter(json.dumps(d["tokens"]["colors"], sort_keys=True) for d in DOCS.values())
    assert max(palettes.values()) == 1


def test_within_a_category_each_template_has_its_own_look():
    for category in EXPECTED:
        docs = [(i, d) for i, d in DOCS.items() if i.startswith(category + "/")]
        for (a, x), (b, y) in combinations(docs, 2):
            assert (x["tokens"]["fonts"]["heading"], x["tokens"]["fonts"]["body"]) != (y["tokens"]["fonts"]["heading"], y["tokens"]["fonts"]["body"]), (a, b)
            ca, cb = x["tokens"]["colors"]["primary"], y["tokens"]["colors"]["primary"]
            assert (ca, x["tokens"]["colors"]["background"]) != (cb, y["tokens"]["colors"]["background"]), (a, b)


def test_template_library_uses_real_variety():
    headers = Counter(d["site"]["header"]["props"]["layout"] for d in DOCS.values())
    assert len(headers) >= 5
    fonts = {d["tokens"]["fonts"]["heading"] for d in DOCS.values()}
    assert len(fonts) >= 18
    dark = [i for i, d in DOCS.items() if _lum(d["tokens"]["colors"]["background"]) < .1]
    light = [i for i, d in DOCS.items() if _lum(d["tokens"]["colors"]["background"]) > .5]
    assert len(dark) >= 8 and len(light) >= 25


def test_every_template_has_a_distinct_real_thumbnail():
    seen = set()
    for info in LIB.templates:
        assert info.thumbnail.is_file(), info.id
        with Image.open(info.thumbnail) as image:
            assert image.size == (640, 480)
            assert len(image.convert("RGB").getcolors(1 << 24)) > 200, f"{info.id} looks blank"
        seen.add(hashlib.sha1(info.thumbnail.read_bytes()).hexdigest())
    assert len(seen) == 69


def test_new_templates_need_only_a_new_folder(tmp_path):
    (tmp_path / "categories.json").write_text(json.dumps([{"id": "c", "name": "C"}]), encoding="utf-8")
    folder = tmp_path / "c" / "t"
    folder.mkdir(parents=True)
    doc = dict(DOCS["corporate/corporate-classic"])
    doc["meta"] = {**doc["meta"], "id": "c/t", "template_name": "New One"}
    (folder / "template.json").write_text(json.dumps(doc), encoding="utf-8")
    library = TemplateLibrary(tmp_path)
    assert [t.name for t in library.templates] == ["New One"]
    assert library.load("c/t")["meta"]["id"] == "c/t"


def test_damaged_template_is_reported_not_fatal(tmp_path):
    (tmp_path / "categories.json").write_text(json.dumps([{"id": "c", "name": "C"}]), encoding="utf-8")
    (tmp_path / "c" / "bad").mkdir(parents=True)
    (tmp_path / "c" / "bad" / "template.json").write_text("{oops", encoding="utf-8")
    library = TemplateLibrary(tmp_path)
    assert library.templates == [] and "bad" in library.problems[0]


def test_missing_index_and_template_errors(tmp_path):
    assert TemplateLibrary(tmp_path).problems
    with pytest.raises(TemplateError):
        LIB.get("no/such")


def test_search_and_filter():
    assert {t.name for t in LIB.search("streetwear")} == {"Streetwear"}
    assert len(LIB.search("", "music")) == 5
    assert LIB.search("zzzzz") == []
