"""Inspecting and importing resource packages.

    inspect_package(path)  ->  Inspection   what is inside, what it is, its licence, what will convert
    import_package(path, store) -> ImportResult   converts it and files it in the user's library

Supported: ZIP files and folders holding an HTML/CSS website, a block theme, block patterns,
a Mulusa template or section, or a collection of images; and single .html, .json (pattern or
Mulusa) and .php pattern files. Nothing in a package is executed. Packages the editor cannot
convert (classic PHP themes, for example) are kept as "reference only", never reported as imported.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from PIL import Image

from ..core.document import SCHEMA, migrate_document, validate_document, walk_nodes
from ..core.errors import StudioError
from ..core.media import MediaError, store_upload
from . import blocks as blocklib
from .convert import Report, add_page, blank_document, finish
from .html_import import convert_site
from .model import Resource, identify_licence
from .safezip import PackageError, extract
from .store import ResourceStore, file_digest, write_json

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_PAGES = 30


@dataclass
class Inspection:
    path: Path
    root: Path                       # the folder that was inspected (extracted for a ZIP)
    kind: str = "unknown"            # html_site | block_theme | classic_theme | patterns | mulusa | media | unknown
    name: str = ""
    description: str = ""
    author: str = ""
    licence: str = "Unknown"
    licence_text: str = ""
    source_url: str = ""
    pages: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)
    scripts: int = 0
    php: int = 0
    images: int = 0
    skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    compatibility: str = "unsupported"
    _temp: tempfile.TemporaryDirectory | None = None

    @property
    def single(self) -> bool:
        """A single file (not a ZIP or folder)."""
        return self.path.is_file() and self.path.suffix.lower() != ".zip"

    @property
    def summary(self) -> list[str]:
        lines = [f"Type: {KIND_NAMES.get(self.kind, self.kind)}"]
        if self.pages:
            lines.append(f"Pages: {len(self.pages)} ({', '.join(self.pages[:6])}{'…' if len(self.pages) > 6 else ''})")
        if self.patterns:
            lines.append(f"Patterns: {len(self.patterns)}")
        if self.stylesheets:
            lines.append(f"Stylesheets: {len(self.stylesheets)}")
        if self.images:
            lines.append(f"Images: {self.images}")
        if self.scripts:
            lines.append(f"Scripts: {self.scripts} (never run; interactive behaviour is not imported)")
        if self.php:
            lines.append(f"PHP files: {self.php} (never run)")
        return lines

    def close(self) -> None:
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None


KIND_NAMES = {
    "html_site": "HTML/CSS website", "block_theme": "WordPress block theme", "classic_theme": "WordPress classic (PHP) theme",
    "patterns": "WordPress block patterns", "mulusa": "Mulusa template or section", "media": "Image collection", "unknown": "Not recognised",
}


@dataclass
class ImportResult:
    resources: list[Resource]
    report: list[str]
    duplicate: bool = False


# ---- inspection ------------------------------------------------------------------------------
def _read_text(path: Path, limit: int = 4 * 1024 * 1024) -> str:
    try:
        with open(path, "rb") as handle:
            return handle.read(limit).decode("utf-8", errors="replace")
    except OSError:
        return ""


def theme_header(text: str) -> dict[str, str]:
    """The comment header of a theme's style.css or a pattern file: 'Theme Name: X' lines."""
    out = {}
    head = text[:8192]
    for key in ("Theme Name", "Description", "Author", "Author URI", "Theme URI", "Version", "License", "License URI", "Text Domain",
                "Title", "Slug", "Categories", "Keywords", "Block Types"):
        m = re.search(rf"^[\s*#@]*{re.escape(key)}\s*:\s*(.+?)\s*$", head, re.M)
        if m:
            out[key] = m.group(1).strip()
    return out


def _package_root(folder: Path) -> Path:
    """A ZIP often wraps everything in one folder; look inside it."""
    entries = [p for p in folder.iterdir() if not p.name.startswith(".")]
    while len(entries) == 1 and entries[0].is_dir():
        folder = entries[0]
        entries = [p for p in folder.iterdir() if not p.name.startswith(".")]
    return folder


