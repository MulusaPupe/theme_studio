from __future__ import annotations

import json
import os

import pytest

from mulusa_theme_studio.core.errors import ProjectError
from mulusa_theme_studio.core.project import Project, safe_folder_name
from mulusa_theme_studio.core.settings import Settings


def change(project):
    project.history.apply("edit", lambda d: d["tokens"]["colors"].update(primary="#123456"))


def test_create_builds_the_folder(tmp_path, template_doc):
    p = Project.create(tmp_path, "My Website", template_doc)
    for sub in ("assets", "exports", "previews"):
        assert (p.folder / sub).is_dir()
    assert p.file.is_file() and p.name == "My Website" and not p.dirty


def test_create_refuses_an_existing_folder(tmp_path, template_doc):
    Project.create(tmp_path, "Site", template_doc)
    with pytest.raises(ProjectError, match="already exists"):
        Project.create(tmp_path, "Site", template_doc)


def test_create_needs_a_usable_name(tmp_path, template_doc):
    with pytest.raises(ProjectError):
        Project.create(tmp_path, ' ?*: ', template_doc)


def test_folder_names_are_safe_on_ntfs():
    assert safe_folder_name('A<b>:c/d\\e|f?g*"') == "Abcdefg"
    assert safe_folder_name("  Trailing dots... ") == "Trailing dots"


def test_save_and_reopen_keeps_everything(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    change(p)
    assert p.dirty
    p.save()
    assert not p.dirty
    again = Project.open(p.folder)
    assert again.document == p.document
    assert again.document["tokens"]["colors"]["primary"] == "#123456"


def test_open_accepts_the_file_itself(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    assert Project.open(p.file).folder == p.folder


def test_save_leaves_no_temporary_files(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    change(p)
    p.save()
    assert not [f for f in os.listdir(p.folder) if f.endswith(".tmp")]


def test_failed_save_keeps_the_previous_file(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    original = p.file.read_text(encoding="utf-8")
    p.history.apply("break", lambda d: d["tokens"]["colors"].update(primary="nope"))
    with pytest.raises(ProjectError, match="not saved"):
        p.save()
    assert p.file.read_text(encoding="utf-8") == original


def test_open_reports_problems_usefully(tmp_path):
    with pytest.raises(ProjectError, match="not a Mulusa"):
        Project.open(tmp_path)
    (tmp_path / "project.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ProjectError, match="not valid JSON"):
        Project.open(tmp_path)
    (tmp_path / "project.json").write_text(json.dumps({"schema": "x"}), encoding="utf-8")
    with pytest.raises(ProjectError) as caught:
        Project.open(tmp_path)
    assert caught.value.details


def test_autosave_never_touches_the_saved_project(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    assert p.autosave() is False  # Nothing to do.
    saved = p.file.read_text(encoding="utf-8")
    change(p)
    assert p.autosave() is True
    assert p.autosave_file.is_file()
    assert p.file.read_text(encoding="utf-8") == saved


def test_recovering_autosave_after_a_crash(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    change(p)
    p.autosave()
    reopened = Project.open(p.folder)  # The crash: unsaved work exists only in the autosave.
    assert reopened.document["tokens"]["colors"]["primary"] != "#123456"
    assert reopened.has_recoverable_autosave()
    reopened.recover_autosave()
    assert reopened.document["tokens"]["colors"]["primary"] == "#123456"
    assert reopened.dirty and reopened.recovered
    reopened.save()
    assert not reopened.has_recoverable_autosave()


def test_damaged_autosave_is_reported_and_project_survives(tmp_path, template_doc):
    p = Project.create(tmp_path, "Site", template_doc)
    p.autosave_file.write_text("{oops", encoding="utf-8")
    with pytest.raises(ProjectError):
        p.recover_autosave()
    assert p.name == "Site"


def test_settings_round_trip_and_damage():
    s = Settings.load()
    s.appearance = "light"
    s.add_recent("/x/a")
    s.add_recent("/x/b")
    s.add_recent("/x/a")
    s.save()
    again = Settings.load()
    assert again.appearance == "light" and again.recent == ["/x/a", "/x/b"]


def test_damaged_settings_fall_back_to_defaults():
    from mulusa_theme_studio.core.settings import config_dir

    config_dir().mkdir(parents=True, exist_ok=True)
    (config_dir() / "settings.json").write_text("{bad", encoding="utf-8")
    assert Settings.load().appearance == "dark"
