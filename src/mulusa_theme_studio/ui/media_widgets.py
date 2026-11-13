"""Shared media pieces: the thumbnail grid, the image picker and the crop dialog."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from ..core import media
from .fields import NoWheelCombo
from .session import Session
from .theme import Palette, make_icon
from .widgets import label

FILE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif)"
ID_ROLE = Qt.ItemDataRole.UserRole
ASPECTS = (("Free", None), ("1:1", 1.0), ("4:3", 4 / 3), ("3:2", 1.5), ("16:9", 16 / 9), ("3:4", .75), ("4:5", .8))
HANDLE = 10


def choose_files(parent: QWidget) -> list[str]:
    files, _ = QFileDialog.getOpenFileNames(parent, "Choose images", str(Path.home()), FILE_FILTER)
    return files


class AssetGrid(QListWidget):
    """Thumbnails of the project's images. Reads the session's document and changes nothing."""

    def __init__(self, session: Session, pal: Palette, icon: int = 84) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(icon, icon))
        self.setGridSize(QSize(icon + 18, icon + 34))
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.filter_text = ""

    def assets(self) -> list[dict]:
        doc = self.session.document
        return list(doc["media"].get("assets", [])) if doc else []

    def rebuild(self) -> None:
        current = self.current_id()
        self.blockSignals(True)
        self.clear()
        needle = self.filter_text.strip().lower()
        project = self.session.project
        for asset in self.assets():
            haystack = f"{asset.get('name', '')} {asset.get('file', '')}".lower()
            if needle and needle not in haystack:
                continue
            item = QListWidgetItem(str(asset.get("name", "")))
            item.setData(ID_ROLE, asset["id"])
            item.setToolTip(f"{asset.get('name')}\n{asset.get('width')} x {asset.get('height')} px, {asset.get('format')}")
            thumb = media.thumbnail(project.folder, asset) if project else None
            item.setIcon(QIcon(str(thumb)) if thumb else make_icon("image", self.pal, 40))
            self.addItem(item)
            if asset["id"] == current:
                self.setCurrentItem(item)
        self.blockSignals(False)

    def current_id(self) -> str:
        item = self.currentItem()
        return str(item.data(ID_ROLE)) if item else ""

    def select_id(self, asset_id: str) -> None:
        for index in range(self.count()):
            if self.item(index).data(ID_ROLE) == asset_id:
                self.setCurrentRow(index)
                return


class MediaPickerDialog(QDialog):
    """Choose an existing project image, or upload a new one. The choice is applied by whoever asked."""

    def __init__(self, session: Session, pal: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Choose an image")
        self.resize(640, 480)
        column = QVBoxLayout(self)
        row = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Search by file name")
        self.search.setClearButtonEnabled(True)
        self.upload = QPushButton(make_icon("upload", pal, 15), "Upload images")
        row.addWidget(self.search, 1)
        row.addWidget(self.upload)
        column.addLayout(row)
        self.grid = AssetGrid(session, pal, 110)
        column.addWidget(self.grid, 1)
        self.empty = label("No images in this project yet. Upload one to use it here and anywhere else on the site.", "muted", wrap=True)
        column.addWidget(self.empty)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use = self.buttons.addButton("Use this image", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        column.addWidget(self.buttons)
        self.search.textChanged.connect(self._filter)
        self.upload.clicked.connect(self._upload)
        self.grid.currentItemChanged.connect(lambda *_: self._state())
        self.grid.itemDoubleClicked.connect(lambda *_: self.accept())
        self._refresh()

    def _filter(self, text: str) -> None:
        self.grid.filter_text = text
        self._refresh()

    def _refresh(self) -> None:
        self.grid.rebuild()
        self._state()

    def _state(self) -> None:
        self.use.setEnabled(bool(self.grid.current_id()))
        self.empty.setVisible(not self.grid.assets())

    def add_files(self, paths: list[str]) -> None:
        added = self.session.upload_media(paths)
        self._refresh()
        if added:
            self.grid.select_id(added[-1]["id"])

    def _upload(self) -> None:
        files = choose_files(self)
        if files:
            self.add_files(files)

    @property
    def asset_id(self) -> str:
        return self.grid.current_id()


class CropView(QWidget):
    """Shows an image with a crop rectangle that can be moved and resized. Works in image pixels."""

    changed = Signal()

    def __init__(self, path: Path, width: int, height: int) -> None:
        super().__init__()
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        self.pixmap = QPixmap.fromImage(reader.read())
        self.image_w, self.image_h = width, height
        self.box = QRect(0, 0, width, height)
        self.aspect: float | None = None
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self._drag = ""
        self._start = QPoint()
        self._origin = QRect()

    def _scale(self) -> tuple[float, QRectF]:
        scale = min(self.width() / self.image_w, self.height() / self.image_h)
        w, h = self.image_w * scale, self.image_h * scale
        return scale, QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _on_screen(self) -> QRectF:
        scale, area = self._scale()
        return QRectF(area.x() + self.box.x() * scale, area.y() + self.box.y() * scale, self.box.width() * scale, self.box.height() * scale)

    def set_aspect(self, aspect: float | None) -> None:
        self.aspect = aspect
        if aspect:
            w, h = self.image_w, self.image_h
            if w / h > aspect:
                new_w, new_h = round(h * aspect), h
            else:
                new_w, new_h = w, round(w / aspect)
            self.box = QRect((w - new_w) // 2, (h - new_h) // 2, new_w, new_h)
        self.update()
        self.changed.emit()

    def set_box(self, left: int, top: int, right: int, bottom: int) -> None:
        self.box = QRect(QPoint(left, top), QPoint(right - 1, bottom - 1))
        self._clamp()

    def crop_box(self) -> tuple[int, int, int, int]:
        return self.box.left(), self.box.top(), self.box.left() + self.box.width(), self.box.top() + self.box.height()

    def _clamp(self) -> None:
        box = self.box.normalized()
        box.setWidth(max(4, min(box.width(), self.image_w)))
        box.setHeight(max(4, min(box.height(), self.image_h)))
        box.moveLeft(max(0, min(box.left(), self.image_w - box.width())))
        box.moveTop(max(0, min(box.top(), self.image_h - box.height())))
        self.box = box
        self.update()
        self.changed.emit()

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        _scale, area = self._scale()
        painter.drawPixmap(area.toRect(), self.pixmap)
        shown = self._on_screen()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 130))
        for rect in (
            QRectF(area.left(), area.top(), area.width(), shown.top() - area.top()),
            QRectF(area.left(), shown.bottom(), area.width(), area.bottom() - shown.bottom()),
            QRectF(area.left(), shown.top(), shown.left() - area.left(), shown.height()),
            QRectF(shown.right(), shown.top(), area.right() - shown.right(), shown.height()),
        ):
            painter.drawRect(rect)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#E8B04B"), 2))
        painter.drawRect(shown)
        painter.setBrush(QColor("#E8B04B"))
        for corner in (shown.topLeft(), shown.topRight(), shown.bottomLeft(), shown.bottomRight()):
            painter.drawRect(QRectF(corner.x() - HANDLE / 2, corner.y() - HANDLE / 2, HANDLE, HANDLE))
        painter.end()

    def _hit(self, point: QPoint) -> str:
        shown = self._on_screen()
        for name, corner in (("tl", shown.topLeft()), ("tr", shown.topRight()), ("bl", shown.bottomLeft()), ("br", shown.bottomRight())):
            if abs(point.x() - corner.x()) <= HANDLE and abs(point.y() - corner.y()) <= HANDLE:
                return name
        return "move" if shown.contains(point) else ""

    def mousePressEvent(self, event):  # noqa: N802
        self._drag = self._hit(event.position().toPoint())
        self._start = event.position().toPoint()
        self._origin = QRect(self.box)

    def mouseMoveEvent(self, event):  # noqa: N802
        point = event.position().toPoint()
        if not self._drag:
            hit = self._hit(point)
            cursors = {"tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor, "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor, "move": Qt.CursorShape.SizeAllCursor}
            self.setCursor(cursors.get(hit, Qt.CursorShape.ArrowCursor))
            return
        scale, _area = self._scale()
        dx, dy = round((point.x() - self._start.x()) / scale), round((point.y() - self._start.y()) / scale)
        box = QRect(self._origin)
        if self._drag == "move":
            box.translate(dx, dy)
        else:
            if "l" in self._drag:
                box.setLeft(min(box.left() + dx, box.right() - 3))
            if "r" in self._drag:
                box.setRight(max(box.right() + dx, box.left() + 3))
            if "t" in self._drag:
                box.setTop(min(box.top() + dy, box.bottom() - 3))
            if "b" in self._drag:
                box.setBottom(max(box.bottom() + dy, box.top() + 3))
            if self.aspect:
                height = max(4, round(box.width() / self.aspect))
                if "t" in self._drag:
                    box.setTop(box.bottom() - height + 1)
                else:
                    box.setHeight(height)
            box.setLeft(max(0, box.left()))
            box.setTop(max(0, box.top()))
            box.setRight(min(self.image_w - 1, box.right()))
            box.setBottom(min(self.image_h - 1, box.bottom()))
        self.box = box
        self._clamp()

    def mouseReleaseEvent(self, _event):  # noqa: N802
        self._drag = ""


class CropDialog(QDialog):
    """Crop into a new image. The original file stays in the project, unchanged."""

    def __init__(self, path: Path, asset: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Crop {asset.get('name', 'image')}")
        self.resize(720, 560)
        column = QVBoxLayout(self)
        self.view = CropView(path, int(asset.get("width", 1)), int(asset.get("height", 1)))
        column.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addWidget(label("Shape"))
        self.aspect = NoWheelCombo()
        for text, value in ASPECTS:
            self.aspect.addItem(text, value)
        self.aspect.activated.connect(lambda _i: self.view.set_aspect(self.aspect.currentData()))
        row.addWidget(self.aspect)
        self.size = label("", "faint")
        row.addWidget(self.size, 1)
        column.addLayout(row)
        column.addWidget(label("This makes a new image. The original stays in your media library.", "faint", wrap=True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton("Crop", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.view.changed.connect(self._show_size)
        self._show_size()

    def _show_size(self) -> None:
        left, top, right, bottom = self.view.crop_box()
        self.size.setText(f"{right - left} x {bottom - top} px")
