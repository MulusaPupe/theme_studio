"""The one object that holds what is open. Panels observe it and never talk to each other."""
from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..components import registry
from ..components.presets import PAGE_STARTERS, ROLE_STARTERS
from ..core import media, operations as ops, pages, properties
from ..core.document import (
    Document, describe_node, find_node, find_page, home_page, instantiate_template, new_id, node_label, type_label,
    validate_document,
)
from ..core.errors import ProjectError, StudioError
from ..core.structure import SHARED_TYPES
from ..core.project import Project
from ..core.settings import Settings
from ..core.templates import TemplateInfo, TemplateLibrary

VIEWPORTS = {"desktop": 1440, "tablet": 820, "mobile": 390}


READ_ONLY_NOTE = "This is a template preview. Choose Use this template to start editing it."


@dataclass(frozen=True)
class ActionState:
    """What can be done with the selection right now, and why not if it cannot."""
    duplicate: bool = False
    delete: bool = False
    up: bool = False
    down: bool = False
    copy: bool = False
    paste: bool = False
    reason: str = ""


# Which elements can show an image, and where. A request for anything else is ignored.
MEDIA_SLOTS = {"image": ("media",), "section": ("background",), "video": ("poster",), "gallery": ("item",), "header": ("logo",)}


class Session(QObject):
    projectChanged = Signal()       # a project was opened, created or closed
    documentChanged = Signal()      # the design changed: redraw it
    pageChanged = Signal()
    selectionChanged = Signal()
    saveStateChanged = Signal()
    templatePreviewChanged = Signal()
    viewportChanged = Signal()
    noticeRaised = Signal(str)      # a short message for the status area
    componentDragChanged = Signal() # a component drag from the library began or ended
    mediaPickerRequested = Signal(str, str, int)  # node id, slot, gallery index: choose an image
    cropRequested = Signal(str, str)    # node id, slot: crop what this element shows
    scopeChanged = Signal()         # the device that style edits apply to

    def __init__(self, settings: Settings, library: TemplateLibrary) -> None:
        super().__init__()
        self.settings = settings
        self.library = library
        self.project: Project | None = None
        self.preview: TemplateInfo | None = None
        self.preview_doc: Document | None = None
        self.page_id = ""
        self.selected_id = ""
        self.selection_origin = "panel"  # canvas | panel | edit: decides whether the canvas scrolls
        self.keep_view = False           # True while redrawing after an edit, to hold the scroll position
        self.clipboard: dict | None = None
        self.dragging_component = ""
        self.edit_scope = ""             # "" for all devices, or desktop | tablet | mobile
        self.live_edit = False           # True while redrawing after a property edit: no page reload
        self.viewport = "desktop"
        self.last_save_note = ""

    # What is on the canvas ----------------------------------------------------
    @property
    def document(self) -> Document | None:
        if self.preview_doc is not None:
            return self.preview_doc
        return self.project.document if self.project else None

    @property
    def read_only(self) -> bool:
        return self.preview_doc is not None or self.project is None

    @property
    def current_page(self) -> dict | None:
        doc = self.document
        return find_page(doc, self.page_id) if doc and self.page_id else None

    @property
    def selected_node(self) -> dict | None:
        doc = self.document
        return find_node(doc, self.selected_id) if doc and self.selected_id else None

    @property
    def selected_label(self) -> str:
        node = self.selected_node
        return node_label(node) if node else ""

    # Projects -----------------------------------------------------------------
    def create_project(self, name: str, template_id: str, parent: Path | None = None) -> Project:
        template_doc = self.library.load(template_id)
        project = Project.create(parent or self.settings.projects_path, name, template_doc, self.settings.author)
        self._adopt(project)
        return project

    def open_project(self, path: Path) -> Project:
        project = Project.open(path)
        self._adopt(project)
        return project

    def _adopt(self, project: Project) -> None:
        self.project = project
        self.preview = None
        self.preview_doc = None
        self.page_id = home_page(project.document)["id"]
        self.selected_id = ""
        self.last_save_note = "All changes saved"
        self.settings.add_recent(project.folder)
        self.settings.save()
        self.projectChanged.emit()
        self.templatePreviewChanged.emit()
        self.documentChanged.emit()
        self.pageChanged.emit()
        self.selectionChanged.emit()
        self.saveStateChanged.emit()

    def close_project(self) -> None:
        """Back to the start screen. Unsaved work is the window's to ask about before calling this."""
        if self.project is None and self.preview_doc is None and self.preview is None:
            return
        self.project = None
        self.preview = None
        self.preview_doc = None
        self.page_id = ""
        self.selected_id = ""
        self.last_save_note = ""
        self.projectChanged.emit()
        self.templatePreviewChanged.emit()
        self.documentChanged.emit()
        self.pageChanged.emit()
        self.selectionChanged.emit()
        self.saveStateChanged.emit()

    def recover_autosave(self) -> None:
        if not self.project:
            return
        self.project.recover_autosave()
        self.page_id = home_page(self.project.document)["id"]
        self.last_save_note = "Recovered from autosave, not saved yet"
        self.documentChanged.emit()
        self.pageChanged.emit()
        self.saveStateChanged.emit()

    def save(self) -> None:
        if not self.project:
            return
        self.project.save()
        from datetime import datetime

        self.last_save_note = f"Saved at {datetime.now():%H:%M}"
        self.saveStateChanged.emit()

    def autosave(self) -> bool:
        if not self.project:
            return False
        written = self.project.autosave()
        if written:
            from datetime import datetime

            self.last_save_note = f"Unsaved changes, autosaved at {datetime.now():%H:%M}"
            self.saveStateChanged.emit()
        return written

    # Editing ------------------------------------------------------------------
    def apply_template_to_project(self, template_id: str) -> None:
        """Replace the design with a template, keeping project details. It can be undone."""
        if not self.project:
            raise ProjectError("Open or create a project first.")
        fresh = instantiate_template(self.library.load(template_id), name=self.project.name, author=self.settings.author)
        info = self.library.get(template_id)

        def change(doc: Document) -> None:
            meta = doc["meta"]
            assets = doc.get("media", {}).get("assets", [])
            doc.clear()
            doc.update(copy.deepcopy(fresh))
            doc["meta"].update(created=meta.get("created"), author=meta.get("author", ""), modified=meta.get("modified"))
            doc["media"]["assets"] = assets  # The user's uploaded media stays with the project.
            issues = validate_document(doc)
            if issues:
                raise ProjectError("That template could not be applied.", issues)

        self.project.history.apply(f"Apply template {info.name}", change)
        self._after_history()
        self.close_template_preview(emit_document=False)

    def undo(self) -> None:
        if self.project and not self.read_only and self.project.history.can_undo:
            self.project.history.undo()
            self._media_changed()
            self._after_edit()

    def redo(self) -> None:
        if self.project and not self.read_only and self.project.history.can_redo:
            self.project.history.redo()
            self._media_changed()
            self._after_edit()

    def notify(self, message: str) -> None:
        self.noticeRaised.emit(message)

    def _edit(self, label: str, change: Callable[[Document], object], merge: str | None = None) -> tuple[bool, object]:
        """The one route for structural edits: through history, validated, restored on failure.

        Returns whether the document changed, and what the change returned.
        """
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return False, None
        result: dict[str, object] = {}

        def apply(doc: Document) -> None:
            result["value"] = change(doc)
            issues = validate_document(doc)
            if issues:
                raise ops.EditError(f"That would damage the design: {issues[0]}")

        try:
            changed = self.project.history.apply(label, apply, merge=merge)
        except StudioError as exc:
            self.notify(str(exc))
            return False, None
        return changed, result.get("value")

    def _after_edit(self, select: str | None = None) -> None:
        if select is not None:
            self.selected_id = select
            self.selection_origin = "edit"
        self.keep_view = True
        try:
            self._after_history()
        finally:
            self.keep_view = False

    # Property edits -----------------------------------------------------------
    def _live(self, label: str, change: Callable[[Document], object], merge: str | None) -> tuple[bool, object]:
        """A property or design edit: one undo step per gesture, and no page reload."""
        changed, value = self._edit(label, change, merge)
        if changed:
            self.live_edit = True
            try:
                self._after_live()
            finally:
                self.live_edit = False
        return changed, value

    def _after_live(self) -> None:
        self.last_save_note = "Unsaved changes" if self.project.dirty else "All changes saved"
        self.documentChanged.emit()
        self.saveStateChanged.emit()

    def end_gesture(self) -> None:
        """Called when a slider is released or a field is left: the next change is a new undo step."""
        if self.project:
            self.project.history.seal()

    def edit_prop(self, node_id: str, key: str, value: object, label: str = "") -> bool:
        node = find_node(self.document, node_id) if self.document else None
        name = label or f"Change {type_label(node) if node else 'element'}"
        changed, _ = self._live(name, lambda doc: properties.set_prop(doc, node_id, key, value), f"prop:{node_id}:{key}")
        return bool(changed)

    def edit_style(self, node_id: str, prop: str, value: object) -> bool:
        scope = self.edit_scope
        name = f"Change {prop.replace('_', ' ')}"
        changed, _ = self._live(name, lambda doc: properties.set_style(doc, node_id, prop, value, scope), f"style:{node_id}:{prop}:{scope}")
        return bool(changed)

    def edit_box(self, node_id: str, family: str, side: str, value: object) -> bool:
        scope = self.edit_scope
        changed, _ = self._live(f"Change {family}", lambda doc: properties.set_box_side(doc, node_id, family, side, value, scope), f"box:{node_id}:{family}:{side}:{scope}")
        return bool(changed)

    def edit_overlay(self, node_id: str, color: str, strength: float) -> bool:
        changed, _ = self._live("Change overlay", lambda doc: properties.set_background_overlay(doc, node_id, color, strength), f"overlay:{node_id}")
        return bool(changed)

    def clear_overrides(self, node_id: str) -> bool:
        scope = self.edit_scope
        if not scope:
            return False
        changed, _ = self._live(f"Clear {scope} styles", lambda doc: properties.clear_overrides(doc, node_id, scope), None)
        return bool(changed)

    def reset_device(self, node_id: str) -> bool:
        scope = self.edit_scope
        if not scope:
            return False
        changed, _ = self._live(f"Reset {scope}", lambda doc: properties.reset_device(doc, node_id, scope), None)
        return bool(changed)

    def set_edit_scope(self, scope: str) -> None:
        if scope in ("", "desktop", "tablet", "mobile") and scope != self.edit_scope:
            self.edit_scope = scope
            self.scopeChanged.emit()
        # Editing a device shows that device.
        if scope:
            self.set_viewport(scope)

    def reset_style(self, node_id: str, prop: str) -> bool:
        """Returns one style on the current device to what it inherits."""
        scope = self.edit_scope
        if not scope:
            return False
        changed, _ = self._live(f"Reset {prop.replace('_', ' ')}", lambda doc: properties.set_style(doc, node_id, prop, None, scope), None)
        return bool(changed)

    def reset_box(self, node_id: str, family: str) -> bool:
        scope = self.edit_scope
        if not scope:
            return False

        def change(doc: Document) -> None:
            for side in ("top", "right", "bottom", "left"):
                properties.set_box_side(doc, node_id, family, side, None, scope)
            properties.set_style(doc, node_id, family, None, scope)

        changed, _ = self._live(f"Reset {family}", change, None)
        return bool(changed)

    def set_device_hidden(self, node_id: str, hidden: bool) -> bool:
        scope = self.edit_scope
        changed, _ = self._live(f"{'Hide' if hidden else 'Show'} on {scope}", lambda doc: properties.set_hidden(doc, node_id, scope, hidden), None)
        return bool(changed)

    def set_device_columns(self, node_id: str, value: object) -> bool:
        scope = self.edit_scope
        changed, _ = self._live(f"Change columns on {scope}", lambda doc: properties.set_device_columns(doc, node_id, scope, value), None)
        return bool(changed)

    def edit_query(self, node_id: str, **changes: object) -> bool:
        """Changes what a posts list shows. The number of sample cards changes, so the page is redrawn."""
        changed, _ = self._edit("Change posts list", lambda doc: pages.set_query(doc, node_id, **changes))
        if changed:
            self._after_edit()
        return bool(changed)

    # Pages and menu -----------------------------------------------------------
    def _site_edit(self, label: str, change: Callable[[Document], object]) -> object:
        changed, value = self._edit(label, change)
        if changed:
            self._after_edit()
        return value if changed else None

    def add_page(self, title: str, starter: str = "blank") -> str:
        name, build = PAGE_STARTERS.get(starter, PAGE_STARTERS["blank"])
        after = self.page_id if (self.current_page or {}).get("role") is None else ""
        page_id = self._site_edit(f"Add page {title.strip()}", lambda doc: pages.create_page(doc, title, build(), after=after))
        if page_id:
            self.set_page(page_id)
        return page_id or ""

    def open_role_page(self, role: str) -> str:
        """Opens this template for designing, creating it from the default the first time."""
        doc = self.document
        existing = next((p for p in doc["pages"] if p.get("role") == role), None) if doc else None
        if existing:
            self.set_page(existing["id"])
            return existing["id"]
        title = {"single": "Single post", "archive": "Post archive", "not_found": "Page not found"}[role]
        page_id = self._site_edit(f"Design {title}", lambda d: pages.create_page(d, title, ROLE_STARTERS[role](), role=role))
        if page_id:
            self.set_page(page_id)
        return page_id or ""

    def remove_role_page(self, role: str) -> bool:
        page = next((p for p in self.document["pages"] if p.get("role") == role), None)
        return bool(page and self._site_edit(f"Use the default {role.replace('_', ' ')}", lambda d: pages.delete_page(d, page["id"]) is not None))

    def rename_page(self, page_id: str, title: str) -> None:
        self._site_edit("Rename page", lambda doc: pages.rename_page(doc, page_id, title))

    def set_page_slug(self, page_id: str, slug: str) -> None:
        self._site_edit("Change page address", lambda doc: pages.set_slug(doc, page_id, slug))

    def set_page_details(self, page_id: str, **details: str) -> None:
        self._site_edit("Change page details", lambda doc: pages.set_page_meta(doc, page_id, **details))

    def duplicate_page(self, page_id: str) -> str:
        new = self._site_edit("Duplicate page", lambda doc: pages.duplicate_page(doc, page_id))
        if new:
            self.set_page(new)
        return new or ""

    def delete_page(self, page_id: str) -> bool:
        return self._site_edit("Delete page", lambda doc: pages.delete_page(doc, page_id) is not None) is True

    def move_page(self, page_id: str, step: int) -> None:
        self._site_edit("Move page", lambda doc: pages.move_page(doc, page_id, step))

    def set_home_page(self, page_id: str) -> None:
        self._site_edit("Change homepage", lambda doc: pages.set_home(doc, page_id))

    def add_nav_item(self, label: str, target: object) -> str:
        return self._site_edit("Add menu link", lambda doc: pages.add_nav_item(doc, label, target)) or ""

    def update_nav_item(self, item_id: str, **changes: object) -> None:
        self._site_edit("Change menu link", lambda doc: pages.update_nav_item(doc, item_id, **changes))

    def move_nav_item(self, item_id: str, step: int) -> None:
        self._site_edit("Move menu link", lambda doc: pages.move_nav_item(doc, item_id, step))

    def remove_nav_item(self, item_id: str) -> None:
        self._site_edit("Remove menu link", lambda doc: pages.remove_nav_item(doc, item_id))

    # Global design ------------------------------------------------------------
    def edit_design(self, label: str, change: Callable[[Document], object], merge: str | None = None) -> bool:
        changed, _ = self._live(label, change, merge)
        return bool(changed)

    # Media --------------------------------------------------------------------
    def _media_changed(self) -> None:
        if self.project:
            media.sync_files(self.project.folder, self.project.document)

    def upload_media(self, paths: list[str | Path]) -> list[dict]:
        """Adds image files to the project as one undo step. A bad file is reported and the rest still go in."""
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return []
        stored, problems, reused = [], [], []
        for path in paths:
            try:
                entry = media.store_upload(self.project.folder, Path(path))
            except StudioError as exc:
                problems.append(str(exc))
                continue
            existing = media.find_duplicate(self.project.document, entry["sha256"]) or next((s for s in stored if s["sha256"] == entry["sha256"]), None)
            if existing:
                media.asset_path(self.project.folder, entry).unlink(missing_ok=True)
                reused.append(existing)
            else:
                stored.append(entry)
        added: list[dict] = []
        if stored:
            def change(doc: Document) -> None:
                added.extend(media.add_asset(doc, entry) for entry in stored)
            changed, _ = self._live(f"Upload {len(stored)} image{'s' if len(stored) != 1 else ''}", change, None)
            if not changed:
                added = []
        if problems:
            self.notify(problems[0] if len(problems) == 1 else f"{len(problems)} files were not added. {problems[0]}")
        elif reused and not added:
            self.notify(f"{reused[0].get('name')} is already in this project.")
        return added + reused

    def set_node_media(self, node_id: str, asset_id: str, slot: str = "media", index: int = -1) -> bool:
        """Puts an asset, or a placeholder if ``asset_id`` is empty, into one element. No other element changes."""
        def change(doc: Document) -> None:
            node = find_node(doc, node_id)
            if node is None:
                raise media.MediaError("That element no longer exists.")
            ref = media.asset_ref({"id": asset_id}) if asset_id else None
            if slot == "media":
                if ref is None:
                    ref = media.placeholder_ref(node_id, node["props"].get("alt") or "Image", float(node["props"].get("ratio") or 1.5))
                media.set_image_media(doc, node, ref)
            elif slot == "background":
                if ref is None:
                    media.clear_section_photo(node)
                else:
                    media.set_section_photo(doc, node, ref)
            elif slot == "logo":
                pages.set_header_logo(doc, asset_id)
            elif slot == "poster":
                node["props"]["poster"] = ref or media.placeholder_ref(node_id, "Video poster", 1.78)
            elif slot == "item":
                items = node["props"].setdefault("items", [])
                if ref is None:
                    if not 0 <= index < len(items):
                        raise media.MediaError("That gallery image no longer exists.")
                    del items[index]
                elif index == -1:
                    items.append(ref)
                elif 0 <= index < len(items):
                    items[index] = ref
                else:
                    raise media.MediaError("That gallery image no longer exists.")
            else:
                raise media.MediaError("That is not a place for an image.")
            if ref and ref.get("kind") == "asset" and media.find_asset(doc, asset_id) is None:
                raise media.MediaError("That image is no longer in the project.")

        changed, _ = self._live("Change image", change, None)
        return bool(changed)

    def rename_asset(self, asset_id: str, name: str) -> bool:
        changed, _ = self._live("Rename image", lambda doc: media.rename_asset(doc, asset_id, name), None)
        return bool(changed)

    def delete_asset(self, asset_id: str) -> bool:
        changed, _ = self._live("Delete image", lambda doc: media.remove_asset(doc, asset_id), None)
        self._media_changed()
        return bool(changed)

    def replace_asset_everywhere(self, old_id: str, source: str | Path) -> int:
        """A new file takes the place of an asset wherever it is used, as one undo step."""
        added = self.upload_media([source])
        if not added or added[0]["id"] == old_id:
            return 0
        count: dict[str, int] = {}
        changed, _ = self._live("Replace image everywhere", lambda doc: count.update(n=media.replace_everywhere(doc, old_id, added[0]["id"])), None)
        return count.get("n", 0) if changed else 0

    def crop_asset(self, node_id: str, asset_id: str, box: tuple[int, int, int, int], slot: str = "media") -> str:
        """Crops into a new asset and points this one element at it. The original stays. Returns the new id."""
        asset = media.find_asset(self.document, asset_id) if self.document else None
        if self.read_only or asset is None:
            self.notify("That image is no longer in the project.")
            return ""
        try:
            entry = media.crop_to_file(self.project.folder, asset, box)
        except StudioError as exc:
            self.notify(str(exc))
            return ""

        def change(doc: Document) -> str:
            node = find_node(doc, node_id)
            if node is None:
                raise media.MediaError("That element no longer exists.")
            added = media.add_asset(doc, entry)
            if slot == "background":
                media.set_section_photo(doc, node, media.asset_ref(added))
            else:
                media.set_image_media(doc, node, media.asset_ref(added))
            return added["id"]

        changed, value = self._live("Crop image", change, None)
        if not changed:
            media.asset_path(self.project.folder, entry).unlink(missing_ok=True)
            return ""
        return str(value)

    def request_media_picker(self, node_id: str, slot: str = "media", index: int = -1) -> None:
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return
        node = find_node(self.document, node_id) if self.document else None
        if node and slot in MEDIA_SLOTS.get(node.get("type"), ()):
            self.mediaPickerRequested.emit(node_id, slot, index)

    def request_crop(self, node_id: str, slot: str = "media") -> None:
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
        elif self.document and find_node(self.document, node_id):
            self.cropRequested.emit(node_id, slot)

    # Structural edits ---------------------------------------------------------
    def insert_component(self, component_id: str, parent_ref: str | None = None, index: int | None = None) -> str:
        """Inserts a preset, where it was dropped or else in the natural place. Returns its id."""
        try:
            component = registry.get(component_id)
        except StudioError as exc:
            self.notify(str(exc))
            return ""
        tree = component.build()
        return self._insert_tree(f"Add {component.label}", tree, parent_ref, index)

    def _insert_tree(self, label: str, tree: dict, parent_ref: str | None, index: int | None) -> str:
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return ""
        if parent_ref is None or index is None:
            place = ops.place_for(self.project.document, tree["type"], self.selected_id, self.page_id)
            if place is None:
                self.notify(f"Select a place that can hold {ops.type_name(tree['type'])} first.")
                return ""
            parent_ref, index = place
        changed, value = self._edit(label, lambda doc: ops.insert_tree(doc, parent_ref, index, tree))
        if changed:
            self._after_edit(select=str(value))
            return str(value)
        return ""

    def move_node(self, node_id: str, parent_ref: str, index: int) -> bool:
        node = find_node(self.document, node_id) if self.document else None
        name = type_label(node) if node else "element"
        changed, _ = self._edit(f"Move {name}", lambda doc: ops.move_node(doc, node_id, parent_ref, index))
        if changed:
            self._after_edit(select=node_id)
        return bool(changed)

    def shift_selected(self, step: int) -> None:
        node = self.selected_node
        if node:
            changed, _ = self._edit(f"Move {type_label(node)} {'up' if step < 0 else 'down'}", lambda doc: ops.shift_node(doc, self.selected_id, step))
            if changed:
                self._after_edit(select=self.selected_id)

    def duplicate_selected(self) -> None:
        node = self.selected_node
        if node:
            changed, value = self._edit(f"Duplicate {type_label(node)}", lambda doc: ops.duplicate_node(doc, self.selected_id))
            if changed:
                self._after_edit(select=str(value))

    def delete_selected(self) -> None:
        node = self.selected_node
        if node:
            changed, value = self._edit(f"Delete {type_label(node)}", lambda doc: ops.delete_node(doc, self.selected_id))
            if changed:
                self._after_edit(select=str(value))

    def copy_selected(self) -> None:
        node = self.selected_node
        if not node:
            return
        if node.get("type") in SHARED_TYPES:
            self.notify(f"The {node['type']} is shared by every page and cannot be copied.")
            return
        self.clipboard = copy.deepcopy(node)  # Outside the document and outside history.
        self.notify(f"Copied {describe_node(node)}")
        self.selectionChanged.emit()  # Paste may have just become available.

    def paste(self) -> None:
        if self.clipboard is None:
            self.notify("Nothing has been copied yet.")
            return
        self._insert_tree(f"Paste {type_label(self.clipboard)}", ops.clone_tree(self.clipboard), None, None)

    def actions(self) -> ActionState:
        doc = self.document
        node = self.selected_node
        can_paste = bool(self.clipboard and doc and not self.read_only and ops.place_for(doc, self.clipboard["type"], self.selected_id, self.page_id))
        if not node:
            return ActionState(paste=can_paste)
        if self.read_only:
            return ActionState(reason=READ_ONLY_NOTE)
        if node.get("type") in SHARED_TYPES:
            return ActionState(paste=can_paste, reason=f"The {node['type']} is shared by every page and must stay in place.")
        location = ops.locate(doc, node["id"])
        return ActionState(
            duplicate=True, delete=True, copy=True, paste=can_paste,
            up=location.index > 0, down=location.index < len(location.siblings) - 1,
        )

    def selection_path(self) -> list[dict]:
        doc = self.document
        return ops.ancestors(doc, self.selected_id) if doc and self.selected_id else []

    # Dragging a component from the library -----------------------------------
    def begin_component_drag(self, component_id: str) -> bool:
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Create or open a project, then drag components onto the page.")
            return False
        self.dragging_component = component_id
        self.componentDragChanged.emit()
        return True

    def end_component_drag(self) -> None:
        self.dragging_component = ""
        self.componentDragChanged.emit()

    def _after_history(self) -> None:
        doc = self.project.document
        if not find_page(doc, self.page_id):
            self.page_id = home_page(doc)["id"]
        if self.selected_id and not find_node(doc, self.selected_id):
            self.selected_id = ""
        if self.project.dirty:
            self.last_save_note = "Unsaved changes"
        else:
            self.last_save_note = "All changes saved"
        self.documentChanged.emit()
        self.pageChanged.emit()
        self.selectionChanged.emit()
        self.saveStateChanged.emit()

    # Viewing ------------------------------------------------------------------
    # Resource library ---------------------------------------------------------
    @property
    def resources(self):
        """The Creative Resource Library (bundled and imported resources), opened on first use."""
        if getattr(self, "_resources", None) is None:
            from ..library.catalogue import Library
            self._resources = Library(self.library)
        return self._resources

    def _library_error(self, exc: Exception) -> None:
        self.notify(str(exc) if isinstance(exc, StudioError) else f"That resource could not be used: {exc}")

    def insert_resource(self, resource, index: int | None = None) -> list[str]:
        """Inserts a section (or every section of a template's home page) after the selection, as one undo step."""
        from ..library import apply as libapply
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return []
        if not resource.can_use:
            self.notify(f"'{resource.name}' is kept for reference only and cannot be inserted.")
            return []
        try:
            trees, assets, folder = libapply.load_sections(resource)
        except (OSError, ValueError, StudioError) as exc:
            self._library_error(exc)
            return []
        if not trees:
            self.notify(f"'{resource.name}' has no sections to insert.")
            return []
        place = ops.place_for(self.project.document, "section", self.selected_id, self.page_id)
        if place is None:
            self.notify("Open a page first.")
            return []
        parent_ref, start = place if index is None else (place[0], index)
        project_folder = self.project.folder

        def change(doc: Document) -> list[str]:
            try:
                fresh = libapply.adopt(doc, project_folder, trees, assets, folder)
            except (OSError, ValueError, KeyError) as exc:
                raise ops.EditError(f"The section could not be added: {exc}") from exc
            return [ops.insert_tree(doc, parent_ref, start + i, tree) for i, tree in enumerate(fresh)]

        changed, ids = self._edit(f"Add {resource.name}", change)
        if not changed:
            return []
        self.resources.store.touch(resource.id)
        self._media_changed()
        self._after_edit(select=str(ids[0]))
        return list(ids)

    def apply_resource(self, resource, role: str = "") -> bool:
        """Applies a design resource: palette, type pairing, font (role: heading | body), header, footer,
        pattern or gradient (to the selected section), icon (inserted), or images (added to Media)."""
        from ..core import design
        from ..library import apply as libapply
        from ..render.fonts import catalog
        if self.read_only:
            self.notify(READ_ONLY_NOTE if self.preview else "Open or create a project first.")
            return False
        kind, data = resource.kind, resource.data
        known = frozenset(catalog())
        ok = False
        try:
            if kind == "palette":
                ok = self.edit_design(f"Apply {resource.name}", lambda doc: design.apply_palette(doc, {"colors": data["colors"]}))
            elif kind == "type_pair":
                def pair(doc: Document) -> None:
                    design.set_font(doc, "heading", data["heading"], known)
                    design.set_font(doc, "body", data["body"], known)
                ok = self.edit_design(f"Apply {resource.name}", pair)
            elif kind == "font":
                target = role if role in ("heading", "body") else "body"
                ok = self.edit_design(f"Use {resource.name} for {'headings' if target == 'heading' else 'text'}",
                                      lambda doc: design.set_font(doc, target, data["family"], known))
            elif kind in ("header", "footer"):
                import json as _json
                tree = _json.loads(Path(resource.path).read_text(encoding="utf-8"))["nodes"][0]
                fn = (lambda doc: libapply.apply_header(doc, tree)) if kind == "header" else \
                     (lambda doc: libapply.apply_footer(doc, tree, data.get("sample_brand", "")))
                changed, _ = self._edit(f"Apply {resource.name}", fn)
                if changed:
                    self._after_edit()
                ok = changed
            elif kind == "pattern":
                section = self._selected_section()
                if section is None:
                    self.notify("Select a section first, then apply the background to it.")
                    return False
                sid, folder = section["id"], self.project.folder
                if "gradient" in data:
                    fn = lambda doc: libapply.apply_gradient(find_node(doc, sid), data["gradient"])  # noqa: E731
                else:
                    fn = lambda doc: libapply.apply_pattern(doc, folder, find_node(doc, sid), data["pattern"])  # noqa: E731
                changed, _ = self._edit(f"Apply {resource.name}", fn)
                if changed:
                    self._media_changed()
                    self._after_edit(select=sid)
                ok = changed
            elif kind == "icon":
                tree = {"id": new_id(), "type": "icon", "props": {"name": data["name"]}, "style": {"font_size": "28px"}}
                ok = bool(self._insert_tree(f"Add {resource.name} icon", tree, None, None))
            elif kind == "illustration":
                tree = {"id": new_id(), "type": "illustration", "props": {"name": data["name"], "animate": True, "aria_label": ""},
                        "style": {"width": "100%", "max_width": "420px"}}
                ok = bool(self._insert_tree(f"Add {resource.name} illustration", tree, None, None))
            elif kind == "image":
                folder = Path(resource.path)
                files = [folder / a["file"] for a in data.get("assets", []) if (folder / a["file"]).is_file()]
                ok = bool(self.upload_media(files))
            else:
                self.notify(f"{resource.kind_name} cannot be applied this way.")
                return False
        except (OSError, ValueError, KeyError) as exc:
            self._library_error(exc)
            return False
        if ok:
            self.resources.store.touch(resource.id)
        return ok

    def _selected_section(self) -> dict | None:
        doc = self.document
        if not doc or not self.selected_id:
            return None
        node = find_node(doc, self.selected_id)
        if node and node.get("type") == "section":
            return node
        return next((a for a in reversed(ops.ancestors(doc, self.selected_id)) if a.get("type") == "section"), None)

    def create_project_from_resource(self, resource, name: str, parent: Path | None = None) -> Project | None:
        """A new project from a bundled template or an imported (converted) one."""
        import shutil
        from ..library.packages import load_document
        if resource.kind != "template" or not resource.can_use:
            raise ProjectError(f"'{resource.name}' cannot start a project.")
        if resource.origin == "builtin":
            project = self.create_project(name, resource.data["template_id"], parent)
        else:
            doc = load_document(resource)
            project = Project.create(parent or self.settings.projects_path, name, doc, self.settings.author)
            source = Path(resource.path) / "assets"
            if source.is_dir():
                shutil.copytree(source, project.folder / "assets", dirs_exist_ok=True)
            self._adopt(project)
        self.resources.store.touch(resource.id)
        return project

    def preview_template(self, template_id: str) -> None:
        self.preview = self.library.get(template_id)
        self.preview_doc = self.library.load(template_id)
        self.page_id = home_page(self.preview_doc)["id"]
        self.selected_id = ""
        self.templatePreviewChanged.emit()
        self.documentChanged.emit()
        self.pageChanged.emit()
        self.selectionChanged.emit()

    def close_template_preview(self, *, emit_document: bool = True) -> None:
        if self.preview_doc is None and self.preview is None:
            return
        self.preview = None
        self.preview_doc = None
        doc = self.document
        self.page_id = home_page(doc)["id"] if doc else ""
        self.selected_id = ""
        self.templatePreviewChanged.emit()
        if emit_document:
            self.documentChanged.emit()
        self.pageChanged.emit()
        self.selectionChanged.emit()

    def set_page(self, page_id: str) -> None:
        if page_id != self.page_id and self.document and find_page(self.document, page_id):
            self.page_id = page_id
            self.selected_id = ""
            self.pageChanged.emit()
            self.selectionChanged.emit()

    def select(self, node_id: str, origin: str = "panel") -> None:
        """Selection never touches the document or its history."""
        self.end_gesture()
        doc = self.document
        if node_id and not (doc and find_node(doc, node_id)):
            return
        if node_id != self.selected_id:
            self.selected_id = node_id
            self.selection_origin = origin
            self.selectionChanged.emit()

    def set_viewport(self, name: str) -> None:
        if name in VIEWPORTS and name != self.viewport:
            self.viewport = name
            self.viewportChanged.emit()
            # What you edit follows what you see, so a change made while looking at a phone stays on phones.
            if self.edit_scope != name:
                self.set_edit_scope("" if name == "desktop" else name)
