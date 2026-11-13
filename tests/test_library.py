"""The Creative Resource Library: catalogue, store, safe import, conversion, insertion, export and offline discovery.

Nothing here touches the network: remote catalogues get a fake fetcher, and packages are built in temp folders.
"""
from __future__ import annotations

import json
import stat
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mulusa_theme_studio.core.document import validate_document, walk_document, walk_nodes
from mulusa_theme_studio.library import css as csslib
from mulusa_theme_studio.library.blocks import BlockConverter, parse_blocks
from mulusa_theme_studio.library.catalogue import Library
from mulusa_theme_studio.library.convert import Report
from mulusa_theme_studio.library.model import LICENCES, Resource, identify_licence
from mulusa_theme_studio.library.packages import import_package, inspect_package, load_document, section_trees
from mulusa_theme_studio.library.remote import RemoteCatalogue, RemoteError, RemoteItem, check_url
from mulusa_theme_studio.library.safezip import PackageError, extract
from mulusa_theme_studio.library.store import ResourceStore

# Fixtures ---------------------------------------------------------------------------------------------------

SITE_CSS = """
:root { --brand: #0b5f8c; }
body { background: #f6f9fb; color: #0c2233; font-family: 'Inter', sans-serif; }
.hero { padding: 96px 24px; background: var(--brand); color: #fff; }
.hero h1 { font-size: 56px; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.card:hover { transform: translateY(-4px); }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 640px) { .hero h1 { font-size: 34px; } .cards { grid-template-columns: 1fr; } }
"""

INDEX_HTML = """<!doctype html><html><head><title>Northwind | Home</title><link rel="stylesheet" href="css/site.css">
<script src="js/app.js"></script></head><body>
<header><a class="logo" href="index.html">Northwind</a><nav><a href="index.html">Home</a><a href="about.html">About</a></nav></header>
<section class="hero" onclick="evil()"><h1>Build better</h1><p>We plan and deliver.</p><a class="btn" href="about.html">Learn more</a></section>
<section class="services"><h2>Services</h2><div class="cards">
<div class="card"><img src="img/one.png" alt="One"><h3>Plan</h3><p>Plans.</p></div>
<div class="card"><h3>Build</h3><p>Builds.</p></div>
<div class="card"><h3>Run</h3><p>Runs.</p></div></div></section>
<footer><p>© Northwind</p></footer><script>alert(1)</script></body></html>"""

ABOUT_HTML = """<html><head><title>About</title></head><body><section><h1>About us</h1><p>Since 1990.</p></section></body></html>"""

PATTERN_PHP = """<?php
/**
 * Title: Big hero
 * Slug: demo/big-hero
 * Categories: banner
 */
?>
<!-- wp:cover {"dimRatio":50,"minHeight":480} -->
<div class="wp-block-cover"><div class="wp-block-cover__inner-container">
<!-- wp:heading {"level":1} --><h1 class="wp-block-heading"><?php esc_html_e( 'Hello world', 'demo' ); ?></h1><!-- /wp:heading -->
<!-- wp:paragraph --><p>Intro text</p><!-- /wp:paragraph -->
<!-- wp:buttons --><div class="wp-block-buttons"><!-- wp:button --><div class="wp-block-button"><a class="wp-block-button__link">Go</a></div><!-- /wp:button --></div><!-- /wp:buttons -->
</div></div>
<!-- /wp:cover -->
"""

INDEX_TEMPLATE = """<!-- wp:template-part {"slug":"header"} /-->
<!-- wp:group {"tagName":"main"} --><main class="wp-block-group">
<!-- wp:pattern {"slug":"demo/big-hero"} /-->
<!-- wp:group {"style":{"spacing":{"padding":{"top":"64px","bottom":"64px"}}}} --><div class="wp-block-group">
<!-- wp:heading --><h2 class="wp-block-heading">Features</h2><!-- /wp:heading -->
<!-- wp:columns --><div class="wp-block-columns">
<!-- wp:column --><div class="wp-block-column"><!-- wp:paragraph --><p>Fast</p><!-- /wp:paragraph --></div><!-- /wp:column -->
<!-- wp:column --><div class="wp-block-column"><!-- wp:paragraph --><p>Safe</p><!-- /wp:paragraph --></div><!-- /wp:column -->
</div><!-- /wp:columns --></div><!-- /wp:group -->
<!-- wp:query --><div class="wp-block-query"></div><!-- /wp:query -->
</main><!-- /wp:group -->
<!-- wp:template-part {"slug":"footer"} /-->"""

