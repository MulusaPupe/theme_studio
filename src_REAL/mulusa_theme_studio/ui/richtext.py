"""A rich text box limited to what the renderer allows: paragraphs, bold, italic, underline, lists, links.

It reads and writes only that small set of tags, not Qt's own HTML, so nothing unsafe is stored,
and the renderer sanitises it again in any case.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QTextDocument, QTextListFormat
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLineEdit, QTextEdit, QToolButton, QVBoxLayout

from ..core.styles import is_safe_url
from ..render.html import sanitize_rich_text
from .fields import Field
from .theme import Palette, make_icon


def _fragment_html(fragment) -> str:
    text = escape(fragment.text()).replace(" ", "<br>")
    fmt = fragment.charFormat()
    if fmt.isAnchor() and fmt.anchorHref():
        text = f'<a href="{escape(fmt.anchorHref(), quote=True)}">{text}</a>'
    if fmt.fontUnderline() and not fmt.isAnchor():
        text = f"<u>{text}</u>"
    if fmt.fontItalic():
        text = f"<em>{text}</em>"
    if fmt.fontWeight() >= QFont.Weight.DemiBold:
        text = f"<strong>{text}</strong>"
    return text


def document_to_html(document: QTextDocument) -> str:
    out: list[str] = []
    open_list = ""
    block = document.begin()
    while block.isValid():
        inner = ""
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                inner += _fragment_html(fragment)
            iterator += 1
        text_list = block.textList()
        kind = ""
        if text_list is not None:
            kind = "ol" if text_list.format().style() == QTextListFormat.Style.ListDecimal else "ul"
        if kind != open_list:
            if open_list:
                out.append(f"</{open_list}>")
            if kind:
                out.append(f"<{kind}>")
            open_list = kind
        if kind:
            out.append(f"<li>{inner}</li>")
        elif inner:
            out.append(f"<p>{inner}</p>")
        block = block.next()
    if open_list:
        out.append(f"</{open_list}>")
    return "".join(out)


class RichTextField(Field):
    def __init__(self, pal: Palette) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        bar = QHBoxLayout()
        bar.setSpacing(2)
        for icon, tip, handler in (
            ("bold", "Bold", self._bold), ("italic", "Italic", self._italic), ("underline", "Underline", self._underline),
            ("list", "Bulleted list", self._list), ("link-2", "Add a link to the selected text", self._link),
        ):
            button = QToolButton()
            button.setIcon(make_icon(icon, pal, 14))
            button.setIconSize(QSize(14, 14))
            button.setToolTip(tip)
            button.clicked.connect(handler)
            bar.addWidget(button)
        bar.addStretch(1)
        column.addLayout(bar)
        self.edit = QTextEdit()
        self.edit.setAcceptRichText(False)
        self.edit.setFixedHeight(130)
        self.edit.textChanged.connect(self._changed)
        self.edit.focusOutEvent = self._left(self.edit.focusOutEvent)
        column.addWidget(self.edit)
        self._quiet = False
        self._value = ""

    def _left(self, original):
        def handler(event):
            original(event)
            self.finished.emit()
        return handler

    def _changed(self) -> None:
        if not self._quiet:
            self._value = document_to_html(self.edit.document())
            self.edited.emit(self._value)

    def _merge(self, fmt: QTextCharFormat) -> None:
        self.edit.mergeCurrentCharFormat(fmt)
        self._changed()

    def _bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal if self.edit.fontWeight() >= QFont.Weight.DemiBold else QFont.Weight.Bold)
        self._merge(fmt)

    def _italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.edit.fontItalic())
        self._merge(fmt)

    def _underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.edit.fontUnderline())
        self._merge(fmt)

    def _list(self) -> None:
        cursor = self.edit.textCursor()
        current = cursor.currentList()
        if current:
            current.remove(cursor.block())
        else:
            cursor.createList(QTextListFormat.Style.ListDisc)
        self._changed()

    def _link(self) -> None:
        url, ok = QInputDialog.getText(self, "Add a link", "Web address", QLineEdit.EchoMode.Normal, "https://")
        if ok:
            self.add_link(url.strip())

    def add_link(self, url: str) -> bool:
        if not url or not is_safe_url(url):
            return False
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url)
        cursor.mergeCharFormat(fmt)
        self._changed()
        return True

    def set_value(self, value) -> None:
        text = sanitize_rich_text(str(value or ""))
        if text == self._value:
            return
        self._quiet = True
        self._value = text
        self.edit.setHtml(text)
        self._quiet = False
