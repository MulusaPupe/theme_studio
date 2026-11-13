"""The studio window: toolbar, sidebar, canvas, inspector and status strip."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget, QTextEdit,
    QToolButton, QVBoxLayout, QWidget,
)

from .. import APP_NAME, ORG_NAME, TAGLINE
from ..core import media
from ..core.document import find_node, type_label
from ..core.errors import ProjectError, StudioError
from ..render.site import page_filename, write_site
from .canvas import Canvas
from .dialogs import NewProjectDialog, SettingsDialog
from .panels.components_panel import ComponentsPanel
from .panels.inspector import Inspector
from .panels.layers_panel import LayersPanel
from .panels.media_panel import MediaPanel
from .export_dialog import ExportDialog
from .panels.pages_panel import PagesPanel
from .panels.templates_panel import TemplatesPanel
from .media_widgets import CropDialog, MediaPickerDialog
from .selection_bar import SelectionBar
from .session import VIEWPORTS, Session
from .theme import icon_pixmap, logo_pixmap, make_icon, palette_for, stylesheet
from .widgets import label, separator


class MainWindow(QMainWindow):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.pal = palette_for(session.settings.appearance)
        self.media_dialog = None  # The open image picker or crop dialog, if any.
        QApplication.instance().setStyleSheet(stylesheet(self.pal))
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(logo_pixmap(64)))
        self.resize(1560, 940)
        self.setMinimumSize(1100, 660)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_rail())
        body.addWidget(self._build_sidebar())
        centre = QVBoxLayout()
        centre.setContentsMargins(0, 0, 0, 0)
        centre.setSpacing(0)
        centre.addWidget(self._build_preview_banner())
        self.selection_bar = SelectionBar(session, self.pal)
        centre.addWidget(self.selection_bar)
        self.welcome = self._build_welcome()
        self.canvas = Canvas(session, self.welcome)
        self.canvas.renderFailed.connect(self._show_error)
        self.canvas.zoomChanged.connect(self._update_status)
        centre.addWidget(self.canvas, 1)
        body.addLayout(centre, 1)
        self.inspector = Inspector(session, self.pal)
        body.addWidget(self.inspector)
        layout.addLayout(body, 1)
        layout.addWidget(self._build_status())

        self._autosave = QTimer(self)
        self._autosave.timeout.connect(self._on_autosave)
        self._apply_autosave_settings()

        session.projectChanged.connect(self._update_actions)
        session.documentChanged.connect(self._update_actions)
        session.saveStateChanged.connect(self._update_actions)
        session.templatePreviewChanged.connect(self._update_actions)
        session.selectionChanged.connect(self._update_status)
        session.pageChanged.connect(self._update_status)
        session.viewportChanged.connect(self._update_status)
        session.viewportChanged.connect(lambda: self.device_buttons[session.viewport].setChecked(True))
        self._bind_shortcuts()
        self._update_actions()
        if session.library.problems:
            QTimer.singleShot(0, lambda: self._show_error("Some templates could not be loaded.", session.library.problems))

    # Construction -------------------------------------------------------------
    def _tool(self, icon: str, tip: str, handler=None, *, text: str = "", checkable: bool = False) -> QToolButton:
        button = QToolButton()
        button.setIcon(make_icon(icon, self.pal))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tip)
        button.setAccessibleName(tip.split(" (")[0])
        button.setCheckable(checkable)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if text:
            button.setText(text)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if handler:
            button.clicked.connect(handler)
        return button

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(52)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 12, 0)
        row.setSpacing(4)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(26))
        row.addWidget(logo)
        row.addSpacing(6)
        row.addWidget(label(APP_NAME, "brand"))
        row.addSpacing(14)
        row.addWidget(separator())
        row.addSpacing(6)
        self.home_btn = self._tool("house", "Home: back to the start screen (Ctrl+Shift+H)", self.go_home, text="Home")
        row.addWidget(self.home_btn)
        self.new_btn = self._tool("plus", "New project (Ctrl+N)", lambda: self.new_project(), text="New")
        self.open_btn = self._tool("folder-open", "Open project (Ctrl+O)", self.open_project, text="Open")
        self.save_btn = self._tool("save", "Save (Ctrl+S)", self.save_project, text="Save")
        for button in (self.new_btn, self.open_btn, self.save_btn):
            row.addWidget(button)
        row.addSpacing(6)
        row.addWidget(separator())
        row.addSpacing(6)
        self.undo_btn = self._tool("undo-2", "Undo (Ctrl+Z)", self.session.undo)
        self.redo_btn = self._tool("redo-2", "Redo (Ctrl+Shift+Z)", self.session.redo)
        row.addWidget(self.undo_btn)
        row.addWidget(self.redo_btn)
        row.addStretch(1)

        self.device_group = QButtonGroup(self)
        self.device_group.setExclusive(True)
        self.device_buttons: dict[str, QToolButton] = {}
        for name, icon in (("desktop", "monitor"), ("tablet", "tablet"), ("mobile", "smartphone")):
            button = self._tool(icon, f"{name.title()} preview, {VIEWPORTS[name]} px wide", lambda _=False, n=name: self.session.set_viewport(n), checkable=True)
            self.device_group.addButton(button)
            self.device_buttons[name] = button
            row.addWidget(button)
        self.device_buttons["desktop"].setChecked(True)
        row.addSpacing(6)
        row.addWidget(separator())
        row.addSpacing(6)
        self.zoom_out_btn = self._tool("zoom-out", "Zoom out (Ctrl+-)", lambda: self.canvas.zoom_out())
        self.zoom_label = QPushButton("100%")
        self.zoom_label.setToolTip("Fit to the window (Ctrl+0)")
        self.zoom_label.setFixedWidth(58)
        self.zoom_label.clicked.connect(lambda: self.canvas.zoom_fit())
        self.zoom_in_btn = self._tool("zoom-in", "Zoom in (Ctrl+=)", lambda: self.canvas.zoom_in())
        row.addWidget(self.zoom_out_btn)
        row.addWidget(self.zoom_label)
        row.addWidget(self.zoom_in_btn)
        row.addStretch(1)

        self.preview_btn = self._tool("eye", "Open the website in your browser", self.preview_site, text="Preview")
        row.addWidget(self.preview_btn)
        self.settings_btn = self._tool("settings", "Settings", self.open_settings)
        row.addWidget(self.settings_btn)
        row.addSpacing(6)
        self.export_btn = QPushButton("Export")
        self.export_btn.setIcon(QIcon(icon_pixmap("package", self.pal.faint, 16)))
        self.export_btn.clicked.connect(self.open_export)
        row.addWidget(self.export_btn)
        return bar

    def _build_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setFixedWidth(84)
        column = QVBoxLayout(rail)
        column.setContentsMargins(6, 8, 6, 8)
        column.setSpacing(4)
        self.rail_group = QButtonGroup(self)
        self.rail_group.setExclusive(True)
        self.rail_buttons: list[QToolButton] = []
        for index, (name, icon) in enumerate((("Templates", "layout-template"), ("Components", "blocks"), ("Pages", "files"), ("Layers", "layers"), ("Media", "images"))):
            button = QToolButton()
            button.setProperty("rail", True)
            button.setIcon(make_icon(icon, self.pal, 20))
            button.setIconSize(QSize(20, 20))
            button.setText(name)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setFixedWidth(72)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, i=index: self.side_stack.setCurrentIndex(i))
            self.rail_group.addButton(button)
            self.rail_buttons.append(button)
            column.addWidget(button)
        self.rail_buttons[0].setChecked(True)
        column.addStretch(1)
        library = QToolButton()
        library.setProperty("rail", True)
        library.setIcon(make_icon("book-open", self.pal, 20))
        library.setIconSize(QSize(20, 20))
        library.setText("Library")
        library.setToolTip("Creative Resource Library: templates, sections, palettes, fonts, icons, imports (Ctrl+Shift+L)")
        library.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        library.setFixedWidth(72)
        library.setCursor(Qt.CursorShape.PointingHandCursor)
        library.clicked.connect(self.open_library)
        column.addWidget(library)
        return rail

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("SideBar")
        side.setFixedWidth(280)
        column = QVBoxLayout(side)
        column.setContentsMargins(0, 0, 0, 0)
        self.side_stack = QStackedWidget()
        self.templates_panel = TemplatesPanel(self.session)
        self.templates_panel.useRequested.connect(self.use_template)
        self.templates_panel.errorRaised.connect(self._show_error)
        self.side_stack.addWidget(self.templates_panel)
        self.components_panel = ComponentsPanel(self.session, self.pal)
        self.side_stack.addWidget(self.components_panel)
        self.side_stack.addWidget(PagesPanel(self.session, self.pal))
        self.side_stack.addWidget(LayersPanel(self.session, self.pal))
        self.side_stack.addWidget(MediaPanel(self.session, self.pal))
        column.addWidget(self.side_stack)
        return side

    def _build_preview_banner(self) -> QWidget:
        self.banner = QFrame()
        self.banner.setObjectName("PreviewBanner")
        row = QHBoxLayout(self.banner)
        row.setContentsMargins(14, 8, 14, 8)
        self.banner_text = label("", wrap=True)
        row.addWidget(self.banner_text, 1)
        self.banner_use = QPushButton("Use this template")
        self.banner_use.setProperty("primary", True)
        self.banner_use.clicked.connect(lambda: self.use_template(self.session.preview.id) if self.session.preview else None)
        close = QPushButton("Close preview")
        close.clicked.connect(lambda: self.session.close_template_preview())
        row.addWidget(self.banner_use)
        row.addWidget(close)
        self.banner.setVisible(False)
        return self.banner

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("WelcomeCard")
        card.setFixedWidth(620)
        column = QVBoxLayout(card)
        column.setContentsMargins(36, 36, 36, 32)
        column.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        column.addWidget(logo)
        column.addSpacing(6)
        column.addWidget(label(APP_NAME, "display", wrap=True))
        column.addWidget(label(f"{TAGLINE}", "muted", wrap=True))
        column.addSpacing(10)
        row = QHBoxLayout()
        new = QPushButton("New project")
        new.setProperty("primary", True)
        new.clicked.connect(lambda: self.new_project())
        openb = QPushButton("Open project")
        openb.clicked.connect(self.open_project)
        row.addWidget(new)
        row.addWidget(openb)
        row.addStretch(1)
        column.addLayout(row)
        column.addSpacing(10)
        self.recent_title = label("RECENT PROJECTS", "section")
        column.addWidget(self.recent_title)
        self.recent = QListWidget()
        self.recent.setFixedHeight(130)
        self.recent.itemClicked.connect(lambda item: self._open_path(Path(item.data(Qt.ItemDataRole.UserRole))))
        column.addWidget(self.recent)
        column.addWidget(label(f"Or choose one of {len(self.session.library.templates)} templates on the left to preview it here.", "muted", wrap=True))
        column.addSpacing(4)
        column.addWidget(label(f"Developed by {ORG_NAME}", "faint"))
        outer.addWidget(card)
        self._fill_recent()
        return page

    def _fill_recent(self) -> None:
        self.recent.clear()
        for path in self.session.settings.recent:
            if (Path(path) / "project.json").is_file():
                item = QListWidgetItem(make_icon("folder-open", self.pal, 16), f"{Path(path).name}")
                item.setToolTip(path)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.recent.addItem(item)
        has = self.recent.count() > 0
        self.recent.setVisible(has)
        self.recent_title.setVisible(has)

    def _build_status(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusStrip")
        bar.setFixedHeight(28)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(18)
        self.status_project = label("", "faint")
        self.status_save = label("", "faint")
        self.status_page = label("", "faint")
        self.status_selection = label("", "faint")
        self.status_size = label("", "faint")
        self.status_notice = label("", "notice")
        for widget in (self.status_project, self.status_save, self.status_page, self.status_selection):
            row.addWidget(widget)
        row.addStretch(1)
        row.addWidget(self.status_notice)
        row.addWidget(self.status_size)
        return bar

    def _bind_shortcuts(self) -> None:
        pairs = (
            ("Ctrl+N", lambda: self.new_project()), ("Ctrl+O", self.open_project), ("Ctrl+S", self.save_project),
            ("Ctrl+Z", self.session.undo), ("Ctrl+Shift+Z", self.session.redo), ("Ctrl+Y", self.session.redo),
            ("Ctrl+Shift+L", self.open_library), ("Ctrl+Shift+H", self.go_home),
            ("Ctrl+=", lambda: self.canvas.zoom_in()), ("Ctrl+-", lambda: self.canvas.zoom_out()), ("Ctrl+0", lambda: self.canvas.zoom_fit()),
        )
        for keys, handler in pairs:
            QShortcut(QKeySequence(keys), self, activated=handler)
        # Element shortcuts stand aside while someone is typing in a field.
        editing = (
            ("Delete", self.session.delete_selected), ("Backspace", self.session.delete_selected),
            ("Ctrl+D", self.session.duplicate_selected), ("Ctrl+C", self.session.copy_selected), ("Ctrl+V", self.session.paste),
            ("Alt+Up", lambda: self.session.shift_selected(-1)), ("Alt+Down", lambda: self.session.shift_selected(1)),
            ("Escape", self._on_escape),
        )
        for keys, handler in editing:
            QShortcut(QKeySequence(keys), self, activated=lambda h=handler: self._unless_typing(h))
        self.session.noticeRaised.connect(self._show_notice)
        self.session.mediaPickerRequested.connect(self._pick_media, Qt.ConnectionType.QueuedConnection)
        self.session.cropRequested.connect(self._crop_media, Qt.ConnectionType.QueuedConnection)
        self._notice_timer = QTimer(self, singleShot=True, interval=5000)
        self._notice_timer.timeout.connect(lambda: self.status_notice.setText(""))

    # Media dialogs. Opened here so that panels never need to know about one another.
    def _pick_media(self, node_id: str, slot: str, index: int) -> None:
        dialog = MediaPickerDialog(self.session, self.pal, self)
        self.media_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        def done(result: int) -> None:
            self.media_dialog = None
            if result == QDialog.DialogCode.Accepted and dialog.asset_id:
                self.session.set_node_media(node_id, dialog.asset_id, slot, index)

        dialog.finished.connect(done)
        dialog.open()  # Not exec: the application keeps running beneath it.

    def _crop_media(self, node_id: str, slot: str) -> None:
        doc = self.session.document
        node = find_node(doc, node_id) if doc else None
        if not node or not self.session.project:
            return
        props = node.get("props", {})
        ref = (props.get("background") or {}).get("media") if slot == "background" else props.get("media")
        asset = media.find_asset(doc, ref.get("id")) if isinstance(ref, dict) and ref.get("kind") == "asset" else None
        path = media.asset_path(self.session.project.folder, asset) if asset else None
        if not path or not path.is_file():
            self.session.notify("Choose an uploaded image first. A placeholder cannot be cropped.")
            return
        dialog = CropDialog(path, asset, self)
        self.media_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        def done(result: int) -> None:
            self.media_dialog = None
            if result == QDialog.DialogCode.Accepted:
                self.session.crop_asset(node_id, asset["id"], dialog.view.crop_box(), slot)

        dialog.finished.connect(done)
        dialog.open()

    def _typing(self) -> bool:
        focus = QApplication.focusWidget()
        return isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) or (isinstance(focus, QComboBox) and focus.isEditable())

    def _unless_typing(self, handler) -> None:
        if not self._typing():
            handler()

    def _on_escape(self) -> None:
        self.canvas.cancel_drag()
        self.session.select("", origin="canvas")

    def _show_notice(self, message: str) -> None:
        self.status_notice.setText(message)
        self._notice_timer.start()

    # Keeping the interface truthful -------------------------------------------
    def _update_actions(self) -> None:
        session = self.session
        project = session.project
        previewing = session.preview is not None
        self.save_btn.setEnabled(bool(project and project.dirty))
        self.save_btn.setToolTip("Save (Ctrl+S)" if project and project.dirty else "Nothing new to save")
        history = project.history if project else None
        can_undo = bool(history and history.can_undo and not previewing)
        can_redo = bool(history and history.can_redo and not previewing)
        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)
        self.undo_btn.setToolTip(f"Undo {history.undo_label} (Ctrl+Z)" if can_undo else "Nothing to undo")
        self.redo_btn.setToolTip(f"Redo {history.redo_label} (Ctrl+Shift+Z)" if can_redo else "Nothing to redo")
        has_design = session.document is not None
        for button in (self.zoom_in_btn, self.zoom_out_btn, self.zoom_label, self.preview_btn, *self.device_buttons.values()):
            button.setEnabled(has_design)
        self.export_btn.setEnabled(bool(project) and not previewing)
        self.home_btn.setEnabled(has_design)
        self.export_btn.setToolTip("Export this design as a WordPress theme or a static website" if project and not previewing else "Open or create a project to export it. A template preview cannot be exported.")
        self.banner.setVisible(previewing)
        if previewing:
            names = {c.id: c.name for c in session.library.categories}
            self.banner_text.setText(f"Previewing <b>{session.preview.name}</b> ({names.get(session.preview.category, '')}). {session.preview.description}")
            self.banner_use.setText("Apply to this project" if project else "Use this template")
        self.templates_panel.use.setText("Apply to this project" if project else "Use this template")
        title = f"{project.name}{' *' if project.dirty else ''} | {APP_NAME}" if project else APP_NAME
        self.setWindowTitle(title)
        self._update_status()

    def _update_status(self) -> None:
        session = self.session
        project = session.project
        if session.preview:
            self.status_project.setText(f"Template preview: {session.preview.name}")
            self.status_save.setText("Read-only")
        elif project:
            self.status_project.setText(f"Project: {project.name}")
            self.status_save.setText(session.last_save_note)
        else:
            self.status_project.setText("No project open")
            self.status_save.setText("")
        page = session.current_page
        self.status_page.setText(f"Page: {page['title']}" if page else "")
        node = session.selected_node
        self.status_selection.setText(f"Selected: {type_label(node)}: {session.selected_label}" if node and type_label(node) != session.selected_label else (f"Selected: {session.selected_label}" if node else ""))
        if session.document is not None:
            self.status_size.setText(f"{session.viewport.title()}, {VIEWPORTS[session.viewport]} px at {round(self.canvas.zoom * 100)}%")
            self.zoom_label.setText(f"{round(self.canvas.zoom * 100)}%")
        else:
            self.status_size.setText("")

    # Commands -----------------------------------------------------------------
    def _show_error(self, message: str, details: list[str] | None = None) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(APP_NAME)
        box.setText(message)
        if details:
            box.setDetailedText("\n".join(details))
        box.exec()

    def _handle(self, exc: StudioError) -> None:
        self._show_error(str(exc), getattr(exc, "details", None))

    def _confirm_leave(self) -> bool:
        """Offers to save unsaved work. False means stay where you are."""
        project = self.session.project
        if not project or not project.dirty:
            return True
        answer = QMessageBox.question(
            self, APP_NAME, f"Save your changes to {project.name}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        project.discard_autosave()
        return True

    def go_home(self) -> None:
        """Closes the project (after offering to save) and shows the start screen with recent projects."""
        if not self._confirm_leave():
            return
        self.session.close_project()
        self._fill_recent()
        self.rail_buttons[0].setChecked(True)
        self.side_stack.setCurrentIndex(0)

    def new_project(self, template_id: str = "") -> None:
        if not self._confirm_leave():
            return
        dialog = NewProjectDialog(self.session.library, self.session.settings, template_id, self)
        if dialog.exec():
            try:
                self.session.create_project(dialog.project_name, dialog.template_id, dialog.parent_folder)
                self._fill_recent()
            except StudioError as exc:
                self._handle(exc)

    def open_project(self) -> None:
        if not self._confirm_leave():
            return
        folder = QFileDialog.getExistingDirectory(self, "Open a project folder", str(self.session.settings.projects_path))
        if folder:
            self._open_path(Path(folder))

    def _open_path(self, path: Path) -> None:
        if not self._confirm_leave():
            return
        try:
            project = self.session.open_project(path)
            if project.has_recoverable_autosave():
                answer = QMessageBox.question(
                    self, APP_NAME,
                    "This project has newer unsaved work from an autosave. Recover it?\n\n"
                    "Choosing No deletes the autosave and opens the last saved version.",
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.session.recover_autosave()
                else:
                    project.discard_autosave()
            self._fill_recent()
        except StudioError as exc:
            self._handle(exc)

    def save_project(self) -> bool:
        if not self.session.project:
            return True
        try:
            self.session.save()
            return True
        except StudioError as exc:
            self._handle(exc)
            return False

    def open_library(self) -> None:
        from .library_window import LibraryWindow
        if getattr(self, "library_window", None) is None:
            self.library_window = LibraryWindow(self.session, self.pal, self)
            self.library_window.newProjectRequested.connect(self.project_from_resource)
        self.library_window.show()
        self.library_window.raise_()
        self.library_window.activateWindow()

    def project_from_resource(self, resource_id: str) -> None:
        resource = self.session.resources.get(resource_id)
        if resource is None:
            return
        if resource.origin == "builtin":
            self.new_project(resource.data["template_id"])
            return
        if not self._confirm_leave():
            return
        name, ok = QInputDialog.getText(self, "New project", "Project name", text=resource.name)
        if not ok or not name.strip():
            return
        try:
            self.session.create_project_from_resource(resource, name.strip())
            self._fill_recent()
        except StudioError as exc:
            self._handle(exc)

    def use_template(self, template_id: str) -> None:
        if self.session.project:
            answer = QMessageBox.question(
                self, APP_NAME,
                f"Replace the design of {self.session.project.name} with this template?\n\nUploaded media is kept, and you can undo this.",
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self.session.apply_template_to_project(template_id)
                except StudioError as exc:
                    self._handle(exc)
        else:
            self.new_project(template_id)

    def design_screenshot(self) -> bytes | None:
        """The theme's picture in WordPress: the canvas as it looks now."""
        shot = self.canvas.grab()
        if shot.isNull() or shot.width() < 100:
            return None
        shot = shot.scaled(1200, 900, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation).copy(0, 0, 1200, 900)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        shot.save(buffer, "PNG")
        return bytes(buffer.data())

    def open_export(self) -> None:
        if not self.session.project or self.session.preview:
            return
        ExportDialog(self.session, self.design_screenshot(), self).exec()

    def preview_site(self) -> None:
        """Writes the website with no editor code and opens it in the default browser."""
        doc = self.session.document
        if doc is None:
            return
        project = self.session.project if not self.session.read_only else None
        if project:
            target = project.folder / "previews" / "site"
            folder = project.folder
        else:
            target = Path(self.canvas._temp) / "browser-preview"
            folder = None
        try:
            if target.exists():
                shutil.rmtree(target)
            output = write_site(doc, target, project_folder=folder)
        except OSError as exc:
            self._show_error(f"The preview could not be written: {exc}")
            return
        page = self.session.current_page
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.root / page_filename(page)))):
            self._show_error(f"No browser could be opened. The website was written to {output.root}")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.session.settings, self)
        if dialog.exec():
            before = self.session.settings.appearance
            dialog.apply()
            try:
                self.session.settings.save()
            except OSError as exc:
                self._show_error(f"Settings could not be saved: {exc}")
            self._apply_autosave_settings()
            if self.session.settings.appearance != before:
                QMessageBox.information(self, APP_NAME, "The new appearance applies the next time you open the studio.")

    def _apply_autosave_settings(self) -> None:
        settings = self.session.settings
        self._autosave.stop()
        if settings.autosave_enabled:
            self._autosave.start(settings.autosave_seconds * 1000)

    def _on_autosave(self) -> None:
        try:
            self.session.autosave()
        except ProjectError as exc:
            # Never interrupt work with a dialog for a background save; show it where it is noticed.
            self.session.last_save_note = str(exc)
            self._update_status()

    def closeEvent(self, event):  # noqa: N802
        if not self._confirm_leave():
            event.ignore()
            return
        self._autosave.stop()
        self.canvas.shutdown()
        event.accept()
