"""The right sidebar: the selected element's properties, and the site's design settings.

The form is built from the element's type, so only relevant controls appear. It reads the document
and asks the session for changes; it never changes the document itself.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from ...core import media as media_core
from ...core.design import contrast_ratio
from ...core import properties
from ...core.document import media_refs, node_label, site_pages, type_label
from ...core.properties import RATIOS, SHADOWS, VARIANTS, WIDTHS, box_values
from ...core.styles import TONES
from ...render.fonts import catalog
from ..fields import (
    BackgroundField, BoolField, BorderField, BoxField, ChoiceField, CollapsibleGroup, ColorField, DateTimeField, FontField, LengthField,
    LinkField, NoWheelCombo, SegmentField, SliderField, TextField,
)
from ..richtext import RichTextField
from ..session import Session
from ..theme import ICON_DIR, Palette, ensure_fonts_loaded, icon_pixmap, make_icon
from ..widgets import label, separator
from .design_panel import DesignPanel

SWATCHES = (("primary", "Primary"), ("secondary", "Secondary"), ("accent", "Accent"), ("background", "Background"), ("surface", "Surface"), ("text", "Text"))
TEXT_TYPES = {"heading", "text", "richtext", "button", "link", "faq_item", "contact_form"}
BOX_TYPES = {"section", "container", "columns", "row", "header", "footer", "button"}
GAP_TYPES = {"container", "columns", "row", "gallery"}
SCOPES = (("", "All devices"), ("desktop", "Desktop"), ("tablet", "Tablet"), ("mobile", "Mobile"))
SPACE_TOKENS = [("Small space", "$space-s"), ("Medium space", "$space-m"), ("Large space", "$space-l"), ("Element gap", "$gap"), ("Section spacing", "$section")]


def _tone_options(blank: str) -> list[tuple[str, object]]:
    return [(blank, None)] + [(t.capitalize(), t) for t in TONES]


def origin_text(device: str, scope: str) -> str:
    """What the editor says about a value, in the owner's words."""
    if device == scope:
        return f"Overridden for {scope}"
    return "Inherited from tablet" if device == "tablet" else "Inherited from desktop"


