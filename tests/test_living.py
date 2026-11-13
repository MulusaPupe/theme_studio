"""Living elements: animated illustrations, countdowns, progress bars, ambient backgrounds and glass cards,
and the one-page templates built from them. Each is checked on the canvas renderer and in both exports."""
import re
import zipfile
from datetime import datetime, timezone

import pytest

from mulusa_theme_studio.core import properties
from mulusa_theme_studio.core.document import walk_document
from mulusa_theme_studio.core.errors import StudioError
from mulusa_theme_studio.core.styles import check_style
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.exporters import ERROR
from mulusa_theme_studio.exporters.static import StaticExporter, StaticOptions, check_site
from mulusa_theme_studio.exporters.wordpress import ExportOptions, WordPressExporter
from mulusa_theme_studio.exporters.wordpress.check import check_theme
from mulusa_theme_studio.render.html import countdown_parts, illustration_markup, progress_inner
from mulusa_theme_studio.render.illustrations import ILLUSTRATIONS, illustration_svg, static_svg
from mulusa_theme_studio.render.site import PAGE_JS as PAGE_JS_FILE

PAGE_JS = PAGE_JS_FILE.read_text(encoding="utf-8")

LIB = TemplateLibrary()
COUNTDOWN_PAGE = "onepage/ict-coming-soon"


def _node(doc, kind):
    return next(n for n in walk_document(doc) if n["type"] == kind)


# Illustrations -----------------------------------------------------------------------------------------------

def test_there_are_many_drawings_across_trades():
    assert len(ILLUSTRATIONS) >= 30
    groups = {i.group for i in ILLUSTRATIONS.values()}
    assert {"Business", "Technology", "Security", "Music", "Construction"} <= groups


@pytest.mark.parametrize("name", sorted(ILLUSTRATIONS))
def test_each_drawing_is_safe_svg_that_takes_the_site_colours(name):
    svg = illustration_svg(name)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'viewBox="0 0 240 180"' in svg
    lowered = svg.lower()
    assert "<script" not in lowered and "href" not in lowered and not re.search(r"\son\w+=", lowered)
    assert not re.search(r'fill="#|stroke="#', svg), "colours come from the site, not hard-coded"
    still = static_svg(name, {"primary": "#123456", "accent": "#ff8800", "text": "#111111"})
    assert "class=" not in still and "#123456" in still or "#ff8800" in still


def test_an_unknown_drawing_falls_back_and_labels_are_escaped():
    assert illustration_svg("no-such-thing") == illustration_svg("gears")
    still, svg = illustration_markup({"name": "rocket", "animate": False, "aria_label": 'A "rocket" <launch>'})
    assert still == " mts-still"
    assert "<launch>" not in svg and 'role="img"' in svg


def test_illustration_props_are_validated():
    doc = LIB.load(COUNTDOWN_PAGE)
    node = _node(doc, "illustration")
    properties.set_prop(doc, node["id"], "name", "vinyl")
    assert node["props"]["name"] == "vinyl"
    for bad in ("../x", "Vinyl!", "<svg>"):
        with pytest.raises(StudioError):
            properties.set_prop(doc, node["id"], "name", bad)


# Countdown ---------------------------------------------------------------------------------------------------

