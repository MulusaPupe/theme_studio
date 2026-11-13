from __future__ import annotations

import copy

import pytest

from mulusa_theme_studio.core.document import media_refs
from mulusa_theme_studio.render.css import declarations, style_value, tokens_css
from mulusa_theme_studio.render.html import RenderContext, render_node, sanitize_rich_text
from mulusa_theme_studio.render.placeholders import placeholder_svg
from mulusa_theme_studio.render.site import write_site


def ctx(doc, **kw):
    return RenderContext(doc=doc, **kw)


def test_text_is_escaped(template_doc):
    out = render_node({"id": "a", "type": "heading", "props": {"text": "<script>x</script>", "level": 2}}, ctx(template_doc))
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_unsafe_links_are_neutralised(template_doc):
    out = render_node({"id": "a", "type": "button", "props": {"label": "x", "href": "javascript:alert(1)"}}, ctx(template_doc))
    assert "javascript" not in out
    out = render_node({"id": "a", "type": "link", "props": {"label": "x", "href": "https://example.com/a"}}, ctx(template_doc))
    assert "https://example.com/a" in out


def test_style_values_cannot_escape_their_rule():
    for bad in ("red;} body{display:none", "url(http://evil)", "<script>", "expression(1)", "a\\b"):
        assert style_value(bad) is None
    assert declarations({"color": "$primary", "behaviour": "x", "padding": "1px;}"}) == "color:var(--mts-primary)"


def test_rich_text_keeps_format_and_drops_danger():
    out = sanitize_rich_text('<p onclick="x">Hi <strong>there</strong></p><script>evil()</script><a href="javascript:x">y</a><img src=x>')
    assert out == '<p>Hi <strong>there</strong></p><a href="#">y</a>'


def test_attribute_injection_in_ids_is_blocked(template_doc):
    node = {"id": 'x"><script>', "type": "section", "props": {}, "style": {"color": "red"}, "children": []}
    out = render_node(node, ctx(template_doc, editor=True))
    assert "<script>" not in out


def test_unknown_element_renders_nothing(template_doc):
    assert render_node({"id": "a", "type": "alien"}, ctx(template_doc)) == ""


def test_global_token_change_reaches_the_stylesheet(template_doc):
    a = tokens_css(template_doc["tokens"])
    changed = copy.deepcopy(template_doc["tokens"])
    changed["colors"]["primary"] = "#abcdef"
    changed["fonts"]["heading"] = "Anton"
    b = tokens_css(changed)
    assert "--mts-primary:#abcdef" in b and "'Anton'" in b and a != b


def test_placeholders_follow_the_palette(template_doc):
    ref = next(media_refs(template_doc))
    colors = copy.deepcopy(template_doc["tokens"]["colors"])
    before = placeholder_svg(ref, colors)
    colors.update(primary="#00ff00", secondary="#00ee00", accent="#00dd00")
    assert placeholder_svg(ref, colors) != before
    assert placeholder_svg(ref, colors) == placeholder_svg(ref, colors)  # Stable between renders.


def test_every_subject_and_art_style_draws(template_doc):
    colors = template_doc["tokens"]["colors"]
    for subject in ("portrait", "building", "food", "garment", "vinyl", "landscape", "interior", "circuit", "books", "abstract", "crane", "unknown"):
        for art in ("gradient", "mono", "soft", "flat", "line"):
            assert placeholder_svg({"seed": subject, "subject": subject, "ratio": 1.5}, colors, art).startswith("data:image/svg+xml,")


def test_site_is_complete_and_self_contained(tmp_path, template_doc):
    out = write_site(template_doc, tmp_path)
    assert set(out.pages) == {p["id"] for p in template_doc["pages"]}
    assert (tmp_path / "index.html").is_file()
    css = (tmp_path / "assets" / "style.css").read_text(encoding="utf-8")
    assert "@font-face" in css and "http" not in css.replace("http://www.w3.org", "")
    fonts = template_doc["tokens"]["fonts"]
    assert len(list((tmp_path / "assets" / "fonts").iterdir())) >= 2 and fonts["heading"] in css
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in html and "<main>" in html and "fonts.googleapis" not in html


def test_previews_contain_no_editor_code(tmp_path, template_doc):
    write_site(template_doc, tmp_path / "plain")
    write_site(template_doc, tmp_path / "editor", editor=True)
    plain = (tmp_path / "plain" / "index.html").read_text(encoding="utf-8")
    editor = (tmp_path / "editor" / "index.html").read_text(encoding="utf-8")
    assert "data-mts-id" not in plain and "mtsSelect" not in plain
    assert "data-mts-id" in editor and "mtsSelect" in editor


