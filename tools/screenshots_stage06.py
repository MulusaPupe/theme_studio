"""Stages 04-06 screenshots of the application, from the five-page sample."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
os.environ["MTS_CONFIG_DIR"] = tempfile.mkdtemp()
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mulusa_theme_studio.core.document import walk_nodes  # noqa: E402
from mulusa_theme_studio.core.settings import Settings  # noqa: E402
from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402
from mulusa_theme_studio.ui.export_dialog import ExportDialog  # noqa: E402
from mulusa_theme_studio.ui.main_window import MainWindow  # noqa: E402
from mulusa_theme_studio.ui.session import Session  # noqa: E402


def wait(ms: int = 1500) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main(project: Path, out: Path) -> None:
    app = QApplication([])
    out.mkdir(parents=True, exist_ok=True)
    session = Session(Settings(), TemplateLibrary())
    window = MainWindow(session)
    window.resize(1600, 1000)
    window.show()
    session.open_project(project)
    wait(2500)

    def shot(name: str, target=None) -> None:
        wait()
        (target or window).grab().save(str(out / f"{name}.png"))
        print(name)

    def show(index: int) -> None:
        window.rail_buttons[index].click()

    def nodes(kind):
        return [n for n in walk_nodes(session.current_page["nodes"]) if n["type"] == kind]

    show(2)
    shot("app-pages-manager")
    heading = nodes("heading")[0]
    session.select(heading["id"])
    session.set_viewport("mobile")
    shot("app-mobile-override")
    session.set_viewport("tablet")
    shot("app-tablet-inherited")
    session.set_viewport("desktop")
    query = nodes("query")[0]
    session.select(query["id"])
    window.canvas.view.page().runJavaScript(f"document.querySelector('[data-mts-id=\"{query['id']}\"]').scrollIntoView({{block:'center'}})")
    shot("app-posts-list-settings")
    session.select(session.document["site"]["header"]["id"])
    window.canvas.view.page().runJavaScript("scrollTo(0,0)")
    shot("app-header-form")
    session.open_role_page("single")
    show(1)
    shot("app-single-post-template")
    session.set_page("home")
    dialog = ExportDialog(session, window.design_screenshot(), window)
    dialog.folder.setText(tempfile.mkdtemp())
    dialog.show()
    dialog.run_check()
    shot("app-export-checked", dialog)
    dialog.run_export()
    shot("app-export-done", dialog)
    dialog.close()
    session.project = None
    window.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
