"""Finding resources online through official, documented APIs, and only those.

    WordPress.org Pattern Directory   https://api.wordpress.org/patterns/1.0/    (patterns are GPLv2 or later)
    WordPress.org Theme Directory     https://api.wordpress.org/themes/info/1.2/  (every listed theme is GPL)
    GitHub repository search          https://api.github.com/search/repositories  (licence read per repository)

Nothing is scraped and nothing is downloaded until the user asks for one item. Answers are cached
on disk, so a search made before still works offline. Only https URLs on the hosts below are
fetched, downloads are size-capped, and a GitHub repository without a recognised licence is
offered as a link only. Webflow, Framer, ThemeForest and showcase sites such as Awwwards and
Codrops have no download permission for their designs; the library links to them as inspiration.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core.errors import StudioError
from .model import identify_licence
from .packages import ImportResult, import_package
from .store import ResourceStore, write_json

ALLOWED_HOSTS = {"api.wordpress.org", "downloads.wordpress.org", "ts.w.org", "s.w.org", "i0.wp.com",
                 "api.github.com", "codeload.github.com"}
USER_AGENT = "MulusaThemeStudio/1.0 (resource library)"
CACHE_SECONDS = 24 * 3600
MAX_DOWNLOAD = 60 * 1024 * 1024
TIMEOUT = 20

INSPIRATION = [
    ("WordPress Theme Directory", "https://wordpress.org/themes/", "Free GPL themes; block themes import directly."),
    ("WordPress Pattern Directory", "https://wordpress.org/patterns/", "Free GPL block patterns; they import as sections."),
    ("HTML5 UP", "https://html5up.net/", "Free HTML templates under Creative Commons Attribution 3.0; download the ZIP and import it."),
    ("Bootstrap examples", "https://getbootstrap.com/docs/5.3/examples/", "MIT-licensed layout examples; download and import the HTML."),
    ("Lucide icons", "https://lucide.dev/icons/", "ISC-licensed icons; a set is bundled already."),
    ("Google Fonts", "https://fonts.google.com/", "Open-licensed fonts; thirty are bundled for offline use."),
    ("SVG Backgrounds", "https://www.svgbackgrounds.com/", "Check each background's licence before use."),
    ("Webflow templates", "https://webflow.com/templates", "Inspiration only: templates are licensed to Webflow sites, not for import."),
    ("Made in Webflow", "https://webflow.com/made-in-webflow", "Inspiration only unless a project states it may be cloned and reused."),
    ("Framer Marketplace", "https://www.framer.com/marketplace/", "Inspiration only: templates are licensed for Framer."),
    ("Awwwards", "https://www.awwwards.com/", "Inspiration only: award sites are not licensed for reuse."),
    ("Codrops", "https://tympanus.net/codrops/", "Tutorials and demos; read each demo's licence before reusing code."),
]


class RemoteError(StudioError):
    pass


@dataclass
class RemoteItem:
    id: str
    name: str
    kind: str                 # "section" (pattern) or "template" (theme, repository)
    source: str
    source_url: str
    description: str = ""
    licence: str = "Unknown"
    preview_url: str = ""
    download_url: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    content: str = ""         # a pattern's block markup, which needs no separate download
    notes: list[str] = field(default_factory=list)

    @property
    def importable(self) -> bool:
        return bool(self.content or self.download_url) and identify_licence(self.licence).redistributable


@dataclass
class SearchResult:
    items: list[RemoteItem]
    offline: bool = False     # the answer came from the cache because the network failed
    message: str = ""


Fetcher = Callable[[str], bytes]


def _default_fetch(url: str, limit: int = MAX_DOWNLOAD) -> bytes:
    check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:   # noqa: S310 - https and host checked above
        final = response.geturl()
        check_url(final)
        data = response.read(limit + 1)
    if len(data) > limit:
        raise RemoteError("The download is larger than the library accepts.")
    return data


def check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise RemoteError(f"The library does not download from {parts.hostname or url}.")


class RemoteCatalogue:
    def __init__(self, store: ResourceStore, fetch: Fetcher | None = None) -> None:
        self.store = store
        self.fetch = fetch or _default_fetch

    # Cache --------------------------------------------------------------------
    def _cache_file(self, url: str) -> Path:
        return self.store.cache_dir / "api" / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")

    def _get_json(self, url: str) -> tuple[object, bool]:
        file = self._cache_file(url)
        try:
            cached = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if cached and time.time() - cached.get("at", 0) < CACHE_SECONDS:
            return cached["data"], False
        try:
            data = json.loads(self.fetch(url).decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError, RemoteError, ValueError) as exc:
            if cached:
                return cached["data"], True
            raise RemoteError(f"Could not reach the catalogue ({exc}). Try again when you are online.") from exc
        write_json(file, {"at": time.time(), "url": url, "data": data})
        return data, False

    # Searches -----------------------------------------------------------------
    def search_patterns(self, query: str, per_page: int = 24) -> SearchResult:
        url = "https://api.wordpress.org/patterns/1.0/?" + urllib.parse.urlencode({"search": query, "per_page": per_page, "locale": "en_US"})
        try:
            data, offline = self._get_json(url)
        except RemoteError as exc:
            return SearchResult([], True, str(exc))
        items = []
        for p in data if isinstance(data, list) else []:
            title = (p.get("title") or {}).get("rendered", "Pattern") if isinstance(p.get("title"), dict) else str(p.get("title", "Pattern"))
            content = p.get("pattern_content") or ""
            if "<!-- wp:" not in content:
                continue
            meta = p.get("meta") or {}
            items.append(RemoteItem(
                id=f"wporg-pattern:{p.get('id')}", name=title, kind="section", source="WordPress.org Pattern Directory",
                source_url=f"https://wordpress.org/patterns/pattern/{p.get('id')}/", description=str(meta.get("wpop_description", ""))[:240],
                licence="GPL-2.0-or-later", tags=list(p.get("category_slugs") or [])[:6], content=content,
            ))
        return SearchResult(items, offline)

    def search_themes(self, query: str, per_page: int = 24) -> SearchResult:
        params = {"action": "query_themes", "request[search]": query, "request[tag][]": "full-site-editing",
                  "request[per_page]": per_page, "request[fields][description]": 1}
        url = "https://api.wordpress.org/themes/info/1.2/?" + urllib.parse.urlencode(params)
        try:
            data, offline = self._get_json(url)
        except RemoteError as exc:
            return SearchResult([], True, str(exc))
        items = []
        for t in (data or {}).get("themes", []) if isinstance(data, dict) else []:
            slug, version = t.get("slug", ""), t.get("version", "")
            shot = t.get("screenshot_url", "")
            notes = []
            if t.get("template") and t.get("template") != slug:
                notes.append(f"A child theme of '{t['template']}': its parent's templates are not included.")
            author = t.get("author", {})
            items.append(RemoteItem(
                id=f"wporg-theme:{slug}", name=t.get("name", slug), kind="template", source="WordPress.org Theme Directory",
                source_url=t.get("homepage") or f"https://wordpress.org/themes/{slug}/", description=str(t.get("description", ""))[:300],
                licence="GPL-2.0-or-later", preview_url=("https:" + shot) if shot.startswith("//") else shot,
                download_url=f"https://downloads.wordpress.org/theme/{slug}.{version}.zip" if slug and version else "",
                author=author.get("user_nicename", "") if isinstance(author, dict) else str(author), notes=notes,
            ))
        return SearchResult(items, offline)

    def search_github(self, query: str, topic: str = "wordpress-block-theme", per_page: int = 20) -> SearchResult:
        q = f"{query} topic:{topic}".strip()
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": q, "per_page": per_page, "sort": "stars"})
        try:
            data, offline = self._get_json(url)
        except RemoteError as exc:
            return SearchResult([], True, str(exc))
        items = []
        for r in (data or {}).get("items", []) if isinstance(data, dict) else []:
            lic = identify_licence(((r.get("license") or {}).get("spdx_id")) or "")
            notes = [] if lic.redistributable else ["No recognised licence: shown as a link only, not imported."]
            items.append(RemoteItem(
                id=f"github:{r.get('full_name')}", name=r.get("name", ""), kind="template", source="GitHub",
                source_url=r.get("html_url", ""), description=str(r.get("description") or "")[:300], licence=lic.id,
                download_url=f"https://codeload.github.com/{r.get('full_name')}/zip/refs/heads/{r.get('default_branch', 'main')}" if lic.redistributable else "",
                author=(r.get("owner") or {}).get("login", ""), tags=list(r.get("topics") or [])[:6], notes=notes,
            ))
        return SearchResult(items, offline)

    # Download and import ------------------------------------------------------------
    def preview(self, item: RemoteItem) -> Path | None:
        """The item's screenshot, cached; None when there is none or the network is down."""
        if not item.preview_url:
            return None
        file = self.store.cache_dir / "previews" / (hashlib.sha256(item.preview_url.encode()).hexdigest()[:24] + ".img")
        if file.is_file():
            return file
        try:
            data = self.fetch(item.preview_url)
        except (urllib.error.URLError, OSError, RemoteError):
            return None
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data[:8 * 1024 * 1024])
        return file

    def download(self, item: RemoteItem) -> Path:
        if not item.importable:
            raise RemoteError(f"'{item.name}' cannot be imported: " + (item.notes[0] if item.notes else "it has no permitted download."))
        folder = self.store.cache_dir / "downloads"
        folder.mkdir(parents=True, exist_ok=True)
        if item.content:
            file = folder / (hashlib.sha256(item.id.encode()).hexdigest()[:16] + ".json")
            write_json(file, [{"id": item.id, "title": {"rendered": item.name}, "pattern_content": item.content,
                               "link": item.source_url, "category_slugs": item.tags}])
            return file
        file = folder / (hashlib.sha256(item.download_url.encode()).hexdigest()[:16] + ".zip")
        if not file.is_file():
            try:
                data = self.fetch(item.download_url)
            except (urllib.error.URLError, OSError) as exc:
                raise RemoteError(f"The download failed ({exc}).") from exc
            file.write_bytes(data)
        return file

    def import_item(self, item: RemoteItem) -> ImportResult:
        path = self.download(item)
        result = import_package(path, self.store, name=item.name, source=item.source, source_url=item.source_url,
                                licence=item.licence, tags=item.tags)
        for res in result.resources:
            if res.author in ("", "Unknown") and item.author:
                res.author = item.author
            res.origin = "remote"
            if not result.duplicate:
                self.store.update(res)
        return result


def item_to_json(item: RemoteItem) -> dict:
    return asdict(item)
