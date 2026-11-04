"""Project folders on disk.

    MyWebsite/
        project.json          the universal document (written atomically)
        .autosave.json        newer unsaved work, if any; never replaces project.json by itself
        assets/               the user's media
        exports/              finished theme packages
        previews/             generated pages (safe to delete)

All pages live in project.json rather than one file per page, so that a save is
one atomic write and a crash can never leave pages from different moments.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .document import Document, instantiate_template, now_iso, validate_document
from .errors import ProjectError
from .history import History
from .media import empty_trash, sync_files

PROJECT_FILE = "project.json"
AUTOSAVE_FILE = ".autosave.json"
SUBFOLDERS = ("assets", "exports", "previews")


def safe_folder_name(name: str) -> str:
    """A folder name that is valid on Windows, macOS, Linux and NTFS drives."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    return cleaned[:80]


def _write_json_atomic(path: Path, doc: Document) -> None:
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


class Project:
    """An open project: its folder, its document and whether it has unsaved work."""

    def __init__(self, folder: Path, doc: Document) -> None:
        self.folder = Path(folder)
        self.history = History(doc)
        self._saved_state = json.dumps(doc, sort_keys=True)
        self.recovered = False

    @property
    def document(self) -> Document:
        return self.history.document

    @property
    def name(self) -> str:
        return self.document["meta"]["name"]

    @property
    def file(self) -> Path:
        return self.folder / PROJECT_FILE

    @property
    def autosave_file(self) -> Path:
        return self.folder / AUTOSAVE_FILE

    @property
    def dirty(self) -> bool:
        return json.dumps(self.document, sort_keys=True) != self._saved_state

    @classmethod
    def create(cls, parent: Path, name: str, template_doc: Document, author: str = "") -> "Project":
        name = name.strip()
        folder_name = safe_folder_name(name)
        if not folder_name:
            raise ProjectError("Please give the project a name that contains letters or numbers.")
        folder = Path(parent) / folder_name
        if folder.exists() and any(folder.iterdir()):
            raise ProjectError(f"A folder named '{folder_name}' already exists in {parent}. Choose another name.")
        doc = instantiate_template(template_doc, name=name, author=author)
        issues = validate_document(doc)
        if issues:
            raise ProjectError("The chosen template is damaged, so the project was not created.", issues)
        try:
            for sub in SUBFOLDERS:
                (folder / sub).mkdir(parents=True, exist_ok=True)
            _write_json_atomic(folder / PROJECT_FILE, doc)
        except OSError as exc:
            raise ProjectError(f"Could not create the project in {folder}: {exc}") from exc
        return cls(folder, doc)

    @classmethod
    def open(cls, path: Path) -> "Project":
        """Open a project folder, or the project.json inside one."""
        path = Path(path)
        folder = path.parent if path.is_file() else path
        file = folder / PROJECT_FILE
        if not file.is_file():
            raise ProjectError(f"{folder} is not a Mulusa Theme Studio project: it has no {PROJECT_FILE}.")
        doc = cls._read(file)
        for sub in SUBFOLDERS:
            try:
                (folder / sub).mkdir(exist_ok=True)
            except OSError:
                pass  # A read-only project can still be opened and viewed.
        project = cls(folder, doc)
        # An unsaved session may have shelved files that this saved document still needs.
        sync_files(folder, doc)
        if not project.has_recoverable_autosave():
            empty_trash(folder)  # No undo history survives a reopen, so nothing can ask for them.
        return project

    @staticmethod
    def _read(file: Path) -> Document:
        try:
            doc = json.loads(file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ProjectError(f"Could not read {file}: {exc}") from exc
        except ValueError as exc:
            raise ProjectError(f"{file.name} is damaged and is not valid JSON ({exc}).") from exc
        issues = validate_document(doc)
        if issues:
            raise ProjectError(f"{file.name} failed validation, so it was not opened.", issues)
        return doc

    def save(self) -> None:
        issues = validate_document(self.document)
        if issues:
            raise ProjectError("The project has problems and was not saved.", issues)
        self.document["meta"]["modified"] = now_iso()
        try:
            _write_json_atomic(self.file, self.document)
        except OSError as exc:
            raise ProjectError(f"Could not save to {self.file}: {exc}") from exc
        self._saved_state = json.dumps(self.document, sort_keys=True)
        self.recovered = False
        self.autosave_file.unlink(missing_ok=True)

    def autosave(self) -> bool:
        """Write unsaved work beside the project. Returns True if anything was written."""
        if not self.dirty:
            return False
        try:
            _write_json_atomic(self.autosave_file, self.document)
        except OSError as exc:
            raise ProjectError(f"Autosave failed: {exc}") from exc
        return True

    def has_recoverable_autosave(self) -> bool:
        """True if an autosave exists that is newer than the last save."""
        if not self.autosave_file.is_file():
            return False
        return self.autosave_file.stat().st_mtime >= self.file.stat().st_mtime

    def recover_autosave(self) -> None:
        """Load the autosave as unsaved work. project.json is untouched until the user saves."""
        doc = self._read(self.autosave_file)
        self.history = History(doc)
        self.recovered = True
        sync_files(self.folder, doc)

    def discard_autosave(self) -> None:
        self.autosave_file.unlink(missing_ok=True)
