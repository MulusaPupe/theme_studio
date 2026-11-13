"""Drives a real WordPress in Qt's browser engine. Test tooling only: the application never imports it."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

# Asks the editor's own parser. isValid is exactly what produces "This block contains unexpected content".
BLOCK_REPORT = """
(function(){
 const walk=(b,out)=>{for(const x of b){if(!x.isValid){out.push({name:x.name,issues:(x.validationIssues||[]).map(i=>i.args?i.args.map(String).join(' ').slice(0,1500):String(i)),original:(x.originalContent||'').slice(0,800)});}walk(x.innerBlocks,out);}return out;};
 const count=b=>b.reduce((n,x)=>n+1+count(x.innerBlocks),0);
 window.__mtsWalk=walk;window.__mtsCount=count;return true;})()
"""


class Browser:
    def __init__(self, base: str, width: int = 1440, height: int = 1000) -> None:
        self.app = QApplication.instance() or QApplication([])
        self.base = base.rstrip("/")
        self.profile = QWebEngineProfile()
        self.view = QWebEngineView()
        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)
        self.view.resize(width, height)
        self.view.show()

    def wait(self, ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def open(self, path: str, settle: int = 500) -> None:
        loop = QEventLoop()
        self.page.loadFinished.connect(loop.quit)
        QTimer.singleShot(60000, loop.quit)
        self.page.load(QUrl(path if path.startswith("http") else self.base + path))
        loop.exec()
        self.page.loadFinished.disconnect(loop.quit)
        self.wait(settle)

    def js(self, code: str):
        box: list = []
        loop = QEventLoop()

        def done(value) -> None:
            box.append(value)
            loop.quit()

        self.page.runJavaScript(code, 0, done)
        QTimer.singleShot(60000, loop.quit)
        loop.exec()
        return box[0] if box else None

    def until(self, code: str, timeout: float = 45) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.js(code):
                return True
            self.wait(250)
        return False

    def login(self, user: str = "admin", password: str = "admin") -> None:
        self.open("/wp-login.php")
        self.js(f"document.getElementById('user_login').value={json.dumps(user)};document.getElementById('user_pass').value={json.dumps(password)};true")
        loop = QEventLoop()
        self.page.loadFinished.connect(loop.quit)
        QTimer.singleShot(30000, loop.quit)
        self.js("document.getElementById('loginform').submit();true")
        loop.exec()
        self.page.loadFinished.disconnect(loop.quit)

    def open_editor(self, post_id: int) -> bool:
        self.open(f"/wp-admin/post.php?post={post_id}&action=edit")
        ready = self.until("!!(window.wp&&wp.data&&wp.data.select('core/editor')&&wp.data.select('core/editor').__unstableIsEditorReady&&wp.data.select('core/editor').__unstableIsEditorReady())||!!(window.wp&&wp.data&&wp.data.select('core/block-editor')&&wp.data.select('core/block-editor').getBlocks().length)")
        self.js(BLOCK_REPORT)
        return ready

    def invalid_in_editor(self) -> tuple[int, list[dict]]:
        result = self.js("JSON.stringify((()=>{const b=wp.data.select('core/block-editor').getBlocks();return {n:__mtsCount(b),bad:__mtsWalk(b,[])}})())")
        data = json.loads(result)
        return data["n"], data["bad"]

    def parse_report(self, markup: str) -> tuple[int, list[dict]]:
        result = self.js(f"JSON.stringify((()=>{{const b=wp.blocks.parse({json.dumps(markup)});return {{n:__mtsCount(b),bad:__mtsWalk(b,[])}}}})())")
        data = json.loads(result)
        return data["n"], data["bad"]

    def patterns(self) -> list[dict]:
        self.js("window.__mtsP=null;wp.apiFetch({path:'/wp/v2/block-patterns/patterns'}).then(r=>{window.__mtsP=JSON.stringify(r)});true")
        self.until("!!window.__mtsP")
        return json.loads(self.js("window.__mtsP"))

    def shoot(self, path: str | Path, width: int, url: str | None = None) -> dict:
        """A real browser at a real width, measuring whether the page overflows it."""
        self.view.resize(width, 1000)
        self.wait(200)
        if url:
            self.open(url, 800)
        self.js("document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager');true")
        self.wait(600)
        facts = json.loads(self.js("JSON.stringify({inner:innerWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})"))
        self.view.grab().save(str(path))
        return facts
