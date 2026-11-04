"""Reusable property controls. Each shows a value, says when it was edited and when a gesture ended.

They know nothing about documents or sessions: the panels connect them, and core checks every value.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPlainTextEdit, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from ..core.properties import compose_border, parse_border
from ..core.styles import BORDER_STYLES, UNITS, is_color
from .theme import Palette, make_icon

_NUMBER_UNIT = re.compile(r"^(-?\d*\.?\d+)([a-z%]*)$")
COLOR_CHOICES = (
    ("$primary", "Primary"), ("$secondary", "Secondary"), ("$accent", "Accent"), ("$background", "Background"),
    ("$surface", "Surface"), ("$text", "Text"), ("$muted", "Muted text"), ("$border", "Border"),
)


class Field(QWidget):
    edited = Signal(object)  # The value changed because of the person, not because of set_value.
    finished = Signal()      # A gesture ended: the next change starts a new undo step.

    def set_value(self, value) -> None:
        raise NotImplementedError


class NoWheelCombo(QComboBox):
    """Scrolling the panel must not silently change a dropdown it passes over."""

    def wheelEvent(self, event):  # noqa: N802
        event.ignore()


class TextField(Field):
    def __init__(self, multiline: bool = False, placeholder: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.multiline = multiline
        if multiline:
            self.edit = QPlainTextEdit()
            self.edit.setFixedHeight(84)
            self.edit.setPlaceholderText(placeholder)
            self.edit.textChanged.connect(self._changed)
            self.edit.focusOutEvent = self._focus_out(self.edit.focusOutEvent)
        else:
            self.edit = QLineEdit(placeholderText=placeholder)
            self.edit.textEdited.connect(self._changed)
            self.edit.editingFinished.connect(self.finished)
        layout.addWidget(self.edit)
        self._quiet = False

    def _focus_out(self, original):
        def handler(event):
            original(event)
            self.finished.emit()
        return handler

    def _text(self) -> str:
        return self.edit.toPlainText() if self.multiline else self.edit.text()

    def _changed(self, *_) -> None:
        if not self._quiet:
            self.edited.emit(self._text())

    def set_value(self, value) -> None:
        text = "" if value is None else str(value)
        if text == self._text():
            return
        self._quiet = True
        if self.multiline:
            self.edit.setPlainText(text)
        else:
            self.edit.setText(text)
        self._quiet = False


class ChoiceField(Field):
    def __init__(self, options: list[tuple[str, object]]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = NoWheelCombo()
        for text, value in options:
            self.combo.addItem(text, value)
        self.combo.activated.connect(self._activated)
        layout.addWidget(self.combo)

    def _activated(self, _index: int) -> None:
        self.edited.emit(self.combo.currentData())
        self.finished.emit()

    def set_value(self, value) -> None:
        index = self.combo.findData(value)
        if index < 0 and value not in (None, ""):
            self.combo.addItem(f"Custom ({value})", value)
            index = self.combo.count() - 1
        self.combo.setCurrentIndex(max(index, 0))


class FontField(ChoiceField):
    """Bundled fonts only, each shown in its own face, so choosing one works offline."""

    def __init__(self, families: list[str], leading: list[tuple[str, object]]) -> None:
        super().__init__(leading + [(family, family) for family in families])
        for index in range(len(leading), self.combo.count()):
            self.combo.setItemData(index, QFont(self.combo.itemText(index), 13), Qt.ItemDataRole.FontRole)


class SegmentField(Field):
    """A row of mutually exclusive buttons, such as text alignment."""

    def __init__(self, options: list[tuple[str, object, str]], pal: Palette, *, default=None) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.group = QButtonGroup(self, exclusive=False)
        self.buttons: dict[object, QToolButton] = {}
        self.default = default
        for icon, value, tip in options:
            button = QToolButton()
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.setIcon(make_icon(icon, pal, 15)) if icon else button.setText(tip)
            button.setIconSize(QSize(15, 15))
            button.clicked.connect(lambda checked, v=value: self._clicked(v, checked))
            self.buttons[value] = button
            layout.addWidget(button)
        layout.addStretch(1)

    def _clicked(self, value, checked: bool) -> None:
        # Pressing the active choice again clears it, returning to the inherited value.
        self.set_value(value if checked else self.default)
        self.edited.emit(value if checked else self.default)
        self.finished.emit()

    def set_value(self, value) -> None:
        for key, button in self.buttons.items():
            button.setChecked(key == value)


class BoolField(Field):
    def __init__(self, text: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.box = QCheckBox(text)
        self.box.clicked.connect(lambda checked: (self.edited.emit(bool(checked)), self.finished.emit()))
        layout.addWidget(self.box)

    def set_value(self, value) -> None:
        self.box.setChecked(bool(value))


class SliderField(Field):
    """A number, with a slider beside it. Dragging the slider is one gesture and one undo step."""

    def __init__(self, low: float, high: float, step: float = 1, suffix: str = "", factor: float = 1, empty: str = "") -> None:
        super().__init__()
        # With `empty`, one extra stop at the far left means "no value of its own", so an unset
        # property never shows a number the element does not really have.
        low = low - step if empty else low
        self.factor, self.step, self.low = factor, step, low
        self.empty = empty
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((high - low) / step))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(low, high)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(0 if step >= 1 else len(str(step).split(".")[1]))
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(76)
        if empty:
            self.spin.setSpecialValueText(empty)
        self.spin.wheelEvent = lambda event: event.ignore()
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.slider.sliderReleased.connect(self.finished)
        self.spin.valueChanged.connect(self._from_spin)
        self.spin.editingFinished.connect(self.finished)
        self._quiet = False

    def _emit(self, shown: float) -> None:
        if self.empty and shown <= self.low:
            self.edited.emit(None)
            return
        value = shown / self.factor if self.factor != 1 else shown
        value = round(value, 4)
        self.edited.emit(int(value) if float(value).is_integer() and self.step >= 1 else value)

    def _from_slider(self, position: int) -> None:
        if self._quiet:
            return
        shown = self.low + position * self.step
        self._quiet = True
        self.spin.setValue(shown)
        self._quiet = False
        self._emit(shown)

    def _from_spin(self, shown: float) -> None:
        if self._quiet:
            return
        self._quiet = True
        self.slider.setValue(round((shown - self.low) / self.step))
        self._quiet = False
        self._emit(shown)

    def set_value(self, value) -> None:
        self._quiet = True
        try:
            shown = float(value) * self.factor
        except (TypeError, ValueError):
            shown = self.low
        self.spin.setValue(shown)
        self.slider.setValue(round((shown - self.low) / self.step))
        self._quiet = False


class LengthField(Field):
    """A size: type a number, choose a unit, use a site spacing value, or drag the optional slider.

    Values it cannot show as a number, such as clamp(), stay visible and intact until changed.
    """

    def __init__(self, pal: Palette, *, units: tuple[str, ...] = UNITS[:4], tokens: list[tuple[str, str]] | None = None,
                 slider: tuple[float, float] | None = None, placeholder: str = "Auto", allow_auto: bool = False) -> None:
        super().__init__()
        self.range = slider
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.edit = QLineEdit(placeholderText=placeholder)
        self.edit.setMinimumWidth(60)
        self.edit.textEdited.connect(self._typed)
        self.edit.editingFinished.connect(self._leave)
        self.unit = NoWheelCombo()
        self.unit.addItems(list(units))
        self.unit.setFixedWidth(62)
        self.unit.activated.connect(self._unit_changed)
        row.addWidget(self.edit, 1)
        row.addWidget(self.unit)
        if tokens:
            button = QToolButton()
            button.setIcon(make_icon("sliders-horizontal", pal, 14))
            button.setToolTip("Use a site spacing value")
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(button)
            for text, token in tokens:
                menu.addAction(text, lambda t=token: self._token(t))
            button.setMenu(menu)
            row.addWidget(button)
        column.addLayout(row)
        self.slider = None
        if slider:
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(int(slider[0]), int(slider[1]))
            self.slider.valueChanged.connect(self._slid)
            self.slider.sliderReleased.connect(self.finished)
            column.addWidget(self.slider)
        self._quiet = False
        self.allow_auto = allow_auto
        self._last = ""

    def _compose(self) -> str | None:
        text = self.edit.text().strip()
        if not text:
            return None
        return f"{text}{self.unit.currentText()}" if re.fullmatch(r"-?\d*\.?\d+", text) else text

    def _typed(self, _text: str) -> None:
        self._sync_slider()
        self.edited.emit(self._compose())

    def _leave(self) -> None:
        self.finished.emit()

    def _unit_changed(self, _i: int) -> None:
        if re.fullmatch(r"-?\d*\.?\d+", self.edit.text().strip()):
            self.edited.emit(self._compose())
            self.finished.emit()

    def _token(self, token: str) -> None:
        self.edited.emit(token)
        self.finished.emit()

    def _slid(self, value: int) -> None:
        if self._quiet:
            return
        unit = self.unit.currentText()
        shown = value if unit in ("px", "%", "vw", "vh") else round(value / 16, 3)
        self._quiet = True
        self.edit.setText(f"{shown:g}")
        self._quiet = False
        self.edited.emit(f"{shown:g}{unit}")

    def _sync_slider(self) -> None:
        if not self.slider:
            return
        match = _NUMBER_UNIT.match(self.edit.text().strip())
        self._quiet = True
        if match:
            value = float(match.group(1))
            self.slider.setValue(int(value if self.unit.currentText() in ("px", "%", "vw", "vh") else value * 16))
        self._quiet = False

    def set_value(self, value) -> None:
        text = "" if value is None else str(value)
        if self.edit.hasFocus() and self._compose() == (text or None):
            return
        match = _NUMBER_UNIT.match(text)
        self._quiet = True
        if match and (match.group(2) in [self.unit.itemText(i) for i in range(self.unit.count())] or match.group(2) == ""):
            self.edit.setText(match.group(1))
            if match.group(2):
                self.unit.setCurrentText(match.group(2))
        else:
            self.edit.setText(text)
            self.edit.setToolTip(text)
        self._quiet = False
        self._sync_slider()


def _swatch_icon(color: str, size: int = 18) -> QIcon:
    pixmap = QPixmap(size, size)
    qcolor = QColor(color)
    pixmap.fill(qcolor if qcolor.isValid() else QColor(0, 0, 0, 0))
    return QIcon(pixmap)


class ColorField(Field):
    """A fixed colour or a site colour: swatch and picker, hex entry, and a row of the site's colours."""

    def __init__(self, pal: Palette, *, tokens: bool = True, resolve=None, clearable: bool = True) -> None:
        super().__init__()
        self.resolve = resolve or (lambda value: value)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.swatch = QToolButton()
        self.swatch.setObjectName("ColorSwatch")
        self.swatch.setToolTip("Open the colour picker")
        self.swatch.setFixedSize(28, 28)
        self.swatch.setIconSize(QSize(20, 20))
        self.swatch.clicked.connect(self.pick)
        self.hex = QLineEdit(placeholderText="#rrggbb")
        self.hex.setMaxLength(32)
        self.hex.editingFinished.connect(self._hex_done)
        row.addWidget(self.swatch)
        row.addWidget(self.hex, 1)
        if clearable:
            clear = QToolButton()
            clear.setIcon(make_icon("x", pal, 13))
            clear.setToolTip("Remove this colour and go back to what the design gives")
            clear.clicked.connect(lambda: (self.edited.emit(None), self.finished.emit()))
            row.addWidget(clear)
        column.addLayout(row)
        self.chips: dict[str, QToolButton] = {}
        if tokens:
            chips = QHBoxLayout()
            chips.setSpacing(3)
            for token, name in COLOR_CHOICES:
                chip = QToolButton()
                chip.setObjectName("ColorChip")
                chip.setCheckable(True)
                chip.setFixedSize(22, 22)
                chip.setIconSize(QSize(14, 14))
                chip.setToolTip(f"Site colour: {name}. It follows the global palette.")
                chip.clicked.connect(lambda _=False, t=token: self._use(t))
                self.chips[token] = chip
                chips.addWidget(chip)
            chips.addStretch(1)
            column.addLayout(chips)
        self.value = ""

    def _use(self, value: str) -> None:
        self.edited.emit(value)
        self.finished.emit()

    def _hex_done(self) -> None:
        text = self.hex.text().strip()
        if text.lower() == self.value.lower() or (not text and not self.value):
            return
        self.edited.emit(text or None)
        self.finished.emit()

    def pick(self) -> None:
        original = self.value
        start = QColor(self.resolve(original)) if self.resolve(original) else QColor("#808080")
        dialog = QColorDialog(start, self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dialog.currentColorChanged.connect(lambda c: self.edited.emit(c.name()))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.edited.emit(original or None)  # Cancel puts back what was there.
        self.finished.emit()

    def refresh_chips(self) -> None:
        for token, chip in self.chips.items():
            chip.setIcon(_swatch_icon(self.resolve(token) or "#808080", 14))

    def set_value(self, value) -> None:
        self.value = "" if value is None else str(value)
        if not self.hex.hasFocus() or self.hex.text().strip().lower() != self.value.lower():
            self.hex.setText(self.value)
        shown = self.resolve(self.value)
        self.swatch.setIcon(_swatch_icon(shown or "#00000000", 20))
        for token, chip in self.chips.items():
            chip.setChecked(token == self.value)
        self.refresh_chips()


_GRADIENT = re.compile(r"^linear-gradient\(\s*(\d+)deg\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*\)$")


class BackgroundField(Field):
    """None, a solid colour or a two-colour gradient, without writing any CSS."""

    def __init__(self, pal: Palette, resolve=None) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.mode = NoWheelCombo()
        self.mode.addItems(["From the design", "Solid colour", "Gradient"])
        self.mode.activated.connect(self._mode)
        self.first = ColorField(pal, resolve=resolve, clearable=False)
        self.second = ColorField(pal, resolve=resolve, clearable=False)
        self.angle = SliderField(0, 360, 5, "°")
        column.addWidget(self.mode)
        column.addWidget(self.first)
        column.addWidget(self.second)
        column.addWidget(self.angle)
        self.first.edited.connect(lambda _v: self._emit())
        self.second.edited.connect(lambda _v: self._emit())
        self.angle.edited.connect(lambda _v: self._emit())
        for field in (self.first, self.second, self.angle):
            field.finished.connect(self.finished)
        self._show(0)

    def _show(self, mode: int) -> None:
        self.first.setVisible(mode > 0)
        self.second.setVisible(mode == 2)
        self.angle.setVisible(mode == 2)

    def _mode(self, mode: int) -> None:
        self._show(mode)
        if mode == 1 and not self.first.value:
            self.first.set_value("$surface")
        if mode == 2:
            if not self.first.value:
                self.first.set_value("$primary")
            if not self.second.value:
                self.second.set_value("$accent")
        self._emit()
        self.finished.emit()

    def _emit(self) -> None:
        mode = self.mode.currentIndex()
        if mode == 0:
            self.edited.emit(None)
        elif mode == 1:
            self.edited.emit(self.first.value or None)
        else:
            self.edited.emit(f"linear-gradient({int(self.angle.spin.value())}deg,{self.first.value},{self.second.value})")

    def set_value(self, value) -> None:
        text = "" if value is None else str(value)
        match = _GRADIENT.match(text)
        if match:
            mode = 2
            self.angle.set_value(int(match.group(1)))
            self.first.set_value(match.group(2))
            self.second.set_value(match.group(3))
        elif text and is_color(text):
            mode = 1
            self.first.set_value(text)
        else:
            mode = 0
            if text:  # A richer value from a template: shown as design-provided and kept until changed.
                self.mode.setToolTip(text)
        self.mode.setCurrentIndex(mode)
        self._show(mode)


class BorderField(Field):
    def __init__(self, pal: Palette, resolve=None) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.style_box = NoWheelCombo()
        self.style_box.addItems([s.capitalize() for s in BORDER_STYLES])
        self.style_box.activated.connect(self._style_changed)
        self.width_box = QDoubleSpinBox()
        self.width_box.setRange(0, 40)
        self.width_box.setSuffix(" px")
        self.width_box.setDecimals(1)
        self.width_box.wheelEvent = lambda event: event.ignore()
        self.width_box.valueChanged.connect(lambda _v: self._emit())
        self.width_box.editingFinished.connect(self.finished)
        row.addWidget(self.style_box, 1)
        row.addWidget(self.width_box)
        self.color = ColorField(pal, resolve=resolve, clearable=False)
        self.color.edited.connect(lambda _v: self._emit())
        self.color.finished.connect(self.finished)
        column.addLayout(row)
        column.addWidget(self.color)
        self._quiet = False

    def _style_changed(self, index: int) -> None:
        if index > 0 and self.width_box.value() == 0:
            self._quiet = True
            self.width_box.setValue(1)
            self._quiet = False
        if index > 0 and not self.color.value:
            self.color.set_value("$border")
        self._emit()
        self.finished.emit()

    def _emit(self) -> None:
        if self._quiet:
            return
        style = BORDER_STYLES[self.style_box.currentIndex()]
        if style == "none" or self.width_box.value() == 0:
            self.edited.emit(None)
        else:
            self.edited.emit(compose_border(f"{self.width_box.value():g}px", style, self.color.value or "$border"))

    def set_value(self, value) -> None:
        width, style, color = parse_border(value)
        self._quiet = True
        self.style_box.setCurrentIndex(BORDER_STYLES.index(style) if style in BORDER_STYLES else 0)
        match = _NUMBER_UNIT.match(width)
        self.width_box.setValue(float(match.group(1)) if match else 0)
        self.color.set_value(color or None)
        self._quiet = False


class BoxField(QWidget):
    """Four sides of margin or padding. Blank means the design's own value."""

    sideEdited = Signal(str, object)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        self.sides: dict[str, QLineEdit] = {}
        for index, (side, name) in enumerate((("top", "Top"), ("right", "Right"), ("bottom", "Bottom"), ("left", "Left"))):
            edit = QLineEdit(placeholderText=name)
            edit.setToolTip(f"{name}. A number means pixels; 2rem and 5% also work.")
            edit.textEdited.connect(lambda text, s=side: self.sideEdited.emit(s, text.strip() or None))
            edit.editingFinished.connect(self.finished)
            self.sides[side] = edit
            grid.addWidget(edit, index // 2, index % 2)

    def set_values(self, values: dict[str, str]) -> None:
        for side, edit in self.sides.items():
            text = values.get(side, "")
            shown = text[:-2] if re.fullmatch(r"-?\d*\.?\d+px", text) else text
            if not edit.hasFocus():
                edit.setText(shown)
                edit.setToolTip(text or edit.placeholderText())


class LinkField(Field):
    """Where a button or link goes: one of the site's pages, or a web address."""

    def __init__(self) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        self.combo = NoWheelCombo()
        self.combo.activated.connect(self._chosen)
        self.url = QLineEdit(placeholderText="https://example.com")
        self.url.editingFinished.connect(self._typed)
        column.addWidget(self.combo)
        column.addWidget(self.url)

    def set_pages(self, pages: list[tuple[str, str]]) -> None:
        self.combo.clear()
        for title, page_id in pages:
            self.combo.addItem(f"Page: {title}", {"page": page_id})
        self.combo.addItem("Web address", "url")

    def _chosen(self, _i: int) -> None:
        data = self.combo.currentData()
        self.url.setVisible(data == "url")
        if data != "url":
            self.edited.emit(data)
            self.finished.emit()
        else:
            self.url.setFocus()

    def _typed(self) -> None:
        if self.combo.currentData() == "url":
            self.edited.emit(self.url.text().strip() or "#")
            self.finished.emit()

    def set_value(self, value) -> None:
        index = self.combo.findData(value) if isinstance(value, dict) else -1
        if index >= 0:
            self.combo.setCurrentIndex(index)
            self.url.setVisible(False)
        else:
            self.combo.setCurrentIndex(self.combo.count() - 1)
            self.url.setVisible(True)
            if not self.url.hasFocus():
                self.url.setText("" if isinstance(value, dict) or value is None else str(value))


class CollapsibleGroup(QFrame):
    """A titled group of controls that folds away."""

    toggled = Signal(str, bool)

    def __init__(self, title: str, icon: str, pal: Palette, expanded: bool = True) -> None:
        super().__init__()
        self.title = title
        self.setObjectName("PropGroup")
        self.pal = pal
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.header = QToolButton()
        self.header.setObjectName("PropHeader")
        self.header.setText(title)
        self.header.setIcon(make_icon(icon, pal, 15))
        self.header.setIconSize(QSize(15, 15))
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.clicked.connect(self._toggle)
        self.state = QLabel()
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 8, 0)
        head.addWidget(self.header, 1)
        head.addWidget(self.state)
        column.addLayout(head)
        self.body = QWidget()
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(12, 2, 12, 12)
        self.rows.setSpacing(8)
        column.addWidget(self.body)
        self.set_expanded(expanded)

    def _toggle(self, checked: bool) -> None:
        self.set_expanded(checked)
        self.toggled.emit(self.title, checked)

    def set_expanded(self, expanded: bool) -> None:
        self.header.setChecked(expanded)
        self.body.setVisible(expanded)
        self.state.setPixmap(QPixmap(make_icon("chevron-down" if expanded else "chevron-right", self.pal, 13).pixmap(13, 13)))

    def add_row(self, text: str, widget: QWidget, tip: str = "") -> QLabel | None:
        caption = None
        if text:
            caption = QLabel(text)
            caption.setProperty("role", "field")
            if tip:
                caption.setToolTip(tip)
            self.rows.addWidget(caption)
        if tip:
            widget.setToolTip(tip)
        self.rows.addWidget(widget)
        return caption

