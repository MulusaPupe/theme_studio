"""The component library: browse, then drag onto the canvas or double-click to add."""
from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from ...components import registry
from ..canvas import COMPONENT_MIME
from ..session import Session
from ..theme import Palette, icon_pixmap
from ..widgets import label


class ComponentTile(QFrame):
    """One component. Drag it to the canvas, or double-click to add it in the natural place."""

    def __init__(self, component: registry.ComponentDef, session: Session, pal: Palette) -> None:
        super().__init__()
        self.component = component
        self.session = session
        self.setObjectName("Tile")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{component.description}\nDrag onto the page, or double-click to add.")
        self.setAccessibleName(component.label)
        self.setFixedHeight(66)
        self._press: QPoint | None = None
        column = QVBoxLayout(self)
        column.setContentsMargins(4, 9, 4, 7)
        column.setSpacing(4)
        art = QLabel()
        art.setPixmap(icon_pixmap(component.icon, pal.text, 20))
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(component.label)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setProperty("role", "tile")
        for child in (art, name):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            column.addWidget(child)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._press = None

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._press is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if (event.position().toPoint() - self._press).manhattanLength() >= QApplication.startDragDistance():
            self._press = None
            self.start_drag()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = None
            self.session.insert_component(self.component.id)

    def make_drag(self) -> QDrag:
        mime = QMimeData()
        mime.setData(COMPONENT_MIME, self.component.id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        preview = self.grab()
        drag.setPixmap(preview)
        drag.setHotSpot(QPoint(preview.width() // 2, preview.height() // 2))
        return drag

    def start_drag(self) -> None:
        if not self.session.begin_component_drag(self.component.id):
            return
        try:
            self.make_drag().exec(Qt.DropAction.CopyAction)
        finally:
            self.session.end_component_drag()


class ComponentsPanel(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.tiles: list[ComponentTile] = []
        self._headers: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(label("Components", "title"))
        layout.addWidget(label("Drag onto the page, or double-click to add.", "faint", wrap=True))
        self.search = QLineEdit(placeholderText="Search components")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        layout.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        self.column = QVBoxLayout(body)
        self.column.setContentsMargins(0, 2, 6, 2)
        self.column.setSpacing(6)
        self._grids: dict[str, tuple[QWidget, QGridLayout]] = {}
        for group in registry.groups():
            header = label(group.upper(), "section")
            self._headers[group] = header
            self.column.addWidget(header)
            holder = QWidget()
            grid = QGridLayout(holder)
            grid.setContentsMargins(0, 0, 0, 8)
            grid.setSpacing(6)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            self._grids[group] = (holder, grid)
            self.column.addWidget(holder)
            for component in registry.catalogue():
                if component.group == group:
                    self.tiles.append(ComponentTile(component, session, pal))
        self.column.addStretch(1)
        self.empty = label("No components match that search.", "muted", wrap=True)
        self.empty.hide()
        self.column.insertWidget(0, self.empty)
        self.apply_filter("")

    def apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        any_shown = False
        for group, (holder, grid) in self._grids.items():
            shown = 0
            for tile in self.tiles:
                if tile.component.group != group:
                    continue
                match = not needle or needle in f"{tile.component.label} {tile.component.description}".lower()
                tile.setVisible(match)
                if match:
                    # Re-flow so filtering leaves no gaps in the grid.
                    grid.addWidget(tile, shown // 2, shown % 2)
                    shown += 1
            holder.setVisible(shown > 0)
            self._headers[group].setVisible(shown > 0)
            any_shown = any_shown or shown > 0
        self.empty.setVisible(not any_shown)
