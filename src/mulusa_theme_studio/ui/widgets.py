"""Small shared widgets."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import Palette, icon_pixmap


def label(text: str = "", role: str = "", *, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    if wrap:
        widget.setWordWrap(True)
    return widget


def separator(vertical: bool = True) -> QFrame:
    line = QFrame()
    line.setObjectName("Separator")
    if vertical:
        line.setFixedWidth(1)
        line.setFixedHeight(22)
    else:
        line.setFixedHeight(1)
    return line


class Notice(QFrame):
    """States plainly that a feature is not built yet, and which stage delivers it."""

    def __init__(self, pal: Palette, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Notice")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(icon_pixmap("info", pal.accent, 16))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(icon)
        column = QVBoxLayout()
        column.setSpacing(2)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 650;")
        column.addWidget(heading)
        column.addWidget(label(body, "muted", wrap=True))
        outer.addLayout(column, 1)
