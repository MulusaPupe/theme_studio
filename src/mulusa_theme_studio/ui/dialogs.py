"""New project and settings dialogs."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..core.project import safe_folder_name
from ..core.settings import Settings
from ..core.templates import TemplateLibrary
from .widgets import label


class NewProjectDialog(QDialog):
    def __init__(self, library: TemplateLibrary, settings: Settings, template_id: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.library = library
        self.setWindowTitle("New project")
        self.resize(1020, 720)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(12)
        outer.addWidget(label("Start a new website", "title"))

        form = QFormLayout()
        self.name = QLineEdit(placeholderText="My Website")
        self.name.textChanged.connect(self._validate)
        form.addRow("Project name", self.name)
        location_row = QHBoxLayout()
        self.location = QLineEdit(str(settings.projects_path))
        self.location.textChanged.connect(self._validate)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        location_row.addWidget(self.location, 1)
        location_row.addWidget(browse)
        form.addRow("Save in", location_row)
        outer.addLayout(form)

        filters = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItem("All categories", None)
        for category in library.categories:
            self.category.addItem(category.name, category.id)
        self.category.currentIndexChanged.connect(self._fill)
        filters.addWidget(label("Template", "section"))
        filters.addStretch(1)
        filters.addWidget(self.category)
        outer.addLayout(filters)

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setIconSize(QSize(224, 168))
        self.grid.setGridSize(QSize(240, 214))
        self.grid.setSpacing(6)
        self.grid.itemSelectionChanged.connect(self._validate)
        outer.addWidget(self.grid, 1)

        self.message = label("", "muted", wrap=True)
        outer.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.create = buttons.addButton("Create project", QDialogButtonBox.ButtonRole.AcceptRole)
        self.create.setProperty("primary", True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._wanted = template_id
        self._fill()
        self._validate()
        self.name.setFocus()

    def _fill(self) -> None:
        current = self.template_id or self._wanted
        self.grid.clear()
        for info in self.library.search("", self.category.currentData()):
            item = QListWidgetItem(info.name)
            pixmap = QPixmap(str(info.thumbnail))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            item.setToolTip(info.description)
            item.setData(Qt.ItemDataRole.UserRole, info.id)
            self.grid.addItem(item)
            if info.id == current:
                item.setSelected(True)
                self.grid.scrollToItem(item)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save projects in", self.location.text())
        if folder:
            self.location.setText(folder)

    @property
    def template_id(self) -> str:
        items = self.grid.selectedItems() if hasattr(self, "grid") else []
        return items[0].data(Qt.ItemDataRole.UserRole) if items else ""

    @property
    def project_name(self) -> str:
        return self.name.text().strip()

    @property
    def parent_folder(self) -> Path:
        return Path(self.location.text().strip()).expanduser()

    def _validate(self) -> None:
        folder = safe_folder_name(self.project_name)
        problem = ""
        if not self.project_name:
            problem = "Enter a project name."
        elif not folder:
            problem = "The name needs at least one letter or number."
        elif not self.location.text().strip():
            problem = "Choose where to save the project."
        elif (self.parent_folder / folder).exists() and any((self.parent_folder / folder).iterdir()):
            problem = f"A folder named '{folder}' already exists there."
        elif not self.template_id:
            problem = "Choose a template."
        self.message.setText(problem or f"The project will be created in {self.parent_folder / folder}")
        self.create.setEnabled(not problem)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(12)
        outer.addWidget(label("Settings", "title"))
        form = QFormLayout()
        self.appearance = QComboBox()
        self.appearance.addItem("Dark", "dark")
        self.appearance.addItem("Light", "light")
        self.appearance.setCurrentIndex(0 if settings.appearance == "dark" else 1)
        form.addRow("Appearance", self.appearance)
        self.author = QLineEdit(settings.author)
        form.addRow("Default author", self.author)
        row = QHBoxLayout()
        self.folder = QLineEdit(str(settings.projects_path))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form.addRow("Projects folder", row)
        self.autosave = QCheckBox("Autosave unsaved work")
        self.autosave.setChecked(settings.autosave_enabled)
        form.addRow("", self.autosave)
        self.seconds = QSpinBox()
        self.seconds.setRange(15, 900)
        self.seconds.setSuffix(" seconds")
        self.seconds.setValue(settings.autosave_seconds)
        form.addRow("Autosave every", self.seconds)
        outer.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Projects folder", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def apply(self) -> None:
        self.settings.appearance = self.appearance.currentData()
        self.settings.author = self.author.text().strip()
        self.settings.projects_dir = self.folder.text().strip()
        self.settings.autosave_enabled = self.autosave.isChecked()
        self.settings.autosave_seconds = self.seconds.value()
