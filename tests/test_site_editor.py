"""Stages 04 to 06 through the real window: pages, menu, devices, posts lists and the export dialog."""
from __future__ import annotations

import zipfile

import pytest
from PySide6.QtWidgets import QPushButton

from mulusa_theme_studio.core.document import find_node, find_page, home_page, site_pages, walk_nodes
from mulusa_theme_studio.ui.export_dialog import ExportDialog

from .test_editor import editor, window  # noqa: F401
from .test_ui import js, settle


@pytest.fixture
def w(editor):  # noqa: F811
    return editor


def panel(w):
    return w.side_stack.widget(2)


def doc(w):
    return w.session.document


def of(w, kind, nth=0):
    return [n for n in walk_nodes(w.session.current_page["nodes"]) if n["type"] == kind][nth]


def page_ids(w):
    return [p["id"] for p in site_pages(doc(w))]


# Pages ----------------------------------------------------------------------
def test_add_page_with_a_layout_opens_it_and_undo_removes_it(w, qtbot):
    before = page_ids(w)
    p = panel(w)
    p.new_title.setText("Team")
    p.new_starter.setCurrentIndex(p.new_starter.findData("services"))
    p.add_btn.click()
    page = w.session.current_page
    assert page["title"] == "Team" and page["id"] not in before and page["nodes"]
    assert p.new_title.text() == ""
    assert any(p.list.item(i).text() == "Team" for i in range(p.list.count()))
    w.session.undo()
    assert page_ids(w) == before and find_page(doc(w), page["id"]) is None


def test_add_page_without_a_title_explains_and_changes_nothing(w):
    before = page_ids(w)
    panel(w).new_title.setText("  ")
    panel(w).add_btn.click()
    assert page_ids(w) == before


def test_rename_and_address_change_through_the_form(w):
    p = panel(w)
    target = next(pg for pg in site_pages(doc(w)) if not pg.get("home"))
    w.session.set_page(target["id"])
    p.title.setText("Renamed")
    p.title.editingFinished.emit()
    p.slug.setText("Brand New Address")
    p.slug.editingFinished.emit()
    page = find_page(doc(w), target["id"])
    assert page["title"] == "Renamed" and page["slug"] == "brand-new-address"


def test_homepage_address_cannot_be_edited_and_cannot_be_deleted(w):
    w.session.set_page(home_page(doc(w))["id"])
    p = panel(w)
    assert not p.slug.isEnabled() and not p.delete_btn.isEnabled() and not p.home_btn.isEnabled()
    assert "cannot be deleted" in p.delete_btn.toolTip()


def test_delete_asks_first_and_declining_changes_nothing(w, monkeypatch):
    p = panel(w)
    target = next(i["page"] for i in doc(w)["navigation"]["primary"] if i.get("page") and not find_page(doc(w), i["page"]).get("home"))
    w.session.set_page(target)
    asked = []
    monkeypatch.setattr(p, "_confirm", lambda title, text: asked.append(text) or False)
    p.delete_btn.click()
    assert find_page(doc(w), target) and "menu link" in asked[0]
    monkeypatch.setattr(p, "_confirm", lambda title, text: True)
    p.delete_btn.click()
    assert find_page(doc(w), target) is None
    assert not any(i.get("page") == target for i in doc(w)["navigation"]["primary"])
    assert w.session.current_page["id"] == home_page(doc(w))["id"]
    w.session.undo()
    assert find_page(doc(w), target) and any(i.get("page") == target for i in doc(w)["navigation"]["primary"])


def test_duplicate_reorder_and_homepage_buttons(w):
    p = panel(w)
    source = next(pg for pg in site_pages(doc(w)) if not pg.get("home"))
    w.session.set_page(source["id"])
    p.duplicate_btn.click()
    copy = w.session.current_page
    assert copy["id"] != source["id"] and "copy" in copy["title"].lower()
    order = page_ids(w)
    p.up_btn.click()
    assert page_ids(w).index(copy["id"]) == order.index(copy["id"]) - 1
    p.home_btn.click()
    assert home_page(doc(w))["id"] == copy["id"]


def test_each_page_keeps_its_content_when_switching_and_through_undo(w):
    first = w.session.current_page["id"]
    heading = of(w, "heading")
    w.session.edit_prop(heading["id"], "text", "Only here")
    other = next(i for i in page_ids(w) if i != first)
    w.session.set_page(other)
    assert w.session.current_page["id"] == other
    w.session.set_page(first)
    assert find_node(doc(w), heading["id"])["props"]["text"] == "Only here"
    w.session.undo()
    assert find_node(doc(w), heading["id"])["props"]["text"] != "Only here"