class Inspector(QWidget):
    def __init__(self, session: Session, pal: Palette) -> None:
        super().__init__()
        self.session = session
        self.pal = pal
        self.setObjectName("Inspector")
        self.setFixedWidth(316)
        self.syncs: list[Callable[[dict], None]] = []
        self.fields: dict[str, object] = {}  # Named controls, for reading the form and for tests.
        self.origins: dict[str, QLabel] = {}  # Where each style on this device comes from.
        self.groups: dict[str, CollapsibleGroup] = {}
        self._collapsed: set[str] = {"Borders and effects"}
        self._built_for = ""
        self._built_scope = ""
        ensure_fonts_loaded()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        tabs = QHBoxLayout()
        tabs.setContentsMargins(10, 8, 10, 8)
        tabs.setSpacing(4)
        self.tab_group = QButtonGroup(self, exclusive=True)
        self.tab_buttons = []
        for index, text in enumerate(("Properties", "Site design")):
            button = QPushButton(text)
            button.setObjectName("SideTab")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, i=index: self.show_tab(i))
            self.tab_group.addButton(button)
            self.tab_buttons.append(button)
            tabs.addWidget(button)
        outer.addLayout(tabs)
        outer.addWidget(separator(False))
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # Properties tab
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        top = QVBoxLayout()
        top.setContentsMargins(14, 10, 14, 8)
        top.setSpacing(2)
        self.sel_name = label("Nothing selected", "", wrap=True)
        self.sel_name.setStyleSheet("font-weight: 600;")
        self.sel_type = label("Click an element on the canvas.", "muted", wrap=True)
        self.sel_details = label("", "faint", wrap=True)
        top.addWidget(self.sel_name)
        top.addWidget(self.sel_type)
        top.addWidget(self.sel_details)
        column.addLayout(top)
        self.scope_bar = self._build_scope_bar()
        column.addWidget(self.scope_bar)
        self.read_only_note = label("This is a template preview. Create a project from it to edit.", "notice", wrap=True)
        self.read_only_note.setContentsMargins(14, 0, 14, 8)
        column.addWidget(self.read_only_note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        column.addWidget(self.scroll, 1)
        self.form_holder = QWidget()
        self.form = QVBoxLayout(self.form_holder)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(0)
        self.scroll.setWidget(self.form_holder)
        self.summary = self._build_summary()
        self.form.addWidget(self.summary)
        self.form_widgets = QWidget()
        self.form_rows = QVBoxLayout(self.form_widgets)
        self.form_rows.setContentsMargins(0, 0, 0, 0)
        self.form_rows.setSpacing(0)
        self.form.addWidget(self.form_widgets)
        self.form.addStretch(1)
        self.stack.addWidget(page)

        self.design = DesignPanel(session, pal)
        self.stack.addWidget(self.design)
        self.show_tab(0)

        session.documentChanged.connect(self.refresh)
        session.selectionChanged.connect(self.refresh)
        session.scopeChanged.connect(self._on_scope)
        session.templatePreviewChanged.connect(self.refresh)
        session.projectChanged.connect(self.refresh)
        self.refresh()

    # Shell ---------------------------------------------------------------------
    def show_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.tab_buttons[index].setChecked(True)

    def _build_scope_bar(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(14, 0, 14, 8)
        column.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.scope_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self, exclusive=True)
        for scope, text in SCOPES:
            button = QPushButton(text)
            button.setObjectName("ScopeTab")
            button.setCheckable(True)
            button.setToolTip("Styles here apply to every device." if not scope else f"Styles here apply on {text.lower()} only, and leave other devices alone.")
            button.clicked.connect(lambda _=False, s=scope: self.session.set_edit_scope(s))
            group.addButton(button)
            self.scope_buttons[scope] = button
            row.addWidget(button)
        self.scope_buttons[""].setChecked(True)
        column.addLayout(row)
        self.scope_note = label("", "faint", wrap=True)
        column.addWidget(self.scope_note)
        self.clear_scope = QPushButton("Reset everything on this device")
        self.clear_scope.clicked.connect(self._clear_scope)
        column.addWidget(self.clear_scope)
        return holder

    def _clear_scope(self) -> None:
        if self.session.selected_id:
            self.session.reset_device(self.session.selected_id)

    def _build_summary(self) -> QWidget:
        """What shows when nothing is selected: the project at a glance, and the way to change it."""
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(14, 6, 14, 14)
        column.setSpacing(10)
        self.project_info = label("", "muted", wrap=True)
        column.addWidget(self.project_info)
        column.addWidget(separator(False))
        column.addWidget(label("GLOBAL DESIGN", "section"))
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(6)
        self.swatch_widgets: dict[str, tuple[QFrame, object]] = {}
        for row, (key, name) in enumerate(SWATCHES):
            chip = QFrame()
            chip.setObjectName("Swatch")
            chip.setFixedSize(20, 20)
            value = label("", "faint")
            self.grid.addWidget(chip, row, 0)
            self.grid.addWidget(label(name), row, 1)
            self.grid.addWidget(value, row, 2)
            self.swatch_widgets[key] = (chip, value)
        column.addLayout(self.grid)
        self.fonts = label("", "muted", wrap=True)
        self.shape = label("", "muted", wrap=True)
        column.addWidget(self.fonts)
        column.addWidget(self.shape)
        self.open_design = QPushButton("Edit site design")
        self.open_design.setToolTip("Colours, fonts, corners and spacing for the whole site")
        self.open_design.clicked.connect(lambda: self.show_tab(1))
        column.addWidget(self.open_design)
        return holder

    # Refresh -------------------------------------------------------------------
    def _on_scope(self) -> None:
        scope = self.session.edit_scope
        self.scope_buttons[scope].setChecked(True)
        self._built_for = ""
        self.refresh()

    def refresh(self) -> None:
        node = self.session.selected_node
        doc = self.session.document
        read_only = self.session.read_only
        self.read_only_note.setVisible(bool(doc) and read_only)
        self.scope_bar.setVisible(bool(node) and not read_only)
        self.summary.setVisible(not node)
        self.form_widgets.setVisible(bool(node))
        self.form_widgets.setEnabled(not read_only)
        if node:
            self.sel_name.setText(node_label(node))
            self.sel_type.setText(f"Type: {type_label(node)}")
            self.sel_details.setText("")
            key = f"{node['id']}:{node.get('type')}:{read_only}"
            if key != self._built_for:
                self._build_form(node)
                self._built_for = key
            self._sync(node)
        else:
            self._clear_form()
            self.sel_name.setText("Nothing selected")
            self.sel_type.setText("Click an element on the canvas.")
            self.sel_details.setText("")
        self._refresh_summary(doc)
        self._refresh_scope_note(node)

    def _refresh_scope_note(self, node: dict | None) -> None:
        scope = self.session.edit_scope
        has = bool(node and (node.get("responsive") or {}).get(scope)) if scope else False
        self.clear_scope.setVisible(has)
        self.scope_note.setVisible(bool(scope))
        if scope:
            self.scope_note.setText(f"Changes here apply on {scope} only. Other devices keep their styles. Text and images are shared by all devices.")

    def _refresh_summary(self, doc: dict | None) -> None:
        for key, (chip, value) in self.swatch_widgets.items():
            color = doc["tokens"]["colors"].get(key, "") if doc else ""
            chip.setStyleSheet(f"background: {color};" if color else "")
            value.setText(color.upper())
        self.open_design.setVisible(bool(doc))
        if doc:
            fonts = doc["tokens"]["fonts"]
            shape = doc["tokens"].get("shape", {})
            spacing = doc["tokens"].get("spacing", {})
            self.fonts.setText(f"Headings: {fonts['heading']}\nBody: {fonts['body']}")
            self.shape.setText(f"Corners: {shape.get('radius', '-')}\nContent width: {spacing.get('width', '-')}\nSection spacing: {spacing.get('section', '-')}")
            refs = list(media_refs(doc))
            placeholders = sum(1 for r in refs if r.get("kind") == "placeholder")
            self.project_info.setText(
                f"{doc['meta'].get('name', '')}: {len(doc['pages'])} pages, {len(doc['media'].get('assets', []))} uploaded images, "
                f"{placeholders} placeholders still to replace.\n\nClick any element on the canvas to edit it."
            )
        else:
            self.fonts.setText("")
            self.shape.setText("")
            self.project_info.setText("Open a project or preview a template to see its design here.")

    def _clear_form(self) -> None:
        self.syncs = []
        self.fields = {}
        self.origins = {}
        self.groups = {}
        self._built_for = ""
        while self.form_rows.count():
            widget = self.form_rows.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _sync(self, node: dict) -> None:
        for sync in self.syncs:
            sync(node)

    # Reading and writing -------------------------------------------------------
    def _style_value(self, node: dict, prop: str):
        return properties.style_origin(node, prop, self.session.edit_scope)[0]

    def _origin_row(self, group, prop: str, *, box: bool = False) -> None:
        """On a device, says where the value above comes from and offers the way back to it."""
        scope = self.session.edit_scope
        if not scope:
            return
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 4)
        row.setSpacing(6)
        note = label("", "faint")
        reset = QPushButton("Reset")
        reset.setToolTip("Stop overriding this, and use the inherited value.")
        row.addWidget(note, 1)
        row.addWidget(reset)
        group.add_row("", holder)
        self.origins[prop] = note
        act = self.session.reset_box if box else self.session.reset_style
        reset.clicked.connect(lambda: act(self._node_id(), prop))

        def sync(node: dict) -> None:
            if box:
                device = next((d for d in properties._FALLBACK[scope] if any(key == prop or key.startswith(f"{prop}_") for key in ((node.get("responsive") or {}).get(d) or {}).get("style", {}))), "")
            else:
                device = properties.style_origin(node, prop, scope)[1]
            note.setText(origin_text(device, scope))
            reset.setVisible(device == scope)

        self.syncs.append(sync)

    def _resolve_color(self, value) -> str:
        """Turns $primary into its current colour, for showing in a swatch."""
        text = "" if value is None else str(value)
        doc = self.session.document
        if text.startswith("$") and doc:
            colors = doc["tokens"]["colors"]
            aliases = {"$c-text": "text", "$c-muted": "muted", "$c-border": "border", "$c-card": "surface", "$c-accent": "accent", "$c-bg": "background"}
            return colors.get(aliases.get(text, text[1:]), "")
        return text if text.startswith("#") else ""

    def _node_id(self) -> str:
        return self.session.selected_id

    def _group(self, title: str, icon: str) -> CollapsibleGroup:
        group = CollapsibleGroup(title, icon, self.pal, title not in self._collapsed)
        group.toggled.connect(self._remember)
        self.form_rows.addWidget(group)
        self.groups[title] = group
        return group

    def _remember(self, title: str, expanded: bool) -> None:
        (self._collapsed.discard if expanded else self._collapsed.add)(title)

    def _bind(self, group: CollapsibleGroup, name: str, text: str, field, read, write, tip: str = "") -> None:
        group.add_row(text, field, tip)
        self.fields[name] = field

        def on_edit(value) -> None:
            node_id = self._node_id()
            ok = write(node_id, value)
            if not ok:
                # Refused or unchanged: the control goes back to what the document holds.
                node = self.session.selected_node
                if node:
                    field.set_value(read(node))

        field.edited.connect(on_edit)
        field.finished.connect(self.session.end_gesture)
        self.syncs.append(lambda node: field.set_value(read(node)))

    def _prop(self, group, key: str, text: str, field, *, default=None, tip: str = "", blank_none: bool = False) -> None:
        def read(node):
            return node.get("props", {}).get(key, default)

        def write(node_id, value):
            return self.session.edit_prop(node_id, key, None if blank_none and value in ("", None) else value)

        self._bind(group, key, text, field, read, write, tip)

    def _style(self, group, prop: str, text: str, field, tip: str = "") -> None:
        self._bind(group, prop, text, field, lambda node: self._style_value(node, prop),
                   lambda node_id, value: self.session.edit_style(node_id, prop, value), tip)
        self._origin_row(group, prop)

    def _length(self, **options) -> LengthField:
        return LengthField(self.pal, **options)

    def _color(self) -> ColorField:
        return ColorField(self.pal, resolve=self._resolve_color)

    # The form ------------------------------------------------------------------
    def _build_form(self, node: dict) -> None:
        self._clear_form()
        kind = node.get("type")
        if not self.session.edit_scope:
            self._content_group(node, kind)
        else:
            self._device_group(node, kind)
        if kind in TEXT_TYPES or (kind == "post_field" and node.get("props", {}).get("field") != "featured_image"):
            self._typography_group(kind)
        elif kind == "icon":
            group = self._group("Icon style", "star")
            self._style(group, "font_size", "Size", self._length(slider=(10, 160)))
            self._style(group, "color", "Colour", self._color())
        if kind not in ("divider",):
            self._background_group(node, kind)
        self._layout_group(kind)
        self._effects_group()
        self.form_rows.addStretch(1)

    def _device_group(self, node: dict, kind: str) -> None:
        scope = self.session.edit_scope
        group = self._group(f"On {scope}", "smartphone")
        hide = BoolField(f"Hide this on {scope}")
        self._bind(group, "hidden", "", hide, lambda current: bool(((current.get("responsive") or {}).get(scope) or {}).get("hidden")),
                   lambda node_id, value: self.session.set_device_hidden(node_id, bool(value)), "It stays in the design and on other devices.")
        if kind in ("columns", "gallery"):
            field = ChoiceField([("Automatic", None)] + [(str(i), i) for i in range(1, 7)])
            self._bind(group, "device_columns", "Columns", field, lambda current: (((current.get("responsive") or {}).get(scope) or {}).get("props") or {}).get("columns"),
                       lambda node_id, value: self.session.set_device_columns(node_id, value), "Automatic stacks columns on phones and reduces wide rows on tablets.")
        if kind in ("image", "post_field"):
            self._style(group, "object_fit", "Image fit", ChoiceField([("From the design", None), ("Fill the frame", "cover"), ("Show it all", "contain")]))
            self._style(group, "height", "Image height", self._length(units=("px", "vh", "rem"), placeholder="Auto"))
        if kind in ("row", "container"):
            self._style(group, "flex_direction", "Direction", ChoiceField([("From the design", None), ("In a row", "row"), ("Stacked", "column")]))
            self._style(group, "justify_content", "Alignment", ChoiceField([("From the design", None), ("Start", "flex-start"), ("Centre", "center"), ("End", "flex-end"), ("Spread out", "space-between")]))

    def _query_group(self, node: dict) -> None:
        def source(key, default):
            return lambda current: (current.get("props", {}).get("source") or {}).get(key, default)

        def setting(key, default):
            return lambda current: current.get("props", {}).get(key, default)

        def write(key, convert=lambda value: value):
            return lambda node_id, value: self.session.edit_query(node_id, **{key: convert(value)})

        group = self._group("Posts shown", "newspaper")
        group.add_row("", label("Real posts appear on the published site. The cards here are samples, so you can design them.", "faint", wrap=True))
        self._bind(group, "count", "Number of posts", ChoiceField([(str(i), i) for i in range(1, 25)]), source("count", 3), write("count"))
        orders = [("Newest first", ("date", "desc")), ("Oldest first", ("date", "asc")), ("Title, A to Z", ("title", "asc")), ("Title, Z to A", ("title", "desc")), ("Recently updated", ("modified", "desc"))]
        field = ChoiceField([(text, f"{by}:{way}") for text, (by, way) in orders])
        self._bind(group, "order", "Sort", field, lambda current: f"{(current['props'].get('source') or {}).get('order_by', 'date')}:{(current['props'].get('source') or {}).get('order', 'desc')}",
                   lambda node_id, value: self.session.edit_query(node_id, order_by=value.split(":")[0], order=value.split(":")[1]))
        self._bind(group, "categories", "Only these categories", TextField(placeholder="All categories, or names with commas"),
                   lambda current: ", ".join((current["props"].get("source") or {}).get("categories", [])),
                   write("categories", lambda value: [part.strip() for part in str(value or "").split(",") if part.strip()]))
        self._bind(group, "follow_page", "", BoolField("Follow the archive being viewed"), source("follow_page", False), write("follow_page"), "For an archive template: shows the category, tag or date the visitor opened.")
        self._bind(group, "pagination", "", BoolField("Show page numbers"), setting("pagination", False), write("pagination"))
        look = self._group("Posts layout", "columns-3")
        self._bind(look, "layout", "Arrangement", ChoiceField([("Grid", "grid"), ("List", "list")]), setting("layout", "grid"), write("layout"))
        self._bind(look, "columns", "Columns", ChoiceField([(str(i), i) for i in range(1, 7)]), setting("columns", 3), write("columns"), "Grids only. Reduced automatically on smaller screens.")
        self._bind(look, "image_position", "Image", ChoiceField([("Above the text", "top"), ("Beside the text", "left")]), setting("image_position", "top"), write("image_position"))
        shown = self._group("Details on each post", "list-checks")
        for key, text in (("featured_image", "Featured image"), ("excerpt", "Excerpt"), ("date", "Date"), ("author", "Author"), ("categories", "Categories"), ("tags", "Tags"), ("read_more", "Read more link")):
            def toggle(node_id, value, k=key):
                hidden = set(self.session.selected_node["props"].get("hide") or ())
                (hidden.discard if value else hidden.add)(k)
                return self.session.edit_query(node_id, hide=sorted(hidden))

            self._bind(shown, f"show_{key}", "", BoolField(text), lambda current, k=key: k not in (current["props"].get("hide") or ()), toggle)
        shown.add_row("", label("A detail only shows if the card contains it. Add more from Components when designing the Single post template, or edit the card here.", "faint", wrap=True))

    def _content_group(self, node: dict, kind: str) -> None:
        if kind == "image":
            self._image_group(node)
            return
        if kind == "query":
            self._query_group(node)
            return
        if kind not in ("heading", "text", "richtext", "button", "link", "icon", "faq_item", "contact_form", "header", "columns", "container", "video", "gallery",
                        "illustration", "countdown", "progress", "section"):
            return
        group = self._group("Motion" if kind == "section" else "Content", "sparkles" if kind == "section" else "type")
        if kind == "section":
            self._prop(group, "ambient", "Living background", ChoiceField([("None", None), ("Aurora glow", "aurora"), ("Tech grid scan", "grid"), ("Twinkling stars", "stars"), ("Moving waves", "waves")]),
                       blank_none=True, tip="A gentle animated layer behind the content. Visitors who turn off animations see it still.")
            group.add_row("", label("Pairs well with a glass card: select a container and set Glass blur under Borders and effects.", "faint", wrap=True))
        elif kind == "illustration":
            from ...render.illustrations import ILLUSTRATIONS
            options = [(f"{item.group}: {item.title}", name) for name, item in sorted(ILLUSTRATIONS.items(), key=lambda kv: (kv[1].group, kv[1].title))]
            self._prop(group, "name", "Illustration", ChoiceField(options), default="gears")
            self._prop(group, "animate", "", BoolField("Animate"), default=True, tip="Visitors who turn off animations always see it still.")
            self._prop(group, "aria_label", "Accessible label", TextField(placeholder="Decorative if empty"), blank_none=True)
            group.add_row("", label("It takes the site's colours and adapts to dark and photo sections. Set its size with Width under Layout.", "faint", wrap=True))
        elif kind == "countdown":
            from ...core.properties import UTC_OFFSETS
            self._prop(group, "target", "Counts down to", DateTimeField())
            offsets = sorted(UTC_OFFSETS, key=lambda o: (1 if o[0] == "+" else -1) * (int(o[1:3]) * 60 + int(o[4:6])))
            self._prop(group, "utc_offset", "Time zone", ChoiceField([(f"UTC{o}" if o != "+00:00" else "UTC", o) for o in offsets]), default="+00:00",
                       tip="The time zone of the date above. Zambia, for example, is UTC+02:00.")
            self._prop(group, "show_seconds", "", BoolField("Show seconds"), default=True)
            self._prop(group, "done_text", "When it ends", TextField(placeholder="We are live."), blank_none=True)
            for key, word in (("days", "Days"), ("hours", "Hours"), ("minutes", "Minutes"), ("seconds", "Seconds")):
                self._prop(group, f"label_{key}", f"Label: {word.lower()}", TextField(placeholder=word), blank_none=True)
            group.add_row("", label("It ticks live on the published site and on the canvas. The date is also written under it.", "faint", wrap=True))
        elif kind == "progress":
            self._prop(group, "mode", "Kind", ChoiceField([("Loading (keeps moving)", "loading"), ("A set amount", "value")]), default="loading")
            self._prop(group, "value", "Amount", SliderField(0, 100, 1, "%"), default=60)
            self._prop(group, "label", "Label", TextField(placeholder="Optional"), blank_none=True)
            self._prop(group, "show_value", "", BoolField("Show the percentage"), default=True)
        elif kind == "heading":
            self._prop(group, "text", "Heading text", TextField(True))
            self._prop(group, "level", "Level", ChoiceField([(f"H{i}", i) for i in range(1, 7)]), default=2, tip="H1 is the page's main title. Use one on each page, then H2 and H3 for structure.")
        elif kind == "text":
            self._prop(group, "text", "Paragraph", TextField(True))
            self._prop(group, "muted", "", BoolField("Softer colour for secondary text"), default=False)
        elif kind == "richtext":
            self._prop(group, "html", "Text", RichTextField(self.pal))
        elif kind in ("button", "link"):
            self._prop(group, "label", "Label", TextField())
            field = LinkField()
            field.set_pages([(p.get("title", p["id"]), p["id"]) for p in site_pages(self.session.document)])
            self._prop(group, "href", "Destination", field, default="#")
            if kind == "button":
                self._prop(group, "variant", "Style", ChoiceField([(v.capitalize(), v) for v in VARIANTS]), default="primary")
            else:
                self._prop(group, "arrow", "", BoolField("Show an arrow"), default=False)
            self._prop(group, "aria_label", "Accessible label", TextField(placeholder="Optional"), tip="Read by screen readers instead of the label, when the label alone is not clear.", blank_none=True)
        elif kind == "icon":
            names = sorted(path.stem for path in ICON_DIR.glob("*.svg"))
            self._prop(group, "name", "Icon", ChoiceField([(n.replace("-", " ").capitalize(), n) for n in names]), default="star")
            self._prop(group, "aria_label", "Accessible label", TextField(placeholder="Decorative if empty"), blank_none=True)
        elif kind == "faq_item":
            self._prop(group, "question", "Question", TextField())
            self._prop(group, "answer", "Answer", TextField(True))
            self._prop(group, "open", "", BoolField("Open by default"), default=False)
        elif kind == "contact_form":
            self._prop(group, "submit", "Button text", TextField())
            for index, item in enumerate(node.get("props", {}).get("fields", [])):
                self._form_field_row(group, index, item)
        elif kind == "header":
            self._prop(group, "brand", "Site title", TextField())
            self._media_row(group, node, "logo", "Logo")
            self.fields["logo_crop"].hide()
            self._prop(group, "layout", "Layout", ChoiceField([("Classic", "classic"), ("Menu, title, button", "split"), ("Centred", "centered"), ("Masthead", "masthead"), ("Minimal", "minimal")]), default="classic")
            self._prop(group, "sticky", "", BoolField("Stay at the top when scrolling"), default=False)
            self._prop(group, "mobile_menu", "Menu on small screens", ChoiceField([("Behind a menu button", "burger"), ("Always visible", "inline")]), default="burger", tip="Below 860 px wide.")
            group.add_row("", label("Menu links are edited in the Pages tab, under Menu.", "faint", wrap=True))
            cta = self._group("Header button", "mouse-pointer-click")
            def read_cta(key, default=""):
                return lambda current: (current["props"].get("cta") or {}).get(key, default)
            def write_cta(key):
                def write(node_id, value):
                    current = dict(self.session.selected_node["props"].get("cta") or {"label": "", "href": "#"})
                    current[key] = value
                    return self.session.edit_prop(node_id, "cta", current if current.get("label") else None)
                return write
            self._bind(cta, "cta_label", "Label", TextField(placeholder="No button"), read_cta("label"), write_cta("label"))
            cta_target = LinkField()
            cta_target.set_pages([(p["title"], p["id"]) for p in site_pages(self.session.document)])
            self._bind(cta, "cta_href", "Destination", cta_target, read_cta("href", "#"), write_cta("href"))
        elif kind == "columns":
            self._prop(group, "columns", "Columns", ChoiceField([(str(i), i) for i in range(1, 7)]), default=2, tip="How many columns on a desktop. They stack on phones.")
            self._prop(group, "width", "Width", ChoiceField([("From the design", None)] + [(w.capitalize(), w) for w in WIDTHS]), blank_none=True)
        elif kind == "container":
            self._prop(group, "width", "Width", ChoiceField([("From the design", None)] + [(w.capitalize(), w) for w in WIDTHS]), blank_none=True)
        elif kind == "video":
            self._prop(group, "url", "Video link", TextField(placeholder="https://"), default="")
            self._prop(group, "title", "Title", TextField())
            self._media_row(group, node, "poster", "Poster image")
        elif kind == "gallery":
            self._prop(group, "columns", "Columns", ChoiceField([(str(i), i) for i in range(1, 7)]), default=3)
            self._gallery_rows(group, node)

    def _form_field_row(self, group, index: int, item: dict) -> None:
        field = TextField()
        field.set_value(item.get("label", ""))
        group.add_row(f"Field {index + 1} label", field)

        def write(value, i=index):
            node = self.session.selected_node
            if not node:
                return
            fields = [dict(f) for f in node["props"].get("fields", [])]
            if i < len(fields):
                fields[i]["label"] = value
                self.session.edit_prop(node["id"], "fields", fields, "Change form")

        field.edited.connect(write)
        field.finished.connect(self.session.end_gesture)
        self.syncs.append(lambda node, i=index: field.set_value((node["props"].get("fields") or [{}] * (i + 1))[i].get("label", "") if i < len(node["props"].get("fields") or []) else ""))

    def _typography_group(self, kind: str) -> None:
        group = self._group("Typography", "type")
        families = sorted(catalog())
        self._style(group, "font_family", "Font", FontField(families, [("From the design", None), ("Site heading font", "$font-heading"), ("Site body font", "$font-body")]))
        self._style(group, "font_size", "Size", self._length(slider=(8, 120), placeholder="From the design"))
        weights = [("From the design", None)] + [(f"{w}  {n}", str(w)) for w, n in ((300, "Light"), (400, "Regular"), (500, "Medium"), (600, "Semibold"), (700, "Bold"), (800, "Extra bold"), (900, "Black"))]
        self._style(group, "font_weight", "Weight", ChoiceField(weights))
        self._style(group, "color", "Colour", self._color())
        self._style(group, "line_height", "Line height", SliderField(.8, 3, .05, empty="Auto"), "Drag fully left to use the value from the design.")
        self._style(group, "letter_spacing", "Letter spacing", self._length(units=("px", "em"), placeholder="Normal"))
        self._style(group, "text_align", "Alignment", SegmentField([("align-left", "left", "Left"), ("align-center", "center", "Centre"), ("align-right", "right", "Right"), ("align-justify", "justify", "Justify")], self.pal))
        self._style(group, "text_transform", "Letter case", ChoiceField([("From the design", None), ("As typed", "none"), ("UPPERCASE", "uppercase"), ("lowercase", "lowercase"), ("Capitalised", "capitalize")]))
        self._style(group, "text_decoration", "Decoration", ChoiceField([("None", None), ("Underline", "underline"), ("Strikethrough", "line-through")]))
        self._style(group, "font_style", "Style", ChoiceField([("Upright", None), ("Italic", "italic")]))

    def _background_group(self, node: dict, kind: str) -> None:
        title = "Colours and background"
        group = self._group(title, "palette")
        if kind in ("section", "container", "header", "footer") and not self.session.edit_scope:
            options = _tone_options("From the design" if kind != "section" else "Default")
            tone = ChoiceField(options)
            self._prop(group, "tone", "Tone", tone, blank_none=True)

            def sync_tone(current: dict) -> None:
                # A photo can arrive or leave while this form stays open, including through undo.
                background = current.get("props", {}).get("background")
                has_photo = kind == "section" and isinstance(background, dict) and isinstance(background.get("media"), dict)
                tone.combo.setEnabled(not has_photo)
                tone.combo.setToolTip("This section has a background image, so it keeps the image tone." if has_photo else "A tone sets the background and keeps text inside it readable.")

            self.syncs.append(sync_tone)
        if kind == "section" and not self.session.edit_scope:
            self._media_row(group, node, "background", "Background image")
            self._overlay_rows(group, node)
        self._style(group, "background", "Background", BackgroundField(self.pal, resolve=self._resolve_color))
        self.contrast_note = label("", "notice", wrap=True)
        group.rows.addWidget(self.contrast_note)
        self.syncs.append(self._sync_contrast)

    def _sync_contrast(self, node: dict) -> None:
        doc = self.session.document
        background = self._resolve_color(self._style_value(node, "background"))
        tone = node.get("props", {}).get("tone") or "default"
        colors = doc["tokens"]["colors"]
        text = {"default": colors["text"], "surface": colors["text"], "inverse": colors["background"], "primary": colors["on_primary"], "accent": colors["on_accent"], "image": "#ffffff"}.get(tone, colors["text"])
        low = bool(background) and node.get("type") in ("section", "container") and contrast_ratio(background, text) < 4.5
        self.contrast_note.setVisible(low)
        if low:
            self.contrast_note.setText(f"Text may be hard to read here ({contrast_ratio(background, text):.1f}:1). Try another tone or a different background.")

    def _overlay_rows(self, group, node: dict) -> None:
        strength = SliderField(0, 95, 5, "%", factor=100)
        group.add_row("Overlay strength", strength, "A dark wash over the image, so text stays readable.")
        self.fields["overlay"] = strength
        strength.edited.connect(lambda value: self.session.edit_overlay(self._node_id(), "#000000", float(value)))
        strength.finished.connect(self.session.end_gesture)

        def sync(current: dict) -> None:
            background = current.get("props", {}).get("background")
            overlay = str(background.get("overlay", "")) if isinstance(background, dict) else ""
            has_photo = isinstance(background, dict) and isinstance(background.get("media"), dict)
            strength.setEnabled(has_photo)
            match = re.match(r"^rgba\(\d+,\d+,\d+,([\d.]+)\)$", overlay)
            strength.set_value(float(match.group(1)) if match else 0)

        self.syncs.append(sync)

    def _layout_group(self, kind: str) -> None:
        group = self._group("Spacing and size", "move-vertical")
        margin = BoxField()
        group.add_row("Margin", margin, "Space outside the element.")
        self._bind_box(margin, "margin")
        self._origin_row(group, "margin", box=True)
        if kind in BOX_TYPES or kind in ("heading", "text", "richtext", "image", "link", "contact_form", "faq_item", "gallery", "video"):
            padding = BoxField()
            group.add_row("Padding", padding, "Space inside the element.")
            self._bind_box(padding, "padding")
            self._origin_row(group, "padding", box=True)
        if kind in GAP_TYPES:
            self._style(group, "gap", "Gap", self._length(units=("px", "rem"), tokens=SPACE_TOKENS, slider=(0, 120), placeholder="From the design"), "Space between the items inside.")
        self._style(group, "width", "Width", self._length(units=("px", "%", "rem", "vw"), placeholder="Auto"))
        self._style(group, "max_width", "Maximum width", self._length(units=("px", "%", "rem", "ch"), placeholder="None"))
        title = "Section height" if kind == "section" else "Minimum height"
        self._style(group, "min_height", title, self._length(units=("px", "vh", "rem"), placeholder="Auto", slider=(0, 1000) if kind == "section" else None), "The element grows beyond this if its content needs more room.")
        if kind == "image":
            self._style(group, "height", "Height", self._length(units=("px", "vh", "rem"), placeholder="Auto"))
        if kind in ("button", "link", "image", "icon", "heading", "text"):
            self._style(group, "align_self", "Position in its parent", ChoiceField([("From the design", None), ("Start", "flex-start"), ("Centre", "center"), ("End", "flex-end"), ("Full width", "stretch")]))

    def _bind_box(self, field: BoxField, family: str) -> None:
        self.fields[family] = field
        field.sideEdited.connect(lambda side, value: self.session.edit_box(self._node_id(), family, side, value))
        field.finished.connect(self.session.end_gesture)

        def sync(node: dict) -> None:
            scope = self.session.edit_scope
            style = (node.get("style") or {})
            values = box_values(style, family)
            if scope:
                override = ((node.get("responsive") or {}).get(scope) or {}).get("style") or {}
                values.update({k: v for k, v in box_values(override, family).items() if v})
            field.set_values(values)

        self.syncs.append(sync)

    def _effects_group(self) -> None:
        group = self._group("Borders and effects", "shapes")
        self._style(group, "border", "Border", BorderField(self.pal, resolve=self._resolve_color))
        self._style(group, "border_radius", "Corner radius", self._length(units=("px", "%", "rem"), slider=(0, 80), placeholder="From the design", tokens=[("Default corners", "$radius"), ("Card corners", "$card-radius")]))
        shadow = ChoiceField([("None", None), ("Soft", SHADOWS["soft"]), ("Medium", SHADOWS["medium"]), ("Strong", SHADOWS["strong"])])
        self._style(group, "box_shadow", "Shadow", shadow)
        self._bind(group, "opacity", "Opacity", SliderField(0, 100, 1, "%", factor=100),
                   lambda node: self._style_value(node, "opacity") if self._style_value(node, "opacity") is not None else 1,
                   lambda node_id, value: self.session.edit_style(node_id, "opacity", None if float(value) >= 1 else str(value)))

        def glass_value(node):
            match = re.search(r"blur\((\d+)", str(self._style_value(node, "backdrop_filter") or ""))
            return int(match.group(1)) if match else 0

        def set_glass(node_id, value):
            amount = int(value or 0)
            return self.session.edit_style(node_id, "backdrop_filter", f"blur({amount}px) saturate(140%)" if amount else None)

        self._bind(group, "backdrop_filter", "Glass blur", SliderField(0, 40, 1, "px"), glass_value, set_glass,
                   "Frosted glass: blurs whatever is behind this element. Give it a see-through background, such as a light colour at low opacity.")

    # Images --------------------------------------------------------------------
    def _image_group(self, node: dict) -> None:
        group = self._group("Image", "image")
        self._media_row(group, node, "media", "")
        self._prop(group, "alt", "Alt text", TextField(True, "Describe the image for people who cannot see it"), tip="Read by screen readers and search engines.", default="")
        self._style(group, "object_fit", "Fit", SegmentField([("", "cover", "Cover"), ("", "contain", "Contain"), ("", "fill", "Fill")], self.pal))
        position_x = SliderField(0, 100, 1, "%")
        position_y = SliderField(0, 100, 1, "%")
        group.add_row("Horizontal position", position_x, "Which part stays visible when the image is cropped by its frame.")
        group.add_row("Vertical position", position_y)
        self.fields["position_x"], self.fields["position_y"] = position_x, position_y

        def write(_value=None) -> None:
            self.session.edit_style(self._node_id(), "object_position", f"{position_x.spin.value():g}% {position_y.spin.value():g}%")

        position_x.edited.connect(write)
        position_y.edited.connect(write)
        position_x.finished.connect(self.session.end_gesture)
        position_y.finished.connect(self.session.end_gesture)

        def sync(current: dict) -> None:
            parts = str(self._style_value(current, "object_position") or "50% 50%").replace("%", "").split()
            try:
                position_x.set_value(float(parts[0]))
                position_y.set_value(float(parts[1]))
            except (IndexError, ValueError):
                position_x.set_value(50)
                position_y.set_value(50)

        self.syncs.append(sync)
        ratios = [(name.capitalize() if name == "original" else name, value) for name, value in RATIOS.items()]
        ratio = NoWheelCombo()
        for text, value in ratios:
            ratio.addItem(text, value)
        group.add_row("Aspect ratio", ratio, "The shape of the frame. Original follows the image.")
        self.fields["ratio"] = ratio

        def pick_ratio(_i: int) -> None:
            self.session.edit_prop(self._node_id(), "ratio", ratio.currentData())
            self.session.end_gesture()

        ratio.activated.connect(pick_ratio)

        def sync_ratio(current: dict) -> None:
            value = current.get("props", {}).get("ratio")
            best = 0
            for i in range(ratio.count()):
                data = ratio.itemData(i)
                if data is not None and value is not None and abs(float(data) - float(value)) < .01:
                    best = i
            if value is not None and best == 0:
                ratio.addItem(f"Custom ({float(value):.2f})", float(value))
                best = ratio.count() - 1
            ratio.setCurrentIndex(best)

        self.syncs.append(sync_ratio)

    def _media_row(self, group, node: dict, slot: str, caption: str) -> None:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        art = QLabel()
        art.setObjectName("MediaPreview")
        art.setFixedHeight(120)
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info = label("", "faint", wrap=True)
        row = QHBoxLayout()
        row.setSpacing(4)
        choose = QPushButton("Choose image")
        crop = QPushButton("Crop")
        reset = QToolButton()
        reset.setToolTip("Go back to the placeholder" if slot != "background" else "Remove the background image")
        reset.setIcon(make_icon("rotate-ccw", self.pal, 14))
        row.addWidget(choose, 1)
        row.addWidget(crop)
        row.addWidget(reset)
        column.addWidget(art)
        column.addWidget(info)
        column.addLayout(row)
        group.add_row(caption, holder)
        self.fields[f"{slot}_choose"], self.fields[f"{slot}_crop"], self.fields[f"{slot}_reset"], self.fields[f"{slot}_info"] = choose, crop, reset, info
        choose.clicked.connect(lambda: self.session.request_media_picker(self._node_id(), slot))
        crop.clicked.connect(lambda: self.session.request_crop(self._node_id(), slot))
        reset.clicked.connect(lambda: self.session.set_node_media(self._node_id(), "", slot))

        def sync(current: dict) -> None:
            props = current.get("props", {})
            if slot == "background":
                ref = (props.get("background") or {}).get("media") if isinstance(props.get("background"), dict) else None
            else:
                ref = props.get(slot)
            asset = None
            if isinstance(ref, dict) and ref.get("kind") == "asset":
                asset = media_core.find_asset(self.session.document, ref.get("id"))
            crop.setEnabled(asset is not None)
            reset.setEnabled(isinstance(ref, dict) and (asset is not None or slot == "background"))
            choose.setText("Replace image" if asset or isinstance(ref, dict) else "Choose image")
            if asset and self.session.project:
                thumb = media_core.thumbnail(self.session.project.folder, asset)
                art.setPixmap(QPixmap(str(thumb)).scaled(280, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) if thumb else QPixmap())
                info.setText(f"{asset.get('name')}: {asset.get('width')} x {asset.get('height')} px, {asset.get('format')}")
            else:
                art.setPixmap(icon_pixmap("image-plus", self.pal.faint, 36))
                info.setText("A generated placeholder. Choose an image to replace it." if isinstance(ref, dict) else "No image.")

        self.syncs.append(sync)

    def _gallery_rows(self, group, node: dict) -> None:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        group.add_row("Images", holder)
        add = QPushButton("Add image")
        add.clicked.connect(lambda: self.session.request_media_picker(self._node_id(), "item", -1))
        group.rows.addWidget(add)
        rows: list[QWidget] = []

        def sync(current: dict) -> None:
            for row in rows:
                row.setParent(None)
                row.deleteLater()
            rows.clear()
            for index, item in enumerate(current.get("props", {}).get("items", [])):
                row = QWidget()
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                line.setSpacing(4)
                asset = media_core.find_asset(self.session.document, item.get("id")) if item.get("kind") == "asset" else None
                text = asset.get("name") if asset else item.get("label", f"Placeholder {index + 1}")
                name = QLabel(str(text))
                name.setMinimumWidth(0)
                swap = QPushButton("Replace")
                swap.clicked.connect(lambda _=False, i=index: self.session.request_media_picker(self._node_id(), "item", i))
                remove = QPushButton("Remove")
                remove.clicked.connect(lambda _=False, i=index: self.session.set_node_media(self._node_id(), "", "item", i))
                line.addWidget(name, 1)
                line.addWidget(swap)
                line.addWidget(remove)
                column.addWidget(row)
                rows.append(row)

        self.syncs.append(sync)

