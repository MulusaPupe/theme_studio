"""Application start-up."""
from __future__ import annotations

import logging
import os
import sys
import traceback

from . import APP_NAME, ORG_NAME, __version__

log = logging.getLogger("mulusa_theme_studio")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Sites are local files, and one page's stylesheet must be able to load its fonts.
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-logging" not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{flags} --disable-logging".strip()

    from PySide6.QtWebEngineCore import QWebEngineProfile  # noqa: F401  (must load before QApplication)
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .core.settings import Settings
    from .core.templates import TemplateLibrary
    from .ui.main_window import MainWindow
    from .ui.session import Session
    from .ui.theme import load_fonts

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    load_fonts()

    def on_exception(kind, value, tb) -> None:
        # An unexpected fault is reported, logged and never hidden.
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Unhandled error:\n%s", text)
        box = QMessageBox(QMessageBox.Icon.Critical, APP_NAME, f"Something went wrong: {value}\n\nYour last saved work is safe.")
        box.setDetailedText(text)
        box.exec()

    sys.excepthook = on_exception
    window = MainWindow(Session(Settings.load(), TemplateLibrary()))
    window.show()
    return app.exec()
