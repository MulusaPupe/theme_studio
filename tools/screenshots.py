"""Screenshots of the real application window, for checking and for the documentation.

Run: .venv/bin/python tools/screenshots.py OUTPUT_DIR
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
os.environ.setdefault("QT_LOGGING_RULES", "*=false")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mulusa_theme_studio.core.document import walk_nodes  # noqa: E402
from mulusa_theme_studio.core.settings import Settings  # noqa: E402
from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402
from mulusa_theme_studio.ui.main_window import MainWindow  # noqa: E402
from mulusa_theme_studio.ui.session import Session  # noqa: E402
from mulusa_theme_studio.ui.theme import load_fonts  # noqa: E402


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    temp = tempfile.mkdtemp(prefix="mts-shots-")
    os.environ["MTS_CONFIG_DIR"] = temp
    app = QApplication(sys.argv[:1])
    load_fonts()
    settings = Settings(projects_dir=str(Path(temp) / "projects"))
    if len(sys.argv) > 2:
        settings.appearance = sys.argv[2]
    session = Session(settings, TemplateLibrary())
    window = MainWindow(session)
    window.resize(1560, 940)
    window.show()
    tag = settings.appearance

    def shot(name: str, ms: int = 1100) -> None:
        wait(ms)
        window.grab().save(str(out / f"{tag}-{name}.png"))

    shot("01-welcome", 400)
    session.preview_template("fashion/luxury-editorial")
    shot("02-template-preview")
    session.create_project("Mulusa Demo", "construction/heavy-civil")
    window.rail_buttons[3].click()
    node = session.current_page["nodes"][2]
    session.select(node["id"])
    shot("03-project-layers")
    session.set_viewport("tablet")
    session.select("")
    window.rail_buttons[2].click()
    session.set_page("services")
    shot("04-tablet-pages")
    session.set_viewport("mobile")
    window.rail_buttons[1].click()
    session.set_page("home")
    shot("05-mobile-components")
    window.rail_buttons[4].click()
    session.set_viewport("desktop")
    session.preview_template("technology/ai-startup")
    shot("06-media-dark-template")
    session.close_template_preview()
    # Stage 02: selection, the library, a drop indicator and a freshly inserted hero.
    session.set_page("home")
    window.rail_buttons[3].click()
    nodes = session.current_page["nodes"]
    heading = next(n for n in walk_nodes(nodes[1:]) if n["type"] == "heading")
    session.select(heading["id"])
    shot("07-selected-heading")
    window.rail_buttons[1].click()
    session.select("")
    session.begin_component_drag("hero")
    wait(300)
    page = window.canvas.page
    page.runJavaScript("(function(){var s=document.querySelectorAll('main>[data-mts-id]')[1].getBoundingClientRect();scrollTo(0,scrollY+s.top-300);})()")
    wait(200)
    page.runJavaScript("mtsDragOver(600,302)")
    shot("08-dragging-hero", 400)
    page.runJavaScript("mtsDragOver(600,300)")
    session.end_component_drag()
    session.insert_component("hero", f"page:{session.page_id}", 1)
    shot("09-hero-inserted")
    window.rail_buttons[3].click()
    inner = next(n for n in walk_nodes(session.current_page["nodes"][1:2]) if n["type"] == "button")
    session.select(inner["id"])
    shot("10-nested-selection")
    session.set_viewport("mobile")
    shot("11-hero-mobile")
    session.set_viewport("desktop")
    for component in ("about", "services", "features", "testimonials", "team", "pricing", "statistics", "portfolio", "cta", "contact", "faq", "blog", "products"):
        session.insert_component(component, f"page:{session.page_id}", 2)
    session.select("")
    window.resize(1560, 940)
    wait(800)
    canvas = window.canvas
    original = canvas.view.size()
    tall = 0
    for name, width in (("desktop", 1440), ("tablet", 820), ("mobile", 390)):
        session.set_viewport(name)
        wait(500)
        result = []
        page.runJavaScript("document.documentElement.scrollHeight", result.append)
        while not result:
            wait(20)
        tall = result[0]
        canvas.fit = False
        canvas.zoom = 1.0
        page.setZoomFactor(1.0)
        canvas.view.setFixedSize(width, min(tall, 14000))
        canvas.overlay.setGeometry(canvas.view.rect())
        wait(1500)
        canvas.view.grab().save(str(out / f"{tag}-presets-{name}.png"))
        canvas.fit = True
    session.set_viewport("desktop")
    session.project = None
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
