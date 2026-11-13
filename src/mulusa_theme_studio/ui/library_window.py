"""The Creative Resource Library window: discover, browse, search, preview, import and use resources.

Everything here acts through the Session (insertion, design changes, new projects) or through the
library package (import, store, remote catalogue). The window holds no document state of its own.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..core.errors import StudioError
from ..library.model import COMPATIBILITY, SECTION_CATEGORIES, Resource
from .session import Session
from .theme import Palette, icon_pixmap
from .widgets import label

THUMB = QSize(232, 158)
ROLE_ID = Qt.ItemDataRole.UserRole + 1

# Left navigation: (label, kind filter, special view)
VIEWS = [
    ("Discover", None, "discover"),
    ("Website templates", "template", ""),
    ("Sections", "section", ""),
    ("Headers", "header", ""),
    ("Footers", "footer", ""),
    ("Colour palettes", "palette", ""),
    ("Type pairings", "type_pair", ""),
    ("Fonts", "font", ""),
    ("Icons", "icon", ""),
    ("Animated illustrations", "illustration", ""),
    ("Patterns and gradients", "pattern", ""),
    ("Images", "image", ""),
    ("My imports", None, "imported"),
    ("Favourites", None, "favourites"),
    ("Recently used", None, "recent"),
    ("Find online", None, "online"),
]


def swatch_pixmap(colors: dict, size: QSize = THUMB) -> QPixmap:
    pix = QPixmap(size)
    pix.fill(QColor(colors.get("background", "#ffffff")))
    p = QPainter(pix)
    keys = ["primary", "secondary", "accent", "surface", "text"]
    w = size.width() // len(keys)
    for i, k in enumerate(keys):
        p.fillRect(i * w, size.height() // 2, w + 1, size.height() // 2, QColor(colors.get(k, "#888888")))
    p.setPen(QColor(colors.get("text", "#000")))
    f = QFont()
    f.setPointSize(15)
    f.setBold(True)
    p.setFont(f)
    p.drawText(16, 16, size.width() - 32, size.height() // 2 - 24, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Aa")
    p.end()
    return pix


def type_pixmap(heading: str, body: str, pal: Palette, size: QSize = THUMB) -> QPixmap:
    pix = QPixmap(size)
    pix.fill(QColor(pal.raised))
    p = QPainter(pix)
    p.setPen(QColor(pal.text))
    hf = QFont(heading)
    hf.setPixelSize(34)
    p.setFont(hf)
    p.drawText(16, 18, size.width() - 32, 60, Qt.AlignmentFlag.AlignLeft, "Aa Gg")
    bf = QFont(body)
    bf.setPixelSize(14)
    p.setFont(bf)
    p.setPen(QColor(pal.muted))
    p.drawText(16, 86, size.width() - 32, 60, Qt.TextFlag.TextWordWrap, "The quick brown fox jumps over the lazy dog.")
    p.end()
    return pix


def gradient_pixmap(colors: dict, key: str, size: QSize = THUMB) -> QPixmap:
    from PySide6.QtGui import QLinearGradient
    stops = {"primary-secondary": ("primary", "secondary"), "primary-accent": ("primary", "accent"), "surface-fade": ("surface", "background"),
             "spotlight": ("accent", "primary"), "dusk": ("secondary", "text")}.get(key, ("primary", "secondary"))
    pix = QPixmap(size)
    p = QPainter(pix)
    g = QLinearGradient(0, 0, size.width(), size.height())
    g.setColorAt(0, QColor(colors.get(stops[0], "#333")))
    g.setColorAt(1, QColor(colors.get(stops[1], "#999")))
    p.fillRect(pix.rect(), g)
    p.end()
    return pix


class LibraryWindow(QDialog):
    """A non-modal window beside the editor."""

    newProjectRequested = Signal(str)   # resource id: the main window confirms leaving the current project and names it

    def __init__(self, session: Session, pal: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.pal = pal
        self.library = session.resources
        self.setWindowTitle("Creative Resource Library")
        self.setModal(False)
        self.resize(1320, 820)
        self._pending: list[QStandardItem] = []
        self._current: Resource | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        nav_frame = QFrame()
        nav_frame.setObjectName("Rail")
        nav_frame.setFixedWidth(210)
        nav_col = QVBoxLayout(nav_frame)
        nav_col.setContentsMargins(12, 16, 8, 12)
        nav_col.addWidget(label("Resource Library", "title"))
        nav_col.addSpacing(8)
        self.nav = QListWidget()
        self.nav.setFrameShape(QFrame.Shape.NoFrame)
        for name, _, _ in VIEWS:
            self.nav.addItem(name)
        self.nav.currentRowChanged.connect(self._on_view)
        nav_col.addWidget(self.nav, 1)
        self.import_btn = QPushButton("Import a package…")
        self.import_btn.setProperty("primary", True)
        self.import_btn.setToolTip("ZIP, HTML, WordPress block theme or pattern, Mulusa section, or images")
        self.import_btn.clicked.connect(self.open_import)
        nav_col.addWidget(self.import_btn)
        outer.addWidget(nav_frame)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        # Centre: filters and results ------------------------------------------------
        centre = QWidget()
        col = QVBoxLayout(centre)
        col.setContentsMargins(16, 14, 8, 12)
        col.setSpacing(8)
        bar = QHBoxLayout()
        self.heading = label("", "title")
        bar.addWidget(self.heading)
        bar.addStretch(1)
        self.count = label("", "faint")
        bar.addWidget(self.count)
        col.addLayout(bar)
        filters = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Search names, descriptions and tags")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda: self._debounce.start())
        filters.addWidget(self.search, 2)
        self.category = QComboBox()
        self.category.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.category, 1)
        self.tag = QComboBox()
        self.tag.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.tag, 1)
        self.folder = QComboBox()
        self.folder.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.folder, 1)
        col.addLayout(filters)
        self._debounce = QTimer(self, singleShot=True, interval=180)
        self._debounce.timeout.connect(self.refresh)

        self.pages = QStackedWidget()
        self.model = QStandardItemModel(self)
        self.grid = QListView()
        self.grid.setModel(self.model)
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(THUMB)
        self.grid.setGridSize(QSize(THUMB.width() + 22, THUMB.height() + 58))
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setFrameShape(QFrame.Shape.NoFrame)
        self.grid.setSpacing(6)
        self.grid.setStyleSheet(self._grid_css())
        self.grid.selectionModel().currentChanged.connect(lambda cur, _prev: self._select(cur.data(ROLE_ID)))
        self.grid.doubleClicked.connect(lambda idx: self.use(self.library.get(idx.data(ROLE_ID))))
        self.grid.verticalScrollBar().valueChanged.connect(lambda: self._thumbs.start())
        self.pages.addWidget(self.grid)
        self.discover = QScrollArea()
        self.discover.setWidgetResizable(True)
        self.discover.setFrameShape(QFrame.Shape.NoFrame)
        self.pages.addWidget(self.discover)
        self.online = OnlinePanel(self)
        self.pages.addWidget(self.online)
        col.addWidget(self.pages, 1)
        splitter.addWidget(centre)
        self._thumbs = QTimer(self, singleShot=True, interval=30)
        self._thumbs.timeout.connect(self._load_visible_thumbs)

        # Right: details -------------------------------------------------------------
        self.details = DetailPanel(self)
        splitter.addWidget(self.details)
        splitter.setSizes([860, 380])
        self.nav.setCurrentRow(0)

    def _grid_css(self) -> str:
        p = self.pal
        return (f"QListView {{ background: transparent; border: none; color: {p.text}; }}"
                f"QListView::item {{ color: {p.text}; border-radius: 8px; padding: 4px; }}"
                f"QListView::item:hover {{ background: {p.hover}; }}"
                f"QListView::item:selected {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.accent}; }}")

    # Views --------------------------------------------------------------------
    @property
    def view(self) -> tuple[str, str | None, str]:
        return VIEWS[max(0, self.nav.currentRow())]

    def _on_view(self, _row: int) -> None:
        name, kind, special = self.view
        self.heading.setText(name)
        for combo in (self.category, self.tag, self.folder):
            combo.blockSignals(True)
            combo.clear()
        self.category.addItem("All categories", None)
        cats = list(SECTION_CATEGORIES) if kind == "section" else self.library.categories(kind) if kind else []
        for c in cats:
            if kind != "section" or any(r.category == c for r in self.library.all() if r.kind == "section"):
                self.category.addItem(SECTION_CATEGORIES.get(c, c) if kind == "section" else c, c)
        self.tag.addItem("All tags", None)
        for t in self.library.tags(kind):
            self.tag.addItem(t, t)
        self.folder.addItem("All folders", None)
        self.folder.addItem("Not in a folder", "")
        for f in self.library.store.folders():
            self.folder.addItem(f, f)
        for combo in (self.category, self.tag, self.folder):
            combo.blockSignals(False)
        self.category.setVisible(bool(kind) and self.category.count() > 1)
        self.tag.setVisible(special in ("", "imported") and self.tag.count() > 1)
        self.folder.setVisible(special == "imported")
        self.search.setVisible(special != "online")
        self.refresh()

    def refresh(self) -> None:
        name, kind, special = self.view
        if special == "discover":
            self._show_discover()
            return
        if special == "online":
            self.pages.setCurrentWidget(self.online)
            self.count.setText("")
            self.details.show_empty("Search an official catalogue. Items without a licence that allows reuse are shown as links only.")
            return
        text = self.search.text()
        if special == "favourites":
            results = [r for r in self.library.favourites() if not text or all(w in r.haystack() for w in text.lower().split())]
        elif special == "recent":
            results = [r for r in self.library.recent() if not text or all(w in r.haystack() for w in text.lower().split())]
        else:
            results = self.library.search(text, kind=kind, category=self.category.currentData(),
                                          tags=[self.tag.currentData()] if self.tag.currentData() else None,
                                          folder=self.folder.currentData() if special == "imported" else None)
            if special == "imported":
                results = [r for r in results if r.origin != "builtin"]
        self.fill(results)
        self.pages.setCurrentWidget(self.grid)

    def fill(self, results: list[Resource]) -> None:
        self.model.clear()
        self._pending = []
        blank = QPixmap(THUMB)
        blank.fill(QColor(self.pal.raised))
        for r in results:
            item = QStandardItem(QIcon(blank), f"{r.name}\n{self._subtitle(r)}")
            item.setData(r.id, ROLE_ID)
            item.setToolTip(r.description or r.name)
            item.setEditable(False)
            self.model.appendRow(item)
            self._pending.append(item)
        self.count.setText(f"{len(results)} resource{'s' if len(results) != 1 else ''}")
        if not results:
            self.details.show_empty("Nothing matches. Try other words or another category." if self.search.text() else "Nothing here yet.")
        self._thumbs.start()

    def _subtitle(self, r: Resource) -> str:
        if r.kind == "section":
            return SECTION_CATEGORIES.get(r.category, r.category)
        if r.origin != "builtin":
            return f"{r.kind_name} · {COMPATIBILITY.get(r.compatibility, '')}"
        return r.category or r.kind_name

    def _load_visible_thumbs(self) -> None:
        """Thumbnails load lazily: only for items on screen, a few at a time."""
        if not self._pending:
            return
        viewport = self.grid.viewport().rect()
        done = 0
        for item in list(self._pending):
            rect = self.grid.visualRect(item.index())
            if rect.intersects(viewport.adjusted(0, -200, 0, 400)):
                resource = self.library.get(item.data(ROLE_ID))
                if resource:
                    item.setIcon(QIcon(self.thumbnail(resource)))
                self._pending.remove(item)
                done += 1
                if done >= 24:
                    self._thumbs.start()
                    return

    def _illustration_preview(self, r: Resource, size: QSize) -> QPixmap:
        """A still drawing in the open project's colours (Qt's SVG renderer has no CSS, so colours are written in)."""
        from PySide6.QtSvg import QSvgRenderer
        from ..render.illustrations import static_svg
        colors = (self.session.document["tokens"]["colors"] if self.session.document else {}) or {}
        pix = QPixmap(size)
        pix.fill(QColor(colors.get("background", "#ffffff")))
        renderer = QSvgRenderer(static_svg(r.data["name"], colors).encode("utf-8"))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = size.height() - 16
        w = round(h * 240 / 180)
        renderer.render(p, QRectF((size.width() - w) / 2, 8, w, h))
        p.end()
        return pix

    def thumbnail(self, r: Resource, size: QSize = THUMB) -> QPixmap:
        if r.kind == "palette":
            return swatch_pixmap(r.data.get("colors", {}), size)
        if r.kind == "type_pair":
            return type_pixmap(r.data["heading"], r.data["body"], self.pal, size)
        if r.kind == "font":
            return type_pixmap(r.data["family"], r.data["family"], self.pal, size)
        if r.kind == "icon":
            pix = QPixmap(size)
            pix.fill(QColor(self.pal.raised))
            p = QPainter(pix)
            icon = icon_pixmap(r.data["name"], self.pal.text, 48, 1.0)
            p.drawPixmap((size.width() - 48) // 2, (size.height() - 48) // 2, icon)
            p.end()
            return pix
        if r.kind == "illustration":
            return self._illustration_preview(r, size)
        if r.kind == "pattern" and "gradient" in r.data:
            colors = self.session.document["tokens"]["colors"] if self.session.document else {}
            return gradient_pixmap(colors or {"primary": "#1f3a5f", "secondary": "#16293f", "accent": "#d9822b", "surface": "#f3f5f8", "background": "#fff", "text": "#16202b"}, r.data["gradient"], size)
        if r.kind == "pattern":
            return self._pattern_preview(r, size)
        if r.preview and Path(r.preview).is_file():
            pix = QPixmap(r.preview)
            if not pix.isNull():
                return pix.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation).copy(0, 0, size.width(), size.height())
        pix = QPixmap(size)
        pix.fill(QColor(self.pal.raised))
        p = QPainter(pix)
        icon = icon_pixmap({"template": "layout-template", "section": "rows-3", "package": "package"}.get(r.kind, "box"), self.pal.faint, 40, 1.0)
        p.drawPixmap((size.width() - 40) // 2, (size.height() - 40) // 2, icon)
        p.end()
        return pix

    def _pattern_preview(self, r: Resource, size: QSize) -> QPixmap:
        from ..library.patterns import render_pattern
        cache = self.library.store.cache_dir / "patterns" / f"{r.data['pattern']}.png"
        if not cache.is_file():
            render_pattern(r.data["pattern"], "#1d2a3a", "#f5f7fa", cache, (640, 360))
        return QPixmap(str(cache)).scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)

    def _show_discover(self) -> None:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        counts = self.library.counts()
        col.addWidget(label(f"{counts['template']} website templates · {counts['section']} sections · {counts['header']} headers · {counts['footer']} footers · "
                            f"{counts['palette']} palettes · {counts['font']} fonts · {counts['icon']} icons · {counts['pattern']} patterns and gradients", "muted", wrap=True))
        for title, items in self.library.discover().items():
            if not items:
                continue
            col.addWidget(label(title, "section"))
            row = QListWidget()
            row.setViewMode(QListWidget.ViewMode.IconMode)
            row.setFlow(QListWidget.Flow.LeftToRight)
            row.setWrapping(False)
            row.setIconSize(QSize(200, 136))
            row.setFixedHeight(200)
            row.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            row.setMovement(QListWidget.Movement.Static)
            row.setFrameShape(QFrame.Shape.NoFrame)
            row.setStyleSheet(self._grid_css())
            for r in items:
                it = QListWidgetItem(QIcon(self.thumbnail(r, QSize(200, 136))), r.name)
                it.setData(ROLE_ID, r.id)
                it.setToolTip(r.description)
                row.addItem(it)
            row.itemClicked.connect(lambda it: self._select(it.data(ROLE_ID)))
            row.itemDoubleClicked.connect(lambda it: self.use(self.library.get(it.data(ROLE_ID))))
            col.addWidget(row)
        col.addStretch(1)
        self.discover.setWidget(page)
        self.pages.setCurrentWidget(self.discover)
        self.count.setText("")
        self.details.show_empty("Choose a resource to see its details.")

    # Selection and actions ---------------------------------------------------
    def _select(self, resource_id: str | None) -> None:
        r = self.library.get(resource_id) if resource_id else None
        self._current = r
        if r is None:
            self.details.show_empty("")
        else:
            self.details.show(r)

    def use(self, r: Resource | None, role: str = "") -> None:
        """The main action for a resource."""
        if r is None:
            return
        if r.kind == "template":
            self.newProjectRequested.emit(r.id)
            return
        if not self.session.project:
            self.session.notify("Open or create a project first, then add resources to it.")
            self.details.flash("Open or create a project first.")
            return
        if r.kind == "section":
            ok = bool(self.session.insert_resource(r))
        else:
            ok = self.session.apply_resource(r, role)
        self.details.flash(f"{r.name}: done. Undo with Ctrl+Z." if ok else "Not applied. See the message in the editor's status bar.")

    def open_import(self) -> None:
        dialog = ImportDialog(self.session, self)
        if dialog.exec() and dialog.result_resources:
            self.library.store.reload()
            self.nav.setCurrentRow(next(i for i, v in enumerate(VIEWS) if v[2] == "imported"))
            self._on_view(self.nav.currentRow())
            self._select(dialog.result_resources[0].id)

    def after_store_change(self) -> None:
        self.library.store.reload()
        self._on_view(self.nav.currentRow())


class DetailPanel(QScrollArea):
    def __init__(self, window: LibraryWindow) -> None:
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(340)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.col = QVBoxLayout(body)
        self.col.setContentsMargins(12, 16, 16, 16)
        self.col.setSpacing(10)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumHeight(180)
        self.col.addWidget(self.image)
        self.name = label("", "title", wrap=True)
        self.col.addWidget(self.name)
        self.desc = label("", "muted", wrap=True)
        self.col.addWidget(self.desc)
        self.actions = QVBoxLayout()
        self.actions.setSpacing(6)
        self.col.addLayout(self.actions)
        self.note = label("", "notice", wrap=True)
        self.col.addWidget(self.note)
        self.meta = QFormLayout()
        self.meta.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.col.addLayout(self.meta)
        self.report_title = label("Not carried over on import", "section")
        self.col.addWidget(self.report_title)
        self.report = label("", "muted", wrap=True)
        self.report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.col.addWidget(self.report)
        self.col.addStretch(1)
        self.setWidget(body)
        self.show_empty("Choose a resource to see its details.")

    def _clear_actions(self) -> None:
        while self.actions.count():
            w = self.actions.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        while self.meta.rowCount():
            self.meta.removeRow(0)

    def show_empty(self, text: str) -> None:
        self._clear_actions()
        self.image.clear()
        self.name.setText("")
        self.desc.setText(text)
        self.note.setText("")
        self.report_title.hide()
        self.report.hide()

    def flash(self, text: str) -> None:
        self.note.setText(text)

    def _button(self, text: str, handler, primary: bool = False, enabled: bool = True, tip: str = "") -> QPushButton:
        b = QPushButton(text)
        b.setProperty("primary", primary)
        b.setEnabled(enabled)
        if tip:
            b.setToolTip(tip)
        b.clicked.connect(handler)
        self.actions.addWidget(b)
        return b

    def show(self, r: Resource) -> None:  # noqa: A003 - shows a resource
        w = self.window
        session = w.session
        self._clear_actions()
        self.note.setText("")
        self.image.setPixmap(w.thumbnail(r, QSize(340, 230)))
        self.name.setText(r.name)
        self.desc.setText(r.description)
        has_project = session.project is not None
        need = "" if has_project else "Open or create a project first."
        if r.kind == "template":
            self._button("Start a new project from this", lambda: w.use(r), True, r.can_use)
            if r.origin == "builtin":
                self._button("Preview on the canvas", lambda: self._preview_template(r))
            if r.can_use:
                self._button("Insert its home page sections into this page", lambda: self._insert_template(r), enabled=has_project, tip=need)
            self._button("Responsive preview", lambda: ResponsivePreview(session, r, w).exec(), enabled=r.can_use)
        elif r.kind == "section":
            self._button("Insert into the current page", lambda: w.use(r), True, has_project and r.can_use, need)
            self._button("Responsive preview", lambda: ResponsivePreview(session, r, w).exec())
        elif r.kind in ("header", "footer"):
            self._button(f"Use this {r.kind} on my site", lambda: w.use(r), True, has_project, need)
        elif r.kind == "palette":
            self._button("Apply these colours", lambda: w.use(r), True, has_project, need)
        elif r.kind == "type_pair":
            self._button("Apply this pairing", lambda: w.use(r), True, has_project, need)
        elif r.kind == "font":
            self._button("Use for headings", lambda: w.use(r, "heading"), True, has_project, need)
            self._button("Use for text", lambda: w.use(r, "body"), False, has_project, need)
        elif r.kind == "icon":
            self._button("Insert this icon", lambda: w.use(r), True, has_project, need or "Select a container or column on the canvas first.")
        elif r.kind == "illustration":
            self._button("Insert this illustration", lambda: w.use(r), True, has_project, need or "Select a container or column on the canvas first.")
        elif r.kind == "pattern":
            self._button("Apply to the selected section", lambda: w.use(r), True, has_project, need or "Select a section on the canvas first.")
        elif r.kind == "image":
            self._button("Add these images to Media", lambda: w.use(r), True, has_project, need)
        elif r.kind == "package":
            self._button("Show the package files", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(r.path)))
        fav = w.library.store.is_favourite(r.id)
        self._button("★ Remove from favourites" if fav else "☆ Add to favourites", lambda: self._toggle_fav(r))
        if r.source_url:
            self._button("Open the source page", lambda: QDesktopServices.openUrl(QUrl(r.source_url)))
        if r.origin != "builtin":
            self._button("Rename…", lambda: self._rename(r))
            self._button("Move to folder…", lambda: self._move(r))
            if (Path(r.path).parent / "original").is_dir():
                self._button("Show the original package", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(r.path).parent / "original"))))
            self._button("Delete from library", lambda: self._delete(r))
        lic = r.licence_info
        rows = [("Type", r.kind_name), ("Category", SECTION_CATEGORIES.get(r.category, r.category)), ("Source", r.source), ("Author", r.author),
                ("Licence", f"{lic.name}" + ("" if lic.redistributable else " (not a licence to redistribute)") + (" · keep the credit" if lic.attribution else "")),
                ("Format", r.format), ("Compatibility", r.compatibility_name), ("Responsive", r.responsive)]
        if r.added:
            rows.append(("Imported", r.added.replace("T", " ").replace("Z", " UTC")))
        if r.data.get("pages"):
            rows.append(("Contents", f"{r.data['pages']} page(s), {r.data.get('sections', 0)} sections, {r.data.get('assets', 0)} images"))
        if r.tags:
            rows.append(("Tags", ", ".join(r.tags)))
        if r.origin != "builtin" and r.path and not Path(r.path).exists():
            rows.append(("Missing", "The files of this resource are no longer on disk."))
        for key, value in rows:
            if value:
                v = QLabel(str(value))
                v.setWordWrap(True)
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.meta.addRow(label(key, "field"), v)
        self.report_title.setVisible(bool(r.report))
        self.report.setVisible(bool(r.report))
        self.report.setText("\n".join(f"• {line}" for line in r.report))

    def _preview_template(self, r: Resource) -> None:
        try:
            self.window.session.preview_template(r.data["template_id"])
            self.flash("Shown on the canvas. Use 'Start a new project from this' to keep it.")
        except StudioError as exc:
            self.flash(str(exc))

    def _insert_template(self, r: Resource) -> None:
        ids = self.window.session.insert_resource(r)
        self.flash(f"Added {len(ids)} sections. Undo with Ctrl+Z." if ids else "Nothing was added.")

    def _toggle_fav(self, r: Resource) -> None:
        store = self.window.library.store
        store.set_favourite(r.id, not store.is_favourite(r.id))
        self.show(r)

    def _rename(self, r: Resource) -> None:
        text, ok = QInputDialog.getText(self, "Rename", "Name", text=r.name)
        if ok and text.strip():
            self.window.library.store.rename(r.id, text)
            self.window.after_store_change()
            self.window._select(r.id)

    def _move(self, r: Resource) -> None:
        folders = self.window.library.store.folders()
        text, ok = QInputDialog.getItem(self, "Move to folder", "Folder (type a new name to create one; empty for none)", [""] + folders, 0, True)
        if ok:
            self.window.library.store.move_to_folder(r.id, text.strip())
            self.window.after_store_change()

    def _delete(self, r: Resource) -> None:
        answer = QMessageBox.question(self, "Delete", f"Delete '{r.name}' from your library?\n\nProjects that already use it keep their copy.")
        if answer == QMessageBox.StandardButton.Yes:
            self.window.library.store.delete(r.id)
            self.window.after_store_change()
            self.show_empty("Deleted.")


class ImportDialog(QDialog):
    """Select, inspect, preview the report, then import."""

    def __init__(self, session: Session, parent: QWidget | None = None, path: Path | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.result_resources: list[Resource] = []
        self.inspection = None
        self.setWindowTitle("Import a resource package")
        self.resize(640, 560)
        col = QVBoxLayout(self)
        col.addWidget(label("Import a resource package", "title"))
        col.addWidget(label("ZIP files or folders with an HTML/CSS website, a WordPress block theme or patterns, a Mulusa section or template, "
                            "or images. Single .html, .json and .php pattern files work too. Nothing in a package is ever run.", "muted", wrap=True))
        row = QHBoxLayout()
        self.path_edit = QLineEdit(placeholderText="Choose a file or folder")
        self.path_edit.setReadOnly(True)
        row.addWidget(self.path_edit, 1)
        pick = QPushButton("File…")
        pick.clicked.connect(self._pick_file)
        row.addWidget(pick)
        pick_dir = QPushButton("Folder…")
        pick_dir.clicked.connect(self._pick_folder)
        row.addWidget(pick_dir)
        col.addLayout(row)
        self.summary = label("", "", wrap=True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.summary, 1)
        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow("Name in your library", self.name)
        col.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        self.go = QPushButton("Import")
        self.go.setProperty("primary", True)
        self.go.setEnabled(False)
        self.go.clicked.connect(self._import)
        buttons.addWidget(self.go)
        col.addLayout(buttons)
        if path:
            self.inspect(Path(path))

    def _pick_file(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Choose a package", str(Path.home()),
                                              "Packages (*.zip *.html *.htm *.json *.php *.png *.jpg *.jpeg *.webp *.gif);;All files (*)")
        if file:
            self.inspect(Path(file))

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a package folder", str(Path.home()))
        if folder:
            self.inspect(Path(folder))

    def inspect(self, path: Path) -> None:
        from ..library.model import identify_licence
        from ..library.packages import inspect_package
        if self.inspection:
            self.inspection.close()
            self.inspection = None
        self.path_edit.setText(str(path))
        try:
            ins = inspect_package(path)
        except StudioError as exc:
            self.summary.setText(f"This package cannot be imported.\n\n{exc}")
            self.go.setEnabled(False)
            return
        self.inspection = ins
        lic = identify_licence(ins.licence)
        lines = ins.summary + [
            f"Licence: {lic.name}" + ("" if lic.redistributable else "  (unknown or restrictive: use only if you own it or have permission)"),
            f"Expected result: {COMPATIBILITY.get(ins.compatibility, ins.compatibility)}",
        ]
        if ins.problems:
            lines += ["", *[f"• {p}" for p in ins.problems]]
        self.summary.setText("\n".join(lines))
        self.name.setText(ins.name)
        self.go.setEnabled(ins.kind != "unknown")
        self.go.setText("Keep for reference" if ins.compatibility == "reference" else "Import")

    def _import(self) -> None:
        from ..library.packages import import_package
        path = Path(self.path_edit.text())
        if self.inspection:
            self.inspection.close()
            self.inspection = None
        try:
            result = import_package(path, self.session.resources.store, name=self.name.text().strip())
        except StudioError as exc:
            self.summary.setText(f"The import failed and nothing was added.\n\n{exc}")
            return
        self.result_resources = result.resources
        head = result.resources[0]
        if result.duplicate:
            text = f"This package is already in your library as '{head.name}'. Nothing new was added."
        else:
            extra = f" and {len(result.resources) - 1} section(s) from its patterns" if len(result.resources) > 1 else ""
            text = f"Imported '{head.name}': {head.compatibility_name.lower()}{extra}. Find it under My imports."
            if result.report:
                text += "\n\nNot carried over:\n" + "\n".join(f"• {line}" for line in result.report[:14])
        self.summary.setText(text)
        self.go.setEnabled(False)
        self.go.setText("Imported")
        self.close_btn.setText("Done")
        self.close_btn.clicked.disconnect()
        self.close_btn.clicked.connect(self.accept)

    def done(self, code: int) -> None:  # noqa: D401 - closes the inspection with the dialog
        if self.inspection:
            self.inspection.close()
            self.inspection = None
        super().done(code)


class OnlinePanel(QWidget):
    """Searches the official catalogues; imports only what its licence allows."""

    SOURCES = [("WordPress.org patterns", "patterns"), ("WordPress.org block themes", "themes"), ("GitHub block themes", "github"), ("GitHub HTML templates", "github-html")]

    def __init__(self, window: LibraryWindow) -> None:
        super().__init__()
        self.window = window
        self.items = []
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.source = QComboBox()
        for name, key in self.SOURCES:
            self.source.addItem(name, key)
        row.addWidget(self.source)
        self.query = QLineEdit(placeholderText="Search, e.g. pricing, portfolio, restaurant")
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query, 1)
        go = QPushButton("Search")
        go.clicked.connect(self.search)
        row.addWidget(go)
        col.addLayout(row)
        self.status = label("Results come from official APIs and are cached for offline use. Nothing downloads until you import an item.", "faint", wrap=True)
        col.addWidget(self.status)
        self.results = QListWidget()
        self.results.currentRowChanged.connect(self._show)
        col.addWidget(self.results, 2)
        self.info = label("", "muted", wrap=True)
        col.addWidget(self.info)
        buttons = QHBoxLayout()
        self.import_btn = QPushButton("Import into my library")
        self.import_btn.setProperty("primary", True)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.import_selected)
        buttons.addWidget(self.import_btn)
        self.open_btn = QPushButton("Open its page")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.items[self.results.currentRow()].source_url)))
        buttons.addWidget(self.open_btn)
        buttons.addStretch(1)
        col.addLayout(buttons)
        col.addWidget(label("Other sources", "section"))
        from ..library.remote import INSPIRATION
        links = QListWidget()
        links.setMaximumHeight(170)
        for name, url, note in INSPIRATION:
            it = QListWidgetItem(f"{name}: {note}")
            it.setData(ROLE_ID, url)
            it.setToolTip(url)
            links.addItem(it)
        links.itemDoubleClicked.connect(lambda it: QDesktopServices.openUrl(QUrl(it.data(ROLE_ID))))
        col.addWidget(links)

    def catalogue(self):
        from ..library.remote import RemoteCatalogue
        return RemoteCatalogue(self.window.library.store)

    def search(self) -> None:
        q = self.query.text().strip()
        key = self.source.currentData()
        cat = self.catalogue()
        self.status.setText("Searching…")
        self.repaint()
        if key == "patterns":
            res = cat.search_patterns(q)
        elif key == "themes":
            res = cat.search_themes(q)
        else:
            res = cat.search_github(q, "wordpress-block-theme" if key == "github" else "html-template")
        self.items = res.items
        self.results.clear()
        for it in res.items:
            self.results.addItem(f"{it.name}  ·  {it.source}  ·  {it.licence}" + ("" if it.importable else "  ·  link only"))
        msg = res.message or f"{len(res.items)} result(s)."
        if res.offline and res.items:
            msg = "Offline: showing results saved earlier. " + msg
        self.status.setText(msg)

    def _show(self, row: int) -> None:
        if row < 0 or row >= len(self.items):
            self.info.setText("")
            self.import_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            return
        it = self.items[row]
        self.info.setText("\n".join(filter(None, [it.description, f"By {it.author}" if it.author else "", *it.notes])))
        self.import_btn.setEnabled(it.importable)
        self.open_btn.setEnabled(bool(it.source_url))

    def import_selected(self) -> None:
        row = self.results.currentRow()
        if row < 0:
            return
        it = self.items[row]
        self.status.setText(f"Downloading and converting {it.name}…")
        self.repaint()
        try:
            result = self.catalogue().import_item(it)
        except StudioError as exc:
            self.status.setText(str(exc))
            return
        head = result.resources[0]
        self.status.setText(("Already in your library: " if result.duplicate else "Imported: ") + f"{head.name} ({head.compatibility_name}). "
                            "Find it under My imports.")
        self.window.library.store.reload()


class ResponsivePreview(QDialog):
    """Renders a template or section at desktop, tablet and phone widths."""

    WIDTHS = {"Desktop": 1280, "Tablet": 820, "Phone": 390}

    def __init__(self, session: Session, resource: Resource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import copy
        import json
        import tempfile

        from PySide6.QtWebEngineWidgets import QWebEngineView

        from ..library.convert import add_page, blank_document
        from ..render.site import write_site
        self.setWindowTitle(f"Preview: {resource.name}")
        self.resize(1320, 860)
        col = QVBoxLayout(self)
        row = QHBoxLayout()
        self.view = QWebEngineView()
        for name, width in self.WIDTHS.items():
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, w=width: self.set_width(w))
            row.addWidget(b)
        row.addStretch(1)
        col.addLayout(row)
        holder = QScrollArea()
        holder.setWidget(self.view)
        holder.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(holder, 1)
        self._temp = tempfile.TemporaryDirectory(prefix="mts-preview-")
        if resource.kind == "template" and resource.origin == "builtin":
            doc = session.library.load(resource.data["template_id"])
            folder = None
        elif resource.kind == "template":
            from ..library.packages import load_document
            doc, folder = load_document(resource), Path(resource.path)
        else:
            from ..library import apply as libapply
            trees, assets, assets_folder = libapply.load_sections(resource)
            base = copy.deepcopy(session.document) if session.document else blank_document("Preview")
            base["pages"] = []
            base["media"] = copy.deepcopy(base.get("media", {"art": "mono", "assets": []}))
            base["media"]["assets"] = list(base["media"].get("assets", [])) + list(assets)
            add_page(base, "Home", copy.deepcopy(trees), home=True)
            doc, folder = base, (assets_folder.parent if assets_folder else (session.project.folder if session.project else None))
        out = write_site(json.loads(json.dumps(doc)), Path(self._temp.name) / "site", project_folder=folder) if folder else \
            write_site(doc, Path(self._temp.name) / "site")
        self.page_file = next(iter(out.pages.values()))
        self.set_width(1280)

    def set_width(self, width: int) -> None:
        self.view.setFixedSize(width, 760)
        self.view.load(QUrl.fromLocalFile(str(self.page_file)))

    def done(self, code: int) -> None:
        super().done(code)
        self._temp.cleanup()