def _licence_from_files(root: Path) -> tuple[str, str]:
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "LICENCE.txt", "license.txt", "COPYING", "README.txt", "readme.txt", "README.md"):
        file = root / name
        if file.is_file():
            text = _read_text(file, 20000)
            for pattern, lic in (
                (r"Creative Commons Attribution 3\.0|CC BY 3\.0|creativecommons\.org/licenses/by/3\.0", "CC-BY-3.0"),
                (r"Creative Commons Attribution 4\.0|CC BY 4\.0|creativecommons\.org/licenses/by/4\.0", "CC-BY-4.0"),
                (r"Permission is hereby granted, free of charge", "MIT"),
                (r"Apache License,?\s+Version 2\.0", "Apache-2.0"),
                (r"GNU GENERAL PUBLIC LICENSE\s+Version 3", "GPL-3.0-or-later"),
                (r"GNU GENERAL PUBLIC LICENSE\s+Version 2", "GPL-2.0-or-later"),
                (r"Permission to use, copy, modify, and/or distribute", "ISC"),
                (r"This is free and unencumbered software released into the public domain", "Unlicense"),
                (r"CC0 1\.0", "CC0-1.0"),
                (r"License:\s*(.+)", None),
            ):
                m = re.search(pattern, text, re.I)
                if m:
                    found = lic or identify_licence(m.group(1)).id
                    if found != "Unknown":
                        return found, text[:4000]
    return "Unknown", ""


def inspect_package(path: Path) -> Inspection:
    path = Path(path)
    if not path.exists():
        raise PackageError(f"{path} does not exist.")
    temp = None
    if path.is_file() and path.suffix.lower() == ".zip":
        temp = tempfile.TemporaryDirectory(prefix="mts-inspect-")
        extracted = extract(path, Path(temp.name) / "x")
        root = _package_root(extracted.root)
        skipped = extracted.skipped
    elif path.is_dir():
        root, skipped = path, []
    else:
        root, skipped = path.parent, []
    ins = Inspection(path=path, root=root, skipped=skipped, _temp=temp)
    ins.name = path.stem.replace("-", " ").replace("_", " ").strip().title()
    try:
        _classify(ins, path)
    except Exception:
        ins.close()
        raise
    return ins


