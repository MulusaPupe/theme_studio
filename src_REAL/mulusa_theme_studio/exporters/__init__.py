"""Exporters translate the universal document into a platform's format.

The contract and registry exist from the start so the editor never depends on a
particular platform. No exporter is registered yet: the static exporter arrives
in Stage 05 and the WordPress block theme exporter in Stage 06.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..core.document import Document


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


def available() -> list[type[Exporter]]:
    return list(_REGISTRY.values())
