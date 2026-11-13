"""Builds the "Launch & One-page" template collection: full-screen, living single pages.

Each one is a landing page (no site header or footer) with a living background, a glass or soft card,
an animated illustration and a countdown, progress bar or set of links. Ids are deterministic, so
running it twice writes identical files. Names, dates and figures are fictional samples.

Run: .venv/bin/python tools/build_onepage.py   (build_templates.py also calls it)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from template_kit import palette  # noqa: E402

from mulusa_theme_studio.core.document import SCHEMA, validate_document  # noqa: E402

OUT = ROOT / "src" / "mulusa_theme_studio" / "templates"
CATEGORY = ("onepage", "Launch & One-page")
DARK_GLASS = {"background": "rgba(255,255,255,0.08)", "border": "1px solid rgba(255,255,255,0.16)", "backdrop_filter": "blur(16px) saturate(140%)",
              "box_shadow": "0 30px 80px rgba(0,0,0,0.4)"}
LIGHT_GLASS = {"background": "rgba(255,255,255,0.72)", "border": "1px solid rgba(255,255,255,0.9)", "backdrop_filter": "blur(14px) saturate(150%)",
               "box_shadow": "0 24px 60px rgba(20,30,50,0.14)"}


class Builder:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.count = 0

    def id(self) -> str:
        self.count += 1
        return f"{self.slug[:3]}{self.count}"

    def n(self, type_: str, props: dict | None = None, style: dict | None = None, children: list | None = None, name: str = "", mobile: dict | None = None) -> dict:
        node = {"id": self.id(), "type": type_, "props": props or {}, "style": style or {}}
        if name:
            node["name"] = name
        if type_ in ("section", "container", "columns", "row"):
            node["children"] = children or []
        if mobile:
            node["responsive"] = {"mobile": {"style": mobile}}
        return node

    def box(self, *children, name: str = "", mobile: dict | None = None, **style) -> dict:
        return self.n("container", {}, style, list(children), name, mobile)

    def row(self, *children, **style) -> dict:
        style.setdefault("gap", "12px")
        style.setdefault("justify_content", "center")
        return self.n("row", {}, style, list(children))

    def h(self, text: str, level: int = 1, **style) -> dict:
        return self.n("heading", {"text": text, "level": level}, style)

    def p(self, text: str, muted: bool = True, **style) -> dict:
        return self.n("text", {"text": text, **({"muted": True} if muted else {})}, style)

    def btn(self, label: str, href: str, variant: str = "primary", **style) -> dict:
        return self.n("button", {"label": label, "href": href, "variant": variant}, style)

    def art(self, name: str, width: str = "230px") -> dict:
        return self.n("illustration", {"name": name, "animate": True}, {"width": "100%", "max_width": width})

    def countdown(self, target: str, offset: str = "+02:00", done: str = "We are live.") -> dict:
        return self.n("countdown", {"target": target, "utc_offset": offset, "show_seconds": True, "done_text": done}, {"margin_block": "4px"})

    def progress(self, mode: str = "loading", value: int = 60, label: str = "") -> dict:
        props = {"mode": mode, "value": value, "show_value": True}
        if label:
            props["label"] = label
        return self.n("progress", props, {"max_width": "380px", "margin_inline": "auto"})

    def form(self, label: str, submit: str) -> dict:
        return self.n("contact_form", {"fields": [{"label": label, "type": "email"}], "submit": submit}, {"width": "100%", "max_width": "420px", "margin_inline": "auto"})

    def card(self, *children, glass: dict, radius: str = "24px") -> dict:
        style = {**glass, "border_radius": radius, "padding": "46px 38px", "gap": "18px", "align_items": "center", "text_align": "center", "width": "100%"}
        return self.box(*children, name="Glass card", mobile={"padding": "34px 20px"}, **style)


def page_section(b: Builder, card: dict, *, ambient: str = "", tone: str = "", photo: tuple[str, str] | None = None, brand: str = "", note: str = "") -> dict:
    top = b.row(b.p(brand, False, font_weight="700", letter_spacing="0.14em", text_transform="uppercase", font_size=".82rem"), justify_content="center") if brand else None
    bottom = b.p(note, font_size=".8rem", text_align="center") if note else None
    inner = b.box(*(x for x in (top, card, bottom) if x), width="100%", max_width="680px", margin_inline="auto", gap="22px", align_items="center")
    props: dict = {"role": "hero"}
    if tone:
        props["tone"] = tone
    if ambient:
        props["ambient"] = ambient
    if photo:
        props["tone"] = "image"
        props["background"] = {"media": {"kind": "placeholder", "seed": f"{b.slug}-bg", "subject": photo[0], "ratio": 1.78, "label": "Background image"},
                               "overlay": photo[1], "alt": ""}
    container = b.n("container", {"width": "content"}, {"align_items": "center"}, [inner])
    return b.n("section", props, {"min_height": "100vh", "display": "flex", "align_items": "center", "padding_block": "64px"}, [container], "Hero",
               mobile={"padding_block": "40px"})


def document(b: Builder, name: str, template_name: str, description: str, colors: dict, fonts: tuple[str, str], section: dict, *,
             heading_weight: int = 700, radius: str = "10px", button_radius: str = "999px") -> dict:
    footer = b.n("footer", {"tone": "inverse"}, {"padding_block": "40px"}, [b.n("container", {"width": "content"}, {}, [b.p(f"© {name}. All rights reserved.", font_size=".85rem")])], "Site footer")
    return {
        "schema": SCHEMA,
        "meta": {"id": f"onepage/{b.slug}", "template_name": template_name, "name": name, "description": description, "author": "Mulusa Innovations", "version": "1.0.0"},
        "tokens": {
            "colors": colors, "fonts": {"heading": fonts[0], "body": fonts[1], "extra": []},
            "type": {"heading_weight": heading_weight, "heading_transform": "none", "heading_tracking": "-0.02em", "heading_line": 1.08, "base": 17, "ratio": 1.28},
            "shape": {"radius": radius, "button_radius": button_radius, "button_style": "solid", "button_transform": "none", "button_tracking": "0", "button_size": ".97rem"},
            "spacing": {"section": "96px", "gap": "24px", "width": "1120px"},
        },
        "palettes": [{"name": template_name, "colors": colors}],
        "type_pairs": [{"name": f"{fonts[0]} / {fonts[1]}", "heading": fonts[0], "body": fonts[1]}],
        "site": {"header": {"id": b.id(), "type": "header", "props": {"layout": "minimal", "brand": name}, "style": {}, "name": "Site header"}, "footer": footer},
        "navigation": {"primary": []},
        "pages": [{"id": "home", "slug": "home", "title": "Home", "home": True, "layout": "landing", "nodes": [section]}],
        "media": {"art": "gradient", "assets": []},
        "reusable": [],
    }


# The collection -----------------------------------------------------------------------------------------
def maintenance() -> dict:
    b = Builder("maintenance-gears")
    c = palette("#0f172a", "#f1f5f9", "#2563eb", "#f59e0b", secondary="#1e293b", surface="#16213a")
    card = b.card(b.art("gears", "240px"), b.h("We are tuning things up.", font_size="clamp(2rem,5vw,3rem)"),
                  b.p("Our website is getting some planned maintenance. It will be back shortly, faster than before. Thank you for your patience.", max_width="46ch"),
                  b.progress(), b.p("Need us urgently? Email hello@vertexgroup.example", False, font_size=".95rem"), glass=DARK_GLASS)
    return document(b, "Vertex Group", "Maintenance: Gears", "A calm maintenance notice: turning gears, a loading bar and a way to reach you.", c, ("Outfit", "Inter"),
                    page_section(b, card, ambient="grid", brand="Vertex Group", note="© Vertex Group"))


def ict() -> dict:
    b = Builder("ict-coming-soon")
    c = palette("#04161c", "#e6f6f8", "#14b8c4", "#3ddc97", secondary="#082a33", surface="#0a2229")
    card = b.card(b.art("server", "250px"), b.h("Faster networks are on their way.", font_size="clamp(2rem,5vw,3rem)"),
                  b.p("NETSPAN is moving to new infrastructure. Our new site opens with managed connectivity, cloud hosting and 24/7 support.", max_width="48ch"),
                  b.countdown("2027-03-01T08:00"), b.form("Work email", "Tell me when"), glass=DARK_GLASS)
    return document(b, "NETSPAN Systems", "ICT: Coming soon", "A coming-soon page for an ICT company: blinking server racks, a live countdown and sign-up.", c, ("Space Grotesk", "Inter"),
                    page_section(b, card, ambient="grid", brand="NETSPAN Systems", note="Managed networks · Cloud · Support"), radius="6px", button_radius="6px")


def security() -> dict:
    b = Builder("security-launch")
    c = palette("#121214", "#f4f4f5", "#e11d48", "#f43f5e", secondary="#1f1f23", surface="#1b1b1f")
    card = b.card(b.art("shield", "220px"), b.h("Protection, rebuilt.", font_size="clamp(2.1rem,5vw,3.2rem)"),
                  b.p("Sentinel Guard is launching a new home for guarding, CCTV and cyber security services. Until then, our control room is open around the clock.", max_width="48ch"),
                  b.countdown("2027-02-14T09:00"), b.row(b.btn("Call the control room", "tel:+000000000000"), b.btn("Email us", "mailto:hello@sentinel.example", "secondary")), glass=DARK_GLASS)
    return document(b, "Sentinel Guard", "Security: Launch", "A security launch page: a scanning shield, live countdown and a direct line to the control room.", c, ("Sora", "Manrope"),
                    page_section(b, card, photo=("building", "linear-gradient(180deg,rgba(10,10,12,.72),rgba(10,10,12,.88))"), brand="Sentinel Guard", note="Guarding · CCTV · Cyber security"),
                    radius="8px", button_radius="8px")


def music() -> dict:
    b = Builder("music-album")
    c = palette("#160b24", "#f6efff", "#a855f7", "#f472b6", secondary="#24123a", surface="#1e1030")
    card = b.card(b.art("vinyl", "250px"), b.p("New album", False, letter_spacing="0.2em", text_transform="uppercase", font_size=".8rem"),
                  b.h("Night Signals", font_size="clamp(2.6rem,7vw,4.4rem)"),
                  b.p("Eleven songs written between Lusaka and Johannesburg. Out everywhere on the date below.", max_width="44ch"),
                  b.countdown("2027-04-10T00:00", done="Out now."), b.row(b.btn("Pre-save", "#"), b.btn("Watch the teaser", "#", "secondary")), glass=DARK_GLASS)
    return document(b, "Mwila", "Music: Album release", "An album countdown: a spinning record, floating notes and pre-save buttons.", c, ("Unbounded", "DM Sans"),
                    page_section(b, card, ambient="waves", brand="Mwila", note="Tour dates announced soon"), heading_weight=700)


def construction() -> dict:
    b = Builder("construction-progress")
    c = palette("#1c1917", "#fafaf9", "#f59e0b", "#facc15", secondary="#292524", surface="#26221f")
    card = b.card(b.art("crane", "260px"), b.h("Our new site is under construction.", font_size="clamp(2rem,5vw,3rem)"),
                  b.p("Ironbridge builds roads, bridges and industrial sites. While we finish our website, here is how far along we are.", max_width="46ch"),
                  b.progress("value", 72, "Website build"), b.row(b.btn("Request a quote", "mailto:projects@ironbridge.example"), b.btn("Call us", "tel:+000000000000", "secondary")),
                  glass=DARK_GLASS)
    return document(b, "Ironbridge Construction", "Construction: In progress", "A construction holding page: a working crane, real progress and a quote request.", c, ("Oswald", "Work Sans"),
                    page_section(b, card, photo=("crane", "linear-gradient(180deg,rgba(20,16,12,.7),rgba(20,16,12,.9))"), brand="Ironbridge", note="Civil · Structural · Industrial"),
                    heading_weight=600, radius="4px", button_radius="4px")


def saas() -> dict:
    b = Builder("saas-waitlist")
    c = palette("#0b0b1a", "#eef0ff", "#6366f1", "#22d3ee", secondary="#15153a", surface="#121230")
    card = b.card(b.art("rocket", "210px"), b.h("Your reports, written for you.", font_size="clamp(2.1rem,5.4vw,3.4rem)"),
                  b.p("Lumen reads your numbers and writes the weekly report your team actually reads. Join the waitlist for early access.", max_width="46ch"),
                  b.countdown("2027-01-20T16:00", "+00:00", "Early access is open."), b.form("Your email", "Join the waitlist"), glass=DARK_GLASS)
    return document(b, "Lumen AI", "SaaS: Waitlist launch", "A product launch waitlist: a floating rocket over an aurora, a live countdown and sign-up.", c, ("Bricolage Grotesque", "Inter"),
                    page_section(b, card, ambient="aurora", brand="Lumen", note="No spam. One email when we open."), heading_weight=700, radius="14px")


def event() -> dict:
    b = Builder("event-invite")
    c = palette("#0c1d17", "#f0fdf6", "#10b981", "#fbbf24", secondary="#123326", surface="#10281f")
    details = b.row(b.p("12–13 May 2027", False, font_weight="600"), b.p("·", False), b.p("Ndola, Zambia", False, font_weight="600"), gap="10px")
    card = b.card(b.art("calendar", "220px"), b.h("Copperbelt Business Summit", font_size="clamp(2.1rem,5vw,3.3rem)"),
                  b.p("Two days of talks, deals and dinners with the people building the region's next decade.", max_width="46ch"), details,
                  b.countdown("2027-05-12T08:30", done="The summit has started."), b.row(b.btn("Get tickets", "#"), b.btn("Become a sponsor", "#", "secondary")), glass=DARK_GLASS)
    return document(b, "Copperbelt Business Summit", "Event: Invitation", "An event invitation: a ticking calendar, the date and venue, a countdown and tickets.", c, ("Fraunces", "Figtree"),
                    page_section(b, card, ambient="aurora", brand="CBS 2027", note="Early-bird tickets end 1 March"), heading_weight=600)


def restaurant() -> dict:
    b = Builder("restaurant-opening")
    c = palette("#1f140d", "#fbf3ea", "#e0793a", "#f2c46d", secondary="#2c1d13", surface="#2a1b11")
    card = b.card(b.art("pan", "230px"), b.h("Kalulu Kitchen opens soon.", font_size="clamp(2.1rem,5vw,3.3rem)"),
                  b.p("Charcoal grills, village chicken and the best nshima in town. Tables for the opening weekend are going fast.", max_width="44ch"),
                  b.countdown("2027-02-26T18:00", done="We are open. Come hungry."), b.row(b.btn("Book a table", "tel:+000000000000"), b.btn("See the menu", "#", "secondary")), glass=DARK_GLASS)
    return document(b, "Kalulu Kitchen", "Restaurant: Opening", "A restaurant opening page: a sizzling pan, a countdown to the first night and table bookings.", c, ("DM Serif Display", "DM Sans"),
                    page_section(b, card, photo=("food", "linear-gradient(180deg,rgba(24,14,8,.66),rgba(24,14,8,.9))"), brand="Kalulu Kitchen", note="Open Thursday to Sunday"),
                    heading_weight=400, radius="12px")


def links() -> dict:
    b = Builder("photographer-links")
    c = palette("#0d0d0d", "#f5f5f4", "#f5f5f4", "#fb923c", secondary="#1c1917", surface="#171615")
    buttons = [b.btn(label, href, "primary" if i == 0 else "secondary", width="100%", justify_content="center") for i, (label, href) in enumerate(
        (("See the portfolio", "#"), ("Book a shoot", "mailto:book@chandastudio.example"), ("Prints and frames", "#"), ("Instagram", "https://instagram.com/")))]
    card = b.card(b.art("camera", "190px"), b.h("Chanda Studio", font_size="clamp(2rem,5vw,2.8rem)"),
                  b.p("Portraits, weddings and brands, photographed in natural light.", max_width="36ch"),
                  b.box(*buttons, width="100%", max_width="380px", gap="10px"), glass=DARK_GLASS)
    return document(b, "Chanda Studio", "Photography: Link in bio", "A link-in-bio page for a photographer: a flashing camera and every link in one glass card.", c, ("Syne", "Figtree"),
                    page_section(b, card, ambient="stars", note="Lusaka · Available worldwide"), heading_weight=700, radius="14px", button_radius="14px")


def clinic() -> dict:
    b = Builder("clinic-opening")
    c = palette("#f3f8fb", "#0f2a3d", "#0e7490", "#ef4444", surface="#e6f1f6")
    card = b.card(b.art("heartbeat", "240px"), b.h("Riverside Family Clinic opens its doors.", font_size="clamp(2rem,4.6vw,2.9rem)"),
                  b.p("Family doctors, a pharmacy and a laboratory under one roof. Register now and your first visit is free.", max_width="46ch"),
                  b.countdown("2027-03-15T07:30", done="We are open. Walk-ins welcome."), b.row(b.btn("Call to register", "tel:+000000000000"), b.btn("Find us", "#", "secondary")),
                  glass=LIGHT_GLASS)
    return document(b, "Riverside Family Clinic", "Healthcare: Opening", "A bright clinic opening page: a live heartbeat, a countdown and registration by phone.", c, ("Plus Jakarta Sans", "Inter"),
                    page_section(b, card, ambient="waves", brand="Riverside Family Clinic", note="Open every day, 07:30 to 20:00"), heading_weight=700, radius="16px")


def ngo() -> dict:
    b = Builder("ngo-campaign")
    c = palette("#fbf7f0", "#2b2118", "#b45309", "#15803d", surface="#f3ebdd")
    card = b.card(b.art("community", "230px"), b.h("Help us build 12 classrooms.", font_size="clamp(2rem,4.8vw,3rem)"),
                  b.p("Every gift buys bricks, desks and books for children in Chingola. We are almost there.", max_width="44ch"),
                  b.progress("value", 64, "$32,000 of $50,000 raised"), b.row(b.btn("Donate now", "#"), b.btn("Volunteer", "#", "secondary")), glass=LIGHT_GLASS)
    return document(b, "Tiyende Trust", "NGO: Fundraising campaign", "A fundraising page: a community that moves, a real progress bar and two ways to help.", c, ("Lora", "Work Sans"),
                    page_section(b, card, ambient="aurora", brand="Tiyende Trust", note="Registered charity. Every gift is receipted."), heading_weight=600)


def energy() -> dict:
    b = Builder("energy-solar")
    c = palette("#071a10", "#ecfdf3", "#22c55e", "#facc15", secondary="#0d2c1b", surface="#0b2416")
    card = b.card(b.art("solar", "250px"), b.h("Power that pays for itself.", font_size="clamp(2.1rem,5vw,3.3rem)"),
                  b.p("Sunwise designs and installs solar for homes, farms and factories. Our new site launches with instant quotes.", max_width="46ch"),
                  b.countdown("2027-01-31T10:00", done="Instant quotes are live."), b.form("Email for an early quote", "Notify me"), glass=DARK_GLASS)
    return document(b, "Sunwise Energy", "Energy: Coming soon", "A solar energy launch page: turning sun rays, a live countdown and early quote sign-up.", c, ("Archivo", "Inter"),
                    page_section(b, card, ambient="aurora", brand="Sunwise Energy", note="Homes · Farms · Industry"), heading_weight=800, radius="10px")


def mining() -> dict:
    b = Builder("mining-maintenance")
    c = palette("#17130f", "#f7f2ea", "#c2410c", "#eab308", secondary="#241d17", surface="#211a14")
    card = b.card(b.art("mine", "240px"), b.h("Scheduled maintenance.", font_size="clamp(2rem,5vw,3rem)"),
                  b.p("Kafue Minerals' portal is being upgraded. Supplier and contractor services return shortly. Site operations are not affected.", max_width="48ch"),
                  b.progress(), b.p("Urgent site matters: +000 000 000 000", False, font_size=".95rem"), glass=DARK_GLASS)
    return document(b, "Kafue Minerals", "Mining: Maintenance", "A mining company maintenance page: a working headframe, a loading bar and an urgent contact.", c, ("Space Grotesk", "Work Sans"),
                    page_section(b, card, photo=("landscape", "linear-gradient(180deg,rgba(18,14,10,.7),rgba(18,14,10,.9))"), brand="Kafue Minerals", note="Safety first, always"),
                    heading_weight=600, radius="6px", button_radius="6px")


def fashion() -> dict:
    b = Builder("fashion-drop")
    c = palette("#0a0a0a", "#fafaf9", "#fafaf9", "#d4a373", secondary="#1a1a1a", surface="#141414")
    card = b.card(b.art("hanger", "200px"), b.p("Drop 04", False, letter_spacing="0.24em", text_transform="uppercase", font_size=".8rem"),
                  b.h("Maison Zuri", font_size="clamp(2.6rem,7vw,4.6rem)", font_style="italic"),
                  b.p("Hand-finished linen and chitenge silk. Fourteen pieces, made once.", max_width="40ch"),
                  b.countdown("2027-03-05T19:00", done="The drop is live."), b.form("Email for first access", "Get first access"), glass=DARK_GLASS, radius="2px")
    return document(b, "Maison Zuri", "Fashion: Collection drop", "A fashion drop page: a swinging garment, twinkling stars, a countdown and first access.", c, ("Bodoni Moda", "Jost"),
                    page_section(b, card, ambient="stars", note="Lusaka · Paris"), heading_weight=500, radius="2px", button_radius="2px")


BUILDERS = (maintenance, ict, security, music, construction, saas, event, restaurant, links, clinic, ngo, energy, mining, fashion)


def build_onepage(out: Path = OUT) -> int:
    folder = out / CATEGORY[0]
    for file in folder.glob("*/template.json"):
        file.unlink()
    for make in BUILDERS:
        doc = make()
        problems = validate_document(doc)
        if problems:
            raise SystemExit(f"{doc['meta']['id']}: {problems[:3]}")
        target = out / doc["meta"]["id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "template.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    categories = json.loads((out / "categories.json").read_text(encoding="utf-8"))
    if not any(c["id"] == CATEGORY[0] for c in categories):
        categories.append({"id": CATEGORY[0], "name": CATEGORY[1]})
        (out / "categories.json").write_text(json.dumps(categories, indent=1), encoding="utf-8")
    print(f"built {len(BUILDERS)} one-page templates")
    return len(BUILDERS)


if __name__ == "__main__":
    build_onepage()