def _classify(ins: Inspection, path: Path) -> None:
    root = ins.root
    single = path if path.is_file() and path.suffix.lower() != ".zip" else None
    files = [single] if single else [p for p in root.rglob("*") if p.is_file() and len(p.relative_to(root).parts) < 8]
    rel = lambda p: p.relative_to(root).as_posix() if not single else p.name  # noqa: E731
    ins.scripts = sum(p.suffix.lower() in (".js", ".mjs") for p in files)
    ins.php = sum(p.suffix.lower() == ".php" for p in files)
    ins.images = sum(p.suffix.lower() in IMAGE_SUFFIXES | {".svg"} for p in files)
    ins.stylesheets = [rel(p) for p in files if p.suffix.lower() == ".css"]

    # A Mulusa file: a template, project or section document.
    for p in files:
        if p.suffix.lower() == ".json" and p.name in ("template.json", "project.json", "section.json") or single and p.suffix.lower() == ".json":
            data = _json(p)
            if isinstance(data, dict) and (str(data.get("schema", "")).startswith("mulusa.")):
                ins.kind, ins.compatibility = "mulusa", "full"
                meta = data.get("meta", {})
                ins.name = meta.get("template_name") or meta.get("name") or ins.name
                ins.description = meta.get("description", "")
                ins.licence = data.get("licence", "Original" if meta.get("author") == "Mulusa Innovations" else "Unknown")
                return
            if isinstance(data, (dict, list)) and _api_patterns(data):
                ins.kind, ins.compatibility = "patterns", "partial"
                ins.patterns = [p["title"] for p in _api_patterns(data)]
                ins.licence = "GPL-2.0-or-later" if all(p.get("from_directory") for p in _api_patterns(data)) else "Unknown"
                return

    style = root / "style.css" if not single else None
    header = theme_header(_read_text(style)) if style and style.is_file() else {}
    if header.get("Theme Name"):
        ins.name = header["Theme Name"]
        ins.description = header.get("Description", "")
        ins.author = header.get("Author", "")
        ins.source_url = header.get("Theme URI", "")
        ins.licence = identify_licence(header.get("License")).id
        templates = [p for p in files if p.suffix.lower() == ".html" and p.parent.name in ("templates", "block-templates")]
        ins.patterns = [rel(p) for p in files if p.parent.name == "patterns" and p.suffix.lower() in (".php", ".html")]
        if templates:
            ins.kind = "block_theme"
            ins.pages = [p.stem for p in templates]
            ins.compatibility = "partial"
        else:
            ins.kind = "classic_theme"
            ins.compatibility = "reference"
            ins.problems.append("A classic theme builds its pages with PHP at run time, which cannot be converted without running it. It is kept for reference only.")
    else:
        htmls = [p for p in files if p.suffix.lower() in (".html", ".htm")]
        pattern_files = [p for p in files if p.suffix.lower() in (".php", ".html") and "<!-- wp:" in _read_text(p, 200000)]
        if pattern_files and (not htmls or all(p in pattern_files for p in htmls)):
            ins.kind, ins.compatibility = "patterns", "partial"
            ins.patterns = [rel(p) for p in pattern_files]
        elif htmls:
            ins.kind, ins.compatibility = "html_site", "partial"
            htmls.sort(key=lambda p: (p.name.lower() not in ("index.html", "index.htm"), len(p.relative_to(root).parts) if not single else 0, p.name))
            ins.pages = [rel(p) for p in htmls[:MAX_PAGES]]
            if len(htmls) > MAX_PAGES:
                ins.problems.append(f"Only the first {MAX_PAGES} of {len(htmls)} HTML pages are converted.")
        elif ins.images:
            ins.kind, ins.compatibility = "media", "full"
        else:
            ins.problems.append("No HTML pages, theme, patterns or images were found in this package.")
    if ins.licence == "Unknown" and not single:
        ins.licence, ins.licence_text = _licence_from_files(root)
    if ins.licence == "Unknown":
        ins.problems.append("No licence was found. You may use it in your own projects only if you own it or have permission; "
                            "it will not be treated as redistributable.")
    if ins.skipped:
        ins.problems.append(f"{len(ins.skipped)} file(s) were left out because websites do not need them.")


def _json(path: Path):
    try:
        return json.loads(_read_text(path))
    except ValueError:
        return None


def _api_patterns(data) -> list[dict]:
    """Patterns in the shape the WordPress.org pattern directory API returns (or a list of them)."""
    items = data if isinstance(data, list) else [data]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("pattern_content") or item.get("content")
        if isinstance(content, dict):
            content = content.get("raw") or content.get("rendered")
        title = item.get("title")
        if isinstance(title, dict):
            title = title.get("rendered")
        if isinstance(content, str) and "<!-- wp:" in content:
            out.append({"title": str(title or "Pattern"), "content": content, "from_directory": bool(item.get("id") and item.get("link", "").startswith("https://wordpress.org/patterns/")),
                        "link": item.get("link", ""), "categories": item.get("pattern_categories") or item.get("category_slugs") or item.get("categories") or []})
    return out


# ---- import ----------------------------------------------------------------------------------
class _Media:
    """Copies the images a converted document refers to into the item's asset folder."""

    def __init__(self, ins: Inspection, folder: Path, doc_assets: list, report: Report, base: Path) -> None:
        self.ins, self.folder, self.assets, self.report = ins, folder, doc_assets, report
        self.base = base
        self.by_path: dict[Path, dict] = {}

    def __call__(self, src: str, alt: str = ""):
        src = (src or "").strip()
        if not src or src.startswith("data:"):
            if src:
                self.report.lost("Images embedded as data: URLs")
            return None
        if src.startswith(blocklib.THEME_URI):
            target = self.ins.root / src[len(blocklib.THEME_URI):].lstrip("/")
        elif re.match(r"^(https?:)?//", src):
            self.report.lost("Remote images (not downloaded; replace them in the editor)")
            return {"kind": "placeholder", "seed": f"r{abs(hash(src)) % 10**8}", "subject": "abstract", "ratio": 1.5, "label": alt or "Image"}
        else:
            target = (self.base / src.split("?")[0].split("#")[0]).resolve()
        try:
            target.relative_to(self.ins.root.resolve())
        except ValueError:
            self.report.lost("Images outside the package")
            return None
        if not target.is_file():
            self.report.lost("Images missing from the package")
            return None
        if target.suffix.lower() == ".svg":
            self.report.lost("SVG images (add them again as PNG or JPEG)")
            return None
        if target in self.by_path:
            return {"kind": "asset", "id": self.by_path[target]["id"]}
        try:
            asset = store_upload(self.folder, target)
        except (MediaError, StudioError):
            self.report.lost("Images that could not be read")
            return None
        self.assets.append(asset)
        self.by_path[target] = asset
        return {"kind": "asset", "id": asset["id"]}


