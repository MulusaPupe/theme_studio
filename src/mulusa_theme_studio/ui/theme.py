"""The studio's design system: one place for colour, spacing and type in the interface."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
UI_FONT = "Inter"
SPACE = (4, 8, 12, 16, 24, 32)
RADIUS = 8
ACCENT = "#E8B04B"


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    panel: str
    raised: str
    hover: str
    border: str
    text: str
    muted: str
    faint: str
    accent: str
    on_accent: str
    canvas: str
    danger: str


DARK = Palette("dark", "#0F1115", "#16191F", "#1E2229", "#262B34", "#2B313B", "#ECEEF2", "#A2A9B6", "#6F7785", ACCENT, "#17130A", "#0B0D10", "#F0705F")
LIGHT = Palette("light", "#F2F3F5", "#FFFFFF", "#F4F5F7", "#E9EBEF", "#DCDFE5", "#171A20", "#596170", "#6B7280", "#9A6B10", "#FFFFFF", "#DEE1E6", "#C43D2B")


def palette_for(name: str) -> Palette:
    return LIGHT if name == "light" else DARK


ICON_DIR = RESOURCES / "icons"
_design_fonts_loaded = False


def ensure_fonts_loaded() -> None:
    """Loads the bundled families once, so font menus can show each font in its own face, offline."""
    global _design_fonts_loaded
    if _design_fonts_loaded:
        return
    _design_fonts_loaded = True
    for family in json.loads((RESOURCES / "fonts" / "fonts.json").read_text(encoding="utf-8")):
        for item in family["files"]:
            if item["style"] == "normal":
                QFontDatabase.addApplicationFont(str(RESOURCES / "fonts" / item["file"]))


def load_fonts() -> None:
    QFontDatabase.addApplicationFont(str(RESOURCES / "fonts" / "inter-normal.woff2"))


@lru_cache(maxsize=512)
def icon_pixmap(name: str, color: str, size: int = 18, ratio: float = 2.0) -> QPixmap:
    path = RESOURCES / "icons" / f"{name}.svg"
    try:
        svg = path.read_text(encoding="utf-8").replace("currentColor", color)
    except OSError:
        svg = ""
    pixels = round(size * ratio)
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    if renderer.isValid():
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, pixels, pixels))
        painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


@lru_cache(maxsize=512)
def make_icon(name: str, pal: Palette, size: int = 18, *, active: bool = False) -> QIcon:
    icon = QIcon()
    normal = pal.accent if active else pal.text
    icon.addPixmap(icon_pixmap(name, normal, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(icon_pixmap(name, pal.accent, size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(icon_pixmap(name, pal.faint, size), QIcon.Mode.Disabled, QIcon.State.Off)
    return icon


def logo_pixmap(size: int = 28, ratio: float = 2.0) -> QPixmap:
    """The Mulusa mark: an M built from two rising bars on an ink tile."""
    pixels = round(size * ratio)
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(QRectF(0, 0, pixels, pixels), pixels * .24, pixels * .24)
    painter.setBrush(QColor("#17130A"))
    from PySide6.QtGui import QPainterPath

    u = pixels / 24
    path = QPainterPath()
    path.moveTo(5 * u, 18 * u)
    path.lineTo(5 * u, 6 * u)
    path.lineTo(8.6 * u, 6 * u)
    path.lineTo(12 * u, 11.4 * u)
    path.lineTo(15.4 * u, 6 * u)
    path.lineTo(19 * u, 6 * u)
    path.lineTo(19 * u, 18 * u)
    path.lineTo(15.8 * u, 18 * u)
    path.lineTo(15.8 * u, 11.6 * u)
    path.lineTo(12 * u, 17 * u)
    path.lineTo(8.2 * u, 11.6 * u)
    path.lineTo(8.2 * u, 18 * u)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def stylesheet(p: Palette) -> str:
    return f"""
