"""Builds three design variations of the full Vicreations website from its business profile, through the editor's own commands.

Each variation covers the whole company (engineering and construction, branding and signage, print and
promotion, design, supplies and ICT) in a different look: Bold, Corporate and Editorial.

A worked example of using Mulusa Theme Studio for a real client. Each site starts from a
different template and is changed only through Session, the same calls the editor's buttons
make: pages, menu, text, photos, colours, devices, then export. Nothing is invented: the text
comes from the profile, and template content with no source in it (statistics, testimonials,
prices, sample posts) is removed rather than reworded.

    python tools/build_vicreations.py PROFILE.pdf [OUTPUT_FOLDER]

Needs pdfimages (poppler-utils) to take the photos out of the PDF. Tools only; the
application never imports this file.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QCoreApplication

from mulusa_theme_studio.core import design
from mulusa_theme_studio.core.document import find_page, walk_nodes
from mulusa_theme_studio.core.settings import Settings
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.exporters.static import StaticExporter, StaticOptions
from mulusa_theme_studio.exporters.wordpress import ExportOptions, WordPressExporter
from mulusa_theme_studio.ui.session import Session

# ---- facts from the profile ------------------------------------------------------------------
COMPANY = "Vicreations Investment Limited"
BRAND = "VICREATIONS"
TAGLINE = "Simply Versatile"
EMAIL = "sales@vi-creations.com"
PHONES = "+260 968 813 285  |  +260 977 250 848"
ADDRESS = "Shop No. 2, Mtini Building, Luanshya CBD, Zambia"
INTRO = ("Vicreations is a wholly Zambian incorporated company. We are creative professionals working with brands "
         "and companies across the country, helping turn business opportunities into commercial success.")
SERVES = ("We provide engineering, construction and branding services to parastatals, public works agencies, "
          "municipalities and commercial private clients, and keep clients informed so every project stays on "
          "schedule and within budget.")
VALUES = ("We maintain the highest standard of professionalism, integrity, creativity and positive attitude, "
          "with delivery that meets and surpasses client satisfaction.")
MISSION = "To be a world class firm providing efficient, affordable, sustainable and cost effective services of the highest quality."
VISION = "To be established as a regional market leader in products and services that stand out from the rest."
PM = ("Construction project planning and management, feasibility studies, environmental impact assessments, contract "
      "management, supervision, site inspections, quality control and assurance, and construction labour hire.")
CIVIL = ("Civil and structural engineering analysis and design. Steel, reinforced concrete and prefabricated structures. "
         "Roads in gravel, paving blocks, concrete and bituminous surfacing, with drainage works.")
BUILDING = "Residential, commercial and institutional buildings, delivered within the estimated time frame and budget."
SIGNAGE = "Billboards and banners, storefront and office front branding, show booths, exhibition stands, pull-up banners and teardrop flags."
SAFETY = "Workplace safety signage, construction site signage, road signage, worksuit branding and vehicle branding."
PRINT = ("Company profiles, brochures, flyers, business cards, calendars, diaries, receipt, quotation, invoice and "
         "delivery note books, and tickets.")
PROMO = "Event backdrops, posters, name tags, lanyards, ID cards, custom shirt prints, dye sublimation, hoodies, caps and replica jerseys."
DESIGN = "Product labels and stickers, CAD drawings, concept renders, pattern cut-outs and illustrations."
SUPPLY = "Office stationery and consumables, and ICT software and hardware installations."
CLIENTS = "Ministry of Education  ·  Ministry of Agriculture  ·  Ministry of Fisheries and Livestock"
TEAM = [("Victor Mulenga", "Director"), ("Brian Mulenga", "Director"), ("Sam Chanda", "Marketing Director"), ("Susha Mwansa", "Graphics Designer")]
STATS = [("2018", "Year incorporated"), ("4", "Divisions"), ("40+", "Products and services")]
STORY = ("From concept to realisation, whether you are launching a new business, exploring new markets or expanding "
         "existing ones, our team works in consultation with you and brings your vision to reality through creative, "
         "modern solutions.")
DIVISIONS = [
    ("Engineering and construction", "Project planning and management, civil and structural engineering, roads in gravel, paving blocks, "
     "concrete and bitumen with their drainage, and residential, commercial and institutional buildings."),
    ("Branding and signage", SIGNAGE + " Safety, site and road signage, worksuit and vehicle branding."),
    ("Print and promotion", "Company profiles, brochures, business stationery and books, event backdrops, name tags, lanyards, "
     "custom shirt prints, hoodies, caps and replica jerseys."),
    ("Design, supplies and ICT", DESIGN + " " + SUPPLY),
]
CATALOGUE = [
    ("Engineering and construction", ["Project planning and management", "Feasibility studies", "Environmental impact assessments",
                                      "Contract management", "Site supervision and inspections", "Quality control and assurance",
                                      "Structural analysis and design", "Roads: gravel, paving, concrete, bitumen", "Drainage works",
                                      "Residential, commercial and institutional buildings"]),
    ("Branding and signage", ["Billboards and banners", "Storefront and office front branding", "Show booths and exhibition stands",
                              "Pull-up and X-frame banners", "Teardrop flags", "Workplace safety signage", "Construction site signage",
                              "Road signage", "Vehicle branding", "Worksuit branding"]),
    ("Print", ["Company profiles", "Brochures and flyers", "Business cards", "Calendars and branded diaries",
               "Receipt, quotation and invoice books", "Delivery note books", "Site instruction books", "Tickets",
               "Posters and invitation cards", "Product labels and stickers"]),
    ("Promotion, design and supplies", ["Event backdrops and decor", "Name tags, lanyards and ID cards", "Custom shirt prints",
                                        "Dye sublimation", "Hoodies, caps and replica jerseys", "CAD drawings and concept renders",
                                        "Pattern cut-outs and illustrations", "Office stationery", "Office consumables",
                                        "ICT software and hardware installation"]),
]
PROCESS = [("Consult", "We work in consultation with you from the first conversation."),
           ("Interpret", "We read your vision accurately and turn the concept into a design and a plan."),
           ("Deliver", "Creative, modern solutions, built and produced by our own team."),
           ("Report", "We keep you informed throughout, so the work stays on schedule and within budget.")]
CREDENTIALS = [("ZPPA registered", "Supplier on the public e-tendering system, valid to October 2027"),
               ("Tax clearance", "Zambia Revenue Authority clearance for 2026"),
               ("NAPSA compliant", "National Pension Scheme Authority certificate for 2026"),
               ("Workers' Compensation", "Employer compliance certificate for 2026"),
               ("Citizen owned", "Zambian owned, incorporated on 14 May 2018")]
TRIO = [("Our values", VALUES), ("Our mission", MISSION), ("Our vision", VISION)]
MINISTRIES = ["Ministry of Education", "Ministry of Agriculture", "Ministry of Fisheries and Livestock"]

# Photos of Vicreations' own work in the profile (pdfimages numbering). Stock mock-ups are not used.
PHOTOS = {
    "paving": "p-038", "survey": "p-039", "gravel": "p-040", "drainage": "p-041", "rebar": "p-033", "site": "p-034",
    "blocks": "p-044", "column": "p-045", "footings": "p-046", "scaffold": "p-047", "slab": "p-048", "building": "p-049",
    "storefront": "p-054", "wall_sign": "p-072", "bus": "p-069", "truck": "p-073", "culvert": "p-001",
}
CAPTIONS = {
    "paving": ("Bituminous road surfacing", "Roads"), "survey": ("Setting out and survey", "Civil engineering"),
    "gravel": ("Gravel road works", "Roads"), "drainage": ("Drainage works", "Civil engineering"),
    "rebar": ("Reinforcement for a concrete slab", "Structures"), "blocks": ("Foundation blockwork", "Building"),
    "slab": ("Casting a floor slab", "Building"), "building": ("Building under construction", "Building"),
    "storefront": ("ZAMEFA office front branding", "Branding"), "wall_sign": ("DMC Ichimpe Magazines wall sign", "Signage"),
    "bus": ("Chitambo College bus branding", "Vehicle branding"), "truck": ("Truck body branding", "Vehicle branding"),
    "culvert": ("Culvert and headwall works", "Civil engineering"),
    "column": ("Fixing column reinforcement", "Structures"), "footings": ("Foundations set out", "Building"),
    "site": ("Crew on a building site", "Building"), "scaffold": ("Formwork and scaffolding", "Structures"),
}


def extract_photos(pdf: Path, folder: Path) -> dict[str, Path]:
    subprocess.run(["pdfimages", "-f", "1", "-l", "10", "-png", str(pdf), str(folder / "p")], check=True)
    found = {}
    for key, stem in PHOTOS.items():
        path = folder / f"{stem}.png"
        if not path.is_file():
            raise SystemExit(f"Photo {stem} was not found in the PDF. Has the profile changed?")
        target = folder / f"vicreations-{key.replace('_', '-')}.jpg"
        from PIL import Image
        image = Image.open(path).convert("RGB")
        image.thumbnail((2000, 2000))  # the two full-resolution photos are kept sharp but web-sized
        image.save(target, quality=84, optimize=True, progressive=True)
        found[key] = target
    return found


# ---- editing helpers (all through Session) -------------------------------------------------
TEXTUAL = ("heading", "text", "button", "link")


class Site:
    def __init__(self, session: Session) -> None:
        self.s = session

    @property
    def doc(self):
        return self.s.document

    def sections(self, page: str, role: str) -> list[dict]:
        return [n for n in find_page(self.doc, page)["nodes"] if n.get("props", {}).get("role") == role]

    def section(self, page: str, role: str, index: int = 0) -> dict:
        return self.sections(page, role)[index]

    def delete(self, node_id: str) -> None:
        self.s.select(node_id)
        self.s.delete_selected()

    def drop(self, page: str, *roles: str) -> None:
        for role in roles:
            for sec in self.sections(page, role):
                self.delete(sec["id"])

    def fill(self, section_id: str, texts: list) -> None:
        """Sets the section's headings, texts, buttons and links in reading order.
        None keeps one, "-" deletes it, (label, href) also sets where a button or link goes."""
        nodes = [n for n in walk_nodes([self._node(section_id)]) if n["type"] in TEXTUAL]
        if len(texts) > len(nodes):
            raise SystemExit(f"More text than slots in {section_id}: {len(texts)} for {len(nodes)}")
        for node, value in zip(nodes, texts):
            if value is None:
                continue
            if value == "-":
                self.delete(node["id"])
                continue
            href = None
            if isinstance(value, tuple):
                value, href = value
            key = "text" if node["type"] in ("heading", "text") else "label"
            self.s.edit_prop(node["id"], key, value)
            self.s.end_gesture()
            if href is not None:
                self.s.edit_prop(node["id"], "href", href)
                self.s.end_gesture()

    def photos(self, section_id: str, assets: list[str], alts: list[str] | None = None) -> None:
        images = [n for n in walk_nodes([self._node(section_id)]) if n["type"] == "image"]
        for i, (node, asset) in enumerate(zip(images, assets)):
            if asset == "-":
                self.delete(node["id"])
                continue
            self.s.set_node_media(node["id"], asset)
            if alts:
                self.s.edit_prop(node["id"], "alt", alts[i])
                self.s.end_gesture()

    def cards(self, section_id: str, keep: int) -> None:
        """Deletes repeated cards past the first ``keep`` (the children of the section's grid)."""
        grid = next(n for n in walk_nodes([self._node(section_id)]) if n["type"] == "columns")
        for extra in grid["children"][keep:]:
            self.delete(extra["id"])

    def background(self, section_id: str, asset: str) -> None:
        self.s.set_node_media(section_id, asset, "background")

    def _node(self, node_id: str) -> dict:
        from mulusa_theme_studio.core.document import find_node
        return find_node(self.doc, node_id)

    def footer(self, mapping: dict) -> None:
        for node in list(walk_nodes([self.doc["site"]["footer"]])):
            text = node.get("props", {}).get("text") or node.get("props", {}).get("label")
            if text in mapping:
                new = mapping[text]
                if new == "-":
                    self.delete(node["id"])
                else:
                    self.s.edit_prop(node["id"], "text" if node["type"] in ("heading", "text") else "label", new)
                    self.s.end_gesture()

    def colours(self, **values: str) -> None:
        for name, value in values.items():
            self.s.edit_design(f"Colour {name}", lambda doc, n=name, v=value: design.set_color(doc, n, v))

    def remove_page(self, page_id: str) -> None:
        self.s.set_page(find_page(self.doc, "home")["id"])
        self.s.delete_page(page_id)

    def icons(self, section_id: str, names: list[str]) -> None:
        found = [n for n in walk_nodes([self._node(section_id)]) if n["type"] == "icon"]
        for node, name in zip(found, names):
            self.s.edit_prop(node["id"], "name", name)
            self.s.end_gesture()

    def art(self, section_id: str, names: list[str], width: str = "150px") -> None:
        """Swaps the section's icons, in reading order, for animated illustrations in the site's colours.
        Meant for cards with room above the heading, not for compact icon lists."""
        from mulusa_theme_studio.core.document import new_id
        found = [n for n in walk_nodes([self._node(section_id)]) if n["type"] == "icon"]
        for node, name in zip(found, names):
            parent = next(p for p in walk_nodes([self._node(section_id)]) if any(c is node for c in p.get("children", [])))
            index = next(i for i, c in enumerate(parent["children"]) if c is node)
            tree = {"id": new_id(), "type": "illustration", "props": {"name": name, "animate": True, "aria_label": ""},
                    "style": {"width": "100%", "max_width": width, "margin_left": "0", "margin_bottom": "8px"}}
            if not self.s._insert_tree(f"Add {name} illustration", tree, parent["id"], index):
                raise SystemExit(f"Could not place the {name} illustration in {section_id}")
            self.delete(node["id"])

    def ambient(self, section_id: str, value: str) -> None:
        """A living background (aurora, grid, stars, waves). Only on sections without a photograph:
        a photo section becomes a WordPress cover block, which does not carry it."""
        section = self._node(section_id)
        if isinstance(section.get("props", {}).get("background"), dict):
            raise SystemExit(f"{section_id} has a photograph; a living background belongs on a plain section")
        self.s.edit_prop(section_id, "ambient", value)
        self.s.end_gesture()

    def team(self, section_id: str) -> None:
        self.photos(section_id, ["-"] * 8)   # the profile has no portraits; no placeholders are left
        texts = [None]
        for name, role in TEAM:
            texts += [name, role]
        self.fill(section_id, texts)


def stats_texts():
    out = []
    for value, label in STATS:
        out += [value, label]
    return out


def catalogue_texts(title: str, intro: str) -> list:
    out = [title, intro]
    for heading, items in CATALOGUE:
        out += [heading] + items + ["-"] * (10 - len(items))
    return out


def process_texts(title: str) -> list:
    out = [title]
    for step, text in PROCESS:
        out += [None, step, text]   # the step number stays
    return out


def pairs(rows) -> list:
    return [x for pair in rows for x in pair]


def captions(keys) -> list:
    return [x for k in keys for x in CAPTIONS[k]]


def _common_header(v: Site, session: Session, cta: str | None) -> None:
    header = v.doc["site"]["header"]["id"]
    session.edit_prop(header, "brand", BRAND)
    if cta:
        session.edit_prop(header, "cta", {"label": cta, "href": {"page": "contact"}})


def _rename_work(v: Site, session: Session, label: str = "Our work", slug: str = "our-work") -> None:
    session.rename_page("portfolio", label)
    session.set_page_slug("portfolio", slug)
    for item in v.doc["navigation"]["primary"]:
        if item.get("page") == "portfolio":
            session.update_nav_item(item["id"], label=label)


# ==============================================================================================
#  Variation 1: Bold. Dark, orange and condensed capitals, from Construction / Heavy Civil
# ==============================================================================================
def bold(session: Session, parent: Path, img: dict) -> Path:
    project = session.create_project("Vicreations Bold", "construction/heavy-civil", parent)
    v = Site(session)
    a = {k: session.upload_media([p])[0]["id"] for k, p in img.items()}
    v.colours(accent="#f26522", on_accent="#17191c")
    _common_header(v, session, "Request a quote")

    session.set_page("home")
    hero = v.section("home", "hero")
    v.background(hero["id"], a["culvert"])
    v.fill(hero["id"], ["Engineering, branding and supplies for Zambia",
                        "From roads and buildings to billboards, print and ICT: one Luanshya team, working for public institutions and private clients since 2018.",
                        ("Request a quote", {"page": "contact"}), ("See our work", {"page": "portfolio"})])
    index, panels = v.sections("home", "services")
    v.fill(index["id"], ["One company, four ways to help", SERVES, ("All services", {"page": "services"})] + pairs(DIVISIONS))
    v.icons(index["id"], ["hard-hat", "pen-tool", "shirt", "monitor"])   # a compact list: icons fit its narrow column, drawings do not
    v.photos(panels["id"], [a["rebar"], a["storefront"]], ["Vicreations engineers fixing slab reinforcement", "ZAMEFA office front branded by Vicreations"])
    v.fill(panels["id"], ["Engineering and construction", PM, " · ".join(CATALOGUE[0][1][6:]), ("Ask about this", {"page": "contact"}),
                          "Branding and signage", "Signs, stands and branded vehicles that make a business easy to find and hard to forget.",
                          " · ".join(CATALOGUE[1][1]), ("Ask about this", {"page": "contact"})])
    work = v.section("home", "portfolio")
    keys = ["paving", "drainage", "wall_sign", "building"]
    v.photos(work["id"], [a[k] for k in keys], [CAPTIONS[k][0] for k in keys])
    v.fill(work["id"], ["Recent work"] + captions(keys))
    band = v.section("home", "statement")
    v.background(band["id"], a["site"])
    v.fill(band["id"], ["Professionalism, integrity and creativity on every job, from the first plan to handover."])
    v.fill(v.section("home", "process")["id"], process_texts("How a project runs"))
    v.drop("home", "catalogue", "testimonials")
    v.fill(v.section("home", "credentials")["id"], ["Registered, compliant and ready to tender"] + pairs(CREDENTIALS))
    v.ambient(v.section("home", "credentials")["id"], "grid")
    v.fill(v.section("home", "clients")["id"], ["Trusted by"] + MINISTRIES)
    v.fill(v.section("home", "call_to_action")["id"], ["Have a project to price?", ("Request a quote", {"page": "contact"})])
    v.ambient(v.section("home", "call_to_action")["id"], "aurora")

    session.set_page("about")
    ph = v.section("about", "page_header")
    v.background(ph["id"], a["survey"])
    v.fill(ph["id"], ["About us", "A wholly Zambian company, incorporated in 2018 and based in Luanshya."])
    about = v.section("about", "about")
    v.photos(about["id"], [a["scaffold"]], ["Formwork and scaffolding on a Vicreations site"])
    v.fill(about["id"], ["Who is Vicreations?", INTRO, STORY, ("Our services", {"page": "services"})])
    v.fill(v.section("about", "values")["id"], pairs(TRIO))
    v.fill(v.section("about", "statistics")["id"], stats_texts())
    v.team(v.section("about", "team")["id"])
    v.fill(v.section("about", "team")["id"], ["The team behind the work"])
    v.drop("about", "credentials")   # it leads the home page

    session.set_page("services")
    ph = v.section("services", "page_header")
    v.background(ph["id"], a["scaffold"])
    v.fill(ph["id"], ["Services", "Engineering and construction, branding and signage, print and promotion, design, supplies and ICT."])
    svc = v.section("services", "services")
    v.photos(svc["id"], [a["survey"], a["gravel"], a["slab"]], ["Setting out and survey", "Gravel road works", "Casting a floor slab"])
    v.fill(svc["id"], ["Engineering and construction",
                       "Construction project management", PM, ("Ask about this", {"page": "contact"}),
                       "Civil engineering and roads", CIVIL, ("Ask about this", {"page": "contact"}),
                       "Building construction", BUILDING, ("Ask about this", {"page": "contact"})])
    v.fill(v.section("services", "catalogue")["id"], catalogue_texts("Everything we make and supply", "The full list from our profile, across all four divisions, and many more on request."))
    feat = v.section("services", "features")
    v.photos(feat["id"], [a["bus"]], ["Chitambo College bus branded by Vicreations"])
    v.fill(feat["id"], ["Branding that travels", SAFETY, "Vehicle branding", "Storefront branding", "Exhibition stands", "Site safety signage", "Worksuit branding"])
    v.drop("services", "pricing")

    session.set_page("portfolio")
    ph = v.section("portfolio", "page_header")
    v.background(ph["id"], a["paving"])
    v.fill(ph["id"], ["Our work", "Photographs from Vicreations sites and branding jobs."])
    wall, brand = v.sections("portfolio", "portfolio")
    keys = ["culvert", "survey", "gravel", "drainage", "rebar", "column", "footings", "slab", "building"]
    v.photos(wall["id"], [a[k] for k in keys], [CAPTIONS.get(k, (k, ""))[0] for k in keys])
    v.fill(wall["id"], ["Engineering and construction"] + captions(keys))
    keys = ["storefront", "wall_sign", "bus", "truck"]
    v.photos(brand["id"], [a[k] for k in keys] + ["-", "-"], [CAPTIONS[k][0] for k in keys] + ["", ""])
    v.fill(brand["id"], ["Branding and signage"] + captions(keys) + ["-"] * 4)
    grid = next(n for n in walk_nodes([v._node(brand["id"])]) if n["type"] == "columns")
    session.edit_prop(grid["id"], "columns", 2)
    session.end_gesture()
    v.drop("portfolio", "statistics")
    _rename_work(v, session)

    session.set_page("blog")
    ph = v.section("blog", "page_header")
    v.background(ph["id"], a["blocks"])
    v.fill(ph["id"], ["News", "Updates from our sites and studio, published from WordPress."])
    v.drop("blog", "blog")
    session.insert_component("latest-posts", "page:blog", 1)
    query = next(n for n in walk_nodes(find_page(v.doc, "blog")["nodes"]) if n["type"] == "query")
    session.edit_query(query["id"], count=6, columns=3, pagination=True, hide=["author"])

    session.set_page("contact")
    ph = v.section("contact", "page_header")
    v.background(ph["id"], a["footings"])
    v.fill(ph["id"], ["Contact", "Tell us what you need: a road, a building, a sign or a print run."])
    v.fill(v.section("contact", "contact")["id"], ["Talk to our team", "Send us your drawings, brief or quantities and we will prepare a quotation.", ADDRESS, PHONES, EMAIL])

    v.footer({"IRONBRIDGE": BRAND, "100 Example Road, Your City": ADDRESS, "hello@example.com": EMAIL,
              "© IRONBRIDGE. All rights reserved.": f"© {COMPANY}. {TAGLINE}."})
    for node in walk_nodes([v.doc["site"]["footer"]]):
        if node["type"] == "text" and str(node["props"].get("text", "")).startswith("We deliver commercial"):
            session.edit_prop(node["id"], "text", "Engineering, construction, branding, print and supplies, based in Luanshya.")
        if node["type"] == "link" and node["props"].get("label") == "Projects":
            session.edit_prop(node["id"], "label", "Our work")

    session.set_edit_scope("mobile")
    session.edit_style(hero["id"], "min_height", "600px")
    session.set_edit_scope("")
    session.open_role_page("single")
    session.open_role_page("archive")
    session.set_page("home")
    session.edit_design("Site details", lambda doc: doc["meta"].update(description="Engineering, construction, branding, print and supplies in Zambia.", author=COMPANY))
    session.save()
    return project.folder


# ==============================================================================================
#  Variation 2: Corporate. Navy and orange, rounded and calm, from Corporate / Modern Consulting
# ==============================================================================================
def corporate(session: Session, parent: Path, img: dict) -> Path:
    project = session.create_project("Vicreations Corporate", "corporate/modern-consulting", parent)
    v = Site(session)
    a = {k: session.upload_media([p])[0]["id"] for k, p in img.items()}
    v.colours(primary="#2b3990", secondary="#1d2766", accent="#f26522", on_accent="#ffffff", surface="#eef1f8", text="#151a33")
    _common_header(v, session, "Contact us")

    session.set_page("home")
    hero = v.section("home", "hero")
    v.photos(hero["id"], [a["culvert"]], ["Vicreations engineers on culvert and headwall works"])
    v.fill(hero["id"], ["One team to build, brand and supply", INTRO, ("Contact us", {"page": "contact"})])
    h1 = next(n for n in walk_nodes([v._node(hero["id"])]) if n["type"] == "heading")
    session.edit_style(h1["id"], "font_size", "clamp(2.3rem,4.4vw,3.9rem)")   # sized for the card, not the page
    session.end_gesture()
    bento, panels = v.sections("home", "services")
    v.fill(bento["id"], ["Four divisions, one accountable team"] + pairs(DIVISIONS))
    v.art(bento["id"], ["crane", "palette", "hanger", "code"])
    v.fill(v.section("home", "credentials")["id"], ["Registered, compliant and ready to tender"] + pairs(CREDENTIALS))
    v.ambient(v.section("home", "credentials")["id"], "grid")
    v.photos(panels["id"], [a["building"], a["truck"]], ["A building under construction by Vicreations", "Truck body branded by Vicreations"])
    v.fill(panels["id"], ["Buildings and roads", CIVIL + " " + BUILDING, " · ".join(CATALOGUE[0][1][:6]), ("Ask about this", {"page": "contact"}),
                          "Brands on the move", SAFETY, " · ".join(CATALOGUE[1][1][:6]), ("Ask about this", {"page": "contact"})])
    band = v.section("home", "statement")
    v.background(band["id"], a["wall_sign"])
    v.fill(band["id"], ["Our vision: a regional market leader in products and services that stand out from the rest."])
    work = v.section("home", "portfolio")
    keys = ["paving", "storefront", "drainage", "bus"]
    v.photos(work["id"], [a[k] for k in keys], [CAPTIONS[k][0] for k in keys])
    v.fill(work["id"], ["Recent work for our clients"] + captions(keys))
    v.fill(v.section("home", "process")["id"], process_texts("From concept to realisation"))
    faq = v.section("home", "faq")
    v.fill(faq["id"], ["Trusted by public institutions", CLIENTS])
    faqs = [n for n in walk_nodes([v._node(faq["id"])]) if n["type"] == "faq_item"]
    answers = [("Who do you work with?", "Parastatals, public works agencies, municipalities and commercial private clients."),
               ("Can you supply public institutions?", "Yes. We are registered on the ZPPA e-tendering system and hold current tax, NAPSA and Workers' Compensation certificates."),
               ("Where are you based?", "In Luanshya CBD, on the Copperbelt, and we work across Zambia."),
               ("Can you take a project from concept to completion?", "Yes. We plan, design, build and brand, and keep you informed at every stage.")]
    for node, (q, ans) in zip(faqs, answers):
        session.edit_prop(node["id"], "question", q)
        session.edit_prop(node["id"], "answer", ans)
        session.end_gesture()
    v.fill(v.section("home", "call_to_action")["id"], ["Tell us what you need", "We will reply with a quotation and a programme.", ("Start a conversation", {"page": "contact"})])
    v.ambient(v.section("home", "call_to_action")["id"], "aurora")

    session.set_page("about")
    v.fill(v.section("about", "page_header")["id"], ["About us", "A wholly Zambian company, incorporated on 14 May 2018."])
    v.fill(v.section("about", "about")["id"], [STORY])
    v.fill(v.section("about", "values")["id"], pairs(TRIO))
    v.team(v.section("about", "team")["id"])
    v.fill(v.section("about", "team")["id"], ["Leadership and design"])
    v.fill(v.section("about", "statistics")["id"], stats_texts())

    session.set_page("services")
    v.fill(v.section("services", "page_header")["id"], ["Services", "Engineering, branding, print and supplies."])
    v.fill(v.section("services", "services")["id"], ["What each division does",
                                                     "Engineering and construction", PM + " " + CIVIL + " " + BUILDING,
                                                     "Branding and signage", SIGNAGE + " " + SAFETY,
                                                     "Print and promotion", PRINT + " " + PROMO,
                                                     "Design, supplies and ICT", DESIGN + " " + SUPPLY])
    v.fill(v.section("services", "catalogue")["id"], catalogue_texts("The full catalogue", "Everything listed in our profile, and many more on request."))
    feat = v.section("services", "features")
    v.photos(feat["id"], [a["column"]], ["Fixing reinforcement for a concrete column"])
    v.fill(feat["id"], ["How we work", VALUES, "Professionalism", "Integrity", "Creativity", "Positive attitude", "Client satisfaction"])
    v.drop("services", "pricing")

    session.set_page("portfolio")
    v.fill(v.section("portfolio", "page_header")["id"], ["Our work", "Construction and branding, photographed on site."])
    work = v.section("portfolio", "portfolio")
    keys = ["culvert", "gravel", "slab", "storefront", "wall_sign"]
    v.photos(work["id"], [a[k] for k in keys], [CAPTIONS.get(k, (k, ""))[0] for k in keys])
    texts = ["Selected projects"]
    for k in keys:
        texts += [CAPTIONS[k][0], CAPTIONS[k][1], "-"]
    v.fill(work["id"], texts)
    v.drop("portfolio", "testimonials")
    _rename_work(v, session)
    v.remove_page("blog")

    session.set_page("contact")
    v.fill(v.section("contact", "page_header")["id"], ["Contact", f"{ADDRESS}  ·  {PHONES}"])
    v.fill(v.section("contact", "contact")["id"], ["Speak with our team", f"Email {EMAIL} or send a message below."])
    _footer_generic(v, session)
    session.edit_design("Site details", lambda doc: doc["meta"].update(description="Vicreations Investment Limited: engineering, construction, branding, print and supplies.", author=COMPANY))
    session.set_page("home")
    session.save()
    return project.folder


# ==============================================================================================
#  Variation 3: Editorial. Giant type, white space and Vicreations orange, from Art / Design Studio
# ==============================================================================================
def editorial(session: Session, parent: Path, img: dict) -> Path:
    project = session.create_project("Vicreations Editorial", "art/design-studio", parent)
    v = Site(session)
    a = {k: session.upload_media([p])[0]["id"] for k, p in img.items()}
    v.colours(primary="#e8481c", secondary="#a32c0c", accent="#1d2766", on_accent="#ffffff")
    _common_header(v, session, None)

    session.set_page("home")
    hero = v.section("home", "hero")
    v.photos(hero["id"], [a["wall_sign"]], ["The DMC Ichimpe Magazines wall sign, painted by Vicreations"])
    v.fill(hero["id"], ["Simply versatile", "Engineering, construction, branding, print and supplies, from one Zambian team in Luanshya.",
                        ("See our work", {"page": "portfolio"})])
    v.fill(v.section("home", "services")["id"], ["What we do"] + pairs(DIVISIONS))
    v.fill(v.section("home", "catalogue")["id"], catalogue_texts("Everything we make and supply", "More than forty products and services, and many more on request."))
    work = v.section("home", "portfolio")
    keys = ["culvert", "storefront", "paving", "bus"]
    v.photos(work["id"], [a[k] for k in keys], [CAPTIONS[k][0] for k in keys])
    v.fill(work["id"], ["Selected work"] + captions(keys))
    band = v.section("home", "statement")
    v.background(band["id"], a["site"])
    v.fill(band["id"], ["From concept to realisation, on schedule and within budget."])
    v.fill(v.section("home", "clients")["id"], ["Trusted by"] + MINISTRIES)
    v.fill(v.section("home", "team")["id"], ["The people behind the work"] + pairs(TEAM))
    v.drop("home", "blog")
    v.fill(v.section("home", "call_to_action")["id"], ["Have a brief? Send it to us.", "A road, a building, a sign or a print run: tell us the quantities and the deadline.",
                                                      ("Start a conversation", {"page": "contact"})])
    v.ambient(v.section("home", "call_to_action")["id"], "waves")

    session.set_page("about")
    v.fill(v.section("about", "page_header")["id"], ["About", "Creative professionals working with brands and companies across Zambia."])
    v.fill(v.section("about", "about")["id"], [INTRO])
    v.fill(v.section("about", "values")["id"], pairs(TRIO))
    v.fill(v.section("about", "team")["id"], ["Our people"] + pairs(TEAM))
    v.fill(v.section("about", "credentials")["id"], ["Registered, compliant and ready to tender"] + pairs(CREDENTIALS))

    session.set_page("services")
    v.fill(v.section("services", "page_header")["id"], ["Services", "Four divisions, one accountable team."])
    v.fill(v.section("services", "services")["id"], ["Ways we can help",
                                                     "Engineering and construction", PM + " " + CIVIL + " " + BUILDING,
                                                     "Branding and signage", SIGNAGE + " " + SAFETY,
                                                     "Print and promotion", PRINT + " " + PROMO,
                                                     "Design, supplies and ICT", DESIGN + " " + SUPPLY])
    v.fill(v.section("services", "catalogue")["id"], catalogue_texts("The full list", "Everything in our profile, and many more on request."))
    v.drop("services", "pricing")
    session.rename_page("services", "Services")
    session.set_page_slug("services", "services")
    for item in v.doc["navigation"]["primary"]:
        if item.get("page") == "services":
            session.update_nav_item(item["id"], label="Services")

    session.set_page("portfolio")
    v.fill(v.section("portfolio", "page_header")["id"], ["Work", "Engineering and branding by Vicreations."])
    first, second = v.sections("portfolio", "portfolio")
    keys = ["drainage", "rebar", "gravel", "building"]
    v.photos(first["id"], [a[k] for k in keys], [CAPTIONS[k][0] for k in keys])
    v.fill(first["id"], ["Engineering and construction"] + captions(keys))
    keys = ["storefront", "wall_sign", "bus", "truck"]
    v.photos(second["id"], [a[k] for k in keys] + ["-"], [CAPTIONS[k][0] for k in keys] + [""])
    texts = ["Branding and signage"]
    for k in keys:
        texts += [CAPTIONS[k][0], CAPTIONS[k][1], "-"]
    v.fill(second["id"], texts + ["-", "-", "-"])
    v.remove_page("blog")

    session.set_page("contact")
    v.fill(v.section("contact", "page_header")["id"], ["Contact", "Quotations for engineering, branding, print and supplies."])
    v.fill(v.section("contact", "contact")["id"], ["Say hello", "Tell us what you need, the quantities and your deadline.", ADDRESS, PHONES, EMAIL])
    _footer_generic(v, session)
    session.edit_design("Site details", lambda doc: doc["meta"].update(description="Vicreations: engineering, construction, branding, print and supplies in Zambia.", author=COMPANY))
    session.set_page("home")
    session.save()
    return project.folder


def _footer_generic(v: Site, session: Session) -> None:
    """Replaces whatever sample identity the template's footer carries."""
    old_brand = None
    for node in walk_nodes([v.doc["site"]["footer"]]):
        props = node.get("props", {})
        text = str(props.get("text", ""))
        if node["type"] == "heading" and old_brand is None:
            old_brand = text
            session.edit_prop(node["id"], "text", BRAND)
            if "vw" in str(node.get("style", {}).get("font_size", "")):
                # A wordmark sized to its sample name: size it again for the longer real one.
                sys.path.insert(0, str(ROOT / "tools"))
                from template_kit import fit_text
                session.edit_style(node["id"], "font_size", fit_text(BRAND, v.doc["tokens"]["fonts"]["heading"], 12))
        elif text.startswith("©"):
            session.edit_prop(node["id"], "text", f"© {COMPANY}. {TAGLINE}.")
        elif text == "100 Example Road, Your City":
            session.edit_prop(node["id"], "text", ADDRESS)
        elif text in ("hello@example.com",):
            session.edit_prop(node["id"], "text", EMAIL)
        elif text in ("+000 000 000 000",):
            session.edit_prop(node["id"], "text", PHONES)
        elif node["type"] == "text" and len(text) > 60:
            session.edit_prop(node["id"], "text", "Engineering, construction, branding and print, based in Luanshya, Zambia.")
        elif node["type"] == "link" and props.get("label") in ("Insights", "Notes", "News"):
            v.delete(node["id"])
        elif node["type"] == "link" and props.get("label") in ("Case Studies", "Work"):
            session.edit_prop(node["id"], "label", "Our work")
        elif node["type"] == "link" and props.get("label") == "Commissions":
            session.edit_prop(node["id"], "label", "Services")
    session.end_gesture()


def export_all(folder: Path, out: Path) -> list[str]:
    from mulusa_theme_studio.core.project import Project
    lines = []
    project = Project.open(folder)
    wp = WordPressExporter().export(project.document, project.folder, out, ExportOptions(theme_name=project.name, author=COMPANY))
    lines.append(f"{project.name}: WordPress {wp.output.name} + {wp.plugin.name if wp.plugin else 'no plugin'}; {len(wp.issues)} note(s)")
    lines += [f"    {i.severity}: {i}" for i in wp.issues]
    st = StaticExporter().export(project.document, project.folder, out, StaticOptions(site_name=project.name, form_email=EMAIL))
    lines.append(f"{project.name}: static {st.output.name}; {len(st.issues)} note(s)")
    lines += [f"    {i.severity}: {i}" for i in st.issues]
    return lines


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    app = QCoreApplication.instance() or QCoreApplication([])
    pdf = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "samples" / "Vicreations"
    target.mkdir(parents=True, exist_ok=True)
    settings = Settings.load()
    settings.author = COMPANY
    report = []
    with tempfile.TemporaryDirectory() as temp:
        photos = extract_photos(pdf, Path(temp))
        for build in (bold, corporate, editorial):
            name = {"bold": "Vicreations Bold", "corporate": "Vicreations Corporate", "editorial": "Vicreations Editorial"}[build.__name__]
            existing = target / name
            if existing.exists() and (existing / "project.json").is_file():
                shutil.rmtree(existing)
            session = Session(settings, TemplateLibrary())
            folder = build(session, target, photos)
            print("built", folder)
            report += export_all(folder, target / "exports")
    print("\n".join(report))