def import_package(path: Path, store: ResourceStore, *, name: str = "", category: str = "", source: str = "",
                   source_url: str = "", licence: str = "", tags: list[str] | None = None) -> ImportResult:
    path = Path(path)
    digest = file_digest(path) if path.is_file() else _folder_digest(path)
    existing = store.find_by_digest(digest)
    if existing:
        return ImportResult([existing], [f"Already in your library as '{existing.name}'."], duplicate=True)
    ins = inspect_package(path)
    try:
        return _import(ins, store, digest, name=name, category=category, source=source, source_url=source_url, licence=licence, tags=tags or [])
    finally:
        ins.close()


def _folder_digest(folder: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(folder).as_posix().encode())
            h.update(file_digest(p).encode())
    return h.hexdigest()


def _base(ins: Inspection, title: str, kind: str, rid: str, digest: str, **kw) -> Resource:
    return Resource(
        id=rid, name=(title or ins.name or "Imported resource")[:80], kind=kind, category=kw.get("category") or "",
        description=ins.description[:300], tags=kw.get("tags", []), source=kw.get("source") or ("Imported file"),
        source_url=kw.get("source_url") or ins.source_url, author=ins.author or "Unknown",
        licence=kw.get("licence") or ins.licence, format=KIND_NAMES.get(ins.kind, ins.kind), compatibility=ins.compatibility,
        responsive="Converted styles, with width media queries as tablet and mobile overrides" if ins.kind == "html_site" else "Desktop, tablet and mobile",
        origin="imported", sha256=digest,
    )


def _keep_original(ins: Inspection, item: Path) -> None:
    """The original package is kept beside the conversion, for inspection."""
    target = item / "original"
    target.mkdir(parents=True, exist_ok=True)
    if ins.path.is_file():
        shutil.copy2(ins.path, target / ins.path.name)
    else:
        shutil.copytree(ins.path, target / ins.path.name, dirs_exist_ok=True)


def _save_project(item: Path, doc: dict) -> Path:
    folder = item / "project"
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    write_json(folder / "project.json", doc)
    return folder


