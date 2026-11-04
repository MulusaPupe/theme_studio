"""Stage 03 through the real window: forms, canvas, media dialogs and history together."""
from __future__ import annotations

import json

import pytest
from PIL import Image
from PySide6.QtTest import QTest

from mulusa_theme_studio.core import design, media
from mulusa_theme_studio.core.document import find_node, media_refs, walk_document, walk_nodes
from mulusa_theme_studio.core.project import Project
from mulusa_theme_studio.ui.richtext import RichTextField, document_to_html
from mulusa_theme_studio.ui.theme import palette_for

from .test_editor import click_node, drag_events, editor, rect_of, real_click, window  # noqa: F401
from .test_ui import js, loaded, settle


def node_of(w, kind, nth=0):
    return [n for n in walk_nodes(w.session.current_page["nodes"]) if n["type"] == kind][nth]


def choose(w, kind, nth=0):
    node = node_of(w, kind, nth)
    w.session.select(node["id"], origin="panel")
    settle(30)
    return node["id"]


def live(w, node_id):
    return find_node(w.session.document, node_id)


def computed(qtbot, w, node_id, prop):
    return js(qtbot, w, f"getComputedStyle(document.querySelector('[data-mts-id=\"{node_id}\"]')).getPropertyValue('{prop}')")


def wait_computed(qtbot, w, node_id, prop, value):
    qtbot.waitUntil(lambda: computed(qtbot, w, node_id, prop) == value, timeout=6000)


def mark_page(qtbot, w):
    """A flag on the live page: still there later means the page was patched, not reloaded."""
    js(qtbot, w, "window.__sameLoad=true;1")


def not_reloaded(qtbot, w):
    return js(qtbot, w, "window.__sameLoad===true") is True


def type_into(field, text):
    field.edit.setFocus()
    field.edit.selectAll()
    QTest.keyClicks(field.edit, text)


def pick(field, value):
    """What a person choosing from the dropdown does: Qt only reports activated for real choices."""
    index = field.combo.findData(value)
    assert index >= 0, value
    field.combo.setCurrentIndex(index)
    field.combo.activated.emit(index)


def image_file(tmp_path, name="photo.png", size=(640, 400), color=(30, 90, 170)):
    path = tmp_path / name
    Image.new("RGB", size, color).save(path)
    return path


def upload(w, path):
    return w.session.upload_media([str(path)])[0]


def media_panel(w):
    from mulusa_theme_studio.ui.panels.media_panel import MediaPanel

    return next(p for p in w.findChildren(MediaPanel))


# What the form shows ---------------------------------------------------------
@pytest.mark.parametrize("kind,present,absent", [
    ("heading", {"text", "level", "font_family", "font_size", "color", "margin"}, {"alt", "tone", "object_fit", "gap"}),
    ("text", {"text", "font_size", "line_height", "padding"}, {"level", "tone", "object_fit"}),
    ("section", {"tone", "background", "min_height", "padding"}, {"text", "level", "alt", "gap"}),
    ("image", {"alt", "object_fit", "position_x", "ratio", "media_choose", "media_crop"}, {"text", "level", "tone"}),
    ("button", {"label", "href", "variant", "aria_label"}, {"alt", "level", "tone"}),
])
def test_selected_element_shows_only_its_own_properties(editor, kind, present, absent):
    choose(editor, kind)
    names = set(editor.inspector.fields)
    assert present <= names, present - names
    assert not absent & names, absent & names


def test_form_shows_the_current_values(editor):
    node = live(editor, choose(editor, "heading"))
    fields = editor.inspector.fields
    assert fields["text"].edit.toPlainText() == node["props"]["text"]
    assert fields["level"].combo.currentData() == node["props"].get("level", 2)


def test_nothing_selected_shows_project_information(editor):
    editor.session.select("", origin="panel")
    settle(30)
    inspector = editor.inspector
    assert inspector.project_info.text().strip()
    assert inspector.swatch_widgets
    inspector.open_design.click()
    assert inspector.design.isVisible()
    inspector.show_tab(0)


