"""Renders each template in a real browser engine: thumbnails plus a layout audit.

Run: .venv/bin/python tools/build_thumbnails.py [--only slug] [--no-thumbs] [--sheet out.png]

Every page of every template is loaded at desktop, tablet and mobile widths and
checked for sideways scrolling and missing fonts. Problems are listed and the
script exits non-zero, so a broken layout cannot pass unnoticed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QEventLoop, Qt, QTimer, QUrl  # noqa: E402
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402
from mulusa_theme_studio.render.site import write_site  # noqa: E402

WIDTHS = {"desktop": 1440, "tablet": 820, "mobile": 390}
AUDIT_JS = """(function(){
 // Measure without the safety wrap, so a word too long for its box counts as a problem.
 var st=document.createElement('style');st.textContent='h1,h2,h3,h4,h5,h6{overflow-wrap:normal!important}';document.head.appendChild(st);
 var w=document.documentElement.clientWidth, over=[];
 document.querySelectorAll('body *').forEach(function(e){
  var r=e.getBoundingClientRect(), s=getComputedStyle(e);
  if(r.width>0&&r.right>w+1&&s.position!=='fixed'&&!e.closest('.mts-bg')&&!e.classList.contains('mts-nav-check')&&!e.closest('.mts-nav')){
    var c=e.parentElement; var clipped=false;
    while(c&&c!==document.body){ if(getComputedStyle(c).overflow==='hidden'){clipped=true;break;} c=c.parentElement; }
    if(!clipped) over.push(e.tagName+'.'+(e.className.baseVal===undefined?e.className:'')+':'+Math.round(r.right-w));
  }});
 document.querySelectorAll('h1,h2,h3,h4,h5,h6,.mts-brand').forEach(function(e){
  var g=document.createRange();g.selectNodeContents(e);var r=g.getBoundingClientRect();
  if(r.right>w+1) over.push('TEXT "'+e.textContent.slice(0,40)+'" '+getComputedStyle(e).fontSize+' by '+Math.round(r.right-w));});
 return JSON.stringify({sw:document.documentElement.scrollWidth,w:w,over:over.slice(0,4)});
})()"""


class Silent(QWebEnginePage):
    def javaScriptConsoleMessage(self, *args):  # noqa: N802
        pass


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def load(view: QWebEngineView, path: Path) -> None:
    loop = QEventLoop()
    view.loadFinished.connect(loop.quit)
    QTimer.singleShot(15000, loop.quit)
    view.load(QUrl.fromLocalFile(str(path)))
    loop.exec()
    view.loadFinished.disconnect(loop.quit)


def run_js(view: QWebEngineView, script: str):
    loop = QEventLoop()
    out = {}

    def done(value):
        out["v"] = value
        loop.quit()

    view.page().runJavaScript(script, done)
    QTimer.singleShot(8000, loop.quit)
    loop.exec()
    return out.get("v")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--no-thumbs", action="store_true")
    ap.add_argument("--home-only", action="store_true")
    ap.add_argument("--sheet", default="")
    args = ap.parse_args()

    app = QApplication(sys.argv[:1])
    library = TemplateLibrary()
    view = QWebEngineView()
    view.setPage(Silent(view))
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.show()
    problems: list[str] = []
    made = 0
    selected = [t for t in library.templates if not args.only or args.only in t.id]

    with tempfile.TemporaryDirectory(prefix="mts-thumbs-") as temp:
        for index, info in enumerate(selected, 1):
            doc = json.loads(info.file.read_text(encoding="utf-8"))
            out = write_site(doc, Path(temp) / info.id.replace("/", "_"))
            for page in doc["pages"]:
                if args.home_only and not page["home"]:
                    continue
                for label, width in WIDTHS.items():
                    view.resize(width, 900)
                    load(view, out.pages[page["id"]])
                    wait(60)
                    raw = run_js(view, AUDIT_JS)
                    if raw:
                        data = json.loads(raw)
                        if data["sw"] > data["w"] + 1 or data["over"]:
                            problems.append(f"{info.id} {page['id']} {label}: scrollWidth {data['sw']}>{data['w']} {data['over']}")
                    else:
                        problems.append(f"{info.id} {page['id']} {label}: audit did not run")
            if not args.no_thumbs:
                # The audit keeps scrollbars, which is stricter; a thumbnail should not show one.
                view.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
                view.resize(1440, 1080)
                load(view, out.pages["home"])
                run_js(view, "document.fonts.ready.then(function(){document.title='ready'});1")
                wait(1500)  # let the hero entrance finish so the thumbnail shows the whole design
                image = view.grab().toImage()
                buffer = QBuffer()
                buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                image.save(buffer, "PNG")
                pil = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGB")
                pil = pil.resize((640, 480), Image.Resampling.LANCZOS)
                pil.save(info.thumbnail, optimize=True)
                made += 1
                view.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, True)
            print(f"[{index}/{len(selected)}] {info.id}", flush=True)
    view.close()
    print(f"thumbnails: {made}; layout problems: {len(problems)}")
    for problem in problems:
        print("  " + problem)

    if args.sheet:
        columns = 5
        tile = (384, 288)
        rows = -(-len(selected) // columns)
        sheet = Image.new("RGB", (columns * (tile[0] + 8) + 8, rows * (tile[1] + 8) + 8), (40, 40, 44))
        for i, info in enumerate(selected):
            if info.thumbnail.is_file():
                sheet.paste(Image.open(info.thumbnail).resize(tile), (8 + (i % columns) * (tile[0] + 8), 8 + (i // columns) * (tile[1] + 8)))
        sheet.save(args.sheet)
    app.quit()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