def test_landing_layout_removes_the_header_from_the_canvas(w, qtbot):
    p = panel(w)
    assert js(qtbot, w, "!!document.querySelector('.mts-header')")
    w.session.set_page_details(w.session.page_id, layout="landing")
    qtbot.waitUntil(lambda: js(qtbot, w, "!document.querySelector('.mts-header')") is True, timeout=8000)
    assert p.layout_choice.currentData() == "landing"


# Menu -----------------------------------------------------------------------
def test_each_menu_link_is_edited_on_its_own_and_reaches_the_canvas(w, qtbot):
    p = panel(w)
    p.nav.setCurrentRow(1)
    item = p._nav_item()
    others = [i["label"] for i in doc(w)["navigation"]["primary"] if i["id"] != item["id"]]
    p.nav_label.setText("Renamed link")
    p.nav_label.editingFinished.emit()
    assert [i["label"] for i in doc(w)["navigation"]["primary"] if i["id"] != item["id"]] == others
    qtbot.waitUntil(lambda: js(qtbot, w, "[...document.querySelectorAll('.mts-nav a')].some(a=>a.textContent==='Renamed link')") is True, timeout=8000)


def test_menu_links_can_be_added_moved_retargeted_and_removed(w):
    p = panel(w)
    count = len(doc(w)["navigation"]["primary"])
    p.nav_add.click()
    menu = doc(w)["navigation"]["primary"]
    assert len(menu) == count + 1
    new = p._nav_item()
    assert new["id"] == menu[-1]["id"]
    p.nav_up.click()
    assert doc(w)["navigation"]["primary"][-2]["id"] == new["id"]
    p._nav_target_done("https://example.com")
    assert p._nav_item()["url"] == "https://example.com"
    p.nav_remove.click()
    assert len(doc(w)["navigation"]["primary"]) == count


def test_an_unsafe_menu_address_is_refused(w):
    p = panel(w)
    p.nav.setCurrentRow(0)
    before = dict(p._nav_item())
    p._nav_target_done("javascript:alert(1)")
    assert p._nav_item() == before


def test_header_form_sets_layout_mobile_menu_and_button(w, qtbot):
    header = doc(w)["site"]["header"]
    w.session.select(header["id"])
    settle(30)
    inspector = w.inspector
    assert not any("Stage" in label_.text() for label_ in inspector.findChildren(type(inspector.sel_name)))
    w.session.edit_prop(header["id"], "layout", "centered")
    qtbot.waitUntil(lambda: js(qtbot, w, "!!document.querySelector('.mts-header-centered')") is True, timeout=8000)
    w.session.edit_prop(header["id"], "mobile_menu", "inline")
    qtbot.waitUntil(lambda: js(qtbot, w, "!!document.querySelector('.mts-nav-inline')") is True, timeout=8000)
    inspector.fields["cta_label"].edited.emit("Talk to us")
    assert header["id"] and doc(w)["site"]["header"]["props"]["cta"]["label"] == "Talk to us"


# Devices --------------------------------------------------------------------
def test_viewing_a_device_edits_that_device(w, qtbot):
    w.session.set_viewport("mobile")
    assert w.session.edit_scope == "mobile"
    w.session.set_viewport("desktop")
    assert w.session.edit_scope == ""
    w.session.set_edit_scope("tablet")
    assert w.session.viewport == "tablet"
    w.session.set_edit_scope("desktop")
    assert (w.session.edit_scope, w.session.viewport) == ("desktop", "desktop")


def test_mobile_edit_leaves_desktop_and_says_where_values_come_from(w, qtbot):
    heading = of(w, "heading")
    before = dict(find_node(doc(w), heading["id"]).get("style") or {})
    w.session.select(heading["id"])
    w.session.set_viewport("mobile")
    settle(30)
    origin = w.inspector.origins
    assert origin["font_size"].text() == "Inherited from desktop"
    w.session.edit_style(heading["id"], "font_size", "19px")
    w.inspector.refresh()
    assert origin["font_size"].text() == "Overridden for mobile"
    assert (find_node(doc(w), heading["id"]).get("style") or {}) == before
    qtbot.waitUntil(lambda: js(qtbot, w, f"getComputedStyle(document.querySelector('[data-mts-id=\"{heading['id']}\"]')).fontSize") == "19px", timeout=8000)
    w.session.reset_style(heading["id"], "font_size")
    w.inspector.refresh()
    assert origin["font_size"].text() == "Inherited from desktop"
    assert "mobile" not in (find_node(doc(w), heading["id"]).get("responsive") or {})