def _import(ins: Inspection, store: ResourceStore, digest: str, **kw) -> ImportResult:
    report = Report()
    for line in ins.problems:
        report.note(line)
    rid = store.new_id()
    item = store.item_dir(rid)
    if ins.kind in ("unknown", "classic_theme"):
        if ins.kind == "unknown":
            raise PackageError("Nothing in this package can be imported: " + "; ".join(ins.problems or ["it was not recognised"]))
        res = _base(ins, kw["name"], "package", rid, digest, **kw)
        res.compatibility = "reference"
        _keep_original(ins, item)
        res.path = str(item / "original")
        res.report = report.lines()
        store.add(res)
        return ImportResult([res], res.report)

    _keep_original(ins, item)
    project_folder = item / "project"
    (project_folder / "assets").mkdir(parents=True, exist_ok=True)
    resources: list[Resource] = []

    if ins.kind == "media":
        files = [p for p in ins.root.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES] if not ins.single else [ins.path]
        assets = []
        for p in files:
            try:
                assets.append(store_upload(project_folder, p))
            except (MediaError, StudioError):
                report.lost("Images that could not be read")
        if not assets:
            shutil.rmtree(item, ignore_errors=True)
            raise PackageError("None of the images in this package could be read.")
        res = _base(ins, kw["name"], "image", rid, digest, **kw)
        res.path = str(project_folder / "assets")
        res.preview = str(project_folder / "assets" / assets[0]["file"])
        res.data = {"assets": assets}
        res.report = report.lines()
        store.add(res)
        return ImportResult([res], res.report)

    if ins.kind == "mulusa":
        data = _json(ins.path if ins.single else next((ins.root / n for n in ("template.json", "project.json", "section.json") if (ins.root / n).is_file()), next(ins.root.rglob("*.json"))))
        if data.get("schema") == "mulusa.section/1":
            doc = blank_document(kw["name"] or ins.name)
            add_page(doc, "Home", data.get("nodes", []), home=True)
        else:
            doc = migrate_document(data)
        issues = validate_document(doc)
        if issues:
            shutil.rmtree(item, ignore_errors=True)
            raise PackageError("This Mulusa file is damaged: " + issues[0])
        assets_src = (ins.root / "assets") if not ins.single else None
        if assets_src and assets_src.is_dir():
            shutil.copytree(assets_src, project_folder / "assets", dirs_exist_ok=True)
        kind = "section" if data.get("schema") == "mulusa.section/1" else "template"
        return _finish_template(ins, store, doc, project_folder, report, rid, digest, kind, resources, **kw)

    if ins.kind == "html_site":
        pages = []
        for rel in ins.pages:
            file = ins.path if ins.single else ins.root / rel
            pages.append((rel, _read_text(file)))
        sheets = []
        for rel in ins.stylesheets:
            if any(x in rel.lower() for x in ("bootstrap", "font-awesome", "fontawesome", "animate", ".min.css")) and "main" not in rel.lower():
                report.note(f"Framework stylesheet {rel} was read for layout only.")
            sheets.append(_read_text(ins.root / rel))
        media = _Media(ins, project_folder, [], report, (ins.path.parent if ins.single else ins.root / PurePosixPath(ins.pages[0]).parent))
        doc = convert_site(pages, sheets, media, kw["name"] or ins.name, report, media.assets)
        doc["media"]["assets"] = media.assets
        return _finish_template(ins, store, doc, project_folder, report, rid, digest, "template", resources, **kw)

    if ins.kind in ("patterns", "block_theme"):
        palette, fonts = _theme_json(ins.root) if ins.kind == "block_theme" else ({}, {})
        patterns = _pattern_files(ins, report)
        media = _Media(ins, project_folder, [], report, ins.root)
        slugs = {p["slug"]: p["content"] for p in patterns if p.get("slug")}
        slugs.update({k.split("/")[-1]: v for k, v in list(slugs.items())})
        conv = blocklib.BlockConverter(report, media, palette, slugs)
        doc = blank_document(kw["name"] or ins.name, colors=_colors_from_palette(palette), fonts=fonts)
        if ins.kind == "block_theme":
            parts = {p.stem: blocklib.strip_php(_read_text(p), report) for p in (ins.root / "parts").glob("*.html")} if (ins.root / "parts").is_dir() else {}
            conv.patterns.update({f"part:{k}": v for k, v in parts.items()})
            tdir = ins.root / ("templates" if (ins.root / "templates").is_dir() else "block-templates")
            # The home page is whichever of the likely templates converts to the most content.
            best, front = [], None
            quiet = Report()
            for n in ("front-page", "page-home", "home", "index", "page"):
                file = tdir / f"{n}.html"
                if file.is_file():
                    trial = blocklib.BlockConverter(quiet, lambda *a: None, palette, conv.patterns).sections(
                        _without_parts(blocklib.parse_blocks(blocklib.strip_php(_read_text(file), quiet))))
                    if len(trial) > len(best):
                        best, front = trial, file
            markup = blocklib.strip_php(_read_text(front), report) if front else ""
            sections = conv.sections(_without_parts(blocklib.parse_blocks(markup)))
            add_page(doc, "Home", sections, home=True)
            report.note("The theme's header and footer template parts were mapped to the editor's site header and footer; "
                        "its navigation menu must be rebuilt in Pages.")
            others = [p for p in tdir.glob("*.html") if p != front and p.stem in ("page", "about", "contact", "page-about", "page-contact")]
            for p in others[:6]:
                secs = conv.sections(_without_parts(blocklib.parse_blocks(blocklib.strip_php(_read_text(p), report))))
                if secs:
                    add_page(doc, p.stem.replace("page-", "").replace("-", " ").title(), secs)
            # Each of the theme's patterns is also offered as a section resource of its own.
            for pat in patterns:
                secs = conv.sections(blocklib.parse_blocks(pat["content"]), pat.get("categories", ""))
                if secs:
                    resources.append(_section_resource(ins, store, pat, secs, palette, fonts, media, report, rid, **kw))
        else:
            for pat in patterns:
                secs = conv.sections(blocklib.parse_blocks(pat["content"]), pat.get("categories", ""))
                if secs:
                    resources.append(_section_resource(ins, store, pat, secs, palette, fonts, media, report, rid, **kw))
            if not resources:
                shutil.rmtree(item, ignore_errors=True)
                raise PackageError("No pattern in this package contains blocks the editor can convert.")
            shutil.rmtree(item / "project", ignore_errors=True)
            for res in resources:
                store.add(res)
            return ImportResult(resources, report.lines())
        doc["media"]["assets"] = media.assets
        return _finish_template(ins, store, doc, project_folder, report, rid, digest, "template", resources, **kw)

    raise PackageError(f"Packages of type {ins.kind} are not supported.")


