"""Real timings on the five-page sample, in the real window. Prints median and worst in milliseconds."""
from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
os.environ["MTS_CONFIG_DIR"] = tempfile.mkdtemp()
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mulusa_theme_studio.core.document import site_pages, walk_nodes  # noqa: E402
from mulusa_theme_studio.core.project import Project  # noqa: E402
from mulusa_theme_studio.core.settings import Settings  # noqa: E402
from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402
from mulusa_theme_studio.exporters.wordpress import ExportOptions, WordPressExporter, _build  # noqa: E402
from mulusa_theme_studio.render.site import write_site  # noqa: E402
from mulusa_theme_studio.ui.main_window import MainWindow  # noqa: E402
from mulusa_theme_studio.ui.session import Session  # noqa: E402


def report(name: str, samples: list[float]) -> None:
    print(f"{name:42s} median {statistics.median(samples):8.1f}  worst {max(samples):8.1f}  ({len(samples)} runs)", flush=True)


def timed(action, runs: int) -> list[float]:
    out = []
    for _ in range(runs):
        start = time.perf_counter()
        action()
        out.append((time.perf_counter() - start) * 1000)
    return out


def main(folder: Path) -> None:
    app = QApplication([])
    report("Open the project (read, migrate, validate)", timed(lambda: Project.open(folder), 10))
    session = Session(Settings(), TemplateLibrary())
    window = MainWindow(session)
    window.resize(1500, 900)
    window.show()

    def js(code: str):
        box: list = []
        loop = QEventLoop()
        window.canvas.view.page().runJavaScript(code, 0, lambda value: (box.append(value), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        return box[0] if box else None

    def until(code: str, timeout: float = 20) -> None:
        end = time.time() + timeout
        while time.time() < end:
            app.processEvents()
            if js(code):
                return
        raise TimeoutError(code)

    session.open_project(folder)
    until("!!window.mtsReady")
    pages = [p["id"] for p in site_pages(session.document)]

    def switch(index=[0]) -> None:
        index[0] = (index[0] + 1) % len(pages)
        session.set_page(pages[index[0]])
        page = session.current_page
        until(f"window.mtsReady&&!!document.querySelector('[data-mts-id=\"{page['nodes'][0]['id']}\"]')")

    report("Switch page, until the canvas shows it", timed(switch, 15))
    session.set_page(pages[0])
    until(f"!!document.querySelector('[data-mts-id=\"{session.current_page['nodes'][0]['id']}\"]')")
    heading = next(n for n in walk_nodes(session.current_page["nodes"]) if n["type"] == "heading")
    size = [40]

    def edit() -> None:
        size[0] = 40 + (size[0] + 1) % 30
        value = f"{size[0]}px"
        session.edit_style(heading["id"], "font_size", value)
        session.end_gesture()
        until(f"getComputedStyle(document.querySelector('[data-mts-id=\"{heading['id']}\"]')).fontSize==='{value}'")

    report("Edit a style, until the canvas shows it", timed(edit, 25))

    def undo_redo() -> None:
        session.undo()
        session.redo()

    report("Undo and redo (document and panels)", timed(undo_redo, 15))
    with tempfile.TemporaryDirectory() as temp:
        report("Render the whole site to files", timed(lambda: write_site(session.document, Path(temp) / "site", project_folder=session.project.folder), 5))
        report("Translate to blocks", timed(lambda: _build(session.document, ExportOptions(theme_name="M")), 10))
        exporter = WordPressExporter()
        report("Check the theme", timed(lambda: exporter.check(session.document, session.project.folder, ExportOptions(theme_name="M")), 5))
        report("Full export with packaging (two ZIPs)", timed(lambda: exporter.export(session.document, session.project.folder, Path(temp) / "out", ExportOptions(theme_name="M")), 5))
        sizes = {p.name: p.stat().st_size for p in (Path(temp) / "out").glob("*.zip")}
        print("ZIP sizes:", sizes)
    session.project = None
    window.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
