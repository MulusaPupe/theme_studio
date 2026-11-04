"""The strip above the canvas: where the selection sits, and what can be done to it."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QToolButton, QWidget

from ..core.document import describe_node, node_label, type_label
from .session import Session
from .theme import Palette, icon_pixmap, make_icon
from .widgets import label, separator

MAX_CRUMBS = 5


class SelectionBar(QFrame):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        self.setObjectName("SelectionBar")
        self.setFixedHeight(40)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(2)
        self.hint = label("Click any element on the page to select it.", "faint")
        row.addWidget(self.hint)
        self.crumbs = QHBoxLayout()
        self.crumbs.setSpacing(0)
        row.addLayout(self.crumbs)
        row.addStretch(1)
        self.buttons: dict[str, QToolButton] = {}
        specs = (
            ("up", "arrow-up", "Move up (Alt+Up)", lambda: session.shift_selected(-1)),
            ("down", "arrow-down", "Move down (Alt+Down)", lambda: session.shift_selected(1)),
            (None, None, None, None),
            ("copy", "copy", "Copy (Ctrl+C)", session.copy_selected),
            ("paste", "clipboard-paste", "Paste (Ctrl+V)", session.paste),
            ("duplicate", "copy-plus", "Duplicate (Ctrl+D)", session.duplicate_selected),
            (None, None, None, None),
            ("delete", "trash-2", "Delete (Del)", session.delete_selected),
        )
        for key, icon, tip, handler in specs:
            if key is None:
                row.addSpacing(4)
                row.addWidget(separator())
                row.addSpacing(4)
                continue
            button = QToolButton()
            button.setIcon(make_icon(icon, pal, 16))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(tip)
            button.setAccessibleName(tip.split(" (")[0])
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, h=handler: h())
            self.buttons[key] = button
            row.addWidget(button)
        self._tips = {key: b.toolTip() for key, b in self.buttons.items()}
        session.selectionChanged.connect(self.refresh)
        session.documentChanged.connect(self.refresh)
        session.pageChanged.connect(self.refresh)
        session.templatePreviewChanged.connect(self.refresh)
        self.refresh()

    def _crumb(self, node: dict, current: bool) -> QPushButton:
        text = type_label(node) if not node.get("name") and not node.get("props", {}).get("role") else node_label(node)
        button = QPushButton(text if len(text) <= 22 else text[:21] + "…")
        button.setObjectName("CrumbCurrent" if current else "Crumb")
        button.setToolTip(describe_node(node) if current else f"Select {describe_node(node)}")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        node_id = node["id"]
        button.clicked.connect(lambda _=False: self.session.select(node_id, origin="panel"))
        return button

    def _clear_crumbs(self) -> None:
        while self.crumbs.count():
            item = self.crumbs.takeAt(0)
            widget: QWidget | None = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh(self) -> None:
        self._clear_crumbs()
        path = self.session.selection_path()
        self.hint.setVisible(not path)
        shown = path[-MAX_CRUMBS:]
        if len(path) > MAX_CRUMBS:
            self.crumbs.addWidget(label("…  ", "faint"))
        for position, node in enumerate(shown):
            if position:
                arrow = label("")
                arrow.setPixmap(icon_pixmap("chevron-right", self.pal.faint, 13))
                self.crumbs.addWidget(arrow)
            self.crumbs.addWidget(self._crumb(node, position == len(shown) - 1))
        state = self.session.actions()
        for key, button in self.buttons.items():
            enabled = getattr(state, key)
            button.setEnabled(enabled)
            button.setToolTip(self._tips[key] if enabled or not state.reason else f"{self._tips[key]}\n{state.reason}")
