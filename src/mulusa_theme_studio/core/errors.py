"""Errors the interface can show to a person as they are."""
from __future__ import annotations


class StudioError(Exception):
    """Base class: the message is written for the user, not the developer."""


class ProjectError(StudioError):
    """A project could not be created, opened or saved."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class TemplateError(StudioError):
    """A template in the library is missing or damaged."""
