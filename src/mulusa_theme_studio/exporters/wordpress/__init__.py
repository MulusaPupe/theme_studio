"""The WordPress block theme exporter. All WordPress knowledge lives in this package."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from ...core.document import Document, home_page, slugify, walk_document
from ...core.pages import broken_page_links
from ...render.fonts import font_files
from ...render.site import PAGE_JS, _all_styles
from ...render.fonts import catalog
from .. import ExportResult, Exporter, register
from .blocks import serialize_all
from .check import ERROR, WARNING, Issue, check_plugin_data, check_theme
from .content_plugin import plugin_php
from .files import (
    Identity, as_json, design_css, functions_php, main_wrap, page_body, page_slug_map, pattern_file, pattern_ref, readme_txt, resolve_for_php,
    role_nodes, style_css, template, theme_json,
)
from .translate import Assets, Report, Rules, Tokens, Translator


@dataclass
class ExportOptions:
    theme_name: str = ""
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    include_content_plugin: bool = True
    screenshot: bytes | None = None  # A PNG of the design, when the caller can draw one.


@dataclass
class WordPressResult(ExportResult):
    plugin: Path | None = None
    issues: list[Issue] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)  # How design pages map to WordPress pages.


def _identity(doc: Document, options: ExportOptions) -> Identity:
    meta = doc["meta"]
    name = options.theme_name.strip() or str(meta.get("name", "")).strip() or "Mulusa site"
    slug = slugify(name)[:60].strip("-") or "mulusa-site"
    if slug[0].isdigit():
        slug = f"site-{slug}"
    return Identity(name, slug, options.description.strip() or str(meta.get("description", "")), options.author.strip() or str(meta.get("author", "")), options.version.strip() or "1.0.0")


def _families(doc: Document) -> set[str]:
    fonts = doc["tokens"]["fonts"]
    families = {fonts["heading"], fonts["body"]} | set(fonts.get("extra", []))
    return families | {str(style["font_family"]) for style in _all_styles(doc) if str(style.get("font_family", "")) in catalog()}


def _default_screenshot(doc: Document, who: Identity) -> bytes:
    """A plain card in the design's colours, for when no drawing of the design is available."""
    from io import BytesIO

    colors = doc["tokens"]["colors"]
    image = Image.new("RGB", (1200, 900), colors["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1200, 540), fill=colors["primary"])
    for index, key in enumerate(("secondary", "accent", "surface", "text", "muted", "border")):
        draw.rectangle((90 + index * 170, 640, 230 + index * 170, 780), fill=colors[key])
    return_buffer = BytesIO()
    image.save(return_buffer, "PNG")
    return return_buffer.getvalue()


@dataclass
class _Build:
    who: Identity
    tokens: Tokens
    report: Report
    assets: Assets
    rules: Rules
    files: dict[str, str]
    site: dict


def _build(doc: Document, options: ExportOptions) -> _Build:
    """Translates the document. Writes nothing."""
    who = _identity(doc, options)
    tokens = Tokens(hashlib.sha1(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:10])
    report, assets, rules = Report(), Assets(), Rules()
    files: dict[str, str] = {}

    def theme(nodes) -> str:
        return serialize_all(Translator(doc, tokens, report=report, assets=assets, rules=rules).nodes(nodes))

    def add_pattern(name: str, title: str, markup: str, **options_) -> str:
        files[f"patterns/{name}.php"] = pattern_file(who, name, title, resolve_for_php(markup, tokens, who), **options_)
        return pattern_ref(who, name)

    # Shared parts. They go through patterns because block files cannot work out addresses.
    files["parts/header.html"] = add_pattern("header", "Site header", theme([doc["site"]["header"]])) + "\n"
    files["parts/footer.html"] = add_pattern("footer", "Site footer", theme([doc["site"]["footer"]])) + "\n"

    single = add_pattern("single", "Single post", theme(role_nodes(doc, "single")))
    files["templates/single.html"] = template(single)
    listing = add_pattern("archive", "Post list", theme(role_nodes(doc, "archive")))
    files["templates/archive.html"] = template(listing)
    files["templates/index.html"] = template(listing)  # Also covers the latest-posts home and search results.
    files["templates/404.html"] = template(add_pattern("not-found", "Page not found", theme(role_nodes(doc, "not_found"))))
    files["templates/page.html"] = template(page_body())
    files["templates/front-page.html"] = template(page_body())
    files["templates/page-landing.html"] = template(page_body(), header=False, footer=False)

    # Each page is a starter pattern too, and an entry for the plugin to import as real content.
    site: dict = {"nonce": tokens.nonce, "home": home_page(doc)["id"], "site_title": str(doc["site"]["header"].get("props", {}).get("brand") or who.name), "pages": [], "forms": {}}
    logo = doc["site"]["header"].get("props", {}).get("logo")
    if isinstance(logo, dict) and logo.get("kind") == "asset":
        asset = next((a for a in doc["media"].get("assets", []) if a.get("id") == logo.get("id")), None)
        if asset:
            site["logo"] = asset["file"]
            assets.images.add(asset["file"])
    for page in doc["pages"]:
        if page.get("role"):
            continue
        add_pattern(f"page-{page['slug']}", f"{page['title']} page", theme(page["nodes"]), inserter=True, page_starter=True)
        markup = serialize_all(Translator(doc, tokens, in_content=True, report=Report(), assets=assets, rules=rules).nodes(page["nodes"]))
        entry = {"id": page["id"], "slug": page["slug"], "title": page["title"], "description": page.get("description", ""), "content": markup}
        if page.get("layout") == "landing":
            entry["template"] = "page-landing"
        site["pages"].append(entry)
    site["forms"] = {re.sub(r"[^a-zA-Z0-9_-]", "", key).lower(): value for key, value in rules.forms.items()}
    return _Build(who, tokens, report, assets, rules, files, site)


def _write_theme(doc: Document, build: _Build, project_folder: Path | None, root: Path, options: ExportOptions) -> list[Issue]:
    """Writes the theme folder and returns any problem with the design's files."""
    issues: list[Issue] = []
    who = build.who
    families = _families(doc)
    root.mkdir(parents=True, exist_ok=True)
    (root / "style.css").write_text(style_css(who), encoding="utf-8")
    (root / "readme.txt").write_text(readme_txt(who, families), encoding="utf-8")
    (root / "theme.json").write_text(as_json(theme_json(doc, families)), encoding="utf-8")
    style = doc["tokens"].get("shape", {}).get("button_style", "solid")
    style = style if style in ("solid", "outline", "underline") else "solid"
    countdown = any(node.get("type") == "countdown" for node in walk_document(doc))
    (root / "functions.php").write_text(functions_php(who, f"mts-btnstyle-{style}", page_slug_map(doc), countdown), encoding="utf-8")
    if countdown:   # The studio's own countdown script, enqueued by functions.php.
        (root / "assets" / "js").mkdir(parents=True, exist_ok=True)
        (root / "assets" / "js" / "mulusa.js").write_text(PAGE_JS.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "screenshot.png").write_bytes(options.screenshot or _default_screenshot(doc, who))
    for name, text in build.files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    css_dir = root / "assets" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "mulusa.css").write_text(design_css(doc, build.rules.css()), encoding="utf-8")
    fonts = root / "assets" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for file in font_files(families):
        shutil.copyfile(file, fonts / file.name)
    images = root / "assets" / "images"
    if build.assets.images or build.assets.placeholders:
        images.mkdir(parents=True, exist_ok=True)
    for name in sorted(build.assets.images):
        source = (Path(project_folder) / "assets" / name) if project_folder else None
        if source is None or not source.is_file():
            issues.append(Issue(ERROR, f"The image file {name} is missing from the project.", "media", "Replace the image, or restore the file to the project's assets folder."))
            continue
        shutil.copyfile(source, images / name)  # Byte for byte, so quality is never reduced.
    for name, svg in build.assets.placeholders.items():
        (images / name).write_text(svg, encoding="utf-8")
    return issues


def _write_plugin(build: _Build, root: Path) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / f"{build.who.slug}-content.php").write_text(plugin_php(build.who, build.tokens.nonce), encoding="utf-8")
    (root / "data" / "site.json").write_text(json.dumps(build.site, ensure_ascii=False), encoding="utf-8")


