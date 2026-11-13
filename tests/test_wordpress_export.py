"""The exporter, from a document to real ZIP files that are opened and read back."""
import json
import re
import zipfile
from pathlib import Path

import pytest

from mulusa_theme_studio.components import presets
from mulusa_theme_studio.core import operations, pages, properties
from mulusa_theme_studio.core.document import find_node, home_page, site_pages, walk_document
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.exporters import available
from mulusa_theme_studio.exporters.wordpress import ERROR, ExportFailed, ExportOptions, WordPressExporter
from mulusa_theme_studio.exporters.wordpress.blocks import Block, encode_attrs
from mulusa_theme_studio.exporters.wordpress.check import check_block_markup, check_theme
from mulusa_theme_studio.exporters.wordpress.files import Identity, header_text, style_css
from mulusa_theme_studio.exporters.wordpress.translate import Assets, Report, Rules, Tokens, Translator

OPTIONS = ExportOptions(theme_name="Test Theme", author="A Tester")


@pytest.fixture
def doc():
    return TemplateLibrary().load("corporate/corporate-classic")


def export(doc, tmp_path, options=OPTIONS, project=None):
    return WordPressExporter().export(doc, project or tmp_path / "no-project", tmp_path / "out", options)


def read_zip(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


def translate(doc, nodes, in_content=True):
    tokens = Tokens("abc")
    report = Report()
    blocks = Translator(doc, tokens, in_content=in_content, report=report, assets=Assets(), rules=Rules()).nodes(nodes)
    return "\n".join(b.serialize() for b in blocks), report, tokens


def block(kind, **props_):
    return {"id": f"x{abs(hash(kind)) % 9999}", "type": kind, "props": props_, "style": {}, "children": []}


# Registration --------------------------------------------------------------
def test_registered_through_the_exporter_interface():
    assert WordPressExporter in available()


# Block comments ------------------------------------------------------------
def test_attributes_are_escaped_the_way_the_editor_escapes_them():
    text = encode_attrs({"a": "--> <b> & \"q\""})
    assert "-->" not in text and "<" not in text and ">" not in text
    assert json.loads(text)["a"] == "--> <b> & \"q\""


def test_self_closing_and_nested_blocks_serialize():
    assert Block("core/spacer", {"height": "1px"}).serialize().endswith("/-->")
    outer = Block("core/group", {}, "<div>", [Block("core/paragraph", {}, "<p>x</p>")], "</div>").serialize()
    assert outer.startswith("<!-- wp:group -->") and outer.endswith("<!-- /wp:group -->")
    assert check_block_markup(outer, "t") == []


@pytest.mark.parametrize("bad,why", [
    ('<!-- wp:group -->\n<div></div>', "never closed"),
    ('<!-- wp:group {bad} -->\n<div></div>\n<!-- /wp:group -->', "not valid JSON"),
    ('<!-- wp:group{"a":1} -->\n<div></div>\n<!-- /wp:group -->', "malformed"),
    ('<!-- wp:nonsense /-->', "Unknown block"),
    ('<!-- wp:group -->\n<div>\n<!-- /wp:group -->', "never closed"),
    ('<!-- wp:group --><!-- wp:column --><!-- /wp:group --><!-- /wp:column -->', "out of order"),
])
def test_the_checker_catches_broken_markup(bad, why):
    assert any(why in i.message for i in check_block_markup(bad, "t"))


# Mapping --------------------------------------------------------------------
@pytest.mark.parametrize("node,expected", [
    (block("heading", text="Hi", level=3), "wp:heading"),
    (block("text", text="Hi"), "wp:paragraph"),
    (block("button", label="Go", href="#", variant="primary"), "wp:button"),
    (block("divider"), "wp:separator"),
    (block("faq_item", question="Q", answer="A"), "wp:details"),
    (block("richtext", html="<ul><li>One</li></ul>"), "wp:list"),
    (block("image", media={"kind": "placeholder", "seed": "s", "label": "x"}, alt="An alt"), "wp:image"),
])
def test_primitive_nodes_become_core_blocks(doc, node, expected):
    text, report, _ = translate(doc, [node])
    assert expected in text
    assert report.errors == []
    assert check_block_markup(re.sub(r"__MTS[a-z0-9]+_[a-z]+_[0-9a-f]*__", "0", text), "t") == []


def test_real_template_nodes_map_to_group_columns_and_heading(doc):
    text, _, _ = translate(doc, home_page(doc)["nodes"])
    for name in ("wp:group", "wp:columns", "wp:column", "wp:heading", "wp:paragraph", "wp:buttons", "wp:image"):
        assert name in text, name


def test_text_is_escaped_so_it_cannot_become_code(doc, tmp_path):
    bad = "<?php system('x'); ?><script>alert(1)</script>"
    heading = next(n for n in walk_document(doc) if n.get("type") == "heading")
    heading["props"]["text"] = bad
    home = next(n for n in walk_document(doc) if n.get("type") == "text")
    home["props"]["text"] = bad
    result = export(doc, tmp_path)
    files = read_zip(result.output)
    for name, data in files.items():
        if name.endswith((".html", ".php")) and "/patterns/" in name or name.endswith(".html"):
            text = data.decode("utf-8")
            assert "system(" not in text.replace("&#039;", "'").split("&lt;?php")[0] or "<?php system" not in text
            assert "<?php system" not in text and "<script" not in text
    assert b"<?php system" not in read_zip(result.plugin)[f"{result.output.stem}-content/data/site.json"]


def test_a_malicious_theme_name_cannot_break_out_of_its_header():
    who = Identity("x */ <?php evil(); ?>\nTheme Name: Other", "x", "d\nAuthor: z", "A", "1.0.0")
    head = style_css(who)
    assert "<?php" not in head and head.count("*/") == 2  # The header's own close, and the note after it.
    assert re.search(r"^Author: A$", head, flags=re.M)


def test_a_slug_in_the_page_address_goes_through_a_php_string_safely(doc, tmp_path):
    item = next(i for i in doc["navigation"]["primary"] if i.get("page"))
    pages.set_slug(doc, item["page"], "new-address")
    files = read_zip(export(doc, tmp_path).output)
    assert b"'new-address'" in files["test-theme/functions.php"]


# Dynamic content ------------------------------------------------------------
def posts_doc(doc, **settings):
    query = presets.query_node(4, 2, **settings)
    home = home_page(doc)
    home["nodes"].insert(1, {"id": "sec1", "type": "section", "props": {}, "style": {}, "children": [{"id": "con1", "type": "container", "props": {}, "style": {}, "children": [query]}]})
    return doc, query


def test_a_posts_list_becomes_a_genuine_query_loop(doc):
    doc, query = posts_doc(doc)
    pages.set_query(doc, query["id"], count=4, order_by="title", order="asc", hide=["author"])
    text, _, _ = translate(doc, [query])
    found = re.search(r"<!-- wp:query (\{.*?\}) -->", text)
    assert found
    data = json.loads(found.group(1))["query"]
    assert data["perPage"] == 4 and data["orderBy"] == "title" and data["order"] == "asc" and data["postType"] == "post"
    assert "wp:post-template" in text and "wp:post-title" in text and "wp:post-featured-image" in text
    assert "wp:post-excerpt" in text and "wp:post-author" not in text


def test_a_category_filter_is_resolved_when_the_site_runs(doc):
    doc, query = posts_doc(doc)
    pages.set_query(doc, query["id"], categories=["Projects"])
    text, _, tokens = translate(doc, [query])
    found = tokens.pattern.search(text)
    assert found and found.group(1) == "terms" and Tokens.decode(found.group(2)) == "projects"


def test_static_and_dynamic_sections_share_a_page(doc, tmp_path):
    doc, _ = posts_doc(doc)
    result = export(doc, tmp_path)
    site = json.loads(read_zip(result.plugin)["test-theme-content/data/site.json"])
    home = next(p for p in site["pages"] if p["id"] == site["home"])
    assert "wp:query" in home["content"] and "wp:heading" in home["content"]


def test_post_templates_use_post_blocks_even_without_a_design(doc, tmp_path):
    files = read_zip(export(doc, tmp_path).output)
    single = files["test-theme/patterns/single.php"].decode()
    assert "wp:post-title" in single and "wp:post-content" in single
    assert "wp:query" in files["test-theme/patterns/archive.php"].decode()


def test_the_single_template_uses_the_owners_design_when_there_is_one(doc, tmp_path):
    nodes = presets.default_single_nodes()
    nodes[0]["name"] = "Mine"
    nodes[0]["children"][0]["children"].insert(0, {"id": "mine", "type": "heading", "props": {"text": "Project story", "level": 2}, "style": {}, "children": []})
    pages.create_page(doc, "Single", nodes, role="single")
    assert "Project story" in read_zip(export(doc, tmp_path).output)["test-theme/patterns/single.php"].decode()


# Package --------------------------------------------------------------------
def test_full_export_writes_a_complete_theme(doc, tmp_path):
    result = export(doc, tmp_path)
    assert result.output.name == "test-theme.zip" and result.plugin.name == "test-theme-content.zip"
    files = read_zip(result.output)
    for name in ("style.css", "theme.json", "functions.php", "screenshot.png", "readme.txt", "templates/index.html", "templates/front-page.html", "templates/page.html",
                 "templates/single.html", "templates/archive.html", "templates/404.html", "parts/header.html", "parts/footer.html", "assets/css/mulusa.css"):
        assert f"test-theme/{name}" in files, name
    assert all(name.startswith("test-theme/") for name in files)
    assert all(data for name, data in files.items()), "no empty files"
    assert files["test-theme/screenshot.png"][:8] == b"\x89PNG\r\n\x1a\n"


def test_style_css_headers(doc, tmp_path):
    head = read_zip(export(doc, tmp_path).output)["test-theme/style.css"].decode()
    for line in ("Theme Name: Test Theme", "Author: A Tester", "Version: 1.0.0", "Requires at least:", "Tested up to:", "Requires PHP:", "License: GNU", "License URI:", "Text Domain: test-theme"):
        assert line in head, line


def test_theme_json_maps_tokens_rather_than_flattening_them(doc, tmp_path):
    data = json.loads(read_zip(export(doc, tmp_path).output)["test-theme/theme.json"])
    assert data["version"] == 3
    palette = {c["slug"]: c["color"] for c in data["settings"]["color"]["palette"]}
    assert palette["primary"] == doc["tokens"]["colors"]["primary"] and "on-primary" in palette
    assert {f["slug"] for f in data["settings"]["typography"]["fontFamilies"]} >= {"heading"}
    assert data["settings"]["layout"]["contentSize"] == doc["tokens"]["spacing"]["width"]
    assert {s["slug"] for s in data["settings"]["spacing"]["spacingSizes"]} >= {"section", "gap"}
    assert data["settings"]["custom"]["mulusa"]["radius"]
    assert data["settings"]["color"]["defaultPalette"] is False


def test_the_stylesheet_reads_colours_from_global_styles(doc, tmp_path):
    css = read_zip(export(doc, tmp_path).output)["test-theme/assets/css/mulusa.css"].decode()
    assert "--mts-primary:var(--wp--preset--color--primary)" in css


def test_shared_parts_are_template_parts_and_not_copied_into_pages(doc, tmp_path):
    result = export(doc, tmp_path)
    files = read_zip(result.output)
    for name in ("page", "front-page", "single", "archive", "404", "index"):
        text = files[f"test-theme/templates/{name}.html"].decode()
        assert 'wp:template-part {"slug":"header"' in text and 'wp:template-part {"slug":"footer"' in text
    assert "wp:navigation-link" in files["test-theme/patterns/header.php"].decode()
    site = json.loads(read_zip(result.plugin)["test-theme-content/data/site.json"])
    assert not any("wp:navigation" in page["content"] for page in site["pages"])


def test_a_landing_page_template_has_no_header(doc, tmp_path):
    other = next(p for p in site_pages(doc) if not p.get("home"))
    pages.set_page_meta(doc, other["id"], layout="landing")
    result = export(doc, tmp_path)
    files = read_zip(result.output)
    assert "template-part" not in files["test-theme/templates/page-landing.html"].decode()
    site = json.loads(read_zip(result.plugin)["test-theme-content/data/site.json"])
    assert next(p for p in site["pages"] if p["id"] == other["id"])["template"] == "page-landing"


def test_every_page_is_offered_for_import_with_its_address(doc, tmp_path):
    result = export(doc, tmp_path)
    site = json.loads(read_zip(result.plugin)["test-theme-content/data/site.json"])
    assert [p["slug"] for p in site["pages"]] == [p["slug"] for p in site_pages(doc)]
    assert site["home"] == home_page(doc)["id"]
    assert [p["slug"] for p in result.pages] == [p["slug"] for p in site_pages(doc)]


def test_post_templates_are_not_offered_as_pages(doc, tmp_path):
    pages.create_page(doc, "Single", presets.default_single_nodes(), role="single")
    site = json.loads(read_zip(export(doc, tmp_path).plugin)["test-theme-content/data/site.json"])
    assert "Single" not in [p["title"] for p in site["pages"]]


# Assets ---------------------------------------------------------------------
def with_image(doc, tmp_path):
    from PIL import Image

    project = tmp_path / "project"
    (project / "assets").mkdir(parents=True)
    Image.new("RGB", (640, 480), "red").save(project / "assets" / "used.png")
    Image.new("RGB", (640, 480), "blue").save(project / "assets" / "unused.png")
    doc["media"]["assets"] = [
        {"id": "a1", "file": "used.png", "name": "Used", "width": 640, "height": 480, "format": "PNG", "alt": ""},
        {"id": "a2", "file": "unused.png", "name": "Unused", "width": 640, "height": 480, "format": "PNG", "alt": ""},
    ]
    image = next(n for n in walk_document(doc) if n.get("type") == "image")
    image["props"]["media"] = {"kind": "asset", "id": "a1"}
    return project


def test_only_used_images_are_packed_and_byte_for_byte(doc, tmp_path):
    project = with_image(doc, tmp_path)
    files = read_zip(export(doc, tmp_path, project=project).output)
    assert files["test-theme/assets/images/used.png"] == (project / "assets" / "used.png").read_bytes()
    assert "test-theme/assets/images/unused.png" not in files


def test_no_export_depends_on_this_computer(doc, tmp_path):
    project = with_image(doc, tmp_path)
    result = export(doc, tmp_path, project=project)
    for archive in (result.output, result.plugin):
        for name, data in read_zip(archive).items():
            if name.endswith((".html", ".php", ".json", ".css", ".txt")):
                text = data.decode("utf-8")
                assert str(tmp_path) not in text and "/tmp/" not in text and "file://" not in text and "/home/" not in text


def test_a_missing_image_stops_the_export(doc, tmp_path):
    project = with_image(doc, tmp_path)
    (project / "assets" / "used.png").unlink()
    with pytest.raises(ExportFailed) as failed:
        export(doc, tmp_path, project=project)
    assert any("used.png" in str(i) for i in failed.value.errors)
    assert not (tmp_path / "out" / "test-theme.zip").exists()


# Checking -------------------------------------------------------------------
@pytest.fixture
def theme_folder(doc, tmp_path):
    files = read_zip(export(doc, tmp_path).output)
    root = tmp_path / "unpacked"
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root / "test-theme"


def test_a_good_theme_passes(theme_folder):
    assert [str(i) for i in check_theme(theme_folder, slug="test-theme") if i.severity == ERROR] == []


@pytest.mark.parametrize("name", ["style.css", "theme.json", "templates/index.html", "parts/header.html", "screenshot.png"])
def test_a_missing_required_file_is_reported(theme_folder, name):
    (theme_folder / name).unlink()
    assert any(name in str(i) for i in check_theme(theme_folder, slug="test-theme"))


def test_broken_json_is_reported(theme_folder):
    (theme_folder / "theme.json").write_text("{nope")
    assert any("JSON" in i.message for i in check_theme(theme_folder, slug="test-theme"))


def test_a_missing_header_line_is_reported(theme_folder):
    path = theme_folder / "style.css"
    path.write_text(path.read_text().replace("Text Domain:", "Nope:"))
    assert any("Text Domain" in i.message for i in check_theme(theme_folder, slug="test-theme"))


def test_a_missing_part_or_pattern_is_reported(theme_folder):
    (theme_folder / "patterns" / "header.php").unlink()
    assert any("header" in i.message for i in check_theme(theme_folder, slug="test-theme"))
    (theme_folder / "templates" / "page.html").write_text('<!-- wp:template-part {"slug":"ghost"} /-->')
    assert any("ghost" in i.message for i in check_theme(theme_folder, slug="test-theme"))


@pytest.mark.parametrize("bad", ["<script>alert(1)</script>", '<a href="javascript:x">y</a>', '<img src="x" onerror="y">'])
def test_unsafe_markup_is_reported(theme_folder, bad):
    (theme_folder / "templates" / "page.html").write_text(bad)
    assert any("Unsafe" in i.message for i in check_theme(theme_folder, slug="test-theme"))


def test_php_in_a_pattern_beyond_the_fixed_forms_is_reported(theme_folder):
    path = theme_folder / "patterns" / "footer.php"
    path.write_text(path.read_text() + "<?php system('x'); ?>")
    assert any("code" in i.message for i in check_theme(theme_folder, slug="test-theme"))


def test_php_in_a_block_template_is_reported(theme_folder):
    (theme_folder / "templates" / "page.html").write_text("<?php echo 1; ?>")
    assert any("PHP" in i.message for i in check_theme(theme_folder, slug="test-theme"))


def test_a_link_to_a_deleted_page_is_a_warning_with_a_fix(doc):
    home_page(doc)["nodes"][0]["children"][0]["children"].insert(0, {"id": "bad1", "type": "link", "props": {"label": "Gone", "href": {"page": "ghost"}}, "style": {}, "children": []})
    issues = WordPressExporter().check(doc, None)
    assert any("Gone" in i.message and i.fix for i in issues)


def test_all_sixty_nine_templates_export_with_no_errors(tmp_path):
    library = TemplateLibrary()
    infos = library.all() if hasattr(library, "all") else library.templates
    assert len(infos) == 69
    for info in infos:
        doc = library.load(info.id)
        # Their art is generated placeholders, so no project folder is needed.
        errors = [str(i) for i in WordPressExporter().check(doc, tmp_path) if i.severity == ERROR]
        assert errors == [], info.id


def test_a_photo_section_with_a_gradient_overlay_saves_the_way_gutenberg_does():
    # Gutenberg's cover save() adds has-background-dim-N and has-background-dim whenever dimRatio
    # is set, 0 included; leaving them out at 0 made the block "invalid" in a real WordPress.
    doc = TemplateLibrary().load("construction/heavy-civil")
    hero = doc["pages"][0]["nodes"][0]
    assert hero["props"]["background"]["overlay"].startswith("linear-gradient")
    markup, report, _ = translate(doc, [hero])
    assert '"dimRatio":0' in markup
    assert 'class="wp-block-cover__background has-background-dim-0 has-background-dim"' in markup
    assert any("overlay is not a plain colour" in w for w in report.warnings)