def test_mobile_says_when_a_value_comes_from_tablet(w):
    heading = of(w, "heading")
    w.session.select(heading["id"])
    w.session.set_viewport("tablet")
    settle(30)
    w.session.edit_style(heading["id"], "font_size", "30px")
    w.session.set_viewport("mobile")
    settle(30)
    assert w.inspector.origins["font_size"].text() == "Inherited from tablet"


def test_hide_on_a_device_and_reset_everything(w, qtbot):
    image = of(w, "image")
    w.session.select(image["id"])
    w.session.set_viewport("mobile")
    settle(30)
    w.inspector.fields["hidden"].edited.emit(True)
    assert find_node(doc(w), image["id"])["responsive"]["mobile"]["hidden"] is True
    qtbot.waitUntil(lambda: js(qtbot, w, f"getComputedStyle(document.querySelector('[data-mts-id=\"{image['id']}\"]')).display") == "none", timeout=8000)
    w.inspector.refresh()
    assert w.inspector.clear_scope.isVisible() or w.inspector.clear_scope.isVisibleTo(w.inspector)
    w.inspector.clear_scope.click()
    assert "responsive" not in find_node(doc(w), image["id"])


def test_columns_can_differ_on_a_device(w):
    columns = of(w, "columns")
    w.session.select(columns["id"])
    w.session.set_viewport("mobile")
    settle(30)
    w.inspector.fields["device_columns"].edited.emit(2)
    assert find_node(doc(w), columns["id"])["responsive"]["mobile"]["props"]["columns"] == 2
    w.session.undo()
    assert "mobile" not in (find_node(doc(w), columns["id"]).get("responsive") or {})


# Posts ----------------------------------------------------------------------
def add_posts(w):
    w.session.insert_component("latest-posts", f"page:{w.session.page_id}", 0)
    settle(30)
    return of(w, "query")


def test_posts_list_settings_reach_the_document_and_the_canvas(w, qtbot):
    query = add_posts(w)
    w.session.select(query["id"])
    settle(30)
    fields = w.inspector.fields
    fields["count"].edited.emit(5)
    assert find_node(doc(w), query["id"])["props"]["source"]["count"] == 5
    qtbot.waitUntil(lambda: js(qtbot, w, f"document.querySelector('[data-mts-id=\"{query['id']}\"]').querySelectorAll('.mts-query-card').length") == 5, timeout=8000)
    fields = w.inspector.fields
    fields["layout"].edited.emit("list")
    w.inspector.fields["order"].edited.emit("title:asc")
    w.inspector.fields["categories"].edited.emit("News, Big Projects")
    source = find_node(doc(w), query["id"])["props"]["source"]
    assert (source["order_by"], source["order"], source["categories"]) == ("title", "asc", ["news", "big-projects"])
    w.inspector.fields["show_excerpt"].edited.emit(False)
    assert find_node(doc(w), query["id"])["props"]["hide"] == ["excerpt"]
    w.inspector.fields["show_excerpt"].edited.emit(True)
    assert find_node(doc(w), query["id"])["props"]["hide"] == []


def test_the_canvas_says_that_posts_are_samples(w, qtbot):
    add_posts(w)
    qtbot.waitUntil(lambda: js(qtbot, w, "(document.querySelector('.mts-sample-tag')||{}).textContent||''") == "Live posts: samples shown here", timeout=8000)


def test_post_parts_are_offered_only_in_the_single_post_template(w):
    panel_ = w.components_panel
    assert not panel_.post_holder.isVisibleTo(panel_)
    panel(w).role_rows["single"][1].click()
    assert w.session.current_page["role"] == "single"
    assert panel_.post_holder.isVisibleTo(panel_)
    assert panel(w).role_rows["single"][0].text().endswith("yours")
    assert w.session.current_page["id"] not in page_ids(w)


def test_a_post_template_can_go_back_to_the_default(w, monkeypatch):
    p = panel(w)
    w.session.open_role_page("archive")
    monkeypatch.setattr(p, "_confirm", lambda *a: True)
    p.role_rows["archive"][2].click()
    assert not any(pg.get("role") == "archive" for pg in doc(w)["pages"])