def _zip_folder(folder: Path, target: Path) -> None:
    temporary = target.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                archive.write(file, Path(folder.name) / file.relative_to(folder))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            temporary.unlink(missing_ok=True)
            raise OSError(f"The archive {target.name} did not verify after writing.")
    temporary.replace(target)


def _design_issues(doc: Document, build: _Build) -> list[Issue]:
    issues = [Issue(ERROR, message, "design") for message in dict.fromkeys(build.report.errors)]
    issues += [Issue(WARNING, message, "design") for message in dict.fromkeys(build.report.warnings)]
    if not doc["meta"].get("author") and not build.who.author:
        issues.append(Issue(WARNING, "The theme has no author name.", "theme details", "Enter an author above."))
    for label in dict.fromkeys(broken_page_links(doc)):
        issues.append(Issue(WARNING, f"'{label}' links to a page that does not exist, so it will go to the homepage.", "links", "Choose a new destination for it."))
    placeholders = len(build.assets.placeholders)
    if placeholders:
        issues.append(Issue(WARNING, f"{placeholders} placeholder images remain. They work, but visitors will see them.", "media", "Replace them with your own images on the canvas."))
    if build.rules.forms:
        issues.append(Issue(WARNING, "This site has contact forms. They need the content plugin to be active, and the server must be able to send email.", "forms"))
    if not any(n.get("type") == "query" for n in walk_document(doc)):
        issues.append(Issue(WARNING, "No page lists posts. Posts you publish will only appear on the blog archive.", "dynamic content", "Add 'Latest posts' from Components if you want them on a page."))
    return issues


