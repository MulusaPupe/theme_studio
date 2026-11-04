"""Application preferences, kept in a small JSON file."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def config_dir() -> Path:
    override = os.environ.get("MTS_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "MulusaThemeStudio"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mulusa-theme-studio"


def default_projects_dir() -> Path:
    return Path.home() / "Documents" / "MulusaThemeStudio" / "projects"


@dataclass
class Settings:
    appearance: str = "dark"  # dark | light
    autosave_enabled: bool = True
    autosave_seconds: int = 60
    projects_dir: str = ""
    author: str = ""
    recent: list[str] = field(default_factory=list)

    @property
    def projects_path(self) -> Path:
        return Path(self.projects_dir) if self.projects_dir else default_projects_dir()

    def add_recent(self, folder: Path, limit: int = 8) -> None:
        text = str(folder)
        self.recent = [text] + [r for r in self.recent if r != text]
        del self.recent[limit:]

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads((config_dir() / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()  # First run, or damaged preferences: start from defaults.
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in raw.items() if k in known})
        settings.autosave_seconds = max(15, int(settings.autosave_seconds))
        if settings.appearance not in ("dark", "light"):
            settings.appearance = "dark"
        return settings

    def save(self) -> None:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "settings.json").write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