THEME_JSON = {"version": 2, "settings": {"color": {"palette": [
    {"slug": "base", "color": "#ffffff"}, {"slug": "contrast", "color": "#111111"}, {"slug": "accent", "color": "#c2410c"}]}}}


def png(path: Path, color=(30, 90, 140), size=(64, 48)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def html_site(folder: Path, licence: str | None = "MIT License\n\nPermission is hereby granted, free of charge") -> Path:
    (folder / "css").mkdir(parents=True)
    (folder / "js").mkdir()
    (folder / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (folder / "about.html").write_text(ABOUT_HTML, encoding="utf-8")
    (folder / "css" / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (folder / "js" / "app.js").write_text("document.body.remove()", encoding="utf-8")
    png(folder / "img" / "one.png")
    if licence:
        (folder / "LICENSE").write_text(licence, encoding="utf-8")
    return folder


def block_theme(folder: Path) -> Path:
    (folder / "templates").mkdir(parents=True)
    (folder / "patterns").mkdir()
    (folder / "style.css").write_text("/*\nTheme Name: Demo Blocks\nAuthor: Someone\nDescription: A test theme.\n"
                                      "License: GNU General Public License v2 or later\n*/", encoding="utf-8")
    (folder / "theme.json").write_text(json.dumps(THEME_JSON), encoding="utf-8")
    (folder / "templates" / "index.html").write_text(INDEX_TEMPLATE, encoding="utf-8")
    (folder / "patterns" / "big-hero.php").write_text(PATTERN_PHP, encoding="utf-8")
    (folder / "functions.php").write_text("<?php system('rm -rf /');", encoding="utf-8")
    png(folder / "screenshot.png", (200, 90, 20), (120, 90))
    return folder


def zip_folder(folder: Path, out: Path) -> Path:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, f"{folder.name}/{p.relative_to(folder).as_posix()}")
    return out


@pytest.fixture
def store(tmp_path) -> ResourceStore:
    return ResourceStore(tmp_path / "lib")


@pytest.fixture
def catalogue(library, store) -> Library:
    return Library(library, store)


# 1. Indexing, 2. search, 3. filtering, 4. metadata ---------------------------------------------------------------

def test_builtin_collection_is_indexed_and_complete(catalogue):
    counts = catalogue.counts()
    assert counts["template"] == 69 and counts["illustration"] >= 30
    assert counts["section"] >= 30 and counts["header"] >= 8 and counts["footer"] >= 8
    assert counts["palette"] >= 20 and counts["type_pair"] >= 10 and counts["font"] >= 20 and counts["icon"] >= 50
    assert counts["pattern"] >= 8
    ids = [r.id for r in catalogue.all()]
    assert len(ids) == len(set(ids))
    from mulusa_theme_studio.library.catalogue import COLLECTIONS
    collections = {t for r in catalogue.search(kind="template") for t in r.tags}
    assert set(COLLECTIONS) <= collections, set(COLLECTIONS) - collections        # every category in the brief has templates
    starters = ["corporate", "construction", "Creative agencies", "Technology and SaaS", "Music and entertainment",
                "Photography and portfolios", "Restaurants and food businesses", "Personal websites and CVs"]
    for words in starters:
        assert catalogue.search(words, kind="template"), words


def test_every_builtin_section_exists_validates_and_has_a_preview(catalogue):
    for r in catalogue.search(kind="section") + catalogue.search(kind="header") + catalogue.search(kind="footer"):
        data = json.loads(Path(r.path).read_text(encoding="utf-8"))
        assert data["nodes"], r.id
        assert r.preview and Path(r.preview).is_file(), r.id
        assert r.licence == "Original" and r.can_use


def test_search_matches_every_word_across_name_description_and_tags(catalogue):
    heroes = catalogue.search("hero", kind="section")
    assert heroes and all("hero" in r.haystack() for r in heroes)
    assert catalogue.search("hero zzzz-no-such-word") == []
    assert catalogue.search("HERO", kind="section") == heroes


def test_filters_combine(catalogue, store):
    first = catalogue.search(kind="section")[0]
    by_cat = catalogue.search(kind="section", category=first.category)
    assert first in by_cat and all(r.category == first.category for r in by_cat)
    tag = next(t for r in catalogue.search(kind="template") for t in r.tags)
    assert all(tag in r.tags for r in catalogue.search(kind="template", tags=[tag]))
    store.set_favourite(first.id, True)
    assert catalogue.search(favourites=True) == [first]
    assert catalogue.search(compatibility="unsupported") == []
    assert {r.kind for r in catalogue.search(kind="palette")} == {"palette"}


def test_metadata_round_trips_through_json(catalogue):
    for r in catalogue.all()[:400]:
        again = Resource.from_json(json.loads(json.dumps(r.to_json())))
        assert again == r
        for field in ("id", "name", "kind", "category", "source", "licence", "compatibility"):
            assert getattr(r, field) not in (None,), field


# Store: folders, favourites, rename, delete, recent, missing ---------------------------------------------------------

def test_store_persists_and_manages_items(tmp_path, store):
    r = store.add(Resource(id=store.new_id(), name="Thing", kind="section", origin="imported", path=str(tmp_path / "gone")))
    assert ResourceStore(tmp_path / "lib").get(r.id).name == "Thing"   # written to disk
    store.rename(r.id, "  Renamed ")
    assert store.get(r.id).name == "Renamed"
    store.move_to_folder(r.id, "Clients")
    assert "Clients" in store.folders() and store.get(r.id).folder == "Clients"
    store.set_favourite(r.id, True)
    store.touch(r.id)
    assert store.is_favourite(r.id) and store.recent()[0] == r.id
    assert store.missing() == [store.get(r.id)]
    store.delete_folder("Clients")
    assert store.get(r.id).folder == "" and "Clients" not in store.folders()
    store.delete(r.id)
    assert store.get(r.id) is None and not store.is_favourite(r.id) and r.id not in store.recent()


def test_a_damaged_index_does_not_crash_the_library(tmp_path):
    root = tmp_path / "lib"
    root.mkdir()
    (root / "index.json").write_text("{not json", encoding="utf-8")
    assert ResourceStore(root).items() == []


# 5. Import validation, 6. ZIP safety ---------------------------------------------------------------------------

def _raw_zip(path: Path, entries) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for info, data in entries:
            z.writestr(info, data)
    return path


@pytest.mark.parametrize("name", ["../evil.html", "/etc/evil.html", "a/../../evil.html", "C:/evil.html"])
def test_path_traversal_is_refused(tmp_path, name):
    package = _raw_zip(tmp_path / "bad.zip", [(zipfile.ZipInfo(name), b"<p>x</p>")])
    with pytest.raises(PackageError):
        extract(package, tmp_path / "out")
    assert not (tmp_path / "evil.html").exists()


def test_symlinks_are_refused(tmp_path):
    info = zipfile.ZipInfo("link.html")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    package = _raw_zip(tmp_path / "link.zip", [(info, "/etc/passwd")])
    with pytest.raises(PackageError, match="link"):
        extract(package, tmp_path / "out")


def test_zip_bombs_are_refused(tmp_path):
    package = tmp_path / "bomb.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.html", b"0" * (20 * 1024 * 1024))
    with pytest.raises(PackageError, match="bomb"):
        extract(package, tmp_path / "out")


def test_unwanted_files_are_skipped_not_extracted(tmp_path):
    package = _raw_zip(tmp_path / "mixed.zip", [(zipfile.ZipInfo("index.html"), b"<p>x</p>"), (zipfile.ZipInfo("run.exe"), b"MZ"),
                                                 (zipfile.ZipInfo("__MACOSX/._index.html"), b"x"), (zipfile.ZipInfo("tool.sh"), b"rm")])
    out = extract(package, tmp_path / "out")
    names = {p.name for p in out.files}
    assert names == {"index.html"} and len(out.skipped) == 2
    assert not (tmp_path / "out" / "run.exe").exists()


@pytest.mark.parametrize("content", [b"", b"not a zip at all", b"PK\x03\x04garbage"])
def test_malformed_packages_fail_cleanly(tmp_path, store, content):
    bad = tmp_path / "broken.zip"
    bad.write_bytes(content)
    with pytest.raises(PackageError):
        import_package(bad, store)
    assert store.items() == []


def test_a_package_with_nothing_usable_is_refused_and_leaves_nothing(tmp_path, store):
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello", encoding="utf-8")
    with pytest.raises(PackageError):
        import_package(folder, store)
    assert store.items() == [] and not any((store.root / "items").glob("*/project"))


def test_inspection_classifies_packages(tmp_path):
    ins = inspect_package(zip_folder(html_site(tmp_path / "site"), tmp_path / "site.zip"))
    try:
        assert ins.kind == "html_site" and ins.compatibility == "partial" and ins.pages[0] == "index.html"
        assert ins.scripts == 1 and ins.licence == "MIT"
    finally:
        ins.close()
    theme = inspect_package(block_theme(tmp_path / "theme"))
    assert theme.kind == "block_theme" and theme.licence == "GPL-2.0-or-later" and theme.patterns
    classic = tmp_path / "classic"
    classic.mkdir()
    (classic / "style.css").write_text("/*\nTheme Name: Old\nLicense: GPLv2\n*/", encoding="utf-8")
    (classic / "index.php").write_text("<?php get_header();", encoding="utf-8")
    assert inspect_package(classic).compatibility == "reference"


# 7. HTML import, 8. CSS parsing ------------------------------------------------------------------------------------

def test_css_parser_computes_specificity_vars_and_media(tmp_path):
    report = Report()
    sheet = csslib.parse(SITE_CSS, report)
    from mulusa_theme_studio.library.html_import import parse_html
    root = parse_html('<body><section class="hero"><h1>x</h1></section></body>', report).root
    h1 = root.find("h1")
    computed = sheet.computed(h1)
    assert computed[""]["font-size"] == "56px" and computed["mobile"]["font-size"] == "34px"
    hero = root.find("section")
    assert sheet.computed(hero)[""]["background"] == "#0b5f8c"     # var() resolved
    lines = " ".join(report.lines()).lower()
    assert "keyframes" in lines or "animation" in lines
    assert "hover" in lines


def test_css_parser_survives_garbage():
    report = Report()
    sheet = csslib.parse("}}} {{{ a { color: red; ;;; } @media { b { } ", report)
    assert sheet is not None


def test_html_site_imports_as_an_editable_template(tmp_path, store):
    result = import_package(zip_folder(html_site(tmp_path / "site"), tmp_path / "site.zip"), store, name="Northwind")
    template = result.resources[0]
    assert template.kind == "template" and template.compatibility == "partial" and template.licence == "MIT"
    doc = load_document(template)
    assert validate_document(doc) == []
    assert [p["title"] for p in doc["pages"]][:2] == ["Home", "About"]
    assert doc["site"]["header"]["props"]["brand"] == "Northwind"
    assert any(item.get("page") for item in doc["navigation"]["primary"])
    nodes = list(walk_document(doc))
    texts = json.dumps(doc)
    assert "Build better" in texts and "evil()" not in texts and "alert(" not in texts
    assert any(n["type"] == "columns" for n in nodes)
    assert any(n.get("responsive", {}).get("mobile") for n in nodes)
    images = [n for n in nodes if n["type"] == "image" and n["props"]["media"].get("kind") == "asset"]
    assert images and (Path(template.path) / "assets").is_dir()
    joined = " ".join(template.report).lower()
    assert "script" in joined
    assert (Path(template.path).parent / "original").is_dir()   # the original package is kept


# 9. Block patterns, 10. block themes ----------------------------------------------------------------------------

def test_block_markup_parses_and_converts():
    blocks = parse_blocks('<!-- wp:heading {"level":3} --><h3>Hi</h3><!-- /wp:heading --><!-- wp:separator /-->')
    assert [b.name for b in blocks] == ["core/heading", "core/separator"] and blocks[0].attrs == {"level": 3}
    report = Report()
    conv = BlockConverter(report, lambda src, alt="": None)
    from mulusa_theme_studio.library.blocks import strip_php
    sections = conv.sections(parse_blocks(strip_php(PATTERN_PHP, report)))
    assert len(sections) == 1 and sections[0]["type"] == "section"
    types = {n["type"] for n in walk_nodes(sections)}
    assert {"heading", "text", "button"} <= types


def test_pattern_file_imports_as_a_section(tmp_path, store):
    file = tmp_path / "big-hero.php"
    file.write_text(PATTERN_PHP, encoding="utf-8")
    result = import_package(file, store, licence="GPL-2.0-or-later")
    assert [r.kind for r in result.resources] == ["section"]
    trees, assets, _ = section_trees(result.resources[0])
    assert "Hello world" in json.dumps(trees)       # the PHP translation call became its text, nothing ran
    assert "esc_html_e" not in json.dumps(trees)


def test_block_theme_imports_with_patterns_and_palette(tmp_path, store):
    result = import_package(zip_folder(block_theme(tmp_path / "theme"), tmp_path / "theme.zip"), store)
    template, *sections = result.resources
    assert template.kind == "template" and template.licence == "GPL-2.0-or-later" and template.name == "Demo Blocks"
    assert template.preview and Path(template.preview).is_file()        # the theme's own screenshot
    assert sections and all(s.kind == "section" for s in sections)
    doc = load_document(template)
    assert validate_document(doc) == []
    text = json.dumps(doc)
    assert "Hello world" in text and "Features" in text           # the pattern reference was expanded
    assert doc["tokens"]["colors"]["primary"].lower() == "#c2410c"      # WordPress's "accent" is the brand colour
    assert doc["tokens"]["colors"]["background"] == "#ffffff"
    assert any("query" in line.lower() or "dynamic" in line.lower() for line in template.report)
    assert not (tmp_path / "pwned").exists()


# 11. Assets, 12. duplicates, 13. licence metadata ---------------------------------------------------------------

def test_image_collection_imports_as_media(tmp_path, store):
    folder = tmp_path / "pics"
    png(folder / "a.png")
    png(folder / "b.png", (200, 40, 40))
    (folder / "broken.png").write_bytes(b"not an image")
    result = import_package(folder, store)
    res = result.resources[0]
    assert res.kind == "image" and len(res.data["assets"]) == 2
    assert all((Path(res.path) / Path(a["file"]).name).is_file() for a in res.data["assets"])


def test_the_same_package_imports_once(tmp_path, store):
    package = zip_folder(html_site(tmp_path / "site"), tmp_path / "site.zip")
    first = import_package(package, store)
    second = import_package(package, store)
    assert second.duplicate and second.resources[0].id == first.resources[0].id
    assert len([r for r in store.items() if r.kind == "template"]) == 1


def test_licences_are_identified_and_unknown_is_never_redistributable(tmp_path, store):
    assert identify_licence("GPLv2 or later").id == "GPL-2.0-or-later"
    assert identify_licence("MIT License").id == "MIT"
    assert identify_licence("SIL Open Font License 1.1").id == "OFL-1.1"
    assert identify_licence("Creative Commons Attribution 3.0").attribution
    assert identify_licence("all rights reserved").id == "Unknown"
    assert not LICENCES["Unknown"].redistributable
    result = import_package(zip_folder(html_site(tmp_path / "site", licence=None), tmp_path / "nolicence.zip"), store)
    res = result.resources[0]
    assert res.licence == "Unknown" and not res.licence_info.redistributable
    assert any("licence" in line.lower() for line in res.report)


# 14. Document conversion, 15. undo/redo after insertion, 17. export -------------------------------------------------

@pytest.fixture
def session(tmp_path, library):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mulusa_theme_studio.core.settings import Settings
    from mulusa_theme_studio.ui.session import Session
    settings = Settings()
    settings.projects_dir = str(tmp_path / "projects")
    s = Session(settings, library)
    s.create_project("Library test", "corporate/corporate-classic")
    yield s
    s.project = None


def test_inserting_a_section_is_one_undo_step(session):
    section = session.resources.search(kind="section")[0]
    before = json.dumps(session.document["pages"][0]["nodes"])
    ids = session.insert_resource(section)
    assert ids and validate_document(session.document) == []
    session.undo()
    assert json.dumps(session.document["pages"][0]["nodes"]) == before
    session.redo()
    assert any(n["id"] == ids[0] for n in session.document["pages"][0]["nodes"])


def test_inserted_ids_are_fresh_each_time(session):
    section = session.resources.search("hero", kind="section")[0]
    a = session.insert_resource(section)
    b = session.insert_resource(section)
    all_ids = [n["id"] for n in walk_document(session.document)]
    assert a != b and len(all_ids) == len(set(all_ids))


def test_design_resources_apply_and_undo(session):
    lib = session.resources
    colours = session.document["tokens"]["colors"]["primary"]
    palette = next(r for r in lib.search(kind="palette") if r.data["colors"]["primary"] != colours)
    assert session.apply_resource(palette)
    assert session.document["tokens"]["colors"]["primary"] == palette.data["colors"]["primary"]
    session.undo()
    assert session.document["tokens"]["colors"]["primary"] == colours
    pair = lib.search(kind="type_pair")[3]
    assert session.apply_resource(pair) and session.document["tokens"]["fonts"]["heading"] == pair.data["heading"]
    header = lib.search(kind="header")[2]
    assert session.apply_resource(header)
    footer = lib.search(kind="footer")[1]
    assert session.apply_resource(footer) and validate_document(session.document) == []
    assert lib.store.recent()[0] == footer.id


def test_patterns_and_gradients_need_a_section_and_then_apply(session):
    lib = session.resources
    pattern = next(r for r in lib.search(kind="pattern") if "pattern" in r.data)
    gradient = next(r for r in lib.search(kind="pattern") if "gradient" in r.data)
    session.selected_id = None
    assert not session.apply_resource(pattern)
    section = session.document["pages"][0]["nodes"][1]
    session.selected_id = section["id"]
    assert session.apply_resource(pattern)
    assert len(session.document["media"]["assets"]) >= 1
    assert session.apply_resource(gradient) and validate_document(session.document) == []
    section = next(n for n in session.document["pages"][0]["nodes"] if n["id"] == section["id"])
    assert "media" not in section["props"].get("background", {}) and "gradient" in section["style"]["background"]


def test_imported_sections_bring_their_images(session, tmp_path):
    result = import_package(zip_folder(html_site(tmp_path / "site"), tmp_path / "site.zip"), session.resources.store)
    session.resources.store.reload()
    template = result.resources[0]
    before = len(session.document["media"]["assets"])
    assert session.insert_resource(template)
    assert len(session.document["media"]["assets"]) == before + 1
    asset = session.document["media"]["assets"][-1]
    assert (session.project.folder / "assets" / Path(asset["file"]).name).is_file()
    session.insert_resource(template)                                 # the same image is not copied twice
    assert len(session.document["media"]["assets"]) == before + 1


def test_a_project_starts_from_an_imported_template_and_exports(session, tmp_path):
    from mulusa_theme_studio.exporters.static import StaticExporter, StaticOptions
    result = import_package(zip_folder(html_site(tmp_path / "site"), tmp_path / "site.zip"), session.resources.store)
    session.resources.store.reload()
    project = session.create_project_from_resource(result.resources[0], "From import")
    assert project and validate_document(session.document) == []
    assert any((project.folder / "assets").iterdir())
    out = StaticExporter().export(session.document, project.folder, tmp_path / "out", StaticOptions(site_name="From import"))
    with zipfile.ZipFile(out.output) as z:
        names = z.namelist()
    assert any(n.endswith("index.html") for n in names) and any(n.endswith(".png") for n in names)


def test_documents_with_inserted_sections_export_to_wordpress(session, tmp_path):
    from mulusa_theme_studio.exporters.wordpress import ERROR, ExportOptions, WordPressExporter
    from mulusa_theme_studio.exporters.wordpress.check import check_theme
    for section in session.resources.search(kind="section")[:12]:
        session.insert_resource(section)
    assert validate_document(session.document) == []
    out = WordPressExporter().export(session.document, session.project.folder, tmp_path / "wp", ExportOptions(theme_name="Library Test"))
    root = tmp_path / "unpacked"
    with zipfile.ZipFile(out.output) as z:
        z.extractall(root)
    theme = next(p.parent for p in root.rglob("style.css"))
    assert [str(i) for i in check_theme(theme, slug=theme.name) if i.severity == ERROR] == []


# 16. Responsive previews -------------------------------------------------------------------------------------------

def test_every_builtin_section_renders_with_responsive_rules(session, tmp_path):
    from mulusa_theme_studio.render.site import write_site
    for section in session.resources.search(kind="section")[:20]:
        session.insert_resource(section)
    out = write_site(session.document, tmp_path / "site", project_folder=session.project.folder)
    css = next((tmp_path / "site").rglob("*.css")).read_text(encoding="utf-8")
    assert "@media" in css
    html = next(iter(out.pages.values())).read_text(encoding="utf-8")
    assert 'name="viewport"' in html


# 18. Offline use and remote discovery ------------------------------------------------------------------------------

PATTERN_API = [{"id": 7, "title": {"rendered": "Remote hero"}, "pattern_content": PATTERN_PHP.split("?>", 1)[1],
                "meta": {"wpop_description": "A hero"}, "category_slugs": ["banner"]},
               {"id": 8, "title": {"rendered": "Empty"}, "pattern_content": "<p>no blocks</p>"}]


def test_remote_search_caches_and_works_offline(store):
    calls = []

    def online(url):
        calls.append(url)
        return json.dumps(PATTERN_API).encode()

    first = RemoteCatalogue(store, online).search_patterns("hero")
    assert [i.name for i in first.items] == ["Remote hero"] and not first.offline
    assert first.items[0].importable and first.items[0].licence == "GPL-2.0-or-later"

    def offline(url):
        raise OSError("network is down")

    import mulusa_theme_studio.library.remote as remote
    cached = RemoteCatalogue(store, offline)
    assert cached.search_patterns("hero").items[0].name == "Remote hero"     # fresh cache, no fetch
    original = remote.CACHE_SECONDS
    try:
        remote.CACHE_SECONDS = -1
        stale = cached.search_patterns("hero")
        assert stale.offline and stale.items[0].name == "Remote hero"
    finally:
        remote.CACHE_SECONDS = original
    nothing = cached.search_patterns("never searched")
    assert nothing.items == [] and nothing.offline and "online" in nothing.message
    assert len(calls) == 1


def test_remote_pattern_imports_without_a_download(store):
    cat = RemoteCatalogue(store, lambda url: json.dumps(PATTERN_API).encode())
    item = cat.search_patterns("hero").items[0]
    result = cat.import_item(item)
    res = result.resources[0]
    assert res.kind == "section" and res.origin == "remote" and res.licence == "GPL-2.0-or-later"
    assert res.source == "WordPress.org Pattern Directory"


def test_unlicensed_repositories_are_links_only(store):
    data = {"items": [{"full_name": "a/free", "name": "free", "license": {"spdx_id": "MIT"}, "default_branch": "main", "html_url": "https://github.com/a/free"},
                      {"full_name": "a/closed", "name": "closed", "license": None, "html_url": "https://github.com/a/closed"}]}
    items = RemoteCatalogue(store, lambda url: json.dumps(data).encode()).search_github("x").items
    assert items[0].importable and not items[1].importable and not items[1].download_url
    with pytest.raises(RemoteError):
        RemoteCatalogue(store, lambda url: b"").download(items[1])


@pytest.mark.parametrize("url", ["http://api.wordpress.org/x", "https://themeforest.net/x", "https://webflow.com/templates",
                                 "file:///etc/passwd", "https://api.wordpress.org.evil.com/x"])
def test_only_official_https_hosts_are_fetched(url):
    with pytest.raises(RemoteError):
        check_url(url)


def test_the_library_works_with_no_network_at_all(catalogue, monkeypatch):
    import socket

    def refuse(*a, **k):
        raise OSError("no network in this test")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    assert catalogue.search("hero") and catalogue.discover()["Featured templates"]


# The window ---------------------------------------------------------------------------------------------------------

def test_library_window_views_and_insert(session, qtbot):
    from mulusa_theme_studio.ui.library_window import ROLE_ID, VIEWS, LibraryWindow
    from mulusa_theme_studio.ui.theme import DARK
    w = LibraryWindow(session, DARK)
    qtbot.addWidget(w)
    for row, (name, kind, special) in enumerate(VIEWS):
        w.nav.setCurrentRow(row)
        if kind and kind != "image":
            assert w.model.rowCount() > 0, name
    w.nav.setCurrentRow(2)
    first = w.library.get(w.model.item(0).data(ROLE_ID))
    count = len(session.document["pages"][0]["nodes"])
    w.use(first)
    assert len(session.document["pages"][0]["nodes"]) == count + 1
    w.search.setText("zzzz-nothing")
    w.refresh()
    assert w.model.rowCount() == 0
