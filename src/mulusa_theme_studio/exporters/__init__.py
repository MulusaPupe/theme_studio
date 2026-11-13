"""Exporters translate the universal document into a platform's format.

The editor only knows this contract, so a new platform is a new package here,
listed in ``_BUILT_IN``. Options and richer results belong to each exporter.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
from dataclasses import dataclass, field
from pathlib import Path

from ..core.document import Document


ERROR, WARNING = "error", "warning"


@dataclass(frozen=True)
class Issue:
    """One finding from an exporter's check. Errors stop an export; warnings are shown."""
    severity: str
    message: str
    where: str = ""
    fix: str = ""

    def __str__(self) -> str:
        return f"{self.where}: {self.message}" if self.where else self.message


@dataclass
class ExportResult:
    output: Path
    warnings: list[str] = field(default_factory=list)


class Exporter(ABC):
    id: str = ""
    label: str = ""

    @abstractmethod
    def validate(self, doc: Document) -> list[str]:
        """Problems that would stop this platform's export from working."""

    @abstractmethod
    def export(self, doc: Document, project_folder: Path, destination: Path) -> ExportResult:
        """Write the package and check it before reporting success."""


_REGISTRY: dict[str, type[Exporter]] = {}


def register(exporter: type[Exporter]) -> type[Exporter]:
    _REGISTRY[exporter.id] = exporter
    return exporter


_BUILT_IN = ("wordpress", "static")


def available() -> list[type[Exporter]]:
    for name in _BUILT_IN:
        import_module(f"{__name__}.{name}")
    return list(_REGISTRY.values())