def _without_parts(blocks: list) -> list:
    return [b for b in blocks if b.name != "core/template-part"]


def _finish_template(ins, store, doc, project_folder, report, rid, digest, kind, extra, **kw) -> ImportResult:
    issues = finish(doc)
    if issues:
        shutil.rmtree(store.item_dir(rid), ignore_errors=True)
        raise PackageError("The converted document did not validate: " + "; ".join(issues[:3]))
    write_json(project_folder / "project.json", doc)
    res = _base(ins, kw["name"], kind, rid, digest, **kw)
    sections = sum(len(p["nodes"]) for p in doc["pages"])
    if ins.compatibility == "partial" and report.losses == 0 and not report.notes:
        res.compatibility = "full"
    res.path = str(project_folder)
    res.data = {"pages": len(doc["pages"]), "sections": sections, "assets": len(doc["media"]["assets"])}
    res.report = report.lines()
    res.preview = _package_screenshot(ins, store.item_dir(rid))
    store.add(res)
    for other in extra:
        other.report = report.lines()
        store.add(other)
    return ImportResult([res, *extra], res.report)


def _package_screenshot(ins: Inspection, item: Path) -> str:
    """A theme's own screenshot (WordPress themes ship one), checked as a real image and copied beside the item."""
    if ins.single:
        return ""
    for name in ("screenshot.png", "screenshot.jpg", "screenshot.webp", "preview.png", "preview.jpg"):
        source = ins.root / name
        if source.is_file() and source.stat().st_size < 8 * 1024 * 1024:
            try:
                with Image.open(source) as image:
                    image.verify()
            except Exception:   # noqa: BLE001 - any unreadable image is simply not used
                continue
            target = item / ("preview" + source.suffix.lower())
            shutil.copyfile(source, target)
            return str(target)
    return ""


def _section_resource(ins, store, pat, sections, palette, fonts, media, report, parent_id, **kw) -> Resource:
    """One pattern -> one section resource with its own small document (sections on one page)."""
    rid = store.new_id()
    folder = store.item_dir(rid) / "project"
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    doc = blank_document(pat.get("title") or "Pattern", colors=_colors_from_palette(palette), fonts=fonts)
    add_page(doc, "Home", sections, home=True)
    used = {n["props"]["media"]["id"] for s in sections for n in walk_nodes([s]) if isinstance(n.get("props", {}).get("media"), dict) and n["props"]["media"].get("kind") == "asset"}
    used |= {s["props"]["background"]["media"]["id"] for s in sections if isinstance(s["props"].get("background"), dict) and s["props"]["background"].get("media", {}).get("kind") == "asset"}
    for asset in media.assets:
        if asset["id"] in used:
            doc["media"]["assets"].append(asset)
            shutil.copy2(media.folder / "assets" / asset["file"], folder / "assets" / asset["file"])
    finish(doc)
    write_json(folder / "project.json", doc)
    res = _base(ins, pat.get("title") or "Pattern", "section", rid, "", **{**kw, "name": pat.get("title")})
    res.category = _category_from(pat.get("categories", "")) or kw.get("category") or "content"
    res.compatibility = "partial"
    res.source_url = pat.get("link") or res.source_url
    res.path = str(folder)
    res.data = {"sections": len(sections), "parent": parent_id}
    res.tags = sorted({*res.tags, *[t.strip() for t in str(pat.get("categories", "")).split(",") if t.strip()]})[:8]
    return res


