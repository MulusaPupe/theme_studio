"""The element hierarchy of the current page. It only observes and asks the session."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ...core.document import describe_node, type_label
from ..session import Session
from ..theme import Palette, make_icon
from ..widgets import label

ICONS = {
    "section": "square", "container": "box", "columns": "columns-3", "row": "rows-3", "divider": "minus",
    "header": "panel-top", "footer": "panel-bottom", "heading": "heading-1", "text": "pilcrow", "richtext": "text",
    "image": "image", "gallery": "gallery-horizontal", "video": "video", "icon": "star", "button": "mouse-pointer-click",
    "link": "link", "faq_item": "circle-help", "contact_form": "mail",
    "illustration": "shapes", "countdown": "clock", "progress": "sliders-horizontal",
}
ID_ROLE = Qt.ItemDataRole.UserRole


class LayersPanel(QWidget):
    def __init__(self, session: Session, pal: Palette | None = None) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        self._syncing = False
        self._expanded: set[str] = set()
        self._items: dict[str, QTreeWidgetItem] = {}
        self._page_key = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(label("Layers", "title"))
        self.empty = label("Open a project or preview a template to see its structure.", "muted", wrap=True)
        layout.addWidget(self.empty)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(False)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tree.currentItemChanged.connect(self._on_current)
        self.tree.itemExpanded.connect(lambda item: self._note(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._note(item, False))
        layout.addWidget(self.tree, 1)
        session.documentChanged.connect(self.refresh)
        session.pageChanged.connect(self.refresh)
        session.selectionChanged.connect(self._sync_selection)
        self.refresh()

    def _note(self, item: QTreeWidgetItem, expanded: bool) -> None:
        if self._syncing:
            return
        key = item.data(0, ID_ROLE)
        if expanded:
            self._expanded.add(key)
        else:
            self._expanded.discard(key)

    def _add(self, parent, node: dict) -> None:
        item = QTreeWidgetItem(parent, [describe_node(node)])
        node_id = node.get("id", "")
        item.setData(0, ID_ROLE, node_id)
        item.setToolTip(0, f"{describe_node(node)}\nType: {type_label(node)}")
        if self.pal:
            item.setIcon(0, make_icon(ICONS.get(node.get("type"), "square"), self.pal, 14))
        self._items[node_id] = item
        for child in node.get("children", []):
            self._add(item, child)
        item.setExpanded(node_id in self._expanded)

    def refresh(self) -> None:
        doc = self.session.document
        self.empty.setVisible(doc is None)
        self._syncing = True
        offset = self.tree.verticalScrollBar().value()
        self.tree.clear()
        self._items = {}
        page = self.session.current_page
        if doc and page:
            root = QTreeWidgetItem(self.tree, [f"{page['title']} page"])
            root.setData(0, ID_ROLE, "")
            root.setToolTip(0, "The whole page. Choose this to clear the selection.")
            if self.pal:
                root.setIcon(0, make_icon("file-text", self.pal, 14))
            self._add(root, doc["site"]["header"])
            for node in page["nodes"]:
                self._add(root, node)
            self._add(root, doc["site"]["footer"])
            root.setExpanded(True)
        self.tree.verticalScrollBar().setValue(offset)
        self._syncing = False
        self._sync_selection()

    def _on_current(self, current, _previous) -> None:
        if not self._syncing:
            self.session.select(current.data(0, ID_ROLE) if current else "", origin="panel")

    def _sync_selection(self) -> None:
        target = self.session.selected_id
        self._syncing = True
        item = self._items.get(target) if target else None
        if item is None:
            self.tree.setCurrentItem(None)
            self.tree.clearSelection()
        else:
            parent = item.parent()
            while parent is not None:
                parent.setExpanded(True)
                key = parent.data(0, ID_ROLE)
                if key:
                    self._expanded.add(key)
                parent = parent.parent()
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)
        self._syncing = False
