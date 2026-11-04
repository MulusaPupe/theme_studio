"""Stage 03 screenshots: the property forms, site design, media library and dialogs, dark and light."""
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

from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mulusa_theme_studio.core.document import walk_nodes  # noqa: E402
from mulusa_theme_studio.core.settings import Settings  # noqa: E402
from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402
from mulusa_theme_studio.ui.main_window import MainWindow  # noqa: E402
from mulusa_theme_studio.ui.panels.media_panel import MediaPanel  # noqa: E402
from mulusa_theme_studio.ui.session import Session  # noqa: E402

OUT = ROOT / "docs" / "screenshots" / "stage03"


def wait(ms: int = 500) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def sample(folder: Path, name: str, top: tuple, bottom: tuple, size=(1280, 800)) -> Path:
    """A plain generated gradient, so the shots need no outside photos."""
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        mix = y / size[1]
        draw.line([(0, y), (size[0], y)], fill=tuple(round(a + (b - a) * mix) for a, b in zip(top, bottom)))
    path = folder / name
    image.save(path)
    return path


def nodes(window, kind):
    return [n for n in walk_nodes(window.session.current_page["nodes"]) if n["type"] == kind]


def shot(window, name: str, target=None) -> None:
    wait(700)
    (target or window).grab().save(str(OUT / f"{name}.png"))
    print(name)


def run(app, theme: str) -> None:
    settings = Settings()
    settings.appearance = theme
    work = Path(tempfile.mkdtemp())
    settings.projects_dir = str(work / "projects")
    window = MainWindow(Session(settings, TemplateLibrary()))
    window.resize(1500, 950)
    window.show()
    session = window.session
    session.create_project("Harbour Trading", "corporate/corporate-classic")
    wait(1500)
    session.select(nodes(window, "heading")[0]["id"], origin="panel")
    shot(window, f"{theme}-heading-form")
    if theme == "dark":
        session.select(nodes(window, "section")[1]["id"], origin="panel")
        shot(window, f"{theme}-section-form")
    a = sample(work, "harbour.png", (20, 60, 110), (220, 150, 90))
    b = sample(work, "workshop.jpg", (60, 90, 70), (210, 220, 190))
    panel = next(p for p in window.findChildren(MediaPanel))
    panel.add_files([str(a), str(b)])
    page = next(p for p in session.document["pages"] if any(n["type"] == "image" for n in walk_nodes(p["nodes"])))
    session.set_page(page["id"])
    wait(1200)
    image = nodes(window, "image")[0]
    session.select(image["id"], origin="panel")
    shot(window, f"{theme}-placeholder-selected")
    assets = session.document["media"]["assets"]
    session.set_node_media(image["id"], assets[0]["id"], "media")
    shot(window, f"{theme}-image-form")
    window.rail_buttons[window.side_stack.indexOf(panel)].click()
    panel.grid.setCurrentRow(0)
    shot(window, f"{theme}-media-library")
    session.select("", origin="panel")
    shot(window, f"{theme}-nothing-selected")
    window.inspector.show_tab(1)
    shot(window, f"{theme}-site-design")
    window.inspector.show_tab(0)
    session.select(image["id"], origin="panel")
    session.request_media_picker(image["id"])
    wait(300)
    shot(window, f"{theme}-picker", window.media_dialog)
    window.media_dialog.reject()
    wait(100)
    session.request_crop(image["id"])
    wait(300)
    window.media_dialog.view.set_box(200, 100, 1000, 700)
    shot(window, f"{theme}-crop", window.media_dialog)
    window.media_dialog.reject()
    session.project.save()
    session.project = None
    window.close()
    window.deleteLater()
    wait(200)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    application = QApplication(sys.argv)
    for name in ("dark", "light"):
        run(application, name)
    print("Saved to", OUT)