* {{ font-family: '{UI_FONT}', 'Segoe UI', sans-serif; font-size: 13px; outline: none; }}
QMainWindow, QDialog {{ background: {p.window}; color: {p.text}; }}
QWidget {{ color: {p.text}; }}
QToolTip {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.border}; padding: 5px 7px; }}
QLabel {{ background: transparent; }}
QLabel[role="muted"] {{ color: {p.muted}; }}
QLabel[role="faint"] {{ color: {p.faint}; font-size: 12px; }}
QLabel[role="title"] {{ font-size: 15px; font-weight: 650; }}
QLabel[role="display"] {{ font-size: 34px; font-weight: 700; }}
QLabel[role="section"] {{ color: {p.muted}; font-size: 11px; font-weight: 650; }}
QLabel[role="brand"] {{ font-size: 12px; font-weight: 750; letter-spacing: 1px; }}
QLabel[role="pill"] {{ background: {p.raised}; color: {p.muted}; border-radius: 9px; padding: 2px 8px; font-size: 11px; }}
#TopBar {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
#SideBar, #Inspector {{ background: {p.panel}; }}
#SideBar {{ border-right: 1px solid {p.border}; }}
#Inspector {{ border-left: 1px solid {p.border}; }}
#Rail {{ background: {p.window}; border-right: 1px solid {p.border}; }}
#CanvasArea {{ background: {p.canvas}; }}
#CanvasBar {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
#StatusStrip {{ background: {p.panel}; border-top: 1px solid {p.border}; }}
#Notice {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS}px; }}
#WelcomeCard {{ background: {p.panel}; border: 1px solid {p.border}; border-radius: 12px; }}
#Separator {{ background: {p.border}; }}
#SelectionBar {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
#Crumb, #CrumbCurrent {{ background: transparent; border: none; padding: 4px 6px; font-weight: 500; border-radius: 5px; }}
#Crumb {{ color: {p.muted}; }}
#Crumb:hover {{ background: {p.hover}; color: {p.text}; }}
#CrumbCurrent {{ color: {p.accent}; font-weight: 650; }}
#SideTab {{ background: transparent; border: none; border-radius: 6px; padding: 5px 10px; font-weight: 550; color: {p.muted}; }}
#SideTab:hover {{ background: {p.hover}; color: {p.text}; }}
#SideTab:checked {{ background: {p.hover}; color: {p.accent}; }}
#ScopeTab {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 5px; padding: 3px 2px; font-size: 11px; color: {p.muted}; }}
#ScopeTab:hover {{ color: {p.text}; }}
#ScopeTab:checked {{ color: {p.accent}; border-color: {p.accent}; }}
#PropGroup {{ border: none; border-bottom: 1px solid {p.border}; background: transparent; }}
#PropHeader {{ background: transparent; border: none; padding: 9px 12px; font-weight: 600; text-align: left; }}
#PropHeader:hover {{ color: {p.accent}; }}
#Segment {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 5px; padding: 4px 7px; }}
#Segment:checked {{ border-color: {p.accent}; background: {p.hover}; color: {p.accent}; }}
#ColorSwatch, #ColorChip {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 5px; padding: 0; }}
#ColorChip:checked {{ border: 2px solid {p.accent}; }}
#MediaPreview {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 6px; }}
QLabel[role="field"] {{ color: {p.muted}; font-size: 12px; }}
#Tile {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS}px; }}
#Tile:hover {{ background: {p.hover}; border-color: {p.accent}; }}
QLabel[role="tile"] {{ font-size: 11px; }}
QLabel[role="notice"] {{ color: {p.accent}; font-size: 12px; font-weight: 550; }}
#Swatch {{ border: 1px solid {p.border}; border-radius: 5px; }}
#PreviewBanner {{ background: {p.raised}; border-bottom: 1px solid {p.border}; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 6px; }}
QToolButton:hover {{ background: {p.hover}; }}
QToolButton:checked {{ background: {p.hover}; color: {p.accent}; }}
QToolButton:disabled {{ color: {p.faint}; }}
QToolButton[rail="true"] {{ padding: 9px 2px 7px 2px; font-size: 10px; border-radius: 8px; }}
QToolButton[rail="true"]:checked {{ color: {p.accent}; }}
QPushButton {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: 6px; padding: 7px 12px; font-weight: 550; }}
QPushButton:hover {{ background: {p.hover}; }}
QPushButton:disabled {{ color: {p.faint}; border-color: {p.border}; background: transparent; }}
QPushButton[primary="true"] {{ background: {p.accent}; color: {p.on_accent}; border: 1px solid {p.accent}; font-weight: 650; }}
QPushButton[primary="true"]:hover {{ background: {p.accent}; border-color: {p.text}; }}
QPushButton[primary="true"]:disabled {{ background: {p.raised}; color: {p.faint}; border-color: {p.border}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.border}; border-radius: 6px; padding: 6px 8px; selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {p.accent}; }}
QDoubleSpinBox {{ padding: 6px 6px; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QComboBox QAbstractItemView {{ background: {p.raised}; border: 1px solid {p.border}; selection-background-color: {p.hover}; selection-color: {p.text}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QListWidget, QTreeWidget {{ background: transparent; border: none; outline: 0; }}
QTreeWidget {{ show-decoration-selected: 0; }}
QListWidget::item, QTreeWidget::item {{ padding: 5px 6px; border-radius: 5px; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {p.raised}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {p.hover}; color: {p.accent}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p.faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {p.faint}; border-radius: 4px; background: {p.raised}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QMessageBox {{ background: {p.window}; }}
"""


def icon_size(px: int = 18) -> QSize:
    return QSize(px, px)
