"""The static website exporter: plain HTML and CSS that any web host can serve.

It renders through ``render/site.py``, the same route as the canvas and the preview, so the
exported pages are what the designer saw. A static site has no server, so two things that need
one are handled honestly instead of being faked:

* Post lists ("Latest posts") have no posts to show. Their sections are left out, and the
  check says which pages lost a section. Post templates (single, archive) are not exported.
* Contact forms need somewhere to send to. The owner gives a form handler address (a service
  such as Formspree or their own script) or an email address, which opens the visitor's mail
  app. With neither, the export stops and says why.
"""
from __future__ import annotations

import copy
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ...core.document import Document, home_page, slugify, walk_document, walk_nodes
from ...core.pages import broken_page_links
from ...render.site import PAGE_JS, PAGE_JS_NAME, page_filename, write_site
from .. import ERROR, WARNING, ExportResult, Exporter, Issue, register

_EMAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[A-Za-z]{2,}$")
_FORM_OPEN = re.compile(r'<form([^>]*?) action="#" method="post">')
_EDITOR_TRACES = ("data-mts-id", "data-mts-type", "mts-sample-tag", "Live posts: samples")


@dataclass
class StaticOptions:
    site_name: str = ""
    form_action: str = ""  # A form handler URL (https://...). Preferred over email.
    form_email: str = ""  # Used when there is no handler: the form opens the visitor's mail app.


@dataclass
class StaticResult(ExportResult):
    folder: Path | None = None  # The unpacked site, ready to open in a browser.
    issues: list[Issue] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)  # title, file


class StaticExportFailed(Exception):
    def __init__(self, errors: list[Issue], issues: list[Issue]) -> None:
        super().__init__(f"The site was not exported: {errors[0]}")
        self.errors = errors
        self.issues = issues


def _slug(doc: Document, options: StaticOptions) -> tuple[str, str]:
    name = options.site_name.strip() or str(doc["meta"].get("name", "")).strip() or "Mulusa site"
    return name, (slugify(name)[:60].strip("-") or "mulusa-site")


def _has_query(node: dict) -> bool:
    return any(n.get("type") in ("query", "post_field") for n in walk_nodes([node]))


def _prepare(doc: Document) -> tuple[Document, list[Issue]]:
    """A copy of the document with what a static site cannot run taken out, and what was taken."""
    out = copy.deepcopy(doc)
    issues: list[Issue] = []
    roles = [p for p in out["pages"] if p.get("role")]
    if roles:
        out["pages"] = [p for p in out["pages"] if not p.get("role")]
        issues.append(Issue(WARNING, f"{len(roles)} post template(s) are not exported. A static site has no posts.", "post templates"))
    for page in out["pages"]:
        keep = [n for n in page["nodes"] if not _has_query(n)]
        dropped = len(page["nodes"]) - len(keep)
        if dropped:
            page["nodes"] = keep
            if all(n.get("props", {}).get("role") == "page_header" for n in keep):
                issues.append(Issue(WARNING, "Nothing is left on this page but its title, because it only listed posts.", page.get("title", "page"),
                                    "Remove it from the menu for a static site, or export for WordPress."))
            issues.append(Issue(WARNING, f"{dropped} section(s) listing posts are left out, because a static site has no posts.", page.get("title", "page"),
                                "Export for WordPress to keep them, or replace them with your own sections."))
    for part in ("header", "footer"):
        if _has_query(out["site"][part]):
            issues.append(Issue(ERROR, f"The site {part} lists posts, which a static site cannot do.", part, "Remove the posts list from it."))
    return out, issues


def _forms(doc: Document, options: StaticOptions) -> tuple[str | None, list[Issue]]:
    """The opening tag attributes every form gets, or None when the export must stop."""
    count = sum(1 for n in walk_document(doc) if n.get("type") == "contact_form")
    if not count:
        return "", []
    action, email = options.form_action.strip(), options.form_email.strip()
    if action:
        parts = urlsplit(action)
        if parts.scheme != "https" or not parts.netloc:
            return None, [Issue(ERROR, "The form handler address must start with https://.", "forms", "Enter the full address your form service gave you.")]
        return f' action="{action.replace(chr(34), "%22")}" method="post"', [
            Issue(WARNING, f"{count} contact form(s) will post to {parts.netloc}. Send a test message after publishing.", "forms")]
    if email:
        if not _EMAIL.match(email):
            return None, [Issue(ERROR, f"'{email}' is not an email address.", "forms")]
        return f' action="mailto:{email}" method="post" enctype="text/plain"', [
            Issue(WARNING, f"{count} contact form(s) will open the visitor's email app, addressed to {email}. A form handler service is more reliable.", "forms")]
    return None, [Issue(ERROR, f"This site has {count} contact form(s), and a static site cannot send them by itself.", "forms",
                        "Enter a form handler address or an email address for messages.")]


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.refs.append(value)
            if key == "id" and value:
                self.ids.add(value)


