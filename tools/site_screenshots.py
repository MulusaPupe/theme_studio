"""Full-page screenshots of an exported static site, at desktop and phone widths, for review by eye.

    python tools/site_screenshots.py SITE_FOLDER OUT_FOLDER [--pages index,about]

Writes OUT/<page>-desktop.png and OUT/<page>-mobile.png, and OUT/sheet.jpg with all of them.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")

from PySide6.QtCore import QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineCore import QWebEngineSettings  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

WIDTHS = {"desktop": 1440, "mobile": 390}
MAX_HEIGHT = 12000  # very tall grabs can come back blank; the retry below catches it


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def run_js(view: QWebEngineView, script: str):
    box, loop = {}, QEventLoop()

    def done(value):
        box["v"] = value
        loop.quit()

    view.page().runJavaScript(script, 0, done)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    return box.get("v")


def shoot(view: QWebEngineView, page: Path, width: int, out: Path) -> None:
    view.resize(width, 900)
    loop = QEventLoop()
    view.loadFinished.connect(loop.quit)
    view.load(QUrl.fromLocalFile(str(page)))
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    view.loadFinished.disconnect(loop.quit)
    wait(1900)  # let the hero's entrance finish
    # wait for images, then size the view to the page
    run_js(view, "Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => {i.onload = i.onerror = r})))")
    wait(300)
    height = int(run_js(view, "document.documentElement.scrollHeight") or 900)
    # Lazy images below the first screen load only once the view is tall enough, and grow the page.
    for _ in range(4):
        view.resize(width, min(height, MAX_HEIGHT))
        wait(700)
        run_js(view, "Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => {i.onload = i.onerror = r})))")
        grown = int(run_js(view, "document.documentElement.scrollHeight") or height)
        if grown == height:
            break
        height = grown
    image = view.grab().toImage()
    # A tall grab sometimes returns before the lower part is painted: retry until it is not blank.
    for _ in range(4):
        tail = image.copy(0, max(0, image.height() - 600), image.width(), min(600, image.height()))
        if len({tail.pixel(x, y) for x in range(0, tail.width(), 37) for y in range(0, tail.height(), 29)}) > 1:
            break
        wait(900)
        image = view.grab().toImage()
    broken = json.loads(run_js(view, "JSON.stringify([...document.images].filter(i => !i.naturalWidth).map(i => i.src.slice(0, 80)))") or "[]")
    overflow = run_js(view, "document.documentElement.scrollWidth > window.innerWidth + 1")
    image.save(str(out))
    notes = []
    if broken:
        notes.append(f"{len(broken)} broken image(s)")
    if overflow:
        notes.append("sideways scroll")
    print(f"{out.name}: {height}px" + (f"  !! {', '.join(notes)}" if notes else ""))


def sheet(files: list[Path], out: Path, cell: int = 520) -> None:
    from PIL import Image, ImageDraw
    cols = 4
    rows = (len(files) + cols - 1) // cols
    image = Image.new("RGB", (cell * cols, (cell + 20) * rows), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB")
        im.thumbnail((cell - 8, cell - 8))
        x, y = (i % cols) * cell, (i // cols) * (cell + 20)
        image.paste(im, (x + 4, y + 20))
        draw.text((x + 6, y + 4), f.stem, fill=(255, 220, 0))
    image.save(out, quality=82)


def main() -> None:
    site, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    only = None
    if "--pages" in sys.argv:
        only = set(sys.argv[sys.argv.index("--pages") + 1].split(","))
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])  # noqa: F841
    view = QWebEngineView()
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
    view.show()
    files = []
    for page in sorted(site.glob("*.html"), key=lambda p: (p.name != "index.html", p.name)):
        if only and page.stem not in only:
            continue
        for device, width in WIDTHS.items():
            target = out / f"{page.stem}-{device}.png"
            shoot(view, page, width, target)
            files.append(target)
    sheet(files, out / "sheet.jpg")


if __name__ == "__main__":
    main()
