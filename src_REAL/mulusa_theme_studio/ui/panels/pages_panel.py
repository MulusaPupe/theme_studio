"""The pages of the open design. Switching works now; managing pages arrives in Stage 04."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..session import Session
from ..theme import Palette, make_icon
from ..widgets import Notice, label


class PagesPanel(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(label("Pages", "title"))
        self.empty = label("Open a project or preview a template to see its pages.", "muted", wrap=True)
        layout.addWidget(self.empty)
        self.list = QListWidget()
        self.list.itemClicked.connect(lambda item: session.set_page(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.list, 1)
        layout.addWidget(Notice(pal, "Managing pages: Stage 04", "Creating, renaming, duplicating and deleting pages arrive with multi-page management."))
        session.documentChanged.connect(self.refresh)
        session.pageChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        doc = self.session.document
        self.empty.setVisible(doc is None)
        self.list.clear()
        if not doc:
            return
        for page in doc["pages"]:
            text = f"{page['title']}   (homepage)" if page.get("home") else page["title"]
            item = QListWidgetItem(make_icon("house" if page.get("home") else "file-text", self.pal, 16), text)
            item.setData(Qt.ItemDataRole.UserRole, page["id"])
            item.setToolTip(f"/{page['slug']}")
            self.list.addItem(item)
            if page["id"] == self.session.page_id:
                item.setSelected(True)
                self.list.setCurrentItem(item)
