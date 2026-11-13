"""What a resource is: its kind, its metadata, its licence and how well it imports.

Plain data with no Qt. Every resource, bundled or imported, is described by one ``Resource``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

KINDS = {
    "template": "Website templates",
    "section": "Sections",
    "header": "Headers",
    "footer": "Footers",
    "palette": "Colour palettes",
    "type_pair": "Type pairings",
    "font": "Fonts",
    "icon": "Icons",
    "illustration": "Animated illustrations",
    "pattern": "Patterns and gradients",
    "image": "Images",
    "package": "Packages for reference",
}

COMPATIBILITY = {
    "full": "Fully compatible",
    "partial": "Partially compatible",
    "reference": "Reference only",
    "unsupported": "Unsupported",
}

ORIGINS = ("builtin", "imported", "remote")

# Section categories offered in the section library, in display order.
SECTION_CATEGORIES = {
    "hero": "Hero", "about": "About", "services": "Services", "features": "Features", "statistics": "Statistics",
    "team": "Team", "testimonials": "Testimonials", "portfolio": "Portfolio and case studies", "clients": "Clients and partners",
    "pricing": "Pricing", "faq": "FAQ", "contact": "Contact", "call_to_action": "Call to action", "blog": "Blog and news",
    "products": "Products", "events": "Events", "media": "Video and images", "content": "Content",
}


@dataclass(frozen=True)
class Licence:
    id: str
    name: str
    url: str
    redistributable: bool     # may be shipped inside an exported theme
    attribution: bool         # credit must be kept
    copyleft: bool = False


# The licences the importer recognises. Anything else is "Unknown", which never counts as permission.
LICENCES: dict[str, Licence] = {lic.id: lic for lic in (
    Licence("Original", "Mulusa Innovations original work", "", True, False),
    Licence("MIT", "MIT License", "https://opensource.org/license/mit", True, True),
    Licence("ISC", "ISC License", "https://opensource.org/license/isc-license-txt", True, True),
    Licence("Apache-2.0", "Apache License 2.0", "https://www.apache.org/licenses/LICENSE-2.0", True, True),
    Licence("BSD-2-Clause", "BSD 2-Clause License", "https://opensource.org/license/bsd-2-clause", True, True),
    Licence("BSD-3-Clause", "BSD 3-Clause License", "https://opensource.org/license/bsd-3-clause", True, True),
    Licence("GPL-2.0-or-later", "GNU General Public License v2 or later", "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html", True, True, True),
    Licence("GPL-3.0-or-later", "GNU General Public License v3 or later", "https://www.gnu.org/licenses/gpl-3.0.html", True, True, True),
    Licence("LGPL-3.0", "GNU Lesser General Public License v3", "https://www.gnu.org/licenses/lgpl-3.0.html", True, True, True),
    Licence("MPL-2.0", "Mozilla Public License 2.0", "https://www.mozilla.org/MPL/2.0/", True, True, True),
    Licence("CC0-1.0", "Creative Commons Zero (public domain)", "https://creativecommons.org/publicdomain/zero/1.0/", True, False),
    Licence("Unlicense", "The Unlicense (public domain)", "https://unlicense.org/", True, False),
    Licence("CC-BY-3.0", "Creative Commons Attribution 3.0", "https://creativecommons.org/licenses/by/3.0/", True, True),
    Licence("CC-BY-4.0", "Creative Commons Attribution 4.0", "https://creativecommons.org/licenses/by/4.0/", True, True),
    Licence("OFL-1.1", "SIL Open Font License 1.1", "https://openfontlicense.org/", True, True),
    Licence("Unknown", "Licence not stated", "", False, False),
)}

_ALIASES = {
    "mit": "MIT", "mit license": "MIT", "isc": "ISC", "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause", "bsd-3-clause": "BSD-3-Clause",
    "gpl-2.0": "GPL-2.0-or-later", "gpl-2.0+": "GPL-2.0-or-later", "gpl-2.0-or-later": "GPL-2.0-or-later",
    "gplv2": "GPL-2.0-or-later", "gplv2 or later": "GPL-2.0-or-later", "gnu general public license v2 or later": "GPL-2.0-or-later",
    "gnu general public license v2.0 or later": "GPL-2.0-or-later", "gpl-2.0-only": "GPL-2.0-or-later",
    "gpl-3.0": "GPL-3.0-or-later", "gplv3": "GPL-3.0-or-later", "gpl-3.0-or-later": "GPL-3.0-or-later", "gpl-3.0-only": "GPL-3.0-or-later",
    "gnu general public license v3 or later": "GPL-3.0-or-later", "gnu general public license v3.0": "GPL-3.0-or-later",
    "lgpl-3.0": "LGPL-3.0", "mpl-2.0": "MPL-2.0", "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0", "unlicense": "Unlicense",
    "cc-by-3.0": "CC-BY-3.0", "cc by 3.0": "CC-BY-3.0", "creative commons attribution 3.0": "CC-BY-3.0",
    "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0", "ofl-1.1": "OFL-1.1", "ofl": "OFL-1.1",
}


def identify_licence(text: str | None) -> Licence:
    """Turns a licence name as packages write it (SPDX id, "GPLv2 or later", ...) into a known Licence."""
    key = " ".join(str(text or "").strip().lower().replace("license:", "").split())
    if not key:
        return LICENCES["Unknown"]
    if key in _ALIASES:
        return LICENCES[_ALIASES[key]]
    for known in LICENCES.values():
        if key == known.id.lower() or key == known.name.lower():
            return known
    if "gnu general public license" in key or key.startswith("gpl"):
        return LICENCES["GPL-3.0-or-later" if "3" in key else "GPL-2.0-or-later"]
    return LICENCES["Unknown"]


@dataclass
class Resource:
    id: str
    name: str
    kind: str
    category: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "Mulusa Innovations"
    source_url: str = ""
    author: str = "Mulusa Innovations"
    licence: str = "Original"
    format: str = "Mulusa document"
    compatibility: str = "full"
    responsive: str = "Desktop, tablet and mobile"
    origin: str = "builtin"
    folder: str = ""          # a user folder in the library, for organising imported items
    path: str = ""            # where the resource's data lives (file or folder)
    preview: str = ""         # a thumbnail image, if there is one
    added: str = ""
    sha256: str = ""
    data: dict[str, Any] = field(default_factory=dict)   # small kind-specific values: colours, fonts, svg, ...
    report: list[str] = field(default_factory=list)       # what the importer could not convert

    @property
    def licence_info(self) -> Licence:
        return LICENCES.get(self.licence) or identify_licence(self.licence)

    @property
    def kind_name(self) -> str:
        return KINDS.get(self.kind, self.kind)

    @property
    def compatibility_name(self) -> str:
        return COMPATIBILITY.get(self.compatibility, self.compatibility)

    @property
    def can_use(self) -> bool:
        """Whether the editor can put it into a project (reference-only items can only be viewed)."""
        return self.compatibility in ("full", "partial")

    def haystack(self) -> str:
        return " ".join([self.name, self.description, self.category, self.kind, self.source, self.author, *self.tags]).lower()

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict) -> "Resource":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in raw.items() if k in known})
