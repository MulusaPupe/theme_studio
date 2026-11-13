"""The whole library as one searchable list: bundled resources plus the user's imported ones.

Bundled resources are described from what ships with the application (templates, the section
collection, fonts, icons, palettes and type pairings taken from the templates, and generated
patterns), so nothing needs a network and adding a template folder adds its resources too.
"""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from ..core.templates import TemplateLibrary
from .model import KINDS, Resource
from .patterns import GRADIENTS, PATTERNS
from .store import ResourceStore

PKG = Path(__file__).resolve().parents[1]
SECTIONS_DIR = Path(__file__).resolve().parent / "sections"
ICON_DIR = PKG / "resources" / "icons"
FONT_DIR = PKG / "resources" / "fonts"

# The brief's website categories, mapped onto the template categories and descriptions that serve them.
COLLECTIONS = {
    "Corporate and business": ("corporate",),
    "Construction and engineering": ("construction",),
    "Architecture and real estate": ("real_estate", "architect"),
    "Technology and SaaS": ("technology",),
    "AI and software products": ("ai-startup", "developer-tools", "saas"),
    "Creative agencies": ("design-studio", "professional-agency", "creative-collective"),
    "Photography and portfolios": ("photographer", "gallery", "illustrator", "art"),
    "Music and entertainment": ("music",),
    "Fashion and beauty": ("fashion", "beauty"),
    "E-commerce": ("shop", "boutique", "hardware-product", "streetwear"),
    "Hospitality and tourism": ("hospitality", "hotel"),
    "Education": ("education",),
    "Professional services": ("consulting", "executive", "it-services", "law", "professional"),
    "Personal websites and CVs": ("personal",),
    "NGOs and community organisations": ("community",),
    "Healthcare": ("healthcare",),
    "Restaurants and food businesses": ("dining", "bistro", "coffee", "street-food", "restaurant"),
    "Automotive": ("automotive",),
    "News and media": ("news",),
    "Launch, coming soon and one-page": ("onepage",),
}

SECTION_LABELS = {
    "hero": "Hero", "header": "Navigation", "footer": "Footer",
}


