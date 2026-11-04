"""The only door between the canvas page and Python.

JavaScript can report that something happened and ask for one of these few things.
Nothing else is reachable from the page, every argument is checked here, and the session
and core operations then validate the request again before the document changes.
"""
from __future__ import annotations

import logging
import re

from PySide6.QtCore import QObject, Slot

from .session import Session

log = logging.getLogger(__name__)
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PRESET = re.compile(r"^[a-z0-9-]{1,64}$")
ROOT = "root"
MAX_INDEX = 100_000


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID.match(value))


def _valid_parent(value: object) -> bool:
    return value == ROOT or _valid_id(value)


def _valid_index(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_INDEX


class EditorBridge(QObject):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.on_ready = None  # Set by the canvas: called when a freshly loaded page is listening.

    @Slot()
    def reportReady(self) -> None:  # noqa: N802
        if self.on_ready is not None:
            self.on_ready()

    @Slot(str)
    def selectNode(self, node_id: str) -> None:  # noqa: N802
        if _valid_id(node_id):
            self.session.select(node_id, origin="canvas")
        else:
            log.warning("Ignored a selection with an invalid id")

    @Slot()
    def clearSelection(self) -> None:  # noqa: N802
        self.session.select("", origin="canvas")

    @Slot(str, str, int)
    def requestInsert(self, preset_id: str, parent: str, index: int) -> None:  # noqa: N802
        if isinstance(preset_id, str) and _PRESET.match(preset_id) and _valid_parent(parent) and _valid_index(index):
            self.session.insert_component(preset_id, self._parent_ref(parent), index)
        else:
            log.warning("Ignored an insert request with invalid arguments")

    @Slot(str, str, int)
    def requestMove(self, node_id: str, parent: str, index: int) -> None:  # noqa: N802
        if _valid_id(node_id) and _valid_parent(parent) and _valid_index(index):
            self.session.move_node(node_id, self._parent_ref(parent), index)
        else:
            log.warning("Ignored a move request with invalid arguments")

    @Slot(str)
    def requestMediaPicker(self, node_id: str) -> None:  # noqa: N802
        if _valid_id(node_id):
            self.session.request_media_picker(node_id)
        else:
            log.warning("Ignored a media request with an invalid id")

    @Slot(str)
    def reportRefused(self, message: str) -> None:  # noqa: N802
        if isinstance(message, str):
            self.session.notify(message[:120])

    def _parent_ref(self, parent: str) -> str:
        return f"page:{self.session.page_id}" if parent == ROOT else parent
