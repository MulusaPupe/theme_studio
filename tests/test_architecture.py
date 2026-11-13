"""The layering is enforced, because the whole long-term plan depends on it."""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "mulusa_theme_studio"


def imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add("." * node.level + (node.module or ""))
    return found


def files(package: str):
    return list((PKG / package).rglob("*.py"))


def test_core_render_and_exporters_do_not_use_qt():
    for package in ("core", "render", "exporters", "components"):
        for file in files(package):
            assert not [i for i in imports(file) if i.startswith(("PySide6", "PIL.ImageQt"))], file


def test_core_depends_on_nothing_above_it():
    for file in files("core"):
        for name in imports(file):
            assert not {"render", "ui", "exporters", "components"} & set(name.split(".")), (file, name)


def test_render_does_not_depend_on_ui_or_exporters():
    for file in files("render"):
        for name in imports(file):
            assert not any(part in name.split(".") for part in ("ui", "exporters")), (file, name)


def test_no_platform_knowledge_in_the_engine_or_editor():
    """WordPress belongs only in its exporter, never in the document, renderer or canvas."""
    for package in ("core", "render", "components"):
        for file in files(package):
            assert "wordpress" not in file.read_text(encoding="utf-8").lower(), file
    assert "wordpress" not in (PKG / "ui" / "canvas.py").read_text(encoding="utf-8").lower()


def test_the_resource_library_has_no_qt_and_no_editor_dependency():
    """Importing and converting packages is plain Python; the window lives in ui/ and calls into it."""
    for file in files("library"):
        for name in imports(file):
            assert not name.startswith(("PySide6", "PIL.ImageQt")), (file, name)
            assert not {"ui", "exporters"} & set(name.split(".")), (file, name)


def test_imported_code_is_never_executed():
    """No eval, exec, subprocess or dynamic import anywhere in the library package."""
    for file in files("library"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "compile", "__import__"), (file, node.func.id)
        assert not {"subprocess", "importlib", "runpy", "os.system"} & imports(file), file
