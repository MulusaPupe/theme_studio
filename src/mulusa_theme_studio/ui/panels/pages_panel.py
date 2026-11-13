"""The site's structure: its pages, their details, the post templates and the menu."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from ...components.presets import PAGE_STARTERS
from ...core.document import find_page, site_pages, slugify
from ..fields import LinkField
from ..session import Session
from ..theme import Palette, make_icon
from ..widgets import label

ROLES = (("single", "Single post", "How one post looks."), ("archive", "Post archive", "How lists of posts look."), ("not_found", "Page not found", "Shown when an address does not exist."))


class PagesPanel(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        self._filling = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        column = QVBoxLayout(body)
        column.setContentsMargins(12, 12, 12, 12)
        column.setSpacing(8)
        column.addWidget(label("Pages", "title"))
        self.empty = label("Open a project or preview a template to see its pages.", "muted", wrap=True)
        column.addWidget(self.empty)

        self.list = QListWidget()
        self.list.setFixedHeight(170)
        self.list.itemClicked.connect(lambda item: session.set_page(item.data(Qt.ItemDataRole.UserRole)))
        column.addWidget(self.list)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.up_btn = self._tool("arrow-up", "Move this page up", lambda: self._move(-1))
        self.down_btn = self._tool("arrow-down", "Move this page down", lambda: self._move(1))
        self.duplicate_btn = self._tool("copy", "Duplicate this page", lambda: session.duplicate_page(session.page_id))
        self.home_btn = self._tool("house", "Make this the homepage", lambda: session.set_home_page(session.page_id))
        self.delete_btn = self._tool("trash-2", "Delete this page", self._delete)
        for button in (self.up_btn, self.down_btn, self.duplicate_btn, self.home_btn, self.delete_btn):
            tools.addWidget(button)
        tools.addStretch(1)
        column.addLayout(tools)

        self.new_title = QLineEdit(placeholderText="New page title")
        self.new_title.returnPressed.connect(self._add)
        self.new_starter = QComboBox()
        for key, (name, _build) in PAGE_STARTERS.items():
            self.new_starter.addItem(f"Layout: {name}", key)
        self.add_btn = QPushButton("Add page")
        self.add_btn.clicked.connect(self._add)
        column.addWidget(self.new_title)
        column.addWidget(self.new_starter)
        column.addWidget(self.add_btn)

        column.addWidget(label("THIS PAGE", "section"))
        self.title = QLineEdit()
        self.title.editingFinished.connect(lambda: self._details("title"))
        self.slug = QLineEdit()
        self.slug.setToolTip("The last part of the page's web address. Links to the page keep working when it changes.")
        self.slug.editingFinished.connect(lambda: self._details("slug"))
        self.description = QPlainTextEdit()
        self.description.setFixedHeight(64)
        self.description.setToolTip("A short summary for search engines.")
        self.description.focusOutEvent = self._description_left(self.description.focusOutEvent)
        self.layout_choice = QComboBox()
        self.layout_choice.addItem("Standard, with header and footer", "default")
        self.layout_choice.addItem("Landing page, no header or footer", "landing")
        self.layout_choice.activated.connect(lambda _i: self._details("layout"))
        for text, widget in (("Title", self.title), ("Address", self.slug), ("Description", self.description), ("Layout", self.layout_choice)):
            column.addWidget(label(text, "field"))
            column.addWidget(widget)
        self.details = [self.title, self.slug, self.description, self.layout_choice]

        column.addWidget(label("POST TEMPLATES", "section"))
        column.addWidget(label("Used for posts, which come from the website itself. Until you design one, a simple layout in your site's style is used.", "faint", wrap=True))
        self.role_rows: dict[str, tuple[QLabel, QPushButton, QPushButton]] = {}
        for role, name, tip in ROLES:
            row = QHBoxLayout()
            row.setSpacing(4)
            caption = label(name)
            caption.setToolTip(tip)
            design = QPushButton("Design")
            design.clicked.connect(lambda _=False, r=role: session.open_role_page(r))
            reset = QPushButton("Use default")
            reset.clicked.connect(lambda _=False, r=role: self._reset_role(r))
            row.addWidget(caption, 1)
            row.addWidget(design)
            row.addWidget(reset)
            column.addLayout(row)
            self.role_rows[role] = (caption, design, reset)

        column.addWidget(label("MENU", "section"))
        self.nav = QListWidget()
        self.nav.setFixedHeight(150)
        self.nav.currentItemChanged.connect(lambda *_: self._show_nav())
        column.addWidget(self.nav)
        nav_tools = QHBoxLayout()
        nav_tools.setSpacing(4)
        self.nav_up = self._tool("arrow-up", "Move this link earlier", lambda: self._move_nav(-1))
        self.nav_down = self._tool("arrow-down", "Move this link later", lambda: self._move_nav(1))
        self.nav_remove = self._tool("trash-2", "Remove this link from the menu", self._remove_nav)
        self.nav_add = QPushButton("Add link")
        self.nav_add.clicked.connect(self._add_nav)
        for button in (self.nav_up, self.nav_down, self.nav_remove):
            nav_tools.addWidget(button)
        nav_tools.addStretch(1)
        nav_tools.addWidget(self.nav_add)
        column.addLayout(nav_tools)
        self.nav_label = QLineEdit(placeholderText="Label")
        self.nav_label.editingFinished.connect(self._nav_label_done)
        self.nav_target = LinkField()
        self.nav_target.edited.connect(self._nav_target_done)
        column.addWidget(label("Link label", "field"))
        column.addWidget(self.nav_label)
        column.addWidget(label("Goes to", "field"))
        column.addWidget(self.nav_target)
        column.addStretch(1)

        session.documentChanged.connect(self.refresh)
        session.pageChanged.connect(self.refresh)
        session.projectChanged.connect(self.refresh)
        self.refresh()

    def _tool(self, icon: str, tip: str, action) -> QToolButton:
        button = QToolButton()
        button.setIcon(make_icon(icon, self.pal, 15))
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.clicked.connect(lambda _=False: action())
        return button

    # Showing ----------------------------------------------------------------
    def refresh(self) -> None:
        doc = self.session.document
        self._filling = True
        try:
            self.empty.setVisible(doc is None)
            self.list.clear()
            if doc:
                for page in site_pages(doc):
                    text = f"{page['title']}   (homepage)" if page.get("home") else page["title"]
                    item = QListWidgetItem(make_icon("house" if page.get("home") else "file-text", self.pal, 16), text)
                    item.setData(Qt.ItemDataRole.UserRole, page["id"])
                    item.setToolTip(f"/{page['slug']}")
                    self.list.addItem(item)
                    if page["id"] == self.session.page_id:
                        item.setSelected(True)
                        self.list.setCurrentItem(item)
            self._show_details()
            self._show_roles()
            self._fill_nav()
        finally:
            self._filling = False
        self._show_nav()

    def _show_details(self) -> None:
        page = self.session.current_page
        editable = bool(page) and not self.session.read_only
        for widget in self.details + [self.add_btn, self.new_title, self.new_starter]:
            widget.setEnabled(editable)
        role = bool(page and page.get("role"))
        pages = site_pages(self.session.document) if self.session.document else []
        self.up_btn.setEnabled(editable and not role and pages[0] is not page)
        self.down_btn.setEnabled(editable and not role and pages[-1] is not page)
        self.duplicate_btn.setEnabled(editable and not role)
        self.home_btn.setEnabled(editable and not role and not (page or {}).get("home"))
        self.delete_btn.setEnabled(editable and not role and not (page or {}).get("home") and len(pages) > 1)
        self.delete_btn.setToolTip("Delete this page" if not (page or {}).get("home") else "The homepage cannot be deleted. Make another page the homepage first.")
        self.slug.setEnabled(editable and not role and not (page or {}).get("home"))
        self.layout_choice.setEnabled(editable and not role)
        if not page:
            return
        for field, value in ((self.title, page.get("title", "")), (self.slug, page.get("slug", ""))):
            if not field.hasFocus():
                field.setText(value)
        if not self.description.hasFocus():
            self.description.setPlainText(page.get("description", ""))
        self.layout_choice.setCurrentIndex(max(0, self.layout_choice.findData(page.get("layout", "default"))))

    def _show_roles(self) -> None:
        doc = self.session.document
        for role, name, _tip in ROLES:
            caption, design, reset = self.role_rows[role]
            custom = bool(doc) and any(p.get("role") == role for p in doc["pages"])
            caption.setText(f"{name}: yours" if custom else name)
            design.setEnabled(bool(doc) and not self.session.read_only)
            design.setText("Open" if custom else "Design")
            reset.setEnabled(custom and not self.session.read_only)

    def _fill_nav(self) -> None:
        doc = self.session.document
        current = self.nav.currentItem().data(Qt.ItemDataRole.UserRole) if self.nav.currentItem() else None
        self.nav.clear()
        if not doc:
            return
        self.nav_target.set_pages([(p["title"], p["id"]) for p in site_pages(doc)])
        for item in doc["navigation"].get("primary", []):
            page = find_page(doc, item["page"]) if item.get("page") else None
            where = page["title"] if page else item.get("url", "")
            row = QListWidgetItem(f"{item['label']}  ({where})" if where != item["label"] else item["label"])
            row.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.nav.addItem(row)
            if item["id"] == current:
                self.nav.setCurrentItem(row)
        if self.nav.count() and self.nav.currentItem() is None:
            self.nav.setCurrentRow(0)

    def _nav_item(self) -> dict | None:
        doc = self.session.document
        chosen = self.nav.currentItem()
        if not doc or chosen is None:
            return None
        wanted = chosen.data(Qt.ItemDataRole.UserRole)
        return next((i for i in doc["navigation"].get("primary", []) if i["id"] == wanted), None)

    def _show_nav(self) -> None:
        if self._filling:
            return
        item = self._nav_item()
        editable = not self.session.read_only and bool(self.session.document)
        self.nav_add.setEnabled(editable)
        for widget in (self.nav_up, self.nav_down, self.nav_remove, self.nav_label, self.nav_target):
            widget.setEnabled(editable and item is not None)
        if item is None:
            self.nav_label.setText("")
            return
        if not self.nav_label.hasFocus():
            self.nav_label.setText(item["label"])
        self.nav_target.set_value({"page": item["page"]} if item.get("page") else item.get("url", ""))

    # Acting -----------------------------------------------------------------
    def _add(self) -> None:
        title = self.new_title.text().strip()
        if not title:
            self.session.notify("Type a title for the new page first.")
            self.new_title.setFocus()
            return
        if self.session.add_page(title, self.new_starter.currentData()):
            self.new_title.clear()

    def _move(self, step: int) -> None:
        self.session.move_page(self.session.page_id, step)

    def _delete(self) -> None:
        page = self.session.current_page
        if not page:
            return
        links = sum(1 for item in self.session.document["navigation"].get("primary", []) if item.get("page") == page["id"])
        extra = f" {links} menu link will be removed." if links == 1 else f" {links} menu links will be removed." if links else ""
        text = f"Delete the page '{page['title']}' and everything on it?{extra} Links to it from other pages will go to the homepage. You can undo this."
        if self._confirm("Delete page", text):
            self.session.delete_page(page["id"])

    def _confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _reset_role(self, role: str) -> None:
        if self._confirm("Use the default", "Remove your design for this template and use the simple default again? You can undo this."):
            self.session.remove_role_page(role)

    def _details(self, which: str) -> None:
        page = self.session.current_page
        if self._filling or not page or self.session.read_only:
            return
        if which == "title" and self.title.text().strip() != page["title"]:
            self.session.rename_page(page["id"], self.title.text())
        elif which == "slug" and slugify(self.slug.text()) != page["slug"]:
            # Typed as words, kept as an address.
            self.session.set_page_slug(page["id"], slugify(self.slug.text()))
        elif which == "layout" and self.layout_choice.currentData() != page.get("layout", "default"):
            self.session.set_page_details(page["id"], layout=self.layout_choice.currentData())
        self._filling = True
        try:
            self._show_details()
        finally:
            self._filling = False

    def _description_left(self, original):
        def handler(event) -> None:
            original(event)
            page = self.session.current_page
            if page and not self.session.read_only and self.description.toPlainText() != page.get("description", ""):
                self.session.set_page_details(page["id"], description=self.description.toPlainText())
        return handler

    def _select_nav(self, item_id: str) -> None:
        for row in range(self.nav.count()):
            if self.nav.item(row).data(Qt.ItemDataRole.UserRole) == item_id:
                self.nav.setCurrentRow(row)

    def _add_nav(self) -> None:
        page = self.session.current_page
        target = {"page": page["id"]} if page and not page.get("role") else "#"
        item_id = self.session.add_nav_item(page["title"] if page and not page.get("role") else "New link", target)
        if item_id:
            self._select_nav(item_id)
            self.nav_label.setFocus()

    def _move_nav(self, step: int) -> None:
        item = self._nav_item()
        if item:
            self.session.move_nav_item(item["id"], step)

    def _remove_nav(self) -> None:
        item = self._nav_item()
        if item:
            self.session.remove_nav_item(item["id"])

    def _nav_label_done(self) -> None:
        item = self._nav_item()
        if item and not self._filling and self.nav_label.text().strip() != item["label"]:
            self.session.update_nav_item(item["id"], label=self.nav_label.text())
            self._show_nav()

    def _nav_target_done(self, value) -> None:
        item = self._nav_item()
        if item and not self._filling:
            self.session.update_nav_item(item["id"], target=value)
            self._show_nav()
