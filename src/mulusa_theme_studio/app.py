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

    from PySide6.QtCore import QTimer

    from .ui.theme import load_fonts

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    load_fonts()
    splash = None
    if os.environ.get("MTS_NO_SPLASH") != "1" and app.platformName() not in ("offscreen", "minimal"):
        from .ui.splash import Splash
        splash = Splash()
        splash.show()
        splash.step(.12, "Loading fonts and settings…")

    from .core.settings import Settings
    from .core.templates import TemplateLibrary
    settings = Settings.load()
    if splash:
        splash.step(.3, "Loading templates…")
    library = TemplateLibrary()
    if splash:
        splash.step(.55, f"Loaded {len(library.templates)} templates. Starting the canvas engine…")
    from .ui.main_window import MainWindow
    from .ui.session import Session

    def on_exception(kind, value, tb) -> None:
        # An unexpected fault is reported, logged and never hidden.
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Unhandled error:\n%s", text)
        box = QMessageBox(QMessageBox.Icon.Critical, APP_NAME, f"Something went wrong: {value}\n\nYour last saved work is safe.")
        box.setDetailedText(text)
        box.exec()

    sys.excepthook = on_exception
    window = MainWindow(Session(settings, library))  # Always opens on the start screen (home), never inside a project.
    if splash is None:
        window.show()
        return app.exec()
    splash.step(1.0, "Ready")

    def reveal() -> None:
        window.show()
        splash.finish(window)

    QTimer.singleShot(splash.remaining_ms(), reveal)
    return app.exec()
