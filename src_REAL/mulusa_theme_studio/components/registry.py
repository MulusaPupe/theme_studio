"""The component catalogue.

A component is a preset: a function that builds a complete tree of primitive nodes,
with fresh ids each time. There are no opaque blocks, so every part of an inserted
component stays independently selectable. Anything can add a component with
``register`` without the editor changing.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..core.document import Node
from ..core.errors import StudioError


@dataclass(frozen=True)
class ComponentDef:
    id: str
    label: str
    group: str
    icon: str
    description: str
    build: Callable[[], Node]

    @property
    def node_type(self) -> str:
        return self.build()["type"]


_REGISTRY: dict[str, ComponentDef] = {}
_GROUPS: list[str] = []
_loaded = False


def register(component: ComponentDef) -> ComponentDef:
    if component.id in _REGISTRY:
        raise ValueError(f"Component '{component.id}' is already registered.")
    _REGISTRY[component.id] = component
    if component.group not in _GROUPS:
        _GROUPS.append(component.group)
    return component


def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        _loaded = True
        from . import presets  # noqa: F401  (registers the built-in catalogue)


def catalogue() -> list[ComponentDef]:
    _ensure_loaded()
    return list(_REGISTRY.values())


def groups() -> list[str]:
    _ensure_loaded()
    return list(_GROUPS)


def get(component_id: str) -> ComponentDef:
    _ensure_loaded()
    try:
        return _REGISTRY[component_id]
    except KeyError:
        raise StudioError(f"There is no component called '{component_id}'.") from None