def test_groups_collapse_and_stay_collapsed(editor):
    choose(editor, "heading")
    group = editor.inspector.groups["Typography"]
    was = group.body.isVisibleTo(group)
    group.header.click()
    assert group.body.isVisibleTo(group) is not was
    choose(editor, "text")
    again = editor.inspector.groups["Typography"]
    assert again is not group and again.body.isVisibleTo(again) is not was
    again.header.click()


# Acceptance 1, 2 and 10: text, fonts, colour and spacing -----------------------
def test_typing_updates_the_canvas_with_one_undo_step(editor, qtbot):
    node_id = choose(editor, "heading")
    original = live(editor, node_id)["props"]["text"]
    depth = editor.session.project.history.undo_depth
    mark_page(qtbot, editor)
    type_into(editor.inspector.fields["text"], "A new title")
    qtbot.waitUntil(lambda: js(qtbot, editor, f"document.querySelector('[data-mts-id=\"{node_id}\"]').textContent") == "A new title", timeout=6000)
    assert not_reloaded(qtbot, editor), "typing must not reload the page"
    assert editor.session.project.history.undo_depth == depth + 1
    assert editor.session.selected_id == node_id
    editor.session.undo()
    assert live(editor, node_id)["props"]["text"] == original
    settle(100)
    assert editor.session.selected_id == node_id
    assert editor.inspector.fields["text"].edit.toPlainText() == original


def test_change_heading_font_and_colour(editor, qtbot):
    node_id = choose(editor, "heading")
    fields = editor.inspector.fields
    pick(fields["font_family"], "Lora")
    assert live(editor, node_id)["style"]["font_family"] == "Lora"
    qtbot.waitUntil(lambda: "Lora" in computed(qtbot, editor, node_id, "font-family"), timeout=6000)
    fields["color"].hex.setText("#112233")
    fields["color"].hex.editingFinished.emit()
    assert live(editor, node_id)["style"]["color"] == "#112233"
    wait_computed(qtbot, editor, node_id, "color", "rgb(17, 34, 51)")
    fields["color"].chips["$accent"].click()
    assert live(editor, node_id)["style"]["color"] == "$accent"
    assert fields["color"].chips["$accent"].isChecked()


def test_paragraph_typography_and_spacing(editor, qtbot):
    node_id = choose(editor, "text")
    fields = editor.inspector.fields
    fields["font_size"].set_value("20px")
    fields["font_size"].edited.emit("20px")
    fields["line_height"].edited.emit(2)
    fields["text_align"].edited.emit("center")
    fields["padding"].sideEdited.emit("left", "33")
    wait_computed(qtbot, editor, node_id, "padding-left", "33px")
    assert computed(qtbot, editor, node_id, "font-size") == "20px"
    assert computed(qtbot, editor, node_id, "line-height") == "40px"
    assert computed(qtbot, editor, node_id, "text-align") == "center"


def test_slider_drag_is_one_undo_step_and_stays_responsive(editor, qtbot):
    node_id = choose(editor, "section")
    field = editor.inspector.fields["min_height"]
    before = dict(live(editor, node_id).get("style", {}))
    depth = editor.session.project.history.undo_depth
    mark_page(qtbot, editor)
    for value in range(300, 500, 10):
        field.edited.emit(f"{value}px")
    field.finished.emit()
    assert editor.session.project.history.undo_depth == depth + 1
    wait_computed(qtbot, editor, node_id, "min-height", "490px")
    assert not_reloaded(qtbot, editor)
    field.edited.emit("500px")
    assert editor.session.project.history.undo_depth == depth + 2, "a new gesture is a new step"
    editor.session.undo()
    editor.session.undo()
    assert live(editor, node_id).get("style", {}) == before


