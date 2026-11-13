"""Undo and redo for the universal document.

Every change is made through ``History.apply``, which records a labelled
snapshot. Snapshots are JSON strings: immutable, cheap to compare, and they hold
no references into the live document. An AI assistant or any later tool goes
through the same route, so its changes are undoable too.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .document import Document


def _freeze(doc: Document) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class _Entry:
    label: str
    before: str
    after: str


class History:
    def __init__(self, doc: Document, limit: int = 200) -> None:
        self.document = doc
        self._limit = limit
        self._undo: list[_Entry] = []
        self._redo: list[_Entry] = []
        self._merge: str | None = None

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_depth(self) -> int:
        return len(self._undo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else ""

    def seal(self) -> None:
        """Ends any merging run, so the next change starts a new undo step."""
        self._merge = None

    def apply(self, label: str, change: Callable[[Document], None], merge: str | None = None) -> bool:
        """Run ``change`` on the document. Returns False if it changed nothing.

        If ``change`` raises, the document is restored and the error propagates.

        Successive changes with the same ``merge`` key form one undo step until ``seal`` is
        called, so dragging a slider from 24 to 40 undoes as one action.
        """
        before = _freeze(self.document)
        try:
            change(self.document)
        except Exception:
            self._restore(before)
            raise
        after = _freeze(self.document)
        if after == before:
            return False
        if merge is not None and merge == self._merge and self._undo:
            first = self._undo.pop()
            self._redo.clear()
            if first.before != after:  # Dragged back to where it began: nothing left to undo.
                self._undo.append(_Entry(first.label, first.before, after))
            return True
        self._merge = merge
        self._undo.append(_Entry(label, before, after))
        del self._undo[: -self._limit]
        self._redo.clear()
        return True

    def undo(self) -> str:
        self.seal()
        if not self._undo:
            return ""
        entry = self._undo.pop()
        self._restore(entry.before)
        self._redo.append(entry)
        return entry.label

    def redo(self) -> str:
        self.seal()
        if not self._redo:
            return ""
        entry = self._redo.pop()
        self._restore(entry.after)
        self._undo.append(entry)
        return entry.label

    def _restore(self, frozen: str) -> None:
        # Keep the same dict object so holders of the document stay valid.
        self.document.clear()
        self.document.update(json.loads(frozen))
