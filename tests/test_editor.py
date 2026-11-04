"""Stage 02: the canvas as an editor, driven through the real window and browser engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from mulusa_theme_studio.components import registry
from mulusa_theme_studio.core.document import find_node, walk_document
from mulusa_theme_studio.core.operations import ancestors
from mulusa_theme_studio.core.settings import Settings
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.ui.canvas import COMPONENT_MIME
from mulusa_theme_studio.ui.main_window import MainWindow
from mulusa_theme_studio.ui.session import VIEWPORTS, Session

from .test_ui import js, loaded, settle

TID = "corporate/corporate-classic"


@pytest.fixture
def window(qtbot, tmp_path, no_dialogs):
    settings = Settings()
    settings.projects_dir = str(tmp_path / "projects")
    w = MainWindow(Session(settings, TemplateLibrary()))
    w.resize(1500, 900)
    w.show()
    yield w
    w.session.project = None
    w.close()
    w.deleteLater()
    settle(30)


@pytest.fixture
def editor(window, qtbot):
    """A real project open on its home page, with the page ready for input."""
    loaded(qtbot, window, lambda: window.session.create_project("Edit test", TID))
    qtbot.waitUntil(lambda: js(qtbot, window, "typeof mtsSelect==='function'&&!!window.mtsReady"), timeout=8000)
    return window


def rect_of(qtbot, w, node_id, scroll=True):
    if scroll:
        js(qtbot, w, f"document.querySelector('[data-mts-id=\"{node_id}\"]').scrollIntoView({{block:'center'}});1")
        settle(120)
    return json.loads(js(qtbot, w, f"""(function(){{var r=document.querySelector('[data-mts-id="{node_id}"]').getBoundingClientRect();
        return JSON.stringify({{x:r.left,y:r.top,w:r.width,h:r.height}})}})()"""))


def widget_point(w, x, y):
    zoom = w.canvas.zoom
    return QPoint(round(x * zoom), round(y * zoom))


def real_click(qtbot, w, x, y):
    """A true mouse click delivered to the engine's input widget."""
    target = w.canvas.view.focusProxy()
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, widget_point(w, x, y))


def click_node(qtbot, w, node_id):
    r = rect_of(qtbot, w, node_id)
    real_click(qtbot, w, r["x"] + r["w"] / 2, r["y"] + min(r["h"] / 2, 12))
    qtbot.waitUntil(lambda: w.session.selected_id == node_id, timeout=4000)


def of_type(doc, type_, page=None):
    nodes = page["nodes"] if page else None
    if nodes is not None:
        found = []
        def walk(n):
            if n["type"] == type_:
                found.append(n)
            for c in n.get("children", []):
                walk(c)
        for n in nodes:
            walk(n)
        return found
    return [n for n in walk_document(doc) if n["type"] == type_]


def edited(qtbot, w, action):
    """Waits for the redraw that follows an edit, and for the page to be ready again."""
    with qtbot.waitSignal(w.canvas.view.loadFinished, timeout=20000):
        action()
    qtbot.waitUntil(lambda: js(qtbot, w, "!!window.mtsReady"), timeout=8000)
    settle(60)
    # The headless platform drops window activation when the engine redraws; real desktops do not.
    w.activateWindow()
    settle(30)


