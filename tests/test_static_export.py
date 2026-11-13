"""The static website exporter: real files written, zipped, read back and checked."""
import re
import zipfile

import pytest

from mulusa_theme_studio.components import registry
from mulusa_theme_studio.core import operations
from mulusa_theme_studio.core.document import home_page, site_pages, walk_document
from mulusa_theme_studio.exporters import ERROR, available
from mulusa_theme_studio.exporters.static import StaticExporter, StaticExportFailed, StaticOptions, check_site
from mulusa_theme_studio.render.site import page_filename

EMAIL = StaticOptions(site_name="Test Site", form_email="hello@example.com")


@pytest.fixture
def doc(library):
    return library.load("corporate/corporate-classic")


def export(doc, tmp_path, options=EMAIL):
    return StaticExporter().export(doc, tmp_path / "no-project", tmp_path / "out", options)


def has_form(doc):
    return any(n.get("type") == "contact_form" for n in walk_document(doc))


def test_registered_through_the_exporter_interface():
    assert StaticExporter in available()


def test_every_page_is_written_and_zipped(doc, tmp_path):
    result = export(doc, tmp_path)
    with zipfile.ZipFile(result.output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    for page in site_pages(doc):
        assert f"test-site-site/{page_filename(page)}" in names
        assert (result.folder / page_filename(page)).is_file()
    assert "test-site-site/assets/style.css" in names
    assert (result.folder / "index.html").is_file()
    assert [p["file"] for p in result.pages if p["home"]] == ["index.html"]
    assert page_filename(home_page(doc)) == "index.html"


def test_no_editor_markup_or_script_reaches_the_site(doc, tmp_path):
    result = export(doc, tmp_path)
    for page in result.folder.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert "data-mts-" not in text and "<script" not in text.lower()


def test_internal_links_and_files_all_resolve(doc, tmp_path):
    result = export(doc, tmp_path)
    assert not [i for i in check_site(result.folder) if i.severity == ERROR]
    hrefs = set()
    for page in result.folder.glob("*.html"):
        hrefs |= set(re.findall(r'href="([a-z0-9-]+\.html)', page.read_text(encoding="utf-8")))
    assert hrefs and all((result.folder / h).is_file() for h in hrefs)


def test_only_the_fonts_the_stylesheet_uses_are_shipped(doc, tmp_path):
    result = export(doc, tmp_path)
    css = (result.folder / "assets" / "style.css").read_text(encoding="utf-8")
    fonts = list((result.folder / "assets" / "fonts").glob("*"))
    assert fonts and all(f.name in css for f in fonts)
    assert "fonts.googleapis" not in css


def test_forms_without_a_destination_stop_the_export(doc, tmp_path):
    assert has_form(doc)
    with pytest.raises(StaticExportFailed) as failed:
        export(doc, tmp_path, StaticOptions(site_name="Test Site"))
    assert any("form" in str(i).lower() for i in failed.value.errors)
    assert not (tmp_path / "out" / "test-site-site.zip").exists()


def test_forms_post_to_the_handler_given(doc, tmp_path):
    result = export(doc, tmp_path, StaticOptions(site_name="Test Site", form_action="https://forms.example.org/f/abc"))
    text = "".join(p.read_text(encoding="utf-8") for p in result.folder.glob("*.html"))
    assert 'action="https://forms.example.org/f/abc" method="post"' in text
    assert 'action="#"' not in text


def test_forms_fall_back_to_email(doc, tmp_path):
    result = export(doc, tmp_path)
    text = "".join(p.read_text(encoding="utf-8") for p in result.folder.glob("*.html"))
    assert 'action="mailto:hello@example.com"' in text


@pytest.mark.parametrize("bad", ["http://insecure.example.org/f", "javascript:alert(1)", "forms.example.org"])
def test_a_handler_must_be_https(doc, tmp_path, bad):
    with pytest.raises(StaticExportFailed):
        export(doc, tmp_path, StaticOptions(site_name="Test Site", form_action=bad))


def test_a_bad_email_is_refused(doc, tmp_path):
    with pytest.raises(StaticExportFailed):
        export(doc, tmp_path, StaticOptions(site_name="Test Site", form_email="not an address"))


def test_post_lists_are_left_out_and_reported(doc, tmp_path):
    home = home_page(doc)
    operations.insert_tree(doc, f"page:{home['id']}", 1, registry.get("latest-posts").build())
    assert any(n.get("type") == "query" for n in walk_document(doc))
    result = export(doc, tmp_path)
    text = "".join(p.read_text(encoding="utf-8") for p in result.folder.glob("*.html"))
    assert "Sample post" not in text and "mts-query" not in text
    assert any("listing posts" in str(i) for i in result.issues)


def test_the_original_document_is_not_changed(doc, tmp_path):
    import json
    before = json.dumps(doc, sort_keys=True)
    export(doc, tmp_path)
    assert json.dumps(doc, sort_keys=True) == before


def test_an_unrelated_folder_is_never_replaced(doc, tmp_path):
    keep = tmp_path / "out" / "test-site-site"
    keep.mkdir(parents=True)
    (keep / "precious.txt").write_text("mine")
    with pytest.raises(OSError):
        export(doc, tmp_path)
    assert (keep / "precious.txt").read_text() == "mine"


def test_a_second_export_replaces_the_first(doc, tmp_path):
    export(doc, tmp_path)
    result = export(doc, tmp_path)
    assert (result.folder / "index.html").is_file()


def test_check_finds_a_missing_page(doc, tmp_path):
    result = export(doc, tmp_path)
    linked = next(p for p in result.folder.glob("*.html") if p.name != "index.html")
    linked.unlink()
    assert any(i.severity == ERROR for i in check_site(result.folder))


@pytest.mark.parametrize("slug", ["construction/heavy-civil", "construction/engineering-firm", "corporate/modern-consulting"])
def test_other_templates_export_cleanly(library, tmp_path, slug):
    doc = library.load(slug)
    result = StaticExporter().export(doc, tmp_path / "p", tmp_path / "out", EMAIL)
    assert not [i for i in result.issues if i.severity == ERROR]


def test_a_page_that_only_listed_posts_is_reported_as_empty(library, tmp_path):
    doc = library.load("construction/heavy-civil")
    blog = next(p for p in doc["pages"] if p["id"] == "blog")
    blog["nodes"] = [n for n in blog["nodes"] if n.get("props", {}).get("role") == "page_header"]
    operations.insert_tree(doc, "page:blog", 1, registry.get("latest-posts").build())
    result = export(doc, tmp_path)
    assert any("Nothing is left on this page" in str(i) for i in result.issues)