def test_real_slider_movement_uses_one_entry(editor, qtbot):
    choose(editor, "text")
    slider = editor.inspector.fields["line_height"].slider
    depth = editor.session.project.history.undo_depth
    slider.setSliderDown(True)
    for position in range(10, 30, 2):
        slider.setValue(position)
    slider.setSliderDown(False)
    slider.sliderReleased.emit()
    assert editor.session.project.history.undo_depth == depth + 1


def test_invalid_input_is_refused_and_the_form_recovers(editor, qtbot):
    node_id = choose(editor, "heading")
    before = json.dumps(live(editor, node_id), sort_keys=True)
    depth = editor.session.project.history.undo_depth
    field = editor.inspector.fields["color"]
    field.hex.setText("red;}body{display:none")
    field.hex.editingFinished.emit()
    assert json.dumps(live(editor, node_id), sort_keys=True) == before
    assert editor.session.project.history.undo_depth == depth
    assert field.hex.text() == field.value
    size = editor.inspector.fields["font_size"]
    size.edited.emit("url(http://evil)")
    assert json.dumps(live(editor, node_id), sort_keys=True) == before
    assert editor.session.selected_id == node_id


def test_device_override_leaves_desktop_alone(editor, qtbot):
    node_id = choose(editor, "heading")
    inspector = editor.inspector
    base = dict(live(editor, node_id).get("style", {}))
    inspector.scope_buttons["mobile"].click()
    assert editor.session.edit_scope == "mobile"
    inspector.fields["font_size"].edited.emit("19px")
    node = live(editor, node_id)
    assert node["responsive"]["mobile"]["style"]["font_size"] == "19px" and node.get("style", {}) == base
    settle(100)
    assert editor.inspector.fields["font_size"]._compose() == "19px", "the form shows the device's value"
    inspector.clear_scope.click()
    assert "mobile" not in live(editor, node_id).get("responsive", {})
    inspector.scope_buttons[""].click()
    assert editor.session.edit_scope == ""


# Acceptance 3: sections and tone ---------------------------------------------
def test_section_background_and_tone(editor, qtbot):
    node_id = choose(editor, "section", 1)
    fields = editor.inspector.fields
    for tone in ("surface", "inverse", "primary", "accent", "image"):
        pick(fields["tone"], tone)
        assert live(editor, node_id)["props"]["tone"] == tone
        qtbot.waitUntil(lambda t=tone: js(qtbot, editor, f"document.querySelector('[data-mts-id=\"{node_id}\"]').classList.contains('mts-tone-{t}')") is True, timeout=6000)
    fields = editor.inspector.fields
    fields["background"].edited.emit("#223344")
    wait_computed(qtbot, editor, node_id, "background-color", "rgb(34, 51, 68)")
    fields["background"].edited.emit("linear-gradient(90deg,$primary,#000000)")
    qtbot.waitUntil(lambda: "linear-gradient" in computed(qtbot, editor, node_id, "background-image"), timeout=6000)


def test_section_with_a_photo_keeps_the_image_tone(editor, qtbot, tmp_path):
    asset = upload(editor, image_file(tmp_path))
    node_id = choose(editor, "section", 1)
    editor.session.set_node_media(node_id, asset["id"], "background")
    settle(200)
    assert live(editor, node_id)["props"]["tone"] == "image"
    tone = editor.inspector.fields["tone"]
    assert not tone.combo.isEnabled()
    depth = editor.session.project.history.undo_depth
    assert not editor.session.edit_prop(node_id, "tone", "default")
    assert live(editor, node_id)["props"]["tone"] == "image" and editor.session.project.history.undo_depth == depth


# Acceptance 4 to 7: media ----------------------------------------------------
def test_upload_from_the_library_panel_and_inspect(editor, tmp_path):
    panel = media_panel(editor)
    panel.add_files([str(image_file(tmp_path))])
    assert panel.grid.count() == 1
    panel.grid.setCurrentRow(0)
    assert "640" in panel.info.text() and "400" in panel.info.text() and "PNG" in panel.info.text()
    panel.search.setText("nothing like it")
    assert all(panel.grid.item(i).isHidden() for i in range(panel.grid.count()))
    panel.search.setText("pho")
    assert not panel.grid.item(0).isHidden()
    panel.search.clear()
    panel.grid.setCurrentRow(0)
    panel.name.setText("Team")
    panel.name.editingFinished.emit()
    assert editor.session.document["media"]["assets"][0]["name"] == "Team"


