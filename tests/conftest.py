from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
os.environ.setdefault("QT_LOGGING_RULES", "*=false")

import json
from pathlib import Path

import pytest

from mulusa_theme_studio.core.templates import TemplateLibrary

TEMPLATE_ID = "corporate/corporate-classic"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Tests never touch the real preferences."""
    monkeypatch.setenv("MTS_CONFIG_DIR", str(tmp_path / "config"))


@pytest.fixture(scope="session")
def library() -> TemplateLibrary:
    return TemplateLibrary()


@pytest.fixture
def template_doc(library) -> dict:
    return library.load(TEMPLATE_ID)


@pytest.fixture
def no_dialogs(monkeypatch):
    """Any unexpected modal dialog fails the test instead of hanging it."""
    from PySide6.QtWidgets import QMessageBox

    def fail(*args, **kwargs):
        raise AssertionError(f"Unexpected dialog: {args[1:]}")

    monkeypatch.setattr(QMessageBox, "exec", fail)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(fail))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(fail))