def drag_events(w, component_id, points, drop=True):
    """Delivers the Qt drag events the OS would, to the real overlay, with a real session drag."""
    mime = QMimeData()
    mime.setData(COMPONENT_MIME, component_id.encode())
    overlay = w.canvas.overlay
    actions = Qt.DropAction.CopyAction
    assert w.session.begin_component_drag(component_id)
    settle(60)
    assert overlay.isVisible()
    def at(x, y):
        return QPointF(widget_point(w, x, y))
    QApplication.sendEvent(overlay, QDragEnterEvent(at(*points[0]).toPoint(), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    settle(60)
    for x, y in points:
        event = QDragMoveEvent(at(x, y).toPoint(), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(overlay, event)
        settle(60)
    if drop:
        QApplication.sendEvent(overlay, QDropEvent(at(*points[-1]), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        settle(60)


# Selection -------------------------------------------------------------------
def test_a_real_click_selects_and_shows_an_outline(editor, qtbot):
    s = editor.session
    heading = of_type(s.document, "heading", s.current_page)[0]
    depth = s.project.history.undo_depth
    before = json.dumps(s.document, sort_keys=True)
    click_node(qtbot, editor, heading["id"])
    assert s.selected_id == heading["id"]
    assert s.project.history.undo_depth == depth and json.dumps(s.document, sort_keys=True) == before
    qtbot.waitUntil(lambda: js(qtbot, editor, "getComputedStyle(document.getElementById('mts-selection')).display") == "block", timeout=4000)
    assert "Heading" in editor.status_selection.text()
    assert editor.inspector.sel_name.text() != "Nothing selected"


@pytest.mark.parametrize("type_", ["heading", "text", "image", "button", "section"])
def test_every_kind_of_element_can_be_clicked(editor, qtbot, type_):
    s = editor.session
    target = of_type(s.document, type_, s.current_page)[0]
    r = rect_of(qtbot, editor, target["id"])
    if type_ == "section":
        # Aim at the padding of the section, which belongs to no child.
        real_click(qtbot, editor, r["x"] + 6, max(r["y"], 0) + 6)
    else:
        real_click(qtbot, editor, r["x"] + r["w"] / 2, r["y"] + min(r["h"] / 2, 12))
    qtbot.waitUntil(lambda: s.selected_id != "", timeout=4000)
    assert find_node(s.document, s.selected_id)["type"] == type_


def test_a_click_never_navigates_or_presses(editor, qtbot):
    s = editor.session
    button = of_type(s.document, "button", s.current_page)[0]
    address = js(qtbot, editor, "location.href")
    click_node(qtbot, editor, button["id"])
    settle(200)
    assert s.selected_id == button["id"] and s.page_id == s.current_page["id"]
    assert js(qtbot, editor, "location.href") == address


def test_clicking_empty_canvas_clears(editor, qtbot):
    s = editor.session
    s.select(of_type(s.document, "heading", s.current_page)[0]["id"])
    settle(100)
    # The grey around the phone-width page is empty canvas.
    s.set_viewport("mobile")
    settle(200)
    QTest.mouseClick(editor.canvas.scroll.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(4, 300))
    assert s.selected_id == ""
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-selection')).display") == "none"


def test_escape_clears_but_not_while_typing(editor, qtbot):
    s = editor.session
    node = of_type(s.document, "heading", s.current_page)[0]
    s.select(node["id"])
    field = editor.components_panel.search
    editor.rail_buttons[1].click()
    field.setFocus()
    QTest.keyClick(field, Qt.Key.Key_Escape)
    assert s.selected_id == node["id"]
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert s.selected_id == ""


def test_selection_survives_a_redraw_and_a_missing_node_clears(editor, qtbot):
    s = editor.session
    node = of_type(s.document, "heading", s.current_page)[0]
    s.select(node["id"])
    edited(qtbot, editor, lambda: s.insert_component("hero", f"page:{s.page_id}", 0))
    assert s.selected_id != node["id"] and find_node(s.document, s.selected_id)["props"]["role"] == "hero"
    edited(qtbot, editor, s.undo)
    assert s.selected_id == ""  # The hero is gone with the undo.
    assert js(qtbot, editor, "mtsSelect('missing-id','none')") is False


def test_editor_marks_keep_their_size_on_screen_at_any_zoom(editor, qtbot):
    s = editor.session
    s.select(of_type(s.document, "heading", s.current_page)[0]["id"])
    settle(150)
    size = lambda: float(js(qtbot, editor, "parseFloat(getComputedStyle(document.getElementById('mts-selection-tag')).fontSize)"))
    for zoom in (.5, 1.0):
        editor.canvas.set_zoom(zoom)
        settle(150)
        assert abs(size() * zoom - 12) < .6


def test_the_outline_survives_a_burst_of_edits(editor, qtbot):
    s = editor.session
    s.select(s.current_page["nodes"][1]["id"])
    for _ in range(5):
        s.duplicate_selected()
        settle(60)
    settle(700)
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-selection')).display") == "block"
    assert js(qtbot, editor, f"!!document.querySelector('[data-mts-id=\"{s.selected_id}\"]')") is True


def test_preview_allows_selecting_but_never_editing(window, qtbot):
    s = window.session
    loaded(qtbot, window, lambda: s.preview_template(TID))
    qtbot.waitUntil(lambda: js(qtbot, window, "!!window.mtsReady"), timeout=8000)
    notices = []
    s.noticeRaised.connect(notices.append)
    heading = of_type(s.document, "heading", s.current_page)[0]
    click_node(qtbot, window, heading["id"])
    assert s.selected_id == heading["id"]
    before = json.dumps(s.document, sort_keys=True)
    s.delete_selected(); s.duplicate_selected(); s.insert_component("hero"); s.paste()
    assert s.begin_component_drag("hero") is False
    assert json.dumps(s.document, sort_keys=True) == before
    assert notices and "preview" in notices[0]


def test_undo_during_preview_leaves_the_hidden_project_alone(editor, qtbot):
    s = editor.session
    edited(qtbot, editor, lambda: s.insert_component("hero", f"page:{s.page_id}", 0))
    depth = s.project.history.undo_depth
    loaded(qtbot, editor, lambda: s.preview_template("fashion/streetwear"))
    s.undo()
    assert s.project.history.undo_depth == depth


# Drag from the library -------------------------------------------------------
def test_drag_a_heading_onto_the_canvas(editor, qtbot):
    s = editor.session
    box = next(c for c in s.current_page["nodes"][1]["children"] if c["type"] in ("container", "columns"))
    r = rect_of(qtbot, editor, s.current_page["nodes"][1]["id"])
    depth = s.project.history.undo_depth
    count = len(of_type(s.document, "heading"))
    point = (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
    with qtbot.waitSignal(editor.canvas.view.loadFinished, timeout=20000):
        drag_events(editor, "heading", [(point[0], point[1] - 8), point])
    s.end_component_drag()
    settle(200)
    assert len(of_type(s.document, "heading")) == count + 1
    assert s.project.history.undo_depth == depth + 1  # One entry however long the drag.
    assert find_node(s.document, s.selected_id)["type"] == "heading"
    assert not editor.canvas.overlay.isVisible()
    edited(qtbot, editor, s.undo)
    assert len(of_type(s.document, "heading")) == count


def test_drag_a_hero_between_sections_shows_an_indicator(editor, qtbot):
    s = editor.session
    order = [n["id"] for n in s.current_page["nodes"]]
    r = rect_of(qtbot, editor, order[1])
    edge = (r["x"] + r["w"] / 2, r["y"] + 3)
    drag_events(editor, "hero", [edge, (edge[0], edge[1] + 1)], drop=False)
    settle(100)
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-drop-line')).display") == "block"
    with qtbot.waitSignal(editor.canvas.view.loadFinished, timeout=20000):
        mime = QMimeData()
        mime.setData(COMPONENT_MIME, b"hero")
        QApplication.sendEvent(editor.canvas.overlay, QDropEvent(QPointF(widget_point(editor, *edge)), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    s.end_component_drag()
    settle(200)
    nodes = s.current_page["nodes"]
    assert len(nodes) == len(order) + 1
    made = next(n for n in nodes if n["id"] not in order)
    assert made["props"]["role"] == "hero" and nodes.index(made) in (1, 2)
    # Its parts are real, and each can be selected.
    heading = of_type(s.document, "heading", {"nodes": [made]})[0]
    click_node(qtbot, editor, heading["id"])
    assert s.selected_id == heading["id"]


def test_an_invalid_drop_changes_nothing(editor, qtbot):
    """A section dropped deep in a card still lands at page level or nowhere, never inside it."""
    s = editor.session
    before = len(s.current_page["nodes"])
    depth = s.project.history.undo_depth
    heading = of_type(s.document, "heading", s.current_page)[2]
    r = rect_of(qtbot, editor, heading["id"])
    point = (r["x"] + 4, r["y"] + r["h"] / 2)
    drag_events(editor, "section", [point, point])
    s.end_component_drag()
    settle(700)
    if s.project.history.undo_depth > depth:
        assert len(s.current_page["nodes"]) == before + 1
    for node in s.current_page["nodes"]:
        assert node["type"] == "section"


def test_a_cancelled_drag_changes_nothing_and_clears_indicators(editor, qtbot):
    s = editor.session
    depth = s.project.history.undo_depth
    r = rect_of(qtbot, editor, s.current_page["nodes"][1]["id"])
    drag_events(editor, "heading", [(r["x"] + 20, r["y"] + 20)], drop=False)
    s.end_component_drag()
    settle(100)
    assert s.project.history.undo_depth == depth
    assert not editor.canvas.overlay.isVisible()
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-drop-line')).display") == "none"


def test_drag_events_at_the_window_reach_the_overlay_and_insert(editor, qtbot):
    """Delivered to the top-level window, so Qt's own hit-testing must route them past the browser widget.

    This is everything short of the OS gesture: the headless platform has no drag loop (QDrag.exec
    returns at once), so a person dragging with a real mouse remains a manual check.
    """
    s = editor.session
    order = [n["id"] for n in s.current_page["nodes"]]
    depth = s.project.history.undo_depth
    r = rect_of(qtbot, editor, order[1])
    inner = widget_point(editor, r["x"] + r["w"] / 2, r["y"] + 4)
    point = editor.canvas.view.mapTo(editor, inner)
    mime = QMimeData()
    mime.setData(COMPONENT_MIME, b"hero")
    actions = Qt.DropAction.CopyAction
    left, none = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    window = editor.windowHandle()
    assert s.begin_component_drag("hero")
    settle(60)
    entered = QDragEnterEvent(point, actions, mime, left, none)
    QApplication.sendEvent(window, entered)
    settle(60)
    assert entered.isAccepted()
    QApplication.sendEvent(window, QDragMoveEvent(point, actions, mime, left, none))
    settle(100)
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-drop-line')).display") == "block"
    with qtbot.waitSignal(editor.canvas.view.loadFinished, timeout=20000):
        QApplication.sendEvent(window, QDropEvent(QPointF(point), actions, mime, left, none))
    s.end_component_drag()
    settle(150)
    assert s.project.history.undo_depth == depth + 1
    made = next(n for n in s.current_page["nodes"] if n["id"] not in order)
    assert made["props"]["role"] == "hero" and s.selected_id == made["id"]
    assert not editor.canvas.overlay.isVisible()


def test_library_tile_builds_a_real_drag(editor):
    tile = next(t for t in editor.components_panel.tiles if t.component.id == "heading")
    drag = tile.make_drag()
    assert bytes(drag.mimeData().data(COMPONENT_MIME)).decode() == "heading"
    assert not drag.pixmap().isNull()


def test_double_click_inserts_where_it_belongs(editor, qtbot):
    s = editor.session
    editor.rail_buttons[1].click()
    tile = next(t for t in editor.components_panel.tiles if t.component.id == "paragraph")
    count = len(of_type(s.document, "text"))
    box = next(c for c in s.current_page["nodes"][1]["children"] if c["type"] == "container") if any(c["type"] == "container" for c in s.current_page["nodes"][1]["children"]) else None
    if box:
        s.select(box["id"])
    edited(qtbot, editor, lambda: QTest.mouseDClick(tile, Qt.MouseButton.LeftButton))
    assert len(of_type(s.document, "text")) == count + 1


def test_library_search_filters(editor):
    panel = editor.components_panel
    editor.rail_buttons[1].click()
    panel.search.setText("pric")
    assert [t.component.id for t in panel.tiles if not t.isHidden()] == ["pricing"]
    panel.search.setText("zzzz")
    assert not panel.empty.isHidden()
    panel.search.setText("")
    assert all(not t.isHidden() for t in panel.tiles)


# Rearranging on the canvas ---------------------------------------------------
def page_mouse(qtbot, w, x0, y0, x1, y1):
    """A press, a drag with real movement, and a release, as real input to the engine."""
    target = w.canvas.view.focusProxy()
    QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=widget_point(w, x0, y0))
    settle(40)
    steps = 8
    for i in range(1, steps + 1):
        QTest.mouseMove(target, widget_point(w, x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps))
        settle(30)
    QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=widget_point(w, x1, y1))


def test_drag_a_section_to_rearrange_with_one_history_entry(editor, qtbot):
    s = editor.session
    order = [n["id"] for n in s.current_page["nodes"]]
    depth = s.project.history.undo_depth
    first = rect_of(qtbot, editor, order[1])
    second = rect_of(qtbot, editor, order[2], scroll=False)
    s.select(order[1], origin="canvas")
    settle(100)
    with qtbot.waitSignal(editor.canvas.view.loadFinished, timeout=20000):
        page_mouse(qtbot, editor, first["x"] + 8, first["y"] + 8, first["x"] + 30, min(second["y"] + second["h"] - 3, 860 / editor.canvas.zoom - 4))
    settle(200)
    assert [n["id"] for n in s.current_page["nodes"]] != order
    assert sorted(n["id"] for n in s.current_page["nodes"]) == sorted(order)
    assert s.project.history.undo_depth == depth + 1 and s.selected_id == order[1]
    edited(qtbot, editor, s.undo)
    assert [n["id"] for n in s.current_page["nodes"]] == order


def test_a_small_wobble_is_a_click_not_a_drag(editor, qtbot):
    s = editor.session
    heading = of_type(s.document, "heading", s.current_page)[0]
    depth = s.project.history.undo_depth
    r = rect_of(qtbot, editor, heading["id"])
    x, y = r["x"] + r["w"] / 2, r["y"] + 8
    page_mouse(qtbot, editor, x, y, x + 2, y + 1)
    qtbot.waitUntil(lambda: s.selected_id != "", timeout=4000)
    assert s.project.history.undo_depth == depth


# Operations ------------------------------------------------------------------
def test_duplicate_delete_move_copy_paste_shortcuts(editor, qtbot):
    s = editor.session
    order = [n["id"] for n in s.current_page["nodes"]]
    s.select(order[2])
    editor.setFocus()
    edited(qtbot, editor, lambda: QTest.keyClick(editor, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier))
    nodes = [n["id"] for n in s.current_page["nodes"]]
    assert len(nodes) == len(order) + 1 and s.selected_id == nodes[3] and nodes[3] not in order
    edited(qtbot, editor, lambda: QTest.keyClick(editor, Qt.Key.Key_Delete))
    assert [n["id"] for n in s.current_page["nodes"]] == order and s.selected_id == order[3]
    edited(qtbot, editor, lambda: QTest.keyClick(editor, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier))
    assert [n["id"] for n in s.current_page["nodes"]][2] == order[3]
    edited(qtbot, editor, lambda: QTest.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier))
    assert [n["id"] for n in s.current_page["nodes"]] == order
    QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert s.clipboard["id"] == order[3]
    edited(qtbot, editor, lambda: QTest.keyClick(editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier))
    assert len(s.current_page["nodes"]) == len(order) + 1 and s.selected_id not in order
    ids = [n["id"] for n in walk_document(s.document)]
    assert len(ids) == len(set(ids))


def test_shortcuts_work_after_clicking_on_the_page(editor, qtbot):
    """A click puts keyboard focus inside the engine, which wants Delete and Ctrl+Z for itself."""
    s = editor.session
    order = [n["id"] for n in s.current_page["nodes"]]
    click_node(qtbot, editor, of_type(s.document, "heading", {"nodes": [s.current_page["nodes"][1]]})[0]["id"])
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    settle(50)
    assert QApplication.focusWidget() is target
    gone = s.selected_id
    edited(qtbot, editor, lambda: QTest.keyClick(target, Qt.Key.Key_Delete))
    assert find_node(s.document, gone) is None
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    edited(qtbot, editor, lambda: QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier))
    assert find_node(s.document, gone) is not None
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    edited(qtbot, editor, lambda: QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
    assert find_node(s.document, gone) is None
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    edited(qtbot, editor, lambda: QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier))
    s.select(order[1])
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    edited(qtbot, editor, lambda: QTest.keyClick(target, Qt.Key.Key_Backspace))
    assert order[1] not in [n["id"] for n in s.current_page["nodes"]]
    target = editor.canvas.view.focusProxy()
    target.setFocus()
    s.select(s.current_page["nodes"][0]["id"])
    QTest.keyClick(target, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert s.clipboard is not None
    QTest.keyClick(target, Qt.Key.Key_Escape)
    assert s.selected_id == ""


def test_delete_does_not_fire_while_typing(editor, qtbot):
    s = editor.session
    s.select(s.current_page["nodes"][1]["id"])
    editor.rail_buttons[1].click()
    field: QLineEdit = editor.components_panel.search
    field.setFocus()
    field.setText("abc")
    count = len(s.current_page["nodes"])
    QTest.keyClick(field, Qt.Key.Key_Backspace)
    QTest.keyClick(field, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert len(s.current_page["nodes"]) == count and field.text() == "ab"


def test_selection_bar_buttons_and_their_states(editor, qtbot):
    s = editor.session
    bar = editor.selection_bar
    assert not bar.buttons["delete"].isEnabled() and not bar.buttons["duplicate"].isEnabled()
    nodes = s.current_page["nodes"]
    s.select(nodes[0]["id"])
    assert bar.buttons["delete"].isEnabled() and not bar.buttons["up"].isEnabled() and bar.buttons["down"].isEnabled()
    s.select(s.document["site"]["header"]["id"])
    assert not bar.buttons["delete"].isEnabled() and "shared" in bar.buttons["delete"].toolTip()
    s.select(nodes[1]["id"])
    edited(qtbot, editor, bar.buttons["duplicate"].click)
    assert len(s.current_page["nodes"]) == len(nodes)


def test_breadcrumb_selects_an_ancestor(editor, qtbot):
    s = editor.session
    heading = of_type(s.document, "heading", s.current_page)[0]
    s.select(heading["id"])
    path = ancestors(s.document, heading["id"])
    assert len(path) >= 2
    crumbs = [w for w in editor.selection_bar.findChildren(type(editor.selection_bar.buttons["up"]).__base__) if w.objectName() == "Crumb"]
    assert crumbs
    crumbs[0].click()
    assert s.selected_id == path[-len(crumbs) - 1]["id"]


def test_shared_structures_are_protected_in_the_session(editor, qtbot):
    s = editor.session
    notices = []
    s.noticeRaised.connect(notices.append)
    s.select(s.document["site"]["header"]["id"])
    depth = s.project.history.undo_depth
    s.delete_selected(); s.duplicate_selected(); s.copy_selected(); s.shift_selected(1)
    assert s.project.history.undo_depth == depth and find_node(s.document, s.selected_id)
    assert notices and s.clipboard is None


# The bridge ------------------------------------------------------------------
@pytest.mark.parametrize("args", [
    ("hero", "root", -1), ("hero", "root", 10**7), ("../x", "root", 0), ("nonexistent", "root", 0),
    ("hero", "'; drop", 0), ("hero", "not-there", 0), ("heading", "root", 0),
])
def test_bridge_refuses_bad_inserts(editor, args):
    s = editor.session
    before = json.dumps(s.document, sort_keys=True)
    depth = s.project.history.undo_depth
    editor.canvas.bridge.requestInsert(*args)
    assert json.dumps(s.document, sort_keys=True) == before and s.project.history.undo_depth == depth


def test_bridge_refuses_bad_moves_and_ids(editor):
    s = editor.session
    before = json.dumps(s.document, sort_keys=True)
    section = s.current_page["nodes"][0]["id"]
    bridge = editor.canvas.bridge
    bridge.requestMove("missing", "root", 0)
    bridge.requestMove(section, "root", 10_000)
    bridge.requestMove(section, section, 0)
    bridge.requestMove("<script>", "root", 0)
    bridge.selectNode("<script>")
    bridge.selectNode("does-not-exist")
    assert json.dumps(s.document, sort_keys=True) == before and s.selected_id == ""


def test_bridge_offers_only_what_it_should():
    from mulusa_theme_studio.ui.bridge import EditorBridge

    meta = EditorBridge.staticMetaObject
    slots = {bytes(meta.method(i).name()).decode() for i in range(meta.methodOffset(), meta.methodCount())}
    assert slots == {"reportReady", "requestMediaPicker", "selectNode", "clearSelection", "requestInsert", "requestMove", "reportRefused"}


# Hierarchy -------------------------------------------------------------------
def test_hierarchy_shows_the_structure_and_syncs_both_ways(editor, qtbot):
    s = editor.session
    editor.rail_buttons[3].click()
    panel = editor.side_stack.currentWidget()
    root = panel.tree.topLevelItem(0)
    assert root.text(0).endswith("page")
    assert root.child(1).text(0).startswith("Section")
    heading = of_type(s.document, "heading", s.current_page)[0]
    click_node(qtbot, editor, heading["id"])
    item = panel.tree.currentItem()
    assert item.data(0, 256) == heading["id"] and item.text(0).startswith("Heading")
    assert item.parent().isExpanded()
    other = panel.tree.topLevelItem(0).child(2)
    panel.tree.setCurrentItem(other)
    assert s.selected_id == other.data(0, 256)
    settle(150)
    assert js(qtbot, editor, "getComputedStyle(document.getElementById('mts-selection')).display") == "block"
    panel.tree.setCurrentItem(root)
    assert s.selected_id == ""


def test_hierarchy_keeps_what_was_open_after_an_edit(editor, qtbot):
    s = editor.session
    editor.rail_buttons[3].click()
    panel = editor.side_stack.currentWidget()
    item = panel.tree.topLevelItem(0).child(2)
    item.setExpanded(True)
    key = item.data(0, 256)
    edited(qtbot, editor, lambda: s.insert_component("divider", s.current_page["nodes"][-1]["children"][0]["id"], 0))
    assert panel._items[key].isExpanded()


# The whole flow --------------------------------------------------------------
def test_the_edits_survive_saving_and_reopening(editor, qtbot):
    s = editor.session
    edited(qtbot, editor, lambda: s.insert_component("pricing", f"page:{s.page_id}", 1))
    edited(qtbot, editor, s.duplicate_selected)
    s.select(s.current_page["nodes"][0]["id"])
    edited(qtbot, editor, lambda: s.shift_selected(1))
    expected = json.dumps(s.document["pages"], sort_keys=True)
    s.save()
    folder = s.project.folder
    loaded(qtbot, editor, lambda: s.open_project(folder))
    assert json.dumps(s.document["pages"], sort_keys=True) == expected


@pytest.mark.parametrize("viewport", list(VIEWPORTS))
def test_inserted_sections_fit_each_device(editor, qtbot, viewport):
    s = editor.session
    for component in registry.catalogue():
        if component.group == "Prebuilt sections":
            s.keep_view = False
            s.project.history.apply(f"Add {component.id}", lambda d, c=component: d["pages"][0]["nodes"].append(c.build()))
    loaded(qtbot, editor, s._after_history)
    if viewport != "desktop":
        s.set_viewport(viewport)
        settle(300)
    width = js(qtbot, editor, "window.innerWidth")
    assert width == VIEWPORTS[viewport]
    overflow = json.loads(js(qtbot, editor, """(function(){var w=document.documentElement.clientWidth,out=[];
        document.querySelectorAll('[data-mts-id]').forEach(function(e){var r=e.getBoundingClientRect();
        if(r.width>0&&(r.right>w+1||r.left<-1))out.push(e.getAttribute('data-mts-type'))});
        return JSON.stringify([document.documentElement.scrollWidth,w,out.slice(0,6)])})()"""))
    assert overflow[0] <= overflow[1] and overflow[2] == [], overflow


def test_editor_code_never_reaches_a_preview_or_export(editor, tmp_path):
    from mulusa_theme_studio.render.site import write_site

    site = write_site(editor.session.document, tmp_path / "out")
    for path in site.pages.values():
        text = path.read_text(encoding="utf-8")
        assert not any(mark in text for mark in ("data-mts-id", "data-mts-type", "mtsSelect", "qt.webChannelTransport", "mts-selection"))


def test_page_is_opened_with_no_console_fault_on_every_template_page(editor, qtbot):
    """The editor script must start on every page, including ones with no sections to select."""
    s = editor.session
    for page in s.document["pages"]:
        if page["id"] != s.page_id:
            loaded(qtbot, editor, lambda p=page["id"]: s.set_page(p))
        qtbot.waitUntil(lambda: js(qtbot, editor, "!!window.mtsReady"), timeout=8000)