@register
class WordPressExporter(Exporter):
    id = "wordpress"
    label = "WordPress block theme"

    def check(self, doc: Document, project_folder: Path | None, options: ExportOptions | None = None) -> list[Issue]:
        """Builds the whole theme in a temporary folder and checks it, leaving nothing behind."""
        options = options or ExportOptions()
        build = _build(doc, options)
        issues = _design_issues(doc, build)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / build.who.slug
            issues += _write_theme(doc, build, project_folder, root, options)
            issues += check_theme(root, slug=build.who.slug)
            issues += check_plugin_data(build.site, build.tokens.nonce, root)
        return issues

    def validate(self, doc: Document) -> list[str]:
        return [str(issue) for issue in self.check(doc, None) if issue.severity == ERROR]

    def export(self, doc: Document, project_folder: Path, destination: Path, options: ExportOptions | None = None) -> WordPressResult:
        options = options or ExportOptions()
        build = _build(doc, options)
        issues = _design_issues(doc, build)
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / build.who.slug
            issues += _write_theme(doc, build, project_folder, root, options)
            issues += check_theme(root, slug=build.who.slug)
            issues += check_plugin_data(build.site, build.tokens.nonce, root)
            errors = [issue for issue in issues if issue.severity == ERROR]
            if errors:
                raise ExportFailed(errors, issues)
            output = destination / f"{build.who.slug}.zip"
            _zip_folder(root, output)
            plugin = None
            if options.include_content_plugin:
                plugin_root = Path(temp) / f"{build.who.slug}-content"
                _write_plugin(build, plugin_root)
                plugin = destination / f"{build.who.slug}-content.zip"
                _zip_folder(plugin_root, plugin)
        pages = [{"design": page["title"], "slug": page["slug"], "home": page["id"] == build.site["home"]} for page in build.site["pages"]]
        return WordPressResult(output, [str(issue) for issue in issues], plugin, issues, pages)


class ExportFailed(Exception):
    def __init__(self, errors: list[Issue], issues: list[Issue]) -> None:
        super().__init__(f"The theme was not exported: {errors[0]}")
        self.errors = errors
        self.issues = issues