# Export ---------------------------------------------------------------------
def dialog(w, tmp_path, qtbot):
    d = ExportDialog(w.session, None, w)
    qtbot.addWidget(d)
    d.name.setText("Dialog Theme")
    d.author.setText("Someone")
    d.folder.setText(str(tmp_path))
    return d


def test_export_button_works_on_a_project_and_says_so(w):
    assert w.export_btn.isEnabled() and "WordPress" in w.export_btn.toolTip()


def test_dialog_check_then_export_writes_real_zips(w, tmp_path, qtbot):
    d = dialog(w, tmp_path, qtbot)
    assert not d.open_btn.isEnabled()
    d.check_btn.click()
    assert "can be exported" in d.summary.text() or "No problems" in d.summary.text()
    assert not list(tmp_path.glob("*.zip")), "checking writes nothing"
    d.export_btn.click()
    assert d.result is not None and d.open_btn.isEnabled()
    with zipfile.ZipFile(tmp_path / "dialog-theme.zip") as archive:
        assert "dialog-theme/style.css" in archive.namelist()
        assert b"Author: Someone" in archive.read("dialog-theme/style.css")
    assert (tmp_path / "dialog-theme-content.zip").is_file()
    assert "Upload Theme" in d.next_steps.text() and "Create the pages" in d.next_steps.text()


def test_dialog_can_leave_out_the_plugin_and_explains_the_other_route(w, tmp_path, qtbot):
    d = dialog(w, tmp_path, qtbot)
    d.include_plugin.setChecked(False)
    d.export_btn.click()
    assert d.result.plugin is None and not (tmp_path / "dialog-theme-content.zip").exists()
    assert "starter layout" in d.next_steps.text()


def test_a_missing_image_means_no_export_and_no_success_message(w, tmp_path, qtbot):
    source = tmp_path / "pic.png"
    from PIL import Image

    Image.new("RGB", (300, 200), "red").save(source)
    asset = w.session.upload_media([source])[0]
    image = of(w, "image")
    w.session.set_node_media(image["id"], asset["id"])
    (w.session.project.folder / "assets" / asset["file"]).unlink()
    d = dialog(w, tmp_path / "out", qtbot)
    d.check_btn.click()
    assert "must be fixed" in d.summary.text()
    assert any(asset["file"] in d.issues.item(i).text() for i in range(d.issues.count()))
    d.export_btn.click()
    assert d.result is None and not d.open_btn.isEnabled() and "Nothing was exported" in d.summary.text()
    assert not list((tmp_path / "out").glob("*.zip")) if (tmp_path / "out").exists() else True


def test_dialog_switches_to_a_static_site_and_shows_only_what_applies(w, tmp_path, qtbot):
    d = dialog(w, tmp_path, qtbot)
    d.kind.setCurrentIndex(d.kind.findData("static"))
    assert d.is_static() and "static" in d.heading.text()
    assert d.include_plugin.isHidden() and not d.static_note.isHidden()
    assert d.form.isRowVisible(d.form_email) and not d.form.isRowVisible(d.author)
    d.kind.setCurrentIndex(d.kind.findData("wordpress"))
    assert not d.include_plugin.isHidden() and not d.form.isRowVisible(d.form_email)


def test_dialog_static_export_refuses_forms_with_nowhere_to_go_then_writes_the_site(w, tmp_path, qtbot):
    d = dialog(w, tmp_path, qtbot)
    d.kind.setCurrentIndex(d.kind.findData("static"))
    d.export_btn.click()
    assert d.result is None and "Nothing was exported" in d.summary.text()
    assert any("form" in d.issues.item(i).text().lower() for i in range(d.issues.count()))
    d.form_email.setText("hello@example.com")
    d.export_btn.click()
    assert d.result is not None and d.open_btn.isEnabled()
    assert (tmp_path / "dialog-theme-site" / "index.html").is_file()
    assert zipfile.ZipFile(tmp_path / "dialog-theme-site.zip").testzip() is None
    assert "index.html" in d.next_steps.text()


def test_the_design_itself_is_the_screenshot(w):
    assert w.design_screenshot()[:8] == b"\x89PNG\r\n\x1a\n"


def test_every_new_button_is_connected(w):
    dead = [b.toolTip() or b.text() for b in panel(w).findChildren(QPushButton) if b.receivers("2clicked(bool)") == 0 and b.receivers("2clicked()") == 0]
    assert dead == []