def test_internal_links_go_to_real_pages(tmp_path, template_doc):
    write_site(template_doc, tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for page in template_doc["pages"]:
        if not page.get("home"):
            assert f'href="{page["slug"]}.html"' in html
            assert (tmp_path / f"{page['slug']}.html").is_file()


def test_responsive_rules_are_written_in_the_right_order(tmp_path, template_doc):
    node = template_doc["pages"][0]["nodes"][0]
    node["responsive"] = {"tablet": {"style": {"padding": "11px"}}, "mobile": {"style": {"padding": "7px"}, "hidden": True}, "desktop": {"hidden": True}}
    write_site(template_doc, tmp_path)
    css = (tmp_path / "assets" / "style.css").read_text(encoding="utf-8")
    assert css.rindex("(max-width:1024px){") < css.rindex("(max-width:640px){")  # Generated rules, after base.css.
    cls = f".n-{node['id']}"
    assert f"{cls}{{display:none!important;padding:7px}}" in css
    assert f"{cls}{{padding:11px}}" in css


def test_columns_stack_on_mobile_unless_the_design_says_otherwise(template_doc):
    c = ctx(template_doc)
    render_node({"id": "a", "type": "columns", "props": {"columns": 4}, "children": []}, c)
    render_node({"id": "b", "type": "columns", "props": {"columns": 4}, "responsive": {"mobile": {"props": {"columns": 2}}}, "children": []}, c)
    mobile = "".join(c.responsive["mobile"])
    assert ".n-a{grid-template-columns:minmax(0,1fr)}" in mobile
    assert ".n-b{grid-template-columns:repeat(2,minmax(0,1fr))}" in mobile
    assert ".n-a{grid-template-columns:repeat(2,minmax(0,1fr))}" in "".join(c.responsive["tablet"])


def test_uploaded_assets_are_copied_and_paths_cannot_escape(tmp_path, template_doc):
    project = tmp_path / "project"
    (project / "assets").mkdir(parents=True)
    (project / "assets" / "logo.png").write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    template_doc["media"]["assets"] = [{"id": "a1", "file": "logo.png"}, {"id": "a2", "file": "../secret.txt"}]
    nodes = template_doc["pages"][0]["nodes"]
    nodes.append({"id": "i1", "type": "image", "props": {"media": {"kind": "asset", "id": "a1"}}, "style": {}})
    nodes.append({"id": "i2", "type": "image", "props": {"media": {"kind": "asset", "id": "a2"}}, "style": {}})
    out = write_site(template_doc, tmp_path / "site", project_folder=project)
    assert (tmp_path / "site" / "assets" / "media" / "logo.png").read_bytes() == b"png"
    assert not (tmp_path / "site" / "assets" / "media" / "secret.txt").exists()
    assert "../" not in out.pages["home"].read_text(encoding="utf-8")


# Reusing unchanged pages must never change the output ------------------------------
def _site_files(doc, folder):
    from mulusa_theme_studio.render.site import write_site

    site = write_site(doc, folder, editor=True)
    files = {path.name: path.read_text(encoding="utf-8") for path in site.pages.values()}
    files["style.css"] = (site.root / "assets" / "style.css").read_text(encoding="utf-8")
    return files


def _fresh_files(doc, folder):
    from mulusa_theme_studio.render import site

    site._page_cache.clear()
    return _site_files(doc, folder)


def _edits():
    from mulusa_theme_studio.core import design
    from mulusa_theme_studio.core.document import walk_nodes

    def first(doc, kind):
        return next(n for page in doc["pages"] for n in walk_nodes(page["nodes"]) if n["type"] == kind)

    def heading_size(doc):
        first(doc, "heading")["style"]["font_size"] = "41px"

    def later_page_text(doc):
        next(n for n in walk_nodes(doc["pages"][-1]["nodes"]) if n["type"] == "heading")["props"]["text"] = "Changed"

    def page_title(doc):
        doc["pages"][-1]["title"] = "Renamed page"

    def page_slug(doc):
        doc["pages"][-1]["slug"] = "renamed-page"

    def header_brand(doc):
        doc["site"]["header"]["props"]["brand"] = "New brand"

    def colour(doc):
        design.set_color(doc, "primary", "#123456")

    def art(doc):
        doc["media"]["art"] = "pattern" if doc["media"].get("art") != "pattern" else "gradient"

    def asset(doc):
        doc["media"]["assets"].append({"id": "a1", "file": "a.png", "name": "a"})
        first(doc, "image")["props"]["media"] = {"kind": "asset", "id": "a1"}

    return [heading_size, later_page_text, page_title, page_slug, header_brand, colour, art, asset]


@pytest.mark.parametrize("edit", _edits(), ids=lambda e: e.__name__)
def test_reused_pages_match_a_fresh_render(template_doc, tmp_path, edit):
    _site_files(template_doc, tmp_path / "warm")  # Fills the cache with the state before the edit.
    edit(template_doc)
    reused = _site_files(template_doc, tmp_path / "warm")
    assert reused == _fresh_files(template_doc, tmp_path / "fresh")


def test_unchanged_pages_are_not_rendered_again(template_doc, tmp_path, monkeypatch):
    from mulusa_theme_studio.render import site

    _fresh_files(template_doc, tmp_path)
    calls = []
    real = site.render_node
    monkeypatch.setattr(site, "render_node", lambda node, ctx: calls.append(ctx.current_page) or real(node, ctx))
    template_doc["pages"][0]["nodes"][0]["name"] = "Edited"
    site.write_site(template_doc, tmp_path, editor=True)
    assert set(calls) == {template_doc["pages"][0]["id"]}


def test_a_plain_render_never_reuses_an_editor_render(template_doc, tmp_path):
    from mulusa_theme_studio.render.site import write_site

    write_site(template_doc, tmp_path / "e", editor=True)
    plain = write_site(template_doc, tmp_path / "p")
    assert not any("data-mts-id" in body for body in plain.bodies.values())
