"""The centre canvas: a real browser engine showing the rendered website, made interactive.

The view is sized to the chosen device width and scaled by the zoom level, so media
queries respond to the true device width at any zoom. The page reports clicks and drags
through a small bridge (ui/bridge.py); it holds no design state of its own. Every change
goes through the session to the universal document, and the page is then drawn afresh.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import shiboken6
from PySide6.QtCore import QEvent, QFile, QIODevice, QTimer, QUrl, Qt, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QStackedLayout, QVBoxLayout, QWidget

from ..components import registry
from ..render.site import SiteOutput, write_site
from .bridge import EditorBridge
from .session import VIEWPORTS, Session

MIN_ZOOM, MAX_ZOOM = .25, 2.0
COMPONENT_MIME = "application/x-mulusa-component"


class DropOverlay(QWidget):
    """Lies over the page only during a library drag, and turns Qt drag events into page coordinates.

    The page draws the insertion indicator. The overlay is what lets a Qt drag reach it reliably,
    because the engine would otherwise treat the drag as its own.
    """

    def __init__(self, canvas: "Canvas") -> None:
        super().__init__(canvas.view)
        self.canvas = canvas
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()
        self._valid = True

    def _point(self, event) -> tuple[float, float]:
        position = event.position()
        zoom = self.canvas.zoom or 1.0
        return position.x() / zoom, position.y() / zoom

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasFormat(COMPONENT_MIME):
            self._valid = True
            event.acceptProposedAction()
            self.canvas.drag_entered()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802
        if not event.mimeData().hasFormat(COMPONENT_MIME):
            event.ignore()
            return
        x, y = self._point(event)
        self.canvas.page.runJavaScript(f"mtsDragOver({x:.1f},{y:.1f})", self._note_valid)
        # The page answers a moment later, so this reflects the last position checked.
        event.setAccepted(self._valid)

    def _note_valid(self, value) -> None:
        self._valid = value is not False

    def dragLeaveEvent(self, event):  # noqa: N802
        self.canvas.page.runJavaScript("window.mtsDragEnd&&mtsDragEnd()")

    def dropEvent(self, event):  # noqa: N802
        if not event.mimeData().hasFormat(COMPONENT_MIME):
            event.ignore()
            return
        x, y = self._point(event)
        # The page works out the position and asks Python, which checks it before anything changes.
        self.canvas.page.runJavaScript(f"mtsDragDrop({x:.1f},{y:.1f})")
        event.acceptProposedAction()


class _Page(QWebEnginePage):
    """The website must not navigate while it is being edited. Only the canvas itself loads pages."""

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
        if nav_type in (QWebEnginePage.NavigationType.NavigationTypeLinkClicked, QWebEnginePage.NavigationType.NavigationTypeFormSubmitted):
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
        pass


class Canvas(QWidget):
    zoomChanged = Signal()
    renderFailed = Signal(str)

    def __init__(self, session: Session, welcome: QWidget) -> None:
        super().__init__()
        self.session = session
        self.setObjectName("CanvasArea")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._temp = tempfile.mkdtemp(prefix="mts-canvas-")
        self._site: SiteOutput | None = None
        self._loaded_page = ""
        self.fit = True
        self.zoom = 1.0
        self._closed = False

        self.view = QWebEngineView()
        self.page = _Page(self.view)
        self.view.setPage(self.page)
        self.page.setBackgroundColor(Qt.GlobalColor.white)
        # A scrollbar would take width from the page, so the design would not see the true device width.
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        self.bridge = EditorBridge(session)
        self.bridge.on_ready = self._sync_page
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("bridge", self.bridge)
        self.page.setWebChannel(self.channel)
        self._install_channel_script()
        self._restore_y: float | None = None
        self._input_widget = None
        self.view.loadFinished.connect(self._on_loaded)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidget(self.view)

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.scroll)

        self.overlay = DropOverlay(self)
        self.scroll.viewport().installEventFilter(self)  # The margin around a narrow device clears selection.

        self._page_ready = False
        self._patch_timer = QTimer(self, singleShot=True, interval=16)
        self._patch_timer.timeout.connect(self._send_patch)
        self._refit = QTimer(self, singleShot=True, interval=30)
        self._refit.timeout.connect(self.apply_geometry)

        session.documentChanged.connect(self.rerender)
        session.pageChanged.connect(self.show_current_page)
        session.selectionChanged.connect(self.show_selection)
        session.viewportChanged.connect(self._on_viewport)
        session.componentDragChanged.connect(self._on_component_drag)

    def _install_channel_script(self) -> None:
        source = QFile(":/qtwebchannel/qwebchannel.js")
        source.open(QIODevice.OpenModeFlag.ReadOnly)
        script = QWebEngineScript()
        script.setName("mts-webchannel")
        script.setSourceCode(bytes(source.readAll()).decode("utf-8"))
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        self.page.scripts().insert(script)
        source.close()

    def _watch_engine_input(self) -> None:
        """The engine replaces its input widget at times, so this is checked after every load."""
        proxy = self.view.focusProxy()
        if proxy is not None and proxy is not self._input_widget:
            proxy.installEventFilter(self)
            self._input_widget = proxy

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress and watched is self.scroll.viewport():
            self.session.select("", origin="canvas")
        elif event.type() == QEvent.Type.ShortcutOverride and watched is self._input_widget:
            # The engine claims Delete, Ctrl+Z and the like for text editing. Nothing on this page
            # is editable by keyboard, so the application's shortcuts must win once it has focus.
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    # Geometry and zoom --------------------------------------------------------
    @property
    def device_width(self) -> int:
        return VIEWPORTS[self.session.viewport]

    def _available(self):
        area = self.scroll.viewport().size() if self.stack.currentWidget() is self.scroll else self.size()
        return max(area.width(), 200), max(area.height(), 200)

    def fit_zoom(self) -> float:
        available, _ = self._available()
        return max(MIN_ZOOM, min(1.0, (available - 24) / self.device_width))

    def apply_geometry(self) -> None:
        if self._closed:
            return
        if self.fit:
            self.zoom = self.fit_zoom()
        available_w, available_h = self._available()
        width = round(self.device_width * self.zoom)
        self.view.setFixedSize(width, max(available_h, 200))
        self.overlay.setGeometry(0, 0, width, max(available_h, 200))
        self.page.setZoomFactor(self.zoom)
        self.page.runJavaScript(f"window.mtsZoom&&mtsZoom({self.zoom:.4f})")
        self.zoomChanged.emit()

    def set_zoom(self, value: float) -> None:
        self.fit = False
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, value))
        self.apply_geometry()

    def zoom_in(self) -> None:
        self.set_zoom(round(self.zoom + .1, 2))

    def zoom_out(self) -> None:
        self.set_zoom(round(self.zoom - .1, 2))

    def zoom_fit(self) -> None:
        self.fit = True
        self.apply_geometry()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._refit.start()

    def _on_viewport(self) -> None:
        self.fit = True
        self.apply_geometry()

    # Rendering ----------------------------------------------------------------
    def _patchable(self) -> bool:
        return self._page_ready and self._loaded_page == self.session.page_id

    def _schedule_patch(self) -> None:
        """Coalesces a run of changes, such as a slider being dragged, into the latest one."""
        self._patch_timer.start()

    def _send_patch(self) -> None:
        if self._closed or not self._patchable() or self.session.document is None:
            return
        folder = self.session.project.folder if self.session.project and not self.session.read_only else None
        try:
            self._site = write_site(self.session.document, Path(self._temp) / "site", editor=True, project_folder=folder)
        except OSError as exc:
            self.renderFailed.emit(f"The page could not be drawn: {exc}")
            return
        body = self._site.bodies.get(self.session.page_id)
        if body is None:
            return
        args = ",".join(json.dumps(v) for v in (body, self._site.style_href, self._site.body_class))
        self.page.runJavaScript(f"window.mtsPatch&&mtsPatch({args})")

    def rerender(self) -> None:
        if self.session.live_edit and self._patchable():
            self._schedule_patch()  # Rendered when the timer fires, so a fast run of edits draws once.
            return
        self._patch_timer.stop()
        doc = self.session.document
        if doc is None:
            self.stack.setCurrentIndex(0)
            self._site = None
            self._loaded_page = ""
            return
        self.stack.setCurrentWidget(self.scroll)
        folder = self.session.project.folder if self.session.project and not self.session.read_only else None
        try:
            self._site = write_site(doc, Path(self._temp) / "site", editor=True, project_folder=folder)
        except OSError as exc:
            self.renderFailed.emit(f"The page could not be drawn: {exc}")
            return
        self.apply_geometry()
        self._restore_y = self.page.scrollPosition().y() if self.session.keep_view else None
        self._loaded_page = ""
        self.show_current_page()

    def show_current_page(self) -> None:
        if not self._site or self.session.page_id not in self._site.pages:
            return
        if self._loaded_page == self.session.page_id:
            return
        self._loaded_page = self.session.page_id
        self._page_ready = False
        self.view.load(QUrl.fromLocalFile(str(self._site.pages[self.session.page_id])))

    def _on_loaded(self, ok: bool) -> None:
        self._watch_engine_input()
        if not ok:
            # The engine also reports a blocked link or an interrupted load as a failure.
            # Those are normal here; only a page that truly cannot be found is an error.
            target = self._site.pages.get(self.session.page_id) if self._site else None
            if target is not None and not target.is_file():
                self.renderFailed.emit(f"The page could not be displayed: {target.name} is missing.")
            return
        self._sync_page()
        self._restore_y = None
        self._page_ready = True

    def _sync_page(self) -> None:
        """Brings a freshly loaded page up to date. Runs at load end and when the page reports ready,
        because during quick successive edits an interrupted load may report neither reliably."""
        if self._closed:
            return
        self.page.runJavaScript(f"window.mtsEditable&&mtsEditable({json.dumps(not self.session.read_only)})")
        self.page.runJavaScript(f"window.mtsZoom&&mtsZoom({self.zoom:.4f})")
        if self._restore_y is not None:
            self.page.runJavaScript(f"window.mtsScrollTo&&mtsScrollTo({self._restore_y:.1f})")
        self.show_selection()

    def show_selection(self) -> None:
        # Clicking on the canvas must not move the page under the pointer.
        mode = {"canvas": "none", "edit": "nearest"}.get(self.session.selection_origin, "center")
        args = ",".join(json.dumps(v) for v in (self.session.selected_id or "", mode, self.session.selected_label))
        self.page.runJavaScript(f"window.mtsSelect&&mtsSelect({args})")

    # Dragging from the library ------------------------------------------------
    def _on_component_drag(self) -> None:
        if self.session.dragging_component:
            self.overlay.setGeometry(self.view.rect())
            self.overlay.show()
            self.overlay.raise_()
            component = registry.get(self.session.dragging_component)
            args = ",".join(json.dumps(v) for v in (component.node_type, component.label, component.id))
            self.page.runJavaScript(f"window.mtsDragBegin&&mtsDragBegin({args})")
        else:
            self.overlay.hide()
            self.page.runJavaScript("window.mtsDragEnd&&mtsDragEnd()")

    def drag_entered(self) -> None:
        """A drag that left the canvas and came back must start again on the page."""
        if self.session.dragging_component:
            component = registry.get(self.session.dragging_component)
            args = ",".join(json.dumps(v) for v in (component.node_type, component.label, component.id))
            self.page.runJavaScript(f"window.mtsDragBegin&&mtsDragBegin({args})")

    def cancel_drag(self) -> None:
        self.page.runJavaScript("window.mtsDragEnd&&mtsDragEnd()")

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.bridge.on_ready = None
        self._refit.stop()
        self._patch_timer.stop()
        if self._input_widget is not None:
            self._input_widget.removeEventFilter(self)
            self._input_widget = None
        for signal, slot in (
            (self.session.documentChanged, self.rerender),
            (self.session.pageChanged, self.show_current_page),
            (self.session.selectionChanged, self.show_selection),
            (self.session.viewportChanged, self._on_viewport),
            (self.session.componentDragChanged, self._on_component_drag),
        ):
            signal.disconnect(slot)
        # The page must go before its profile does, or the engine can crash at exit.
        self.view.setPage(None)
        shiboken6.delete(self.page)
        shutil.rmtree(self._temp, ignore_errors=True)
