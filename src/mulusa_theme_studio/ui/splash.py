"""The start-up splash: the Mulusa mark, the name and real loading steps (fonts, templates, the canvas engine)."""
from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QSplashScreen

from .. import APP_NAME, ORG_NAME, TAGLINE, __version__
from .theme import ACCENT, UI_FONT, logo_pixmap

WIDTH, HEIGHT = 640, 380
MIN_SHOWN_MS = 900  # Long enough to read the name; never held longer than loading needs beyond this.


def splash_pixmap(progress: float, message: str, ratio: float = 1.0) -> QPixmap:
    """Draws one frame. ``progress`` runs from 0 to 1 and reflects steps actually finished."""
    pix = QPixmap(round(WIDTH * ratio), round(HEIGHT * ratio))
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    card = QRectF(0, 0, WIDTH, HEIGHT)

    base = QLinearGradient(0, 0, WIDTH, HEIGHT)
    base.setColorAt(0, QColor("#14171D"))
    base.setColorAt(1, QColor("#0B0D10"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(base)
    p.drawRoundedRect(card, 16, 16)

    # A soft amber glow, the same light the one-page templates use behind their glass cards.
    p.setClipRect(card)
    glow = QRadialGradient(QPointF(WIDTH * .82, HEIGHT * .08), 300)
    amber = QColor(ACCENT)
    amber.setAlpha(70)
    glow.setColorAt(0, amber)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(glow)
    p.drawRect(card)
    cool = QRadialGradient(QPointF(WIDTH * .05, HEIGHT * 1.05), 260)
    cool.setColorAt(0, QColor(70, 110, 170, 55))
    cool.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(cool)
    p.drawRect(card)
    p.setClipping(False)

    p.setPen(QColor(255, 255, 255, 22))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(card.adjusted(.5, .5, -.5, -.5), 16, 16)

    p.drawPixmap(48, 52, logo_pixmap(56, ratio))

    title = QFont(UI_FONT)
    title.setPixelSize(30)
    title.setWeight(QFont.Weight.Bold)
    title.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, .6)
    p.setFont(title)
    p.setPen(QColor("#ECEEF2"))
    p.drawText(QRectF(48, 140, WIDTH - 96, 44), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, APP_NAME)

    body = QFont(UI_FONT)
    body.setPixelSize(15)
    p.setFont(body)
    p.setPen(QColor("#A2A9B6"))
    p.drawText(QRectF(48, 184, WIDTH - 96, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, TAGLINE)

    # Progress: a thin track with the finished share filled in.
    track = QRectF(48, 286, WIDTH - 96, 4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 26))
    p.drawRoundedRect(track, 2, 2)
    done = max(0.0, min(1.0, progress))
    if done > 0:
        fill = QLinearGradient(track.left(), 0, track.right(), 0)
        fill.setColorAt(0, QColor("#C98A2A"))
        fill.setColorAt(1, QColor(ACCENT))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(track.left(), track.top(), max(4.0, track.width() * done), track.height()), 2, 2)

    small = QFont(UI_FONT)
    small.setPixelSize(12)
    p.setFont(small)
    p.setPen(QColor("#A2A9B6"))
    p.drawText(QRectF(48, 300, WIDTH - 96, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, message)
    p.setPen(QColor("#6F7785"))
    p.drawText(QRectF(48, 336, WIDTH - 96, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"by {ORG_NAME}")
    p.drawText(QRectF(48, 336, WIDTH - 96, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"Version {__version__}")
    p.end()
    return pix


class Splash(QSplashScreen):
    """Shown while the studio loads. ``step`` reports each loading stage as it finishes."""

    def __init__(self) -> None:
        self._ratio = QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 1.0
        super().__init__(splash_pixmap(0, "Starting…", self._ratio), Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAccessibleName(f"{APP_NAME} is starting")
        self.progress = 0.0
        self.message = "Starting…"
        self._clock = QElapsedTimer()
        self._clock.start()

    def step(self, progress: float, message: str) -> None:
        self.progress, self.message = progress, message
        self.setPixmap(splash_pixmap(progress, message, self._ratio))
        QApplication.processEvents()

    def remaining_ms(self) -> int:
        return max(0, MIN_SHOWN_MS - self._clock.elapsed())