class Library:
    def __init__(self, templates: TemplateLibrary | None = None, store: ResourceStore | None = None) -> None:
        self.templates = templates or TemplateLibrary()
        self.store = store or ResourceStore()

    # Bundled resources -----------------------------------------------------------
    @cached_property
    def builtin(self) -> list[Resource]:
        out: list[Resource] = []
        out += self._templates()
        out += self._sections()
        out += self._design_from_templates()
        out += self._fonts()
        out += self._icons()
        out += self._illustrations()
        out += self._patterns()
        return out

    def _templates(self) -> list[Resource]:
        names = {c.id: c.name for c in self.templates.categories}
        out = []
        for info in self.templates.templates:
            key = f"{info.id} {info.category}".lower()
            collections = [name for name, keys in COLLECTIONS.items() if any(k in key for k in keys)]
            out.append(Resource(
                id=f"template:{info.id}", name=info.name, kind="template", category=names.get(info.category, info.category),
                description=info.description, tags=collections, format="Mulusa template", path=str(info.folder),
                preview=str(info.thumbnail) if info.thumbnail.is_file() else "", data={"template_id": info.id},
            ))
        return out

    def _sections(self) -> list[Resource]:
        index = SECTIONS_DIR / "index.json"
        try:
            entries = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for e in entries:
            preview = SECTIONS_DIR / e.get("preview", "")
            out.append(Resource(
                id=f"section:{e['id']}", name=e["name"], kind=e.get("kind", "section"), category=e.get("category", "content"),
                description=e.get("description", ""), tags=e.get("tags", []), format="Mulusa section",
                path=str(SECTIONS_DIR / e["file"]), preview=str(preview) if preview.is_file() else "",
                responsive="Desktop, tablet and mobile (own responsive settings)", data={"source_template": e.get("source_template", "")},
            ))
        return out

    def _design_from_templates(self) -> list[Resource]:
        out, pairs = [], {}
        for info in self.templates.templates:
            try:
                raw = json.loads(info.file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            tokens = raw.get("tokens", {})
            colors = tokens.get("colors", {})
            if colors:
                out.append(Resource(
                    id=f"palette:{info.id}", name=f"{info.name} palette", kind="palette", category="Colour palettes",
                    description=f"The colours of the {info.name} template.", tags=[info.category], format="Colour tokens",
                    data={"colors": colors},
                ))
            fonts = tokens.get("fonts", {})
            pair = (fonts.get("heading"), fonts.get("body"))
            if all(pair) and pair not in pairs:
                pairs[pair] = info
        for (heading, body), info in pairs.items():
            out.append(Resource(
                id=f"type_pair:{heading}|{body}", name=f"{heading} / {body}" if heading != body else heading, kind="type_pair",
                category="Type pairings", description=f"Headings in {heading}, text in {body}. As used by {info.name}.",
                tags=[info.category], licence="OFL-1.1", source="Fontsource (bundled)", format="Font tokens",
                data={"heading": heading, "body": body},
            ))
        return out

    def _fonts(self) -> list[Resource]:
        try:
            fonts = json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [Resource(
            id=f"font:{f['family']}", name=f["family"], kind="font", category=f.get("kind", "sans").title(),
            description=f"{f['family']}, bundled and embedded in exported sites.", tags=[f.get("kind", "")],
            source="Fontsource (bundled)", source_url=f"https://fonts.google.com/specimen/{f['family'].replace(' ', '+')}",
            author="See font", licence=f.get("licence", "OFL-1.1"), format="woff2", data={"family": f["family"], "kind": f.get("kind")},
        ) for f in fonts]

    def _icons(self) -> list[Resource]:
        return [Resource(
            id=f"icon:{p.stem}", name=p.stem.replace("-", " "), kind="icon", category="Lucide", tags=["lucide"],
            source="Lucide (bundled)", source_url=f"https://lucide.dev/icons/{p.stem}", author="Lucide contributors",
            licence="ISC", format="SVG", path=str(p), preview=str(p), data={"name": p.stem},
        ) for p in sorted(ICON_DIR.glob("*.svg"))]

    def _illustrations(self) -> list[Resource]:
        from ..render.illustrations import ILLUSTRATIONS
        return [Resource(
            id=f"illustration:{name}", name=item.title, kind="illustration", category=item.group, tags=list(item.tags),
            description=f"An original animated drawing that takes the site's colours. Good for {', '.join(item.tags[:3])}.",
            format="Animated SVG (CSS motion)", responsive="Scales to any width; still for visitors who turn off animations",
            data={"name": name},
        ) for name, item in ILLUSTRATIONS.items()]

    def _patterns(self) -> list[Resource]:
        out = [Resource(
            id=f"pattern:{key}", name=spec["name"], kind="pattern", category="Patterns", description=spec["description"],
            tags=["pattern", "background"], format="Generated PNG background", data={"pattern": key},
        ) for key, spec in PATTERNS.items()]
        out += [Resource(
            id=f"gradient:{key}", name=spec["name"], kind="pattern", category="Gradients", description=spec["description"],
            tags=["gradient", "background"], format="CSS gradient from site colours", data={"gradient": key},
        ) for key, spec in GRADIENTS.items()]
        return out

    # Everything ---------------------------------------------------------------
    def all(self) -> list[Resource]:
        return self.builtin + self.store.items()

    def get(self, resource_id: str) -> Resource | None:
        return next((r for r in self.all() if r.id == resource_id), None)

    def search(self, text: str = "", *, kind: str | None = None, category: str | None = None, tags: list[str] | None = None,
               favourites: bool = False, origin: str | None = None, folder: str | None = None,
               compatibility: str | None = None) -> list[Resource]:
        words = text.lower().split()
        favs = set(self.store.favourites()) if favourites else None
        out = []
        for r in self.all():
            if kind and r.kind != kind:
                continue
            if category and r.category != category:
                continue
            if tags and not set(tags) <= set(r.tags):
                continue
            if favs is not None and r.id not in favs:
                continue
            if origin and r.origin != origin:
                continue
            if folder is not None and r.folder != folder:
                continue
            if compatibility and r.compatibility != compatibility:
                continue
            if words:
                hay = r.haystack()
                if not all(w in hay for w in words):
                    continue
            out.append(r)
        return out

    def categories(self, kind: str) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.all():
            if r.kind == kind and r.category:
                seen.setdefault(r.category, None)
        return list(seen)

    def tags(self, kind: str | None = None) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.all():
            if kind is None or r.kind == kind:
                for t in r.tags:
                    seen.setdefault(t, None)
        return sorted(seen, key=str.lower)

    def counts(self) -> dict[str, int]:
        out = {k: 0 for k in KINDS}
        for r in self.all():
            out[r.kind] = out.get(r.kind, 0) + 1
        return out

    def recent(self) -> list[Resource]:
        by_id = {r.id: r for r in self.all()}
        return [by_id[i] for i in self.store.recent() if i in by_id]

    def favourites(self) -> list[Resource]:
        by_id = {r.id: r for r in self.all()}
        return [by_id[i] for i in self.store.favourites() if i in by_id]

    def discover(self) -> dict[str, list[Resource]]:
        """The Discover home: featured, recent, imported, and a few of each kind."""
        featured_ids = ["template:construction/heavy-civil", "template:corporate/modern-consulting", "template:technology/saas-launch",
                        "template:art/design-studio", "template:music/artist-portfolio", "template:hospitality/fine-dining",
                        "template:personal/personal-portfolio", "template:art/photographer-dark"]
        by_id = {r.id: r for r in self.all()}
        imported = sorted(self.store.items(), key=lambda r: r.added, reverse=True)
        return {
            "Featured templates": [by_id[i] for i in featured_ids if i in by_id],
            "Recently used": self.recent()[:8],
            "Recently imported": imported[:8],
            "Launch and one-page templates": [r for r in self.builtin if r.kind == "template" and r.data.get("template_id", "").startswith("onepage/")][:10],
            "Animated illustrations": [r for r in self.builtin if r.kind == "illustration"][:12],
            "Hero sections": [r for r in self.builtin if r.kind == "section" and r.category == "hero"][:8],
            "Section collection": [r for r in self.builtin if r.kind == "section" and r.category != "hero"][:12],
        }