def test_countdown_works_out_the_time_left_in_the_chosen_time_zone():
    props = {"target": "2027-03-01T08:00", "utc_offset": "+02:00"}
    parts = countdown_parts(props, now=datetime(2027, 2, 28, 5, 59, 30, tzinfo=timezone.utc))
    assert parts["iso"] == "2027-03-01T08:00:00+02:00"
    assert parts["when"] == "1 March 2027, 08:00 UTC+02:00"
    assert parts["remaining"] == (1, 0, 0, 30)
    after = countdown_parts(props, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert after["remaining"] == (0, 0, 0, 0)
    assert countdown_parts({"target": "soon"})["remaining"] is None


def test_countdown_props_are_validated():
    doc = LIB.load(COUNTDOWN_PAGE)
    node = _node(doc, "countdown")
    properties.set_prop(doc, node["id"], "target", "2028-01-01T00:00")
    properties.set_prop(doc, node["id"], "utc_offset", "+05:30")
    for key, bad in (("target", "tomorrow"), ("target", "2028-01-01 00:00<script>"), ("utc_offset", "+25:00"), ("done_text", "x" * 300)):
        with pytest.raises(StudioError):
            properties.set_prop(doc, node["id"], key, bad)


def test_the_countdown_script_is_small_and_only_touches_its_own_cells():
    assert "data-mts-countdown" in PAGE_JS
    for forbidden in ("fetch(", "XMLHttpRequest", "eval(", "innerHTML", "document.write", "localStorage", "import("):
        assert forbidden not in PAGE_JS, forbidden


# Progress, glass and ambient ---------------------------------------------------------------------------------

def test_progress_shows_a_value_or_a_loading_bar():
    inner, cls, aria = progress_inner({"mode": "value", "value": 72, "label": "Built", "show_value": True})
    assert "72%" in inner and 'aria-valuenow="72"' in aria
    inner, cls, aria = progress_inner({"mode": "loading", "label": "Loading"})
    assert "loading" in cls and "aria-valuenow" not in aria
    _, _, aria = progress_inner({"mode": "value", "value": 900})
    assert 'aria-valuenow="60"' in aria                     # a damaged value never breaks the page


def test_glass_blur_accepts_only_safe_filters():
    assert check_style("backdrop_filter", "blur(14px) saturate(140%)") == "blur(14px) saturate(140%)"
    assert check_style("backdrop_filter", "none") == "none"
    for bad in ("url(#x)", "blur(14px); background:red", "blur(999px)", "expression(alert(1))"):
        with pytest.raises(StudioError):
            check_style("backdrop_filter", bad)


def test_ambient_backgrounds_are_a_closed_list():
    doc = LIB.load(COUNTDOWN_PAGE)
    section = doc["pages"][0]["nodes"][0]
    for value in ("aurora", "grid", "stars", "waves"):
        properties.set_prop(doc, section["id"], "ambient", value)
    with pytest.raises(StudioError):
        properties.set_prop(doc, section["id"], "ambient", "fireworks")


# Exports -----------------------------------------------------------------------------------------------------

def _static(doc, tmp_path):
    return StaticExporter().export(doc, tmp_path / "no-project", tmp_path / "out", StaticOptions(site_name="Live", form_email="hello@example.com"))


def test_a_countdown_page_exports_as_static_html_with_only_the_studio_script(tmp_path):
    result = _static(LIB.load(COUNTDOWN_PAGE), tmp_path)
    assert [str(i) for i in check_site(result.folder) if i.severity == ERROR] == []
    html = (result.folder / "index.html").read_text(encoding="utf-8")
    assert html.count("<script") == 1 and '<script src="assets/mulusa.js" defer></script>' in html
    assert (result.folder / "assets" / "mulusa.js").read_text(encoding="utf-8") == PAGE_JS
    assert re.search(r'data-mts-countdown="2\d{3}-\d\d-\d\dT\d\d:\d\d:00[+-]\d\d:\d\d"', html)
    assert "mts-illus" in html and "mts-ambient" in html


def test_a_changed_or_extra_script_fails_the_static_check(tmp_path):
    result = _static(LIB.load(COUNTDOWN_PAGE), tmp_path)
    (result.folder / "assets" / "mulusa.js").write_text("alert(1)", encoding="utf-8")
    assert any(i.severity == ERROR and "countdown" in i.message for i in check_site(result.folder))
    result2 = _static(LIB.load(COUNTDOWN_PAGE), tmp_path / "again")
    page = result2.folder / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace("</body>", "<script>alert(1)</script></body>"), encoding="utf-8")
    assert any(i.severity == ERROR and "contains a script" in i.message for i in check_site(result2.folder))


def test_pages_without_a_countdown_get_no_script(tmp_path):
    result = _static(LIB.load("onepage/maintenance-gears"), tmp_path)
    if any(n["type"] == "countdown" for n in walk_document(LIB.load("onepage/maintenance-gears"))):
        pytest.skip("this template has a countdown")
    assert "<script" not in (result.folder / "index.html").read_text(encoding="utf-8")
    assert not (result.folder / "assets" / "mulusa.js").exists()


