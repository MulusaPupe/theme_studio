"""The media library: the project's images, and everything that can be done to them."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...core import media
from ...core.document import media_refs
from ..media_widgets import AssetGrid, choose_files
from ..session import Session
from ..theme import Palette, make_icon
from ..widgets import label


class MediaPanel(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(label("Media library", "title"))
        self.summary = label("Open a project or preview a template to see its images.", "muted", wrap=True)
        layout.addWidget(self.summary)
        self.upload_btn = QPushButton(make_icon("upload", pal, 15), "Upload images")
        self.upload_btn.setToolTip("Add PNG, JPG, WebP or GIF files. Your originals are copied, never changed.")
        self.upload_btn.clicked.connect(self._upload)
        layout.addWidget(self.upload_btn)
        self.search = QLineEdit(placeholderText="Search by file name")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        self.grid = AssetGrid(session, pal)
        self.grid.currentItemChanged.connect(lambda *_: self._show_details())
        self.grid.itemDoubleClicked.connect(lambda *_: self._use())
        layout.addWidget(self.grid, 1)
        self.empty = label("Nothing here yet. Upload images, then use them anywhere on the site.", "faint", wrap=True)
        layout.addWidget(self.empty)

        self.details = QWidget()
        column = QVBoxLayout(self.details)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.name = QLineEdit()
        self.name.setToolTip("Rename this image. Press Enter to apply.")
        self.name.editingFinished.connect(self._rename)
        self.info = label("", "faint", wrap=True)
        self.use_btn = QPushButton("Use on selected element")
        self.use_btn.clicked.connect(self._use)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.replace_btn = QPushButton("Replace everywhere")
        self.replace_btn.setToolTip("Choose a new file to take this image's place wherever it is used.")
        self.replace_btn.clicked.connect(self._replace)
        self.delete_btn = QPushButton(make_icon("trash-2", pal, 14), "Delete")
        self.delete_btn.clicked.connect(self._delete)
        row.addWidget(self.replace_btn, 1)
        row.addWidget(self.delete_btn)
        column.addWidget(self.name)
        column.addWidget(self.info)
        column.addWidget(self.use_btn)
        column.addLayout(row)
        layout.addWidget(self.details)

        session.documentChanged.connect(self.refresh)
        session.projectChanged.connect(self.refresh)
        session.templatePreviewChanged.connect(self.refresh)
        session.selectionChanged.connect(self._show_details)
        self.refresh()

    def _filter(self, text: str) -> None:
        self.grid.filter_text = text
        self.grid.rebuild()
        self._show_details()

    def refresh(self) -> None:
        doc = self.session.document
        editable = bool(doc) and not self.session.read_only
        self.upload_btn.setEnabled(editable)
        self.upload_btn.setToolTip("Add PNG, JPG, WebP or GIF files. Your originals are copied, never changed." if editable else "Available once a project is open.")
        self.grid.rebuild()
        if not doc:
            self.summary.setText("Open a project or preview a template to see its images.")
        else:
            refs = list(media_refs(doc))
            placeholders = sum(1 for r in refs if r.get("kind") == "placeholder")
            self.summary.setText(f"{len(doc['media'].get('assets', []))} uploaded images. {placeholders} placeholder images still to replace.")
        self.empty.setVisible(bool(doc) and not self.grid.assets() and editable)
        self._show_details()

    def _asset(self) -> dict | None:
        doc = self.session.document
        return media.find_asset(doc, self.grid.current_id()) if doc and self.grid.current_id() else None

    def _show_details(self) -> None:
        asset = self._asset()
        self.details.setVisible(asset is not None)
        if not asset:
            return
        doc = self.session.document
        used = media.usage_count(doc, asset["id"])
        if not self.name.hasFocus():
            self.name.setText(str(asset.get("name", "")))
        size_kb = int(asset.get("bytes", 0)) / 1024
        size = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
        where = f"Used in {used} place{'s' if used != 1 else ''}" if used else "Not used yet"
        missing = "" if self.session.project and media.asset_path(self.session.project.folder, asset).is_file() else "\nThe file is missing from the project folder."
        parent = media.find_asset(doc, asset.get("parent", ""))
        origin = f"\nCropped from {parent.get('name')}" if parent else ""
        self.info.setText(f"{asset.get('width')} x {asset.get('height')} px, {asset.get('format')}, {size}\n{where}{origin}{missing}")
        self.delete_btn.setEnabled(not used and not self.session.read_only)
        self.delete_btn.setToolTip(f"In use in {used} place{'s' if used != 1 else ''}. Replace it there first." if used else "Delete this image from the project. You can undo this.")
        self.replace_btn.setEnabled(not self.session.read_only)
        node = self.session.selected_node
        self.use_btn.setEnabled(bool(node) and node.get("type") in ("image", "section", "video", "gallery") and not self.session.read_only)
        self.use_btn.setToolTip("Select an image, section, video or gallery on the canvas first." if not self.use_btn.isEnabled() else "Put this image in the selected element only.")

    def add_files(self, paths: list[str]) -> None:
        added = self.session.upload_media(paths)
        if added:
            self.grid.rebuild()
            self.grid.select_id(added[-1]["id"])

    def _upload(self) -> None:
        files = choose_files(self)
        if files:
            self.add_files(files)

    def _rename(self) -> None:
        asset = self._asset()
        if asset and self.name.text().strip() != asset.get("name"):
            if not self.session.rename_asset(asset["id"], self.name.text()):
                self.name.setText(str(asset.get("name", "")))

    def _use(self) -> None:
        asset = self._asset()
        node = self.session.selected_node
        if not asset or not node:
            self.session.notify("Select an image, section, video or gallery on the canvas first.")
            return
        slot = {"image": "media", "section": "background", "video": "poster", "gallery": "item"}.get(node.get("type"))
        if slot is None:
            self.session.notify("That element cannot show an image.")
            return
        self.session.set_node_media(node["id"], asset["id"], slot)

    def _replace(self) -> None:
        asset = self._asset()
        files = choose_files(self) if asset else []
        if files:
            count = self.session.replace_asset_everywhere(asset["id"], files[0])
            self.session.notify(f"Replaced in {count} place{'s' if count != 1 else ''}.")

    def _delete(self) -> None:
        asset = self._asset()
        if not asset:
            return
        answer = QMessageBox.question(self, "Delete image", f"Delete {asset.get('name')} from this project?")
        if answer == QMessageBox.StandardButton.Yes:
            self.session.delete_asset(asset["id"])
