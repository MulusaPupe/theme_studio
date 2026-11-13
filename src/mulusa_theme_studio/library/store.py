"""The user's own library on disk: imported resources, folders, favourites and recently used items.

Small JSON files hold the metadata; large files live in one folder per item, so the index stays
fast to read and works with no network. No database is added: the rest of the application keeps
its data in JSON too.

    <data dir>/library/index.json          imported resources (metadata only)
    <data dir>/library/state.json          favourites, recently used, folders
    <data dir>/library/items/<id>/         original package, converted document, preview, media
    <data dir>/library/cache/              remote catalogue answers and downloads
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .model import Resource


def data_dir() -> Path:
    override = os.environ.get("MTS_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MulusaThemeStudio"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mulusa-theme-studio"


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data) -> None:
    """Atomic: a crash mid-write never leaves half a file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ResourceStore:
    RECENT_LIMIT = 24

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else data_dir() / "library"
        self._items: dict[str, Resource] = {}
        self._state = {"favourites": [], "recent": [], "folders": []}
        self.reload()

    # Paths --------------------------------------------------------------------
    @property
    def index_file(self) -> Path:
        return self.root / "index.json"

    @property
    def state_file(self) -> Path:
        return self.root / "state.json"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    def item_dir(self, resource_id: str) -> Path:
        return self.root / "items" / resource_id

    # Loading ------------------------------------------------------------------
    def reload(self) -> None:
        raw = read_json(self.index_file, {})
        self._items = {}
        for entry in raw.get("items", []) if isinstance(raw, dict) else []:
            try:
                resource = Resource.from_json(entry)
            except TypeError:
                continue  # a damaged entry is skipped, never fatal
            self._items[resource.id] = resource
        state = read_json(self.state_file, {})
        if isinstance(state, dict):
            for key in self._state:
                if isinstance(state.get(key), list):
                    self._state[key] = [str(v) for v in state[key]]

    def _save_index(self) -> None:
        write_json(self.index_file, {"version": 1, "items": [r.to_json() for r in self._items.values()]})

    def _save_state(self) -> None:
        write_json(self.state_file, self._state)

    # Items --------------------------------------------------------------------
    def items(self) -> list[Resource]:
        return list(self._items.values())

    def get(self, resource_id: str) -> Resource | None:
        return self._items.get(resource_id)

    def new_id(self) -> str:
        return "u" + uuid.uuid4().hex[:12]

    def find_by_digest(self, sha256: str) -> Resource | None:
        return next((r for r in self._items.values() if sha256 and r.sha256 == sha256), None)

    def add(self, resource: Resource) -> Resource:
        resource.origin = resource.origin if resource.origin != "builtin" else "imported"
        resource.added = resource.added or now()
        self._items[resource.id] = resource
        self._save_index()
        return resource

    def update(self, resource: Resource) -> None:
        if resource.id not in self._items:
            raise KeyError(resource.id)
        self._items[resource.id] = resource
        self._save_index()

    def rename(self, resource_id: str, name: str) -> None:
        name = " ".join(name.split())
        if not name:
            raise ValueError("A resource needs a name.")
        self._items[resource_id].name = name
        self._save_index()

    def delete(self, resource_id: str) -> None:
        self._items.pop(resource_id, None)
        shutil.rmtree(self.item_dir(resource_id), ignore_errors=True)
        for key in ("favourites", "recent"):
            self._state[key] = [i for i in self._state[key] if i != resource_id]
        self._save_index()
        self._save_state()

    # Folders ------------------------------------------------------------------
    def folders(self) -> list[str]:
        used = {r.folder for r in self._items.values() if r.folder}
        return sorted(set(self._state["folders"]) | used, key=str.lower)

    def create_folder(self, name: str) -> str:
        name = " ".join(name.split())
        if not name:
            raise ValueError("A folder needs a name.")
        if name not in self._state["folders"]:
            self._state["folders"].append(name)
            self._save_state()
        return name

    def delete_folder(self, name: str) -> None:
        """Removes a folder; its items stay in the library, unfiled."""
        self._state["folders"] = [f for f in self._state["folders"] if f != name]
        for resource in self._items.values():
            if resource.folder == name:
                resource.folder = ""
        self._save_state()
        self._save_index()

    def move_to_folder(self, resource_id: str, folder: str) -> None:
        if folder:
            self.create_folder(folder)
        self._items[resource_id].folder = folder
        self._save_index()

    # Favourites and recent (these may name bundled resources too) ---------------
    def favourites(self) -> list[str]:
        return list(self._state["favourites"])

    def is_favourite(self, resource_id: str) -> bool:
        return resource_id in self._state["favourites"]

    def set_favourite(self, resource_id: str, on: bool) -> None:
        favs = [i for i in self._state["favourites"] if i != resource_id]
        if on:
            favs.insert(0, resource_id)
        self._state["favourites"] = favs
        self._save_state()

    def touch(self, resource_id: str) -> None:
        """Marks a resource as just used."""
        self._state["recent"] = ([resource_id] + [i for i in self._state["recent"] if i != resource_id])[: self.RECENT_LIMIT]
        self._save_state()

    def recent(self) -> list[str]:
        return list(self._state["recent"])

    # Integrity ----------------------------------------------------------------
    def missing(self) -> list[Resource]:
        """Imported items whose files have gone from disk."""
        return [r for r in self._items.values() if r.path and not Path(r.path).exists()]