def test_a_countdown_page_exports_as_a_valid_wordpress_theme_that_enqueues_the_script(tmp_path):
    result = WordPressExporter().export(LIB.load(COUNTDOWN_PAGE), tmp_path / "no-project", tmp_path / "out",
                                        ExportOptions(theme_name="Live Theme", author="A Tester"))
    root = tmp_path / "unpacked"
    with zipfile.ZipFile(result.output) as archive:
        archive.extractall(root)
    theme = root / "live-theme"
    assert [str(i) for i in check_theme(theme, slug="live-theme") if i.severity == ERROR] == []
    assert (theme / "assets" / "js" / "mulusa.js").read_text(encoding="utf-8") == PAGE_JS
    php = (theme / "functions.php").read_text(encoding="utf-8")
    assert "wp_enqueue_script(" in php and "mulusa.js" in php
    markup = "".join(p.read_text(encoding="utf-8") for p in [*theme.rglob("*.html"), *theme.glob("patterns/*.php")])
    assert "data-mts-countdown" in markup and "mts-illus" in markup and "mts-ambient" in markup


def test_themes_without_a_countdown_enqueue_no_script(tmp_path):
    result = WordPressExporter().export(LIB.load("corporate/corporate-classic"), tmp_path / "no-project", tmp_path / "out",
                                        ExportOptions(theme_name="Plain Theme", author="A Tester"))
    with zipfile.ZipFile(result.output) as archive:
        names = archive.namelist()
        php = archive.read("plain-theme/functions.php").decode()
    assert "wp_enqueue_script(" not in php and not any(n.endswith("mulusa.js") for n in names)


@pytest.mark.parametrize("tid", sorted(t.id for t in LIB.templates if t.id.startswith("onepage/")))
def test_every_one_page_template_passes_both_export_checks(tid, tmp_path):
    doc = LIB.load(tid)
    assert [str(i) for i in WordPressExporter().check(doc, tmp_path) if i.severity == ERROR] == []
    result = _static(doc, tmp_path)
    assert [str(i) for i in check_site(result.folder) if i.severity == ERROR] == []


# Library -----------------------------------------------------------------------------------------------------

def test_illustrations_are_in_the_resource_library():
    from mulusa_theme_studio.library.catalogue import Library
    library = Library()
    found = library.search("music", kind="illustration")
    assert found and all(r.licence and r.data["name"] in ILLUSTRATIONS for r in found)


# Motion in the full templates ------------------------------------------------------------------------------

FULL = [t.id for t in LIB.templates if not t.id.startswith("onepage/")]


@pytest.mark.parametrize("tid", FULL)
def test_living_backgrounds_stay_calm_and_off_photographs(tid):
    doc = LIB.load(tid)
    for page in doc["pages"]:
        living = [s for s in page["nodes"] if s["type"] == "section" and s["props"].get("ambient")]
        assert len(living) <= 1, f"{page['id']}: one living background per page"
        for section in living:
            assert not isinstance(section["props"].get("background"), dict), "a photo section becomes a WordPress cover block"


def test_template_drawings_are_all_or_nothing_and_never_repeat_in_a_grid():
    with_art = 0
    for tid in FULL:
        for page in LIB.load(tid)["pages"]:
            for node in walk_document({"pages": [page]}):
                if node["type"] != "columns":
                    continue
                cards = [c for c in node.get("children", []) if c["type"] == "container"]
                marks = [next((k for k in c.get("children", []) if k["type"] in ("illustration", "icon")), None) for c in cards]
                kinds = {m["type"] for m in marks if m}
                assert len(kinds) <= 1, f"{tid}: a grid mixes drawings and icons"
                if kinds == {"illustration"}:
                    with_art += 1
                    names = [m["props"]["name"] for m in marks]
                    assert all(names) and len(set(names)) == len(names), (tid, names)
    assert with_art >= 6