def check_site(root: Path) -> list[Issue]:
    """Checks a written site: every local link and file exists, nothing from the editor leaked."""
    issues: list[Issue] = []
    pages = sorted(root.glob("*.html"))
    if not (root / "index.html").is_file():
        issues.append(Issue(ERROR, "The site has no index.html, so it would not open at its address.", "files"))
    css = root / "assets" / "style.css"
    if not css.is_file():
        issues.append(Issue(ERROR, "The stylesheet is missing.", "files"))
    else:
        for ref in re.findall(r"url\(([^)]+)\)", css.read_text(encoding="utf-8")):
            ref = ref.strip("'\" ")
            if ref.startswith(("data:", "#")):
                continue
            if ref.startswith(("http:", "https:", "//")):
                issues.append(Issue(ERROR, f"The stylesheet loads {ref} from another site.", "privacy"))
            elif not (css.parent / unquote(ref.split("?")[0])).is_file():
                issues.append(Issue(ERROR, f"The stylesheet refers to {ref}, which is missing.", "files"))
    placeholders = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for trace in _EDITOR_TRACES:
            if trace in text:
                issues.append(Issue(ERROR, f"Editor markup ('{trace}') was left in the page.", page.name))
        # The one script allowed is the studio's own countdown, unchanged.
        own = f'<script src="assets/{PAGE_JS_NAME}" defer></script>'
        if own in text:
            js = root / "assets" / PAGE_JS_NAME
            if not js.is_file() or js.read_text(encoding="utf-8") != PAGE_JS.read_text(encoding="utf-8"):
                issues.append(Issue(ERROR, "The countdown script is missing or was changed.", page.name))
        if "<script" in text.replace(own, "").lower():
            issues.append(Issue(ERROR, "The page contains a script. Exported pages are plain HTML.", page.name))
        if 'action="#"' in text:
            issues.append(Issue(ERROR, "A form has nowhere to send its message.", page.name))
        placeholders += text.count("data:image/svg+xml")
        parser = _Refs()
        parser.feed(text)
        for ref in parser.refs:
            parts = urlsplit(ref)
            if parts.scheme in ("http", "https", "mailto", "tel", "data") or ref.startswith("//"):
                continue
            if not parts.path:
                if parts.fragment and parts.fragment not in parser.ids:
                    issues.append(Issue(WARNING, f"The link '#{parts.fragment}' points to nothing on this page.", page.name))
                continue
            if not (root / unquote(parts.path)).is_file():
                issues.append(Issue(ERROR, f"'{ref}' points to a file that is not in the site.", page.name))
    if placeholders:
        issues.append(Issue(WARNING, f"{placeholders} placeholder image(s) remain. They work, but visitors will see them.", "media",
                            "Replace them with your own images on the canvas."))
    return issues


def _write(doc: Document, project_folder: Path | None, root: Path, options: StaticOptions) -> tuple[list[Issue], list[dict]]:
    prepared, issues = _prepare(doc)
    attrs, form_issues = _forms(prepared, options)
    issues += form_issues
    for label in dict.fromkeys(broken_page_links(doc)):
        issues.append(Issue(WARNING, f"'{label}' links to a page that does not exist.", "links", "Choose a new destination for it."))
    if attrs is None or any(i.severity == ERROR for i in issues):
        return issues, []
    site = write_site(prepared, root, editor=False, project_folder=project_folder)
    if attrs:
        for path in site.pages.values():
            text = path.read_text(encoding="utf-8")
            path.write_text(_FORM_OPEN.sub(lambda m: f"<form{m.group(1)}{attrs}>", text), encoding="utf-8")
    # write_site keeps every bundled font file it ever copied; ship only the ones the CSS uses.
    css = (root / "assets" / "style.css").read_text(encoding="utf-8")
    for font in (root / "assets" / "fonts").glob("*"):
        if font.name not in css:
            font.unlink()
    (root / "README.txt").write_text(
        "This folder is a complete website made with Mulusa Theme Studio.\n"
        "Upload everything in it, keeping the folders, to your web host's public folder.\n"
        "index.html is the homepage. Open it in a browser to preview the site offline.\n",
        encoding="utf-8")
    home = home_page(prepared)
    pages = [{"title": p.get("title", ""), "file": page_filename(p), "home": p is home} for p in prepared["pages"]]
    return issues + check_site(root), pages


def _zip_folder(folder: Path, target: Path) -> None:
    tmp = target.with_suffix(".zip.part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(folder.parent).as_posix())
    with zipfile.ZipFile(tmp) as archive:
        if archive.testzip() is not None:
            tmp.unlink()
            raise OSError(f"The archive {target.name} did not verify after writing.")
    tmp.replace(target)


@register
class StaticExporter(Exporter):
    id = "static"
    label = "Static website (HTML)"

    def check(self, doc: Document, project_folder: Path | None, options: StaticOptions | None = None) -> list[Issue]:
        """Writes the whole site to a temporary folder and checks it, leaving nothing behind."""
        options = options or StaticOptions()
        _, slug = _slug(doc, options)
        with tempfile.TemporaryDirectory() as temp:
            issues, _ = _write(doc, project_folder, Path(temp) / slug, options)
        return issues

    def validate(self, doc: Document) -> list[str]:
        return [str(issue) for issue in self.check(doc, None) if issue.severity == ERROR]

    def export(self, doc: Document, project_folder: Path, destination: Path, options: StaticOptions | None = None) -> StaticResult:
        options = options or StaticOptions()
        _, slug = _slug(doc, options)
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / f"{slug}-site"
            issues, pages = _write(doc, project_folder, root, options)
            errors = [i for i in issues if i.severity == ERROR]
            if errors:
                raise StaticExportFailed(errors, issues)
            output = destination / f"{slug}-site.zip"
            _zip_folder(root, output)
            folder = destination / f"{slug}-site"
            if folder.exists():
                # Only ever replace an earlier export of this site, never an unrelated folder.
                marker = folder / "README.txt"
                if not (marker.is_file() and "Mulusa Theme Studio" in marker.read_text(encoding="utf-8", errors="ignore")):
                    raise OSError(f"{folder} already exists and is not an earlier export. Choose another folder.")
                shutil.rmtree(folder)
            shutil.copytree(root, folder)
        return StaticResult(output, [str(i) for i in issues], folder, issues, pages)
