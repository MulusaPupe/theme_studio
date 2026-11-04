"""The real window, driven the way a person would use it, with a real browser engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QAbstractButton, QMessageBox

from mulusa_theme_studio.core.settings import Settings
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.ui.main_window import MainWindow
from mulusa_theme_studio.ui.session import VIEWPORTS, Session

TID = "corporate/corporate-classic"
OTHER = "fashion/streetwear"


@pytest.fixture
def window(qtbot, tmp_path, no_dialogs):
    settings = Settings()
    settings.projects_dir = str(tmp_path / "projects")
    w = MainWindow(Session(settings, TemplateLibrary()))
    w.resize(1500, 900)
    w.show()
    yield w
    w.session.project = None  # Nothing to save on the way out.
    w.close()
    w.deleteLater()
    settle(30)


def loaded(qtbot, w, action):
    with qtbot.waitSignal(w.canvas.view.loadFinished, timeout=20000):
        action()
    settle()


def settle(ms=120):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def js(qtbot, w, script):
    out = []
    w.canvas.page.runJavaScript(script, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=8000)
    return out[0]


def test_starts_on_welcome_with_honest_buttons(window):
    assert window.canvas.stack.currentIndex() == 0
    assert not window.save_btn.isEnabled() and not window.undo_btn.isEnabled() and not window.preview_btn.isEnabled()
    assert window.status_project.text() == "No project open"


def test_no_enabled_button_is_dead(window):
    """Every button that can be clicked does something."""
    dead = []
    for button in window.findChildren(QAbstractButton):
        if type(button).__name__ in ("QCheckBox", "QRadioButton") or button.objectName().startswith("qt_"):
            continue
        if button.isEnabled() and button.receivers("2clicked(bool)") == 0 and button.receivers("2clicked()") == 0:
            dead.append(button.toolTip() or button.text())
    assert dead == []


def test_export_is_clearly_marked_as_not_ready(window):
    assert not window.export_btn.isEnabled()
    assert "Stage 05" in window.export_btn.toolTip() and "Stage 06" in window.export_btn.toolTip()


def test_preview_template_on_canvas(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    assert window.canvas.stack.currentWidget() is window.canvas.scroll
    assert window.banner.isVisibleTo(window) and window.preview_btn.isEnabled()
    assert js(qtbot, window, "document.querySelector('.mts-brand').textContent") == "Halden & Partners"
    assert window.status_save.text() == "Read-only"
    assert not window.save_btn.isEnabled()


def test_fonts_load_from_bundled_files(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    settle(400)
    assert js(qtbot, window, "document.fonts.ready.then(()=>0);document.fonts.check(\"600 20px 'Source Serif 4'\")") is True
    assert js(qtbot, window, "[...document.fonts].filter(f=>f.status==='loaded').length") >= 1


@pytest.mark.parametrize("zoom", [None, .5, 1.3])
@pytest.mark.parametrize("device", list(VIEWPORTS))
def test_device_width_is_true_inside_the_browser_at_any_zoom(window, qtbot, device, zoom):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    window.session.set_viewport(device)
    if zoom:
        window.canvas.set_zoom(zoom)
    settle(300)
    assert abs(js(qtbot, window, "document.documentElement.clientWidth") - VIEWPORTS[device]) <= 1
    assert window.device_buttons[device].isChecked()


@pytest.mark.parametrize("tid", ["fashion/luxury-editorial", "construction/heavy-civil", "real_estate/city-agency", "hospitality/fine-dining"])
def test_text_over_photos_is_light_and_readable(window, qtbot, tid):
    """Measured in the browser: this was once nearly invisible and no static check noticed."""
    loaded(qtbot, window, lambda: window.session.preview_template(tid))
    rgb = js(qtbot, window, """(function(){var s=document.querySelector('section .mts-bg').closest('section');
        var out=[];s.querySelectorAll('.mts-muted,h1').forEach(function(e){
          var tone=e.closest('[class*=mts-tone-]'); if(tone!==s)return; out.push(getComputedStyle(e).color)});return out.join('|')})()""")
    assert rgb
    for value in rgb.split("|"):
        channels = [float(x) for x in value[value.index("(") + 1:-1].replace(" ", "").split(",")[:3]]
        assert min(channels) > 200, value


def test_mobile_gets_a_real_menu(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    window.session.set_viewport("mobile")
    settle(300)
    assert js(qtbot, window, "getComputedStyle(document.querySelector('.mts-burger')).display") == "flex"
    assert js(qtbot, window, "getComputedStyle(document.querySelector('.mts-nav')).display") == "none"
    js(qtbot, window, "document.querySelector('.mts-nav-check').checked=true;1")
    assert js(qtbot, window, "getComputedStyle(document.querySelector('.mts-nav')).display") == "block"
    window.session.set_viewport("desktop")
    settle(300)
    assert js(qtbot, window, "getComputedStyle(document.querySelector('.mts-burger')).display") == "none"


def test_columns_really_stack_on_mobile(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    count = "getComputedStyle(document.querySelector('.mts-columns')).gridTemplateColumns.split(' ').length"
    assert js(qtbot, window, count) >= 2
    window.session.set_viewport("mobile")
    settle(300)
    assert js(qtbot, window, count) == 1


def test_create_project_save_and_reopen(window, qtbot, tmp_path):
    loaded(qtbot, window, lambda: window.session.create_project("My Site", TID))
    project = window.session.project
    assert (project.folder / "project.json").is_file()
    assert "My Site" in window.status_project.text()
    assert window.session.settings.recent[0] == str(project.folder)
    assert not window.save_btn.isEnabled()
    window.session.project = None
    loaded(qtbot, window, lambda: window.session.open_project(project.folder))
    assert window.session.project.name == "My Site"


def test_apply_template_undo_redo_and_save(window, qtbot):
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    session = window.session
    original = session.project.document["tokens"]["fonts"]["heading"]
    assert not window.undo_btn.isEnabled()

    loaded(qtbot, window, lambda: session.apply_template_to_project(OTHER))
    doc = session.project.document
    assert doc["tokens"]["fonts"]["heading"] == "Anton" and doc["meta"]["name"] == "Site"
    assert window.undo_btn.isEnabled() and window.save_btn.isEnabled()
    assert "Streetwear" in window.undo_btn.toolTip()
    assert window.windowTitle().startswith("Site *")
    assert js(qtbot, window, "document.querySelector('.mts-brand').textContent") == "BLOCK—09"

    loaded(qtbot, window, session.undo)
    assert session.project.document["tokens"]["fonts"]["heading"] == original
    assert not session.project.dirty and not window.save_btn.isEnabled()

    loaded(qtbot, window, session.redo)
    assert session.project.dirty
    window.save_project()
    assert not window.save_btn.isEnabled()
    assert json.loads(session.project.file.read_text(encoding="utf-8"))["tokens"]["fonts"]["heading"] == "Anton"


def test_applying_a_template_keeps_uploaded_media(window, qtbot):
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    session = window.session
    session.project.document["media"]["assets"] = [{"id": "a1", "file": "logo.png"}]
    loaded(qtbot, window, lambda: session.apply_template_to_project(OTHER))
    assert session.project.document["media"]["assets"] == [{"id": "a1", "file": "logo.png"}]


def test_switching_pages(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    loaded(qtbot, window, lambda: window.session.set_page("about"))
    assert js(qtbot, window, "location.pathname.split('/').pop()") == "about.html"
    assert "About" in window.status_page.text()


def test_a_link_on_the_canvas_never_navigates_the_editor(window, qtbot):
    """Stage 02: a click selects. Pages are switched from the Pages tab."""
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    js(qtbot, window, """document.querySelector('.mts-nav a[href="contact.html"]').click();1""")
    settle(300)
    assert window.session.page_id != "contact"
    assert js(qtbot, window, "location.pathname.split('/').pop()") == "index.html"


def test_selecting_a_layer_highlights_it(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    node = window.session.current_page["nodes"][2]
    window.side_stack.setCurrentIndex(3)
    window.session.select(node["id"])
    settle(200)
    assert js(qtbot, window, f"mtsSelect('{node['id']}',false)") is True
    box = js(qtbot, window, f"""(function(){{var b=document.getElementById('mts-selection').getBoundingClientRect(),
        n=document.querySelector('[data-mts-id="{node['id']}"]').getBoundingClientRect();
        return JSON.stringify([getComputedStyle(document.getElementById('mts-selection')).display,Math.abs(b.top-n.top)<2,Math.abs(b.width-n.width)<2,b.height>10])}})()""")
    assert json.loads(box) == ["block", True, True, True]
    assert window.status_selection.text().startswith("Selected:")
    assert window.inspector.sel_name.text() != "Nothing selected"
    tree = window.side_stack.currentWidget().tree
    assert tree.currentItem().data(0, 256) == node["id"]


def test_selection_outline_is_not_in_previews(window, qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr("mulusa_theme_studio.ui.main_window.QDesktopServices.openUrl", lambda url: opened.append(url) or True)
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    window.preview_site()
    path = Path(opened[0].toLocalFile())
    assert path == window.session.project.folder / "previews" / "site" / "index.html"
    assert "mtsSelect" not in path.read_text(encoding="utf-8")


def test_template_preview_does_not_touch_the_open_project(window, qtbot):
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    before = json.dumps(window.session.project.document, sort_keys=True)
    loaded(qtbot, window, lambda: window.session.preview_template(OTHER))
    assert window.session.read_only and not window.undo_btn.isEnabled()
    loaded(qtbot, window, lambda: window.session.close_template_preview())
    assert json.dumps(window.session.project.document, sort_keys=True) == before
    assert not window.session.project.dirty


def test_autosave_timer_writes_and_reports(window, qtbot):
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    window._on_autosave()
    assert not window.session.project.autosave_file.exists()
    loaded(qtbot, window, lambda: window.session.apply_template_to_project(OTHER))
    window._on_autosave()
    assert window.session.project.autosave_file.exists()
    assert "autosaved" in window.status_save.text().lower()


def test_recovery_is_offered_when_opening(window, qtbot, monkeypatch):
    session = window.session
    loaded(qtbot, window, lambda: session.create_project("Site", TID))
    folder = session.project.folder
    loaded(qtbot, window, lambda: session.apply_template_to_project(OTHER))
    session.project.autosave()
    session.project = None
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    loaded(qtbot, window, lambda: window._open_path(folder))
    settle(300)
    assert session.project.document["tokens"]["fonts"]["heading"] == "Anton"
    assert session.project.dirty and window.windowTitle().startswith("Site *")


def test_open_failure_is_explained_and_harmless(window, qtbot, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(window, "_show_error", lambda text, details=None: messages.append(text))
    window._open_path(tmp_path)
    assert "not a Mulusa" in messages[0]
    assert window.session.project is None


def test_closing_with_unsaved_work_asks_first(window, qtbot, monkeypatch):
    loaded(qtbot, window, lambda: window.session.create_project("Site", TID))
    loaded(qtbot, window, lambda: window.session.apply_template_to_project(OTHER))
    answers = []

    def answer(*a, **k):
        answers.append(a)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", staticmethod(answer))
    assert window._confirm_leave() is False and answers


def test_templates_panel_search_and_filter(window):
    panel = window.templates_panel
    assert panel.list.count() == 50
    panel.search.setText("streetwear")
    assert panel.list.count() == 1
    panel.search.clear()
    panel.category.setCurrentIndex(panel.category.findData("music"))
    assert panel.list.count() == 5 and panel.count.text().startswith("5 of 50")


def test_every_sidebar_tab_opens(window):
    for index, button in enumerate(window.rail_buttons):
        button.click()
        assert window.side_stack.currentIndex() == index


def test_panels_follow_the_design(window, qtbot):
    loaded(qtbot, window, lambda: window.session.preview_template(TID))
    pages = window.side_stack.widget(2)
    assert pages.list.count() == 6 and pages.list.currentItem().text().endswith("(homepage)")
    media = window.side_stack.widget(4)
    assert "placeholder" in media.summary.text()
    colors = window.session.document["tokens"]["colors"]
    assert window.inspector.swatch_widgets["primary"][1].text() == colors["primary"].upper()


def test_new_project_dialog_validates_and_creates(window, qtbot, tmp_path):
    from mulusa_theme_studio.ui.dialogs import NewProjectDialog

    session = window.session
    dialog = NewProjectDialog(session.library, session.settings, TID, window)
    assert dialog.grid.count() == 50 and dialog.template_id == TID
    assert not dialog.create.isEnabled() and "name" in dialog.message.text()
    dialog.name.setText(" ?*: ")
    assert not dialog.create.isEnabled() and "letter or number" in dialog.message.text()
    dialog.name.setText("Good Name")
    dialog.location.setText(str(tmp_path / "there"))
    assert dialog.create.isEnabled() and "Good Name" in dialog.message.text()
    dialog.category.setCurrentIndex(dialog.category.findData("music"))
    assert dialog.grid.count() == 5 and dialog.template_id == ""
    assert not dialog.create.isEnabled() and "template" in dialog.message.text()
    dialog.grid.item(0).setSelected(True)
    assert dialog.create.isEnabled()
    (tmp_path / "there" / "Good Name").mkdir(parents=True)
    (tmp_path / "there" / "Good Name" / "file").write_text("x", encoding="utf-8")
    dialog.name.clear()
    dialog.name.setText("Good Name")
    assert not dialog.create.isEnabled() and "already exists" in dialog.message.text()
    dialog.deleteLater()


def test_settings_dialog_applies_and_autosave_timer_follows(window, qtbot):
    from mulusa_theme_studio.ui.dialogs import SettingsDialog

    settings = window.session.settings
    dialog = SettingsDialog(settings, window)
    dialog.seconds.setValue(30)
    dialog.author.setText("Mulusa")
    dialog.appearance.setCurrentIndex(1)
    dialog.apply()
    window._apply_autosave_settings()
    assert settings.autosave_seconds == 30 and settings.author == "Mulusa" and settings.appearance == "light"
    assert window._autosave.isActive() and window._autosave.interval() == 30000
    dialog.autosave.setChecked(False)
    dialog.apply()
    window._apply_autosave_settings()
    assert not window._autosave.isActive()
    dialog.deleteLater()
