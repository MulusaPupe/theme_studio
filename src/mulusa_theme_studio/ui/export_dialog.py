"""Export: a WordPress block theme or a static website. Details, the check, the files and what to do next."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..exporters import available
from ..exporters.static import StaticExporter, StaticExportFailed, StaticOptions
from ..exporters.wordpress import ERROR, ExportFailed, ExportOptions, WordPressExporter
from .session import Session
from .widgets import label


class ExportDialog(QDialog):
    def __init__(self, session: Session, screenshot: bytes | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.screenshot = screenshot
        kinds = available()
        self.wordpress = next(item for item in kinds if item is WordPressExporter)()
        self.static = next(item for item in kinds if item is StaticExporter)()
        self.exporter = self.wordpress
        self.result = None
        self.setWindowTitle("Export")
        self.resize(720, 680)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)
        self.heading = label("Export a WordPress block theme", "title")
        outer.addWidget(self.heading)
        self.kind = QComboBox()
        self.kind.addItem("WordPress block theme", "wordpress")
        self.kind.addItem("Static website (HTML files for any web host)", "static")
        kind_row = QFormLayout()
        kind_row.addRow("Export as", self.kind)
        outer.addLayout(kind_row)
        outer.addWidget(label("Your design stays in this project. The export is a copy of it that WordPress can run. You do not need to know any code.", "muted", wrap=True))
        meta = session.document["meta"]
        form = QFormLayout()
        self.name = QLineEdit(str(meta.get("name", "")) or session.project.name)
        self.description = QPlainTextEdit(str(meta.get("description", "")))
        self.description.setFixedHeight(64)
        self.author = QLineEdit(str(meta.get("author", "")))
        self.version = QLineEdit("1.0.0")
        self.folder = QLineEdit(str(session.project.folder / "exports"))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        where = QHBoxLayout()
        where.addWidget(self.folder, 1)
        where.addWidget(browse)
        self.form_action = QLineEdit()
        self.form_action.setPlaceholderText("https://formspree.io/f/... (optional)")
        self.form_action.setToolTip("Where contact forms send messages. A form service gives you this address.")
        self.form_email = QLineEdit()
        self.form_email.setPlaceholderText("Used when there is no form handler")
        self.form_email.setToolTip("With no form handler, a form opens the visitor's email app addressed to this.")
        form.addRow("Theme name", self.name)
        form.addRow("Description", self.description)
        form.addRow("Author", self.author)
        form.addRow("Version", self.version)
        form.addRow("Form handler", self.form_action)
        form.addRow("Form email", self.form_email)
        form.addRow("Save in", where)
        outer.addLayout(form)
        self.form = form
        self.include_plugin = QCheckBox("Also create the content plugin")
        self.include_plugin.setChecked(True)
        self.include_plugin.setToolTip("A theme alone cannot create pages in WordPress. This small plugin creates them when you ask it to, and runs contact forms.")
        outer.addWidget(self.include_plugin)
        self.plugin_note = label("A theme decides how a site looks, and cannot create pages by itself. The content plugin adds your pages, images and homepage to WordPress when you press its button. Posts are always written in WordPress.", "faint", wrap=True)
        outer.addWidget(self.plugin_note)
        self.static_note = label("A static site is plain HTML and CSS: fast, and it works on any web host. It has no posts, so post lists are left out, and contact forms need a form handler or an email address.", "faint", wrap=True)
        outer.addWidget(self.static_note)

        self.summary = label("Not checked yet.", "section", wrap=True)
        outer.addWidget(self.summary)
        self.issues = QListWidget()
        self.issues.setWordWrap(True)
        outer.addWidget(self.issues, 1)
        row = QHBoxLayout()
        self.check_btn = QPushButton("Check the theme")
        self.check_btn.clicked.connect(self.run_check)
        self.export_btn = QPushButton("Export ZIP")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.run_export)
        self.open_btn = QPushButton("Open the export folder")
        self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Available after a successful export.")
        self.open_btn.clicked.connect(self.open_folder)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        for button in (self.check_btn, self.export_btn, self.open_btn):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(close)
        outer.addLayout(row)
        self.next_steps = label("", "muted", wrap=True)
        self.next_steps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.next_steps.hide()
        outer.addWidget(self.next_steps)
        self._kind_changed()

    def is_static(self) -> bool:
        return self.kind.currentData() == "static"

    def _kind_changed(self) -> None:
        static = self.is_static()
        self.exporter = self.static if static else self.wordpress
        self.heading.setText("Export a static website" if static else "Export a WordPress block theme")
        for widget in (self.description, self.author, self.version):
            self.form.setRowVisible(widget, not static)
        for widget in (self.form_action, self.form_email):
            self.form.setRowVisible(widget, static)
        self.form.labelForField(self.name).setText("Site name" if static else "Theme name")
        self.include_plugin.setVisible(not static)
        self.plugin_note.setVisible(not static)
        self.static_note.setVisible(static)
        self.issues.clear()
        self.summary.setText("Not checked yet.")
        self.next_steps.hide()
        self.open_btn.setEnabled(False)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Save the export in", self.folder.text())
        if chosen:
            self.folder.setText(chosen)

    def options(self) -> ExportOptions | StaticOptions:
        if self.is_static():
            return StaticOptions(self.name.text(), self.form_action.text(), self.form_email.text())
        return ExportOptions(self.name.text(), self.description.toPlainText(), self.author.text(), self.version.text(), self.include_plugin.isChecked(), self.screenshot)

    def _show(self, issues: list) -> tuple[int, int]:
        self.issues.clear()
        errors = [i for i in issues if i.severity == ERROR]
        warnings = [i for i in issues if i.severity != ERROR]
        for severity, group in (("Must fix", errors), ("Worth checking", warnings)):
            for issue in group:
                text = f"{severity}. {issue.where + ': ' if issue.where else ''}{issue.message}"
                if issue.fix:
                    text += f" {issue.fix}"
                self.issues.addItem(QListWidgetItem(text))
        return len(errors), len(warnings)

    def run_check(self) -> None:
        self.next_steps.hide()
        errors, warnings = self._show(self.exporter.check(self.session.document, self.session.project.folder, self.options()))
        if errors:
            self.summary.setText(f"{errors} problem(s) must be fixed before exporting, and {warnings} to look at.")
        elif warnings:
            self.summary.setText(f"The theme can be exported. {warnings} thing(s) to look at first.")
        else:
            self.summary.setText("No problems found.")

    def run_export(self) -> None:
        self.result = None
        self.open_btn.setEnabled(False)
        self.next_steps.hide()
        try:
            result = self.exporter.export(self.session.document, self.session.project.folder, Path(self.folder.text()), self.options())
        except (ExportFailed, StaticExportFailed) as failed:
            errors, warnings = self._show(failed.issues)
            self.summary.setText(f"Nothing was exported. {errors} problem(s) must be fixed first.")
            return
        except OSError as exc:
            self.summary.setText(f"Nothing was exported, because the file could not be written: {exc}")
            return
        self.result = result
        self._show(result.issues)
        self.open_btn.setEnabled(True)
        self.open_btn.setToolTip("")
        if self.is_static():
            self.summary.setText(f"Exported {result.output.name}, and the same site unpacked in {result.folder.name}.")
            steps = ["1. Open index.html in the unpacked folder to check the site in a browser.",
                     f"2. Upload the contents of {result.folder.name} (or unpack {result.output.name}) to your web host's public folder.", "Pages:"]
            steps += [f"     {page['title']} is {page['file']}" for page in result.pages]
            self.next_steps.setText("\n".join(steps))
            self.next_steps.show()
            return
        self.summary.setText(f"Exported {result.output.name}" + (f" and {result.plugin.name}." if result.plugin else "."))
        steps = [f"1. In WordPress: Appearance, Themes, Add New, Upload Theme. Choose {result.output.name}, install and activate it."]
        if result.plugin:
            steps += [f"2. Plugins, Add New, Upload Plugin. Choose {result.plugin.name}, install and activate it.", "3. Tools, Import site content, Create the pages. Pages:"]
            steps += [f"     {page['design']} becomes /{'' if page['home'] else page['slug'] + '/'}" for page in result.pages]
        else:
            steps.append("2. Create your pages in WordPress. Each page's design is offered as a starter layout when you add a new page.")
        self.next_steps.setText("\n".join(steps))
        self.next_steps.show()

    def open_folder(self) -> None:
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.output.parent)))