def _category_from(categories) -> str:
    from .convert import guess_role
    text = " ".join(categories) if isinstance(categories, list) else str(categories)
    role = guess_role(text) if text else ""
    return "" if role == "content" else role


def _pattern_files(ins: Inspection, report: Report) -> list[dict]:
    out = []
    if ins.single and ins.path.suffix.lower() == ".json":
        for p in _api_patterns(_json(ins.path)):
            out.append({"title": p["title"], "content": p["content"], "link": p["link"], "categories": ",".join(map(str, p["categories"])), "slug": ""})
        return out
    files = [ins.path] if ins.single else [ins.root / rel for rel in ins.patterns] if ins.kind == "patterns" else \
        sorted((ins.root / "patterns").glob("*.*")) if (ins.root / "patterns").is_dir() else []
    for file in files:
        if file.suffix.lower() not in (".php", ".html"):
            continue
        text = _read_text(file)
        header = theme_header(text)
        if header.get("Block Types") and "template-part" in header["Block Types"]:
            pass
        body = blocklib.strip_php(text, report)
        out.append({"title": header.get("Title") or file.stem.replace("-", " ").title(), "slug": header.get("Slug", ""),
                    "categories": header.get("Categories", ""), "content": body, "link": ""})
    return out


def _theme_json(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    data = _json(root / "theme.json") or {}
    settings = data.get("settings", {}) if isinstance(data, dict) else {}
    palette = {}
    for entry in (settings.get("color", {}) or {}).get("palette", []) or []:
        if isinstance(entry, dict) and str(entry.get("color", "")).startswith("#"):
            palette[str(entry.get("slug"))] = entry["color"][:7].lower()
    fonts = {}
    from ..render.fonts import catalog
    for entry in (settings.get("typography", {}) or {}).get("fontFamilies", []) or []:
        family = str(entry.get("fontFamily", "")).split(",")[0].strip().strip("'\"")
        if family in catalog():
            fonts.setdefault("heading" if "head" in str(entry.get("slug")) else "body", family)
    if "body" in fonts and "heading" not in fonts:
        fonts["heading"] = fonts["body"]
    return palette, fonts


def _colors_from_palette(palette: dict[str, str]) -> dict[str, str]:
    """Maps a theme's named colours onto the editor's colour roles, where the names say which is which."""
    out = {}
    pick = lambda *names: next((palette[n] for n in names if n in palette and len(palette[n]) == 7), None)  # noqa: E731
    for role, names in (("background", ("base", "background", "white")), ("text", ("contrast", "foreground", "black", "text")),
                        ("primary", ("primary", "accent-1", "accent", "vivid-cyan-blue")), ("secondary", ("secondary", "accent-2")),
                        ("accent", ("tertiary", "accent-3", "accent-2", "secondary")), ("surface", ("base-2", "tertiary", "surface", "light"))):
        if (c := pick(*names)):
            out[role] = c
    return out


def section_trees(resource: Resource) -> tuple[list[dict], list[dict], Path]:
    """The sections a section or template resource offers for insertion, with its assets and their folder."""
    folder = Path(resource.path)
    doc = json.loads((folder / "project.json").read_text(encoding="utf-8"))
    home = next((p for p in doc["pages"] if p.get("home")), doc["pages"][0])
    return home["nodes"], doc["media"].get("assets", []), folder / "assets"


def load_document(resource: Resource) -> dict:
    doc = json.loads((Path(resource.path) / "project.json").read_text(encoding="utf-8"))
    doc = migrate_document(doc)
    if doc.get("schema") != SCHEMA or validate_document(doc):
        raise PackageError(f"'{resource.name}' is damaged and cannot be opened.")
    return doc
