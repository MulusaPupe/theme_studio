"""Checks a finished theme folder. Nothing is reported as exported unless this passes."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from .. import ERROR, WARNING, Issue  # noqa: F401  (shared by every exporter; re-exported for older imports)
_BLOCK = re.compile(r"<!--\s+(/)?wp:([a-z][a-z0-9_-]*/)?([a-z][a-z0-9_-]*)\s+(\{.*?\}\s+)?(/)?-->", re.S)
_ANY_BLOCK = re.compile(r"<!--\s*/?wp:")
KNOWN_BLOCKS = {
    "group", "heading", "paragraph", "image", "buttons", "button", "columns", "column", "cover", "spacer", "separator", "list", "list-item", "quote",
    "navigation", "navigation-link", "site-title", "site-logo", "template-part", "pattern", "post-content", "post-title", "post-featured-image", "post-excerpt",
    "post-date", "post-author-name", "post-terms", "read-more", "query", "post-template", "query-pagination", "query-pagination-previous", "query-pagination-numbers",
    "query-pagination-next", "query-no-results", "details", "gallery", "video", "embed", "html", "shortcode",
}
REQUIRED = ("style.css", "theme.json", "functions.php", "screenshot.png", "templates/index.html", "templates/page.html", "templates/front-page.html", "templates/single.html", "templates/archive.html", "templates/404.html", "parts/header.html", "parts/footer.html", "assets/css/mulusa.css", "readme.txt")
HEADERS = ("Theme Name", "Author", "Description", "Version", "Requires at least", "Tested up to", "Requires PHP", "License", "License URI", "Text Domain")
VOID = {"img", "hr", "br", "input", "meta", "link", "source", "path", "circle", "line", "rect", "polyline", "polygon", "ellipse"}
_UNSAFE = re.compile(r"<script|javascript:|\bon[a-z]+\s*=\s*[\"']|<iframe|<object|<embed", re.I)
_PHP_ALLOWED = re.compile(r"<\?php echo esc_(url|attr)\( [a-z0-9_]+\( '[^'\\]*(?:\\.[^'\\]*)*' \) \); \?>")
_IMAGE_REF = re.compile(r"get_theme_file_uri\( '(assets/[^']+)' \)")


class _Balance(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"Unexpected closing </{tag}>.")
            if tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.stack.pop()
                if self.stack:
                    self.stack.pop()
        else:
            self.stack.pop()


def check_block_markup(text: str, where: str) -> list[Issue]:
    """The block comments must nest, name known blocks and carry valid JSON; the HTML must balance."""
    issues: list[Issue] = []
    stack: list[str] = []
    matched = 0
    plain = re.sub(r"<\?php.*?\?>", "0", text, flags=re.S)  # Tokens resolved at run time stand in as a value.
    for match in _BLOCK.finditer(plain):
        matched += 1
        closing, namespace, name, attrs, void = match.groups()
        if (namespace or "core/") == "core/" and name not in KNOWN_BLOCKS:
            issues.append(Issue(ERROR, f"Unknown block '{name}'.", where))
        if attrs:
            try:
                json.loads(attrs)
            except ValueError as exc:
                issues.append(Issue(ERROR, f"The settings of block '{name}' are not valid JSON ({exc}).", where))
        if closing:
            if not stack or stack[-1] != name:
                issues.append(Issue(ERROR, f"Block '{name}' closes out of order.", where))
            elif stack:
                stack.pop()
        elif not void:
            stack.append(name)
    if stack:
        issues.append(Issue(ERROR, f"Block '{stack[-1]}' is never closed.", where))
    if len(_ANY_BLOCK.findall(plain)) != matched:
        issues.append(Issue(ERROR, "A block comment is malformed, so WordPress would not read it.", where))
    balance = _Balance()
    balance.feed(_BLOCK.sub("", plain))
    balance.close()
    issues += [Issue(ERROR, problem, where) for problem in balance.problems[:3]]
    if balance.stack:
        issues.append(Issue(ERROR, f"The HTML tag <{balance.stack[-1]}> is never closed.", where))
    return issues


def _unsafe(text: str, where: str) -> list[Issue]:
    return [Issue(ERROR, f"Unsafe content found: {found.group(0)!r}.", where) for found in list(_UNSAFE.finditer(text))[:3]]


def check_theme(root: Path, *, slug: str) -> list[Issue]:
    issues: list[Issue] = []
    for name in REQUIRED:
        if not (root / name).is_file():
            issues.append(Issue(ERROR, "A required file is missing.", name))
    if issues:
        return issues
    head = (root / "style.css").read_text(encoding="utf-8")
    for key in HEADERS:
        if not re.search(rf"^{re.escape(key)}: *\S", head, flags=re.M):
            issues.append(Issue(ERROR, f"The theme header '{key}' is missing.", "style.css"))
    data = None
    try:
        data = json.loads((root / "theme.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        issues.append(Issue(ERROR, f"Not valid JSON: {exc}.", "theme.json"))
    if data is not None:
        if data.get("version") != 3:
            issues.append(Issue(ERROR, "It must use version 3 of the format.", "theme.json"))
        for family in data.get("settings", {}).get("typography", {}).get("fontFamilies", []):
            for face in family.get("fontFace", []):
                for source in face.get("src", []):
                    if not (root / source.removeprefix("file:./")).is_file():
                        issues.append(Issue(ERROR, f"The font file {source} is missing.", "theme.json"))
    known_patterns: set[str] = set()
    for file in sorted((root / "patterns").glob("*.php")) if (root / "patterns").is_dir() else []:
        text = file.read_text(encoding="utf-8")
        where = f"patterns/{file.name}"
        found = re.search(r"^ \* Slug: (\S+)$", text, flags=re.M)
        if not found:
            issues.append(Issue(ERROR, "The pattern has no slug.", where))
        else:
            known_patterns.add(found.group(1))
            if not found.group(1).startswith(f"{slug}/"):
                issues.append(Issue(ERROR, "The pattern slug is not in this theme's namespace.", where))
        body = text.split("?>\n", 1)[1] if "?>\n" in text else text
        for piece in re.findall(r"<\?.*?\?>", body, flags=re.S):
            if not _PHP_ALLOWED.fullmatch(piece):
                issues.append(Issue(ERROR, f"Unexpected code in the pattern: {piece[:60]!r}.", where))
        if re.search(r"<\?(?!php echo esc_)", body):
            issues.append(Issue(ERROR, "Unexpected code in the pattern.", where))
        for ref in _IMAGE_REF.findall(body):
            if not (root / ref).is_file():
                issues.append(Issue(ERROR, f"It refers to {ref}, which is not in the theme.", where))
        issues += check_block_markup(body, where) + _unsafe(body, where)
    parts = {file.stem for file in (root / "parts").glob("*.html")}
    for folder in ("templates", "parts"):
        for file in sorted((root / folder).glob("*.html")):
            text = file.read_text(encoding="utf-8")
            where = f"{folder}/{file.name}"
            if "<?" in text:
                issues.append(Issue(ERROR, "A block template cannot contain PHP.", where))
            if "__MTS" in text:
                issues.append(Issue(ERROR, "An address was left unresolved.", where))
            for part in re.findall(r'wp:template-part \{"slug":"([^"]+)"', text):
                if part not in parts:
                    issues.append(Issue(ERROR, f"It uses the template part '{part}', which does not exist.", where))
            for name in re.findall(r'wp:pattern \{"slug":"([^"]+)"', text):
                if name not in known_patterns:
                    issues.append(Issue(ERROR, f"It uses the pattern '{name}', which does not exist.", where))
            issues += check_block_markup(text, where) + _unsafe(text, where)
    for file in root.rglob("*"):
        if file.is_file() and "__MTS" in (file.read_text(encoding="utf-8", errors="ignore") if file.suffix in (".php", ".html", ".css", ".json") else ""):
            issues.append(Issue(ERROR, "An address was left unresolved.", str(file.relative_to(root))))
    return issues


def check_plugin_data(data: dict, nonce: str, theme_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for page in data.get("pages", []):
        where = f"page '{page.get('title')}'"
        text = re.sub(rf'"__MTS{nonce}_(imageid|terms)_[0-9a-f]*__"', "0", page.get("content", ""))
        text = re.sub(rf"__MTS{nonce}_[a-z]+_[0-9a-f]*__", "0", text)
        issues += check_block_markup(text, where) + _unsafe(text, where)
        for match in re.finditer(rf"__MTS{nonce}_(image|imageid)_([0-9a-f]*)__", page.get("content", "")):
            name = bytes.fromhex(match.group(2)).decode("utf-8")
            if not (theme_root / "assets" / "images" / name).is_file():
                issues.append(Issue(ERROR, f"It uses the image {name}, which is not in the theme.", where))
    return issues
