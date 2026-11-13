"""Browse the template library, preview on the canvas, and start from a template."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QComboBox, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ...core.errors import StudioError
from ..session import Session
from ..widgets import label

THUMB = QSize(232, 174)


class TemplatesPanel(QWidget):
    useRequested = Signal(str)
    errorRaised = Signal(str)

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(label("Templates", "title"))
        self.count = label("", "faint")
        layout.addWidget(self.count)
        self.search = QLineEdit(placeholderText="Search templates")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.category = QComboBox()
        self.category.addItem("All categories", None)
        for category in session.library.categories:
            self.category.addItem(category.name, category.id)
        self.category.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.category)
        self.list = QListWidget()
        self.list.setIconSize(THUMB)
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.setWordWrap(True)
        self.list.setViewMode(QListWidget.ViewMode.ListMode)
        self.list.itemClicked.connect(self._on_clicked)
        self.list.itemDoubleClicked.connect(lambda item: self.useRequested.emit(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.list, 1)
        self.use = QPushButton("Use this template")
        self.use.setProperty("primary", True)
        self.use.setEnabled(False)
        self.use.clicked.connect(self._on_use)
        layout.addWidget(self.use)
        session.templatePreviewChanged.connect(self._sync)
        self.refresh()

    def refresh(self) -> None:
        results = self.session.library.search(self.search.text(), self.category.currentData())
        self.list.clear()
        names = {c.id: c.name for c in self.session.library.categories}
        for info in results:
            item = QListWidgetItem(f"{info.name}\n{names.get(info.category, info.category)}")
            pixmap = QPixmap(str(info.thumbnail))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            item.setToolTip(info.description)
            item.setData(Qt.ItemDataRole.UserRole, info.id)
            item.setSizeHint(QSize(236, THUMB.height() + 52))
            self.list.addItem(item)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setFlow(QListWidget.Flow.TopToBottom)
        self.list.setWrapping(False)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.count.setText(f"{len(results)} of {len(self.session.library.templates)} templates")

    def _on_clicked(self, item: QListWidgetItem) -> None:
        try:
            self.session.preview_template(item.data(Qt.ItemDataRole.UserRole))
        except StudioError as exc:
            self.errorRaised.emit(str(exc))

    def _on_use(self) -> None:
        if self.session.preview:
            self.useRequested.emit(self.session.preview.id)

    def _sync(self) -> None:
        self.use.setEnabled(self.session.preview is not None)
        if self.session.preview is None:
            self.list.clearSelection()