def test_bad_upload_is_explained_and_changes_nothing(editor, tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"nope")
    messages = []
    editor.session.noticeRaised.connect(messages.append)
    depth = editor.session.project.history.undo_depth
    assert editor.session.upload_media([str(bad)]) == []
    assert editor.session.project.history.undo_depth == depth and editor.session.document["media"]["assets"] == []
    assert messages and "broken.png" in messages[-1]


def test_clicking_a_placeholder_opens_the_picker_and_replaces_only_that_image(editor, qtbot, tmp_path):
    page = next(p for p in editor.session.document["pages"] if any(n["type"] == "image" for n in walk_nodes(p["nodes"])))
    if editor.session.current_page is not page:
        loaded(qtbot, editor, lambda: editor.session.set_page(page["id"]))
        qtbot.waitUntil(lambda: js(qtbot, editor, "!!window.mtsReady"), timeout=8000)
    nodes = [n for n in walk_nodes(page["nodes"]) if n["type"] == "image"]
    node_id = nodes[0]["id"]
    others = {n["id"]: dict(n["props"]["media"]) for n in walk_document(editor.session.document) if n["type"] == "image" and n["id"] != node_id}
    r = rect_of(qtbot, editor, node_id)
    real_click(qtbot, editor, r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
    qtbot.waitUntil(lambda: getattr(editor, "media_dialog", None) is not None, timeout=6000)
    dialog = editor.media_dialog
    dialog.add_files([str(image_file(tmp_path))])
    assert dialog.asset_id
    dialog.use.click()
    qtbot.waitUntil(lambda: editor.media_dialog is None, timeout=3000)
    node = live(editor, node_id)
    assert node["props"]["media"]["kind"] == "asset" and node["id"] == node_id
    for other_id, ref in others.items():
        assert live(editor, other_id)["props"]["media"] == ref
    qtbot.waitUntil(lambda: js(qtbot, editor, f"(function(){{var i=document.querySelector('[data-mts-id=\"{node_id}\"] img')||document.querySelector('img[data-mts-id=\"{node_id}\"]');return !!i&&i.naturalWidth===640}})()") is True, timeout=8000)
    assert js(qtbot, editor, f"document.querySelector('[data-mts-id=\"{node_id}\"]').hasAttribute('data-mts-placeholder')") is False
    editor.session.undo()
    settle(100)
    assert live(editor, node_id)["props"]["media"]["kind"] == "placeholder"
    editor.session.redo()
    assert live(editor, node_id)["props"]["media"]["kind"] == "asset"


def test_cancelling_the_picker_changes_nothing(editor, qtbot):
    node_id = choose(editor, "image") if any(n["type"] == "image" for n in walk_nodes(editor.session.current_page["nodes"])) else None
    if node_id is None:
        pytest.skip("no image on this page")
    depth = editor.session.project.history.undo_depth
    editor.session.request_media_picker(node_id, "media", -1)
    qtbot.waitUntil(lambda: getattr(editor, "media_dialog", None) is not None, timeout=3000)
    editor.media_dialog.reject()
    qtbot.waitUntil(lambda: editor.media_dialog is None, timeout=3000)
    assert editor.session.project.history.undo_depth == depth


def go_to_images(w, qtbot):
    page = next(p for p in w.session.document["pages"] if sum(n["type"] == "image" for n in walk_nodes(p["nodes"])) >= 1)
    if w.session.current_page is not page:
        loaded(qtbot, w, lambda: w.session.set_page(page["id"]))
        qtbot.waitUntil(lambda: js(qtbot, w, "!!window.mtsReady"), timeout=8000)
    return page


def test_crop_and_reposition(editor, qtbot, tmp_path):
    page = go_to_images(editor, qtbot)
    asset = upload(editor, image_file(tmp_path))
    node_id = next(n["id"] for n in walk_nodes(page["nodes"]) if n["type"] == "image")
    editor.session.select(node_id, origin="panel")
    editor.session.set_node_media(node_id, asset["id"], "media")
    settle(100)
    original = media.asset_path(editor.session.project.folder, asset).read_bytes()
    editor.session.request_crop(node_id, "media")
    qtbot.waitUntil(lambda: getattr(editor, "media_dialog", None) is not None, timeout=3000)
    dialog = editor.media_dialog
    dialog.view.set_box(100, 50, 400, 250)
    dialog.accept()
    qtbot.waitUntil(lambda: editor.media_dialog is None, timeout=3000)
    ref = live(editor, node_id)["props"]["media"]
    made = media.find_asset(editor.session.document, ref["id"])
    assert made["id"] != asset["id"] and (made["width"], made["height"]) == (300, 200) and made["parent"] == asset["id"]
    assert media.asset_path(editor.session.project.folder, asset).read_bytes() == original
    settle(100)
    fields = editor.inspector.fields
    fields["position_x"].spin.setValue(25)
    fields["object_fit"].edited.emit("contain")
    node = live(editor, node_id)
    assert node["style"]["object_position"].startswith("25%") and node["style"]["object_fit"] == "contain"
    editor.session.end_gesture()
    for _ in range(3):
        editor.session.undo()
    assert live(editor, node_id)["props"]["media"]["id"] == asset["id"]
    assert media.find_asset(editor.session.document, made["id"]) is None


def test_reuse_replace_everywhere_and_refuse_deleting_while_used(editor, qtbot, tmp_path, monkeypatch):
    doc = editor.session.document
    asset = upload(editor, image_file(tmp_path))
    images = [n for n in walk_document(doc) if n["type"] == "image"]
    pages = [p for p in doc["pages"] if any(n["type"] == "image" for n in walk_nodes(p["nodes"]))]
    targets = [next(n for n in walk_nodes(p["nodes"]) if n["type"] == "image")["id"] for p in pages[:2]]
    for target in targets:
        editor.session.set_node_media(target, asset["id"], "media")
    assert media.usage_count(editor.session.document, asset["id"]) == len(targets) >= 2
    assert not editor.session.delete_asset(asset["id"])
    assert media.find_asset(editor.session.document, asset["id"])
    replacement = image_file(tmp_path, "other.png", color=(1, 200, 90))
    assert editor.session.replace_asset_everywhere(asset["id"], str(replacement)) == len(targets)
    new_id = live(editor, targets[0])["props"]["media"]["id"]
    assert new_id != asset["id"] and live(editor, targets[1])["props"]["media"]["id"] == new_id
    assert len(images) > len(targets) and any(r.get("kind") == "placeholder" for r in media_refs(editor.session.document))


def test_delete_unused_then_undo_brings_the_file_back(editor, qtbot, tmp_path):
    asset = upload(editor, image_file(tmp_path))
    path = media.asset_path(editor.session.project.folder, asset)
    assert editor.session.delete_asset(asset["id"])
    assert not path.exists()
    editor.session.undo()
    assert path.is_file() and media.find_asset(editor.session.document, asset["id"])


# Acceptance 8 and 9: global design ------------------------------------------
def root_var(qtbot, w, name):
    return js(qtbot, w, f"getComputedStyle(document.body).getPropertyValue('--mts-{name}').trim()")


def test_global_palette_updates_the_canvas_and_undoes(editor, qtbot):
    inspector = editor.inspector
    inspector.show_tab(1)
    design_panel = inspector.design
    before = dict(editor.session.document["tokens"]["colors"])
    mark_page(qtbot, editor)
    box = design_panel.palette_box
    index = next(i for i in range(box.count()) if box.itemData(i) and box.itemData(i)["colors"]["primary"] != before["primary"])
    design_panel._apply_palette(index)
    colors = editor.session.document["tokens"]["colors"]
    assert colors["primary"] != before["primary"]
    qtbot.waitUntil(lambda: root_var(qtbot, editor, "primary") == colors["primary"], timeout=6000)
    assert not_reloaded(qtbot, editor)
    editor.session.undo()
    assert editor.session.document["tokens"]["colors"] == before
    qtbot.waitUntil(lambda: root_var(qtbot, editor, "primary") == before["primary"], timeout=8000)
    inspector.show_tab(0)


def test_global_colour_field_reaches_elements_using_the_token(editor, qtbot):
    node_id = choose(editor, "heading")
    editor.inspector.fields["color"].chips["$accent"].click()
    editor.inspector.show_tab(1)
    field = editor.inspector.design.color_fields["accent"]
    field.hex.setText("#00aa55")
    field.hex.editingFinished.emit()
    wait_computed(qtbot, editor, node_id, "color", "rgb(0, 170, 85)")
    editor.inspector.show_tab(0)


def test_global_fonts_and_type(editor, qtbot):
    editor.inspector.show_tab(1)
    fields = editor.inspector.design.fields
    pick(fields["font_heading"], "Lora")
    pick(fields["font_body"], "Inter")
    tokens = editor.session.document["tokens"]
    assert tokens["fonts"]["heading"] == "Lora" and tokens["fonts"]["body"] == "Inter"
    qtbot.waitUntil(lambda: "Lora" in root_var(qtbot, editor, "font-heading"), timeout=6000)
    qtbot.waitUntil(lambda: js(qtbot, editor, "document.fonts.check(\"16px 'Lora'\")") is True, timeout=8000)
    depth = editor.session.project.history.undo_depth
    for value in (17.5, 18, 18.5, 19):
        fields["type_base"].edited.emit(value)
    fields["type_base"].finished.emit()
    assert editor.session.project.history.undo_depth == depth + 1
    qtbot.waitUntil(lambda: "19" in root_var(qtbot, editor, "body-size"), timeout=6000)
    editor.inspector.show_tab(0)


# Acceptance 12: save and reopen ---------------------------------------------
def test_everything_survives_save_and_reopen(editor, qtbot, tmp_path):
    session = editor.session
    asset = upload(editor, image_file(tmp_path))
    node_id = next(n["id"] for n in walk_document(session.document) if n["type"] == "image")
    session.set_node_media(node_id, asset["id"], "media")
    session.edit_style(node_id, "object_fit", "contain")
    session.edit_design("Accent", lambda d: design.set_color(d, "accent", "#00aa55"))
    session.end_gesture()
    session.project.save()
    reopened = Project.open(session.project.folder)
    node = find_node(reopened.document, node_id)
    assert node["props"]["media"] == {"kind": "asset", "id": asset["id"]} and node["style"]["object_fit"] == "contain"
    assert reopened.document["tokens"]["colors"]["accent"] == "#00aa55"
    assert media.missing_files(reopened.folder, reopened.document) == []


def test_preview_output_has_no_editor_markers(editor, qtbot, tmp_path):
    from mulusa_theme_studio.render.site import write_site

    site = write_site(editor.session.document, tmp_path / "plain")
    for path in site.pages.values():
        html = path.read_text(encoding="utf-8")
        for marker in ("data-mts-placeholder", "mtsPatch", "data-mts-id"):
            assert marker not in html


# Rich text -------------------------------------------------------------------
def test_rich_text_round_trip_and_sanitising(qtbot):
    field = RichTextField(palette_for("dark"))
    qtbot.addWidget(field)
    seen = []
    field.edited.connect(seen.append)
    field.set_value("<p>Hello <strong>bold</strong> and <em>soft</em></p><ul><li>One</li></ul>")
    out = document_to_html(field.edit.document())
    assert "<strong>bold</strong>" in out and "<em>soft</em>" in out and "<li>One</li>" in out
    field.set_value('<p onclick="x()">ok<script>alert(1)</script></p>')
    out = document_to_html(field.edit.document())
    assert "script" not in out and "onclick" not in out and "alert" not in out
    assert not field.add_link("javascript:alert(1)")


# The bridge stays narrow -----------------------------------------------------
def test_page_cannot_open_the_picker_for_something_else(editor, qtbot):
    editor.session.request_media_picker("no-such-node", "media", -1)
    editor.session.request_media_picker(node_of(editor, "heading")["id"], "media", -1)
    settle(50)
    assert getattr(editor, "media_dialog", None) is None


# Stage 02 still working after all of the above --------------------------------
def test_drag_insert_still_works_after_property_edits(editor, qtbot):
    node_id = choose(editor, "heading")
    editor.session.edit_style(node_id, "color", "#112233")
    editor.session.end_gesture()
    section = node_of(editor, "section", 1)
    count = sum(1 for _ in walk_document(editor.session.document))
    r = rect_of(qtbot, editor, section["id"])
    drag_events(editor, "heading", [(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)])
    qtbot.waitUntil(lambda: sum(1 for _ in walk_document(editor.session.document)) == count + 1, timeout=8000)
    assert live(editor, node_id)["style"]["color"] == "#112233"


def test_click_selects_after_a_live_patch(editor, qtbot):
    node_id = choose(editor, "heading")
    editor.inspector.fields["font_size"].edited.emit("44px")
    settle(150)
    editor.session.end_gesture()
    other = node_of(editor, "text")
    click_node(qtbot, editor, other["id"])
    qtbot.waitUntil(lambda: editor.session.selected_id == other["id"], timeout=4000)
    click_node(qtbot, editor, node_id)
    qtbot.waitUntil(lambda: editor.session.selected_id == node_id, timeout=4000)


# Found by looking at the interface ---------------------------------------------
@pytest.mark.parametrize("field,kind", [("text", "heading"), ("alt", "image"), ("line_height", "text")])
def test_inputs_follow_the_dark_theme(editor, qtbot, field, kind):
    """Text boxes and number fields once stayed white on dark, with pale, unreadable text."""
    go_to_images(editor, qtbot)
    choose(editor, kind)
    control = editor.inspector.fields[field]
    target = getattr(control, "edit", None) or control.spin
    colour = target.grab().toImage().pixelColor(target.width() // 2, target.height() - 6)
    assert editor.pal.name == "dark" and colour.lightness() < 90


def test_unset_line_height_shows_auto_and_can_return_to_it(editor):
    node_id = choose(editor, "text")
    field = editor.inspector.fields["line_height"]
    assert "line_height" not in live(editor, node_id).get("style", {})
    assert field.spin.text() == "Auto"
    field.slider.setValue(field.slider.value() + 10)
    assert float(live(editor, node_id)["style"]["line_height"]) == pytest.approx(1.25)
    field.slider.setValue(0)
    assert "line_height" not in live(editor, node_id).get("style", {})
    assert field.spin.text() == "Auto"


def test_placeholder_shows_how_to_replace_it(editor, qtbot, tmp_path):
    page = go_to_images(editor, qtbot)
    node_id = next(n["id"] for n in walk_nodes(page["nodes"]) if n["type"] == "image")
    chip = "document.getElementById('mts-replace-chip')||document.querySelector('.mts-replace-chip')"
    shown = lambda: js(qtbot, editor, f"(function(){{var c={chip};return !!c&&c.style.display==='block'}})()") is True
    assert not shown()
    editor.session.select(node_id, origin="panel")
    qtbot.waitUntil(shown, timeout=4000)
    assert js(qtbot, editor, f"({chip}).textContent") == "Click to choose an image"
    editor.session.set_node_media(node_id, upload(editor, image_file(tmp_path))["id"], "media")
    qtbot.waitUntil(lambda: not shown(), timeout=6000)
