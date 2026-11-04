"""The template library.

Each template is a self-contained folder, so adding one needs no code change::

    templates/categories.json             order and names of categories
    templates/<category>/<slug>/template.json
    templates/<category>/<slug>/thumbnail.png
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .document import Document, validate_document
from .errors import TemplateError

BUILTIN_ROOT = Path(__file__).resolve().parents[1] / "templates"


@dataclass(frozen=True)
class TemplateInfo:
    id: str
    name: str
    category: str
    description: str
    folder: Path

    @property
    def thumbnail(self) -> Path:
        return self.folder / "thumbnail.png"

    @property
    def file(self) -> Path:
        return self.folder / "template.json"


@dataclass(frozen=True)
class Category:
    id: str
    name: str


class TemplateLibrary:
    def __init__(self, root: Path = BUILTIN_ROOT) -> None:
        self.root = Path(root)
        self.categories: list[Category] = []
        self.templates: list[TemplateInfo] = []
        self.problems: list[str] = []
        self.reload()

    def reload(self) -> None:
        self.categories, self.templates, self.problems = [], [], []
        index = self.root / "categories.json"
        try:
            names = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.problems.append(f"Could not read {index}: {exc}")
            return
        for item in names:
            self.categories.append(Category(item["id"], item["name"]))
            folder = self.root / item["id"]
            if not folder.is_dir():
                self.problems.append(f"Category folder '{item['id']}' is missing.")
                continue
            for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
                # A damaged template is reported and skipped, never fatal to the library.
                try:
                    meta = json.loads((sub / "template.json").read_text(encoding="utf-8"))["meta"]
                    self.templates.append(
                        TemplateInfo(meta["id"], meta["template_name"], item["id"], meta.get("description", ""), sub)
                    )
                except (OSError, ValueError, KeyError) as exc:
                    self.problems.append(f"Template '{sub.name}' was skipped: {exc}")

    def in_category(self, category_id: str) -> list[TemplateInfo]:
        return [t for t in self.templates if t.category == category_id]

    def get(self, template_id: str) -> TemplateInfo:
        for template in self.templates:
            if template.id == template_id:
                return template
        raise TemplateError(f"Template '{template_id}' is not in the library.")

    def search(self, text: str, category_id: str | None = None) -> list[TemplateInfo]:
        needle = text.strip().lower()
        return [
            t for t in self.templates
            if (category_id is None or t.category == category_id)
            and (not needle or needle in f"{t.name} {t.description} {t.category}".lower())
        ]

    def load(self, template_id: str) -> Document:
        info = self.get(template_id)
        try:
            doc = json.loads(info.file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TemplateError(f"Template '{info.name}' could not be read: {exc}") from exc
        issues = validate_document(doc)
        if issues:
            raise TemplateError(f"Template '{info.name}' is damaged: {issues[0]}")
        return doc
