"""Global design settings: one place to change the whole site. Everything goes through the session."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QInputDialog, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ...core import design
from ...render.fonts import catalog
from ..fields import ChoiceField, CollapsibleGroup, ColorField, FontField, LengthField, NoWheelCombo, SliderField
from ..session import Session
from ..theme import Palette, ensure_fonts_loaded
from ..widgets import label

COLOR_NAMES = {"primary": "Primary", "secondary": "Secondary", "accent": "Accent", "background": "Background", "surface": "Surface", "text": "Text", "muted": "Muted text", "border": "Border"}


def palette_icon(colors: dict[str, str], width: int = 56, height: int = 16) -> QIcon:
    keys = ("primary", "secondary", "accent", "background", "text")
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    step = width / len(keys)
    for index, key in enumerate(keys):
        painter.fillRect(round(index * step), 0, round(step) + 1, height, QColor(colors[key]))
    painter.end()
    return QIcon(pixmap)


class DesignPanel(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        ensure_fonts_loaded()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        self.body = QWidget()
        scroll.setWidget(self.body)
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        self.empty = label("Open or create a project to change its design.", "muted", wrap=True)
        self.empty.setContentsMargins(14, 12, 14, 12)
        self.rows.addWidget(self.empty)
        self.syncs = []
        self.color_fields: dict[str, ColorField] = {}
        self.fields: dict[str, object] = {}
        self._build()
        self.rows.addStretch(1)
        session.documentChanged.connect(self.refresh)
        session.templatePreviewChanged.connect(self.refresh)
        session.projectChanged.connect(self.refresh)
        self.refresh()

    def _resolve(self, value) -> str:
        return str(value) if str(value or "").startswith("#") else ""

    def _group(self, title: str, icon: str) -> CollapsibleGroup:
        group = CollapsibleGroup(title, icon, self.pal)
        self.rows.addWidget(group)
        return group

    def _bind(self, group, name: str, text: str, field, read, label_: str, change, merge: bool = True, tip: str = "") -> None:
        group.add_row(text, field, tip)
        self.fields[name] = field

        def on_edit(value) -> None:
            if not self.session.edit_design(label_, lambda doc: change(doc, value), f"design:{name}" if merge else None):
                self.refresh()

        field.edited.connect(on_edit)
        field.finished.connect(self.session.end_gesture)
        self.syncs.append(lambda doc: field.set_value(read(doc)))

    def _build(self) -> None:
        # Palettes
        group = self._group("Colour palette", "palette")
        self.palette_box = NoWheelCombo()
        self.palette_box.setIconSize(QSize(56, 16))
        self.palette_box.activated.connect(self._apply_palette)
        group.add_row("Choose a palette", self.palette_box, "Every element using a site colour changes at once.")
        self.save_palette_btn = QPushButton("Save current colours as a palette")
        self.save_palette_btn.clicked.connect(self._save_palette)
        group.rows.addWidget(self.save_palette_btn)
        # Colours
        colors = self._group("Colours", "palette")
        for key, name in COLOR_NAMES.items():
            field = ColorField(self.pal, tokens=False, resolve=self._resolve, clearable=False)
            self.color_fields[key] = field
            self._bind(colors, f"color_{key}", name, field, lambda doc, k=key: doc["tokens"]["colors"][k], f"Change {name.lower()} colour",
                       lambda doc, value, k=key: design.set_color(doc, k, value if value else doc["tokens"]["colors"][k]))
        # Typography
        typography = self._group("Typography", "type")
        families = sorted(catalog())
        known = frozenset(families)
        for role, name in (("heading", "Heading font"), ("body", "Body font")):
            self._bind(typography, f"font_{role}", name, FontField(families, []), lambda doc, r=role: doc["tokens"]["fonts"][r], f"Change {name.lower()}",
                       lambda doc, value, r=role: design.set_font(doc, r, value, known), merge=False)
        settings = (
            ("base", "Base font size", SliderField(12, 24, .5, " px"), 17),
            ("ratio", "Heading scale", SliderField(1.05, 1.7, .01), 1.3),
            ("body_line", "Body line height", SliderField(1.1, 2.4, .05), 1.65),
        )
        for key, name, field, default in settings:
            self._bind(typography, f"type_{key}", name, field, lambda doc, k=key, d=default: doc["tokens"]["type"].get(k, d), f"Change {name.lower()}",
                       lambda doc, value, k=key: design.set_type(doc, k, value))
        weights = ChoiceField([(f"{w}", w) for w in (300, 400, 500, 600, 700, 800, 900)])
        self._bind(typography, "type_heading_weight", "Heading weight", weights, lambda doc: doc["tokens"]["type"].get("heading_weight", 700), "Change heading weight",
                   lambda doc, value: design.set_type(doc, "heading_weight", value), merge=False)
        # Shape
        shape = self._group("Corners", "shapes")
        for key, name in design.SHAPE_TOKENS.items():
            field = LengthField(self.pal, units=("px", "rem"), slider=(0, 48), placeholder="0")
            self._bind(shape, f"shape_{key}", name, field,
                       lambda doc, k=key: doc["tokens"]["shape"].get(k, doc["tokens"]["shape"].get("radius", "8px")), f"Change {name.lower()}",
                       lambda doc, value, k=key: design.set_shape(doc, k, value if value else "0"))
        # Spacing
        spacing = self._group("Spacing", "move-vertical")
        ranges = {"section": (0, 240), "gap": (0, 96), "width": (640, 1800), "space_s": (0, 48), "space_m": (0, 96), "space_l": (0, 200)}
        defaults = {"section": "96px", "gap": "28px", "width": "1180px", **design.SPACE_DEFAULTS}
        for key, name in design.SPACING_TOKENS.items():
            field = LengthField(self.pal, units=("px", "rem"), slider=ranges[key], placeholder=defaults[key])
            self._bind(spacing, f"space_{key}", name, field,
                       lambda doc, k=key: doc["tokens"]["spacing"].get(k, defaults[k]), f"Change {name.lower()}",
                       lambda doc, value, k=key: design.set_spacing(doc, k, value if value else defaults[k]))

    def _palettes(self, doc: dict) -> list[dict]:
        saved = [p for p in doc.get("palettes", []) if isinstance(p, dict)]
        return saved + list(design.BUILTIN_PALETTES)

    def _apply_palette(self, index: int) -> None:
        palette = self.palette_box.itemData(index)
        if palette:
            self.session.edit_design(f"Apply {palette['name']} palette", lambda doc: design.apply_palette(doc, palette))

    def _save_palette(self) -> None:
        name, ok = QInputDialog.getText(self, "Save palette", "Palette name")
        if ok and name.strip():
            self.session.edit_design("Save palette", lambda doc: design.save_palette(doc, name))

    def refresh(self) -> None:
        doc = self.session.document
        self.empty.setVisible(doc is None)
        for index in range(self.rows.count()):
            widget = self.rows.itemAt(index).widget()
            if isinstance(widget, CollapsibleGroup):
                widget.setVisible(doc is not None)
                widget.setEnabled(not self.session.read_only)
        if not doc:
            return
        self.palette_box.clear()
        self.palette_box.addItem("Choose…", None)
        for palette in self._palettes(doc):
            try:
                self.palette_box.addItem(palette_icon(palette["colors"]), palette["name"], palette)
            except KeyError:
                continue
        for sync in self.syncs:
            sync(doc)
