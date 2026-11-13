"""Builds a proposed new website for CHITNAS Enterprises Ltd (chitnas.com), through the editor's own commands.

A second worked example of Mulusa Theme Studio for a real client, this time a redesign of a live
site. It starts from Corporate / Modern Consulting (the look chosen for Vicreations Corporate),
recoloured to the CHITNAS blue and logo red, and is changed only through Session.

Nothing is invented. Every service, partner, name and contact comes from the current chitnas.com.
Template content with no source there (statistics, testimonials, prices, case studies, sample
posts) is removed rather than reworded. The photographs are the ones on the current site; they
are small stock pictures and stand in until the client supplies its own.

    python tools/build_chitnas.py IMAGES_FOLDER [OUTPUT_FOLDER]

IMAGES_FOLDER holds the pictures downloaded from chitnas.com (names as on the site).
Tools only; the application never imports this file.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QCoreApplication

from build_vicreations import Site, pairs
from mulusa_theme_studio.core.document import walk_nodes
from mulusa_theme_studio.core.settings import Settings
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.exporters.static import StaticExporter, StaticOptions
from mulusa_theme_studio.exporters.wordpress import ExportOptions, WordPressExporter
from mulusa_theme_studio.ui.session import Session

# ---- facts from chitnas.com --------------------------------------------------------------------
COMPANY = "CHITNAS Enterprises Ltd"
BRAND = "CHITNAS"
EMAIL = "info@chitnas.com"
PHONES = "+260 955 557 879  |  +260 977 250 848"     # as in the site's Contact Us block
ADDRESS = "Plot 46, Kariba Road, Kansenshi, Ndola, Zambia"

ICT = ("Shift the burden of day-to-day IT infrastructure maintenance to our professionals. We manage applications, "
       "desktops, servers, enterprise systems, data storage, networks, security and cloud systems on a remote basis.")
CYBER = "Threat detection, security monitoring, incident analysis, firewalls and penetration testing, with computer forensics and audit when something has gone wrong."
BI = ("Business intelligence that supports the critical choices made by the people running your company, built into "
      "your existing workflow so the right information reaches the right people at the right time.")
SECURITY = ("Video surveillance (CCTV), access control, intrusion alarms, fire detection, X-ray baggage scanners, metal "
            "detectors, hydraulic gate barriers, and narcotics and explosive detection systems, powered by SECUERA.")
ENERGY = "Solar, wind and LPG gas solutions, made possible by our cooperating partner Esavior (Guangzhou) Green Energy Co., Ltd."
MINING = "Mining equipment parts, air compressor parts, valves and fittings, and thermal insulation."
MARKETING = ("Every product and service needs a marketing strategy. Once a product is launched we follow its adoption "
             "from introduction through growth, maturity and decline, and recommend strategies for each stage.")
ANALYTICS = ("We use advanced analytical techniques to analyse data and create valuable insights, for enterprises that "
             "want more from their data and a better connection with each of their customers.")
SECUERA = ("Shenzhen SECUERA Technology Co., Ltd researches, develops and manufactures security equipment and "
           "designs security systems. CHITNAS supplies and installs its products in Zambia.")
ESAVIOR = "Our renewable energy partner, Esavior (Guangzhou) Green Energy Co., Ltd, stands behind our solar, wind and LPG gas solutions."

DIVISIONS = [
    ("ICT managed services", ICT),
    ("Cyber security", "Threat detection, security monitoring, incident analysis, firewalls and penetration testing."),
    ("Business intelligence", "Data mining, data analysis, go-to-market strategy, product launch and customer value management."),
    ("Integrated security systems", "CCTV, access control, X-ray baggage and parcel scanners, hydraulic bollards and road block barriers."),
    ("Renewable energy", "Solar, wind and LPG gas, with our partner Esavior Green Energy."),
    ("Mechanical and mining parts", MINING),
]
FORENSICS = [
    ("Cyber crime investigation", "We examine physical and digital evidence to uncover what did or did not happen."),
    ("Data preservation", "Defensible methods to identify and preserve electronic data for an investigation or litigation."),
    ("Data collection", "Forensically sound collection of your data, whatever its volume, for analysis or discovery."),
    ("Data recovery", "Whether data was deleted or changed on purpose or by accident, we recover what was left behind."),
    ("Awareness training", "Information security awareness training, so your staff stop attacks before they start."),
]
CATALOGUE = [
    ("ICT managed services", ["Desktop support", "Applications", "Web development", "Servers", "Enterprise systems",
                              "Data storage", "Networks", "Cloud systems"]),
    ("Cyber security", ["Threat detection", "Security monitoring", "Incident analysis", "Firewalls", "Penetration testing",
                        "Computer forensics and audit", "Cyber crime investigation", "Data recovery", "Security awareness training"]),
    ("Data and business intelligence", ["Data mining", "Data modelling", "Data warehouse consulting", "Data migration",
                                        "Data analysis and discovery", "Data visualisation", "Cloud migration", "Digital strategy",
                                        "Go-to-market and product launch", "Customer value management"]),
    ("Security, energy and mining", ["CCTV", "Access control", "Intrusion alarms", "Fire detection", "X-ray baggage scanners",
                                     "Hydraulic bollards and barriers", "Solar, wind and LPG gas", "Mining equipment parts",
                                     "Air compressor parts", "Valves, fittings and insulation"]),
]
LIFECYCLE = [("Introduction", "We measure how the market adopts a product from launch."),
             ("Growth", "We track how fast it is taken up, and by whom."),
             ("Maturity", "We look for the customers and value still to be won."),
             ("Decline", "We recommend whether to renew, reposition or retire it.")]
TEAM = [("Sam Chanda", "Principal Consultant, Business Intelligence and Marketing"), ("Anthony Chanda", "Principal Consultant, Mining")]
MINING_DATA = ["Web data mining", "Social media data mining", "SQL data mining", "Image data mining", "Excel, Word and PDF data mining"]

# Pictures on the current site (all small; stand-ins until the client sends its own photographs).
PHOTOS = {
    "cctv": "cctv.jpg", "solar": "2019-03-18_5c8f82a78bf63_solar-panels.jpg", "mine": "Konkola-Copper-mine.jpg",
    "server": "server-slide-e1585334540285.jpg",
    "analytics": "tablet-with-analytics_chart_graph_trend-100747040-large.jpg",
}


def prepare_photos(source: Path, folder: Path) -> dict[str, Path]:
    from PIL import Image
    found = {}
    for key, name in PHOTOS.items():
        path = source / name
        if not path.is_file():
            raise SystemExit(f"{name} is missing from {source}")
        target = folder / f"chitnas-{key}.jpg"
        Image.open(path).convert("RGB").save(target, quality=86, optimize=True, progressive=True)  # re-encoded, metadata dropped
        found[key] = target
    return found


def grow(v: Site, section_id: str, count: int, copy_index: int = -1) -> None:
    """Adds repeated items to a section by duplicating one, the way the editor's Duplicate does."""
    grid = next(n for n in walk_nodes([v._node(section_id)]) if n["type"] == "columns")
    while len(grid["children"]) < count:
        v.s.select(grid["children"][copy_index]["id"])
        v.s.duplicate_selected()
        grid = next(n for n in walk_nodes([v._node(section_id)]) if n["type"] == "columns")


def grow_rows(v: Site, section_id: str, count: int) -> None:
    """Adds rows to a list made of sibling rows (each its own columns node) by duplicating the last one."""
    def rows():
        holder = next(n for n in walk_nodes([v._node(section_id)]) if any(c["type"] == "columns" for c in n.get("children", [])))
        return [c for c in holder["children"] if c["type"] == "columns"]
    while len(rows()) < count:
        v.s.select(rows()[-1]["id"])
        v.s.duplicate_selected()


def site(session: Session, parent: Path, img: dict) -> Path:
    project = session.create_project("CHITNAS", "corporate/modern-consulting", parent)
    v = Site(session)
    a = {k: session.upload_media([p])[0]["id"] for k, p in img.items()}
    v.colours(primary="#0b5f8c", on_primary="#f5f9fc", secondary="#073f5e", accent="#d8333d", on_accent="#ffffff",
              background="#f6f9fb", surface="#e8f1f7", text="#0c2233", muted="#46596a", border="#d0dce6")
    header = v.doc["site"]["header"]["id"]
    session.edit_prop(header, "brand", BRAND)
    session.edit_prop(header, "cta", {"label": "Request a quote", "href": {"page": "contact"}})

    session.set_page("home")
    hero = v.section("home", "hero")
    v.photos(hero["id"], [a["cctv"]], ["CCTV cameras installed on a building"])
    v.fill(hero["id"], ["Technology, security and energy for Zambian business",
                        "IT managed services, cyber security, business intelligence, security systems, renewable energy and mining parts, from one Ndola team.",
                        ("Request a quote", {"page": "contact"})])
    h1 = next(n for n in walk_nodes([v._node(hero["id"])]) if n["type"] == "heading")
    session.edit_style(h1["id"], "font_size", "clamp(2.2rem,4.2vw,3.7rem)")
    session.end_gesture()

    bento, panels = v.sections("home", "services")
    grow(v, bento["id"], 6, copy_index=2)
    grid = next(n for n in walk_nodes([v._node(bento["id"])]) if n["type"] == "columns")
    session.edit_style(grid["children"][-1]["id"], "grid_column", "span 3")   # the wide card closes the grid
    session.end_gesture()
    v.fill(bento["id"], ["Six divisions, one accountable team"] + pairs(DIVISIONS))
    v.art(bento["id"], ["server", "shield", "growth", "cctv", "solar", "gears"], "140px")

    v.fill(v.section("home", "credentials")["id"], ["When something goes wrong: computer forensics and audit"] + pairs(FORENSICS))
    v.ambient(v.section("home", "credentials")["id"], "grid")
    v.photos(panels["id"], [a["solar"], a["mine"]], ["Solar panels", "An open-pit copper mine"])
    v.fill(panels["id"], ["Renewable energy", ENERGY, "Solar  ·  Wind  ·  LPG gas", ("Ask about this", {"page": "contact"}),
                          "Mechanical and mining equipment", "Parts and supplies that keep mines and plants running, with a principal consultant for mining on our team.",
                          "Mining equipment parts  ·  Air compressor parts  ·  Valves and fittings  ·  Thermal insulation", ("Ask about this", {"page": "contact"})])
    band = v.section("home", "statement")
    v.background(band["id"], a["server"])
    v.fill(band["id"], ["Shift the burden of day-to-day IT maintenance to us, and get back to running your business."])
    v.drop("home", "portfolio")   # the site shows no projects yet
    process = v.section("home", "process")
    texts = ["How we follow a product in the market"]
    for step, text in LIFECYCLE:
        texts += [None, step, text]
    v.fill(process["id"], texts)
    faq = v.section("home", "faq")
    v.fill(faq["id"], ["Questions we are asked", "Can't see your question? Call or email us and a consultant will answer."])
    answers = [("Can you manage our IT without being on site?", "Yes. We look after applications, desktops, servers, storage, networks, security and cloud systems remotely."),
               ("Whose security equipment do you install?", "SECUERA's. Shenzhen SECUERA Technology designs and manufactures it, and we supply and install it in Zambia."),
               ("Who is behind your renewable energy solutions?", "Our cooperating partner, Esavior (Guangzhou) Green Energy Co., Ltd."),
               ("Where are you based?", "At Plot 46, Kariba Road, Kansenshi, in Ndola.")]
    for node, (q, ans) in zip([n for n in walk_nodes([v._node(faq["id"])]) if n["type"] == "faq_item"], answers):
        session.edit_prop(node["id"], "question", q)
        session.edit_prop(node["id"], "answer", ans)
        session.end_gesture()
    v.fill(v.section("home", "call_to_action")["id"], ["Tell us what you need", "A system to secure, a network to run, data to understand or parts to source.", ("Request a quote", {"page": "contact"})])
    v.ambient(v.section("home", "call_to_action")["id"], "aurora")

    session.set_page("about")
    v.fill(v.section("about", "page_header")["id"], ["About CHITNAS", "A Ndola company working across technology, security, energy and mining."])
    v.fill(v.section("about", "about")["id"], ["We help organisations run their technology, protect their people and property, understand their data and market their products."])
    v.fill(v.section("about", "values")["id"], ["Our security partner", SECUERA, "Our energy partner", ESAVIOR, "Our view of marketing", MARKETING])
    team = v.section("about", "team")
    v.photos(team["id"], ["-"] * 4)   # the site has only phone snapshots; no placeholders are left
    v.cards(team["id"], 2)
    grid = next(n for n in walk_nodes([v._node(team["id"])]) if n["type"] == "columns")
    session.edit_prop(grid["id"], "columns", 2)
    session.end_gesture()
    v.fill(team["id"], ["Principal consultants"] + pairs(TEAM))
    v.drop("about", "statistics")

    session.set_page("services")
    v.fill(v.section("services", "page_header")["id"], ["Services", "Six divisions, from the server room to the mine."])
    v.ambient(v.section("services", "page_header")["id"], "grid")
    rows = v.section("services", "services")
    grow_rows(v, rows["id"], 6)
    v.fill(rows["id"], ["What each division does", "ICT managed services", ICT, "Cyber security and forensics", CYBER,
                        "Business intelligence and marketing", BI + " " + ANALYTICS, "Integrated security systems", SECURITY,
                        "Renewable energy", ENERGY, "Mechanical and mining parts", MINING])
    out = ["Everything we offer", "The full list across our six divisions. Ask us about anything you do not see."]
    for heading, items in CATALOGUE:
        out += [heading] + items + ["-"] * (10 - len(items))
    v.fill(v.section("services", "catalogue")["id"], out)
    feat = v.section("services", "features")
    v.photos(feat["id"], [a["analytics"]], ["Charts on a tablet"])
    v.fill(feat["id"], ["Data mining", "We collect information from the web, social media, databases, documents and images, and prepare it for analysis."] + MINING_DATA)
    v.drop("services", "pricing")

    for page in ("portfolio", "blog"):   # no case studies or articles to publish yet
        v.remove_page(page)

    session.set_page("contact")
    v.fill(v.section("contact", "page_header")["id"], ["Contact", f"{ADDRESS}  ·  {PHONES}"])
    v.fill(v.section("contact", "contact")["id"], ["Speak with a consultant", f"Email {EMAIL} or send a message below."])

    for node in list(walk_nodes([v.doc["site"]["footer"]])):
        props = node.get("props", {})
        text = str(props.get("text") or props.get("label") or "")
        if node["type"] == "link" and text in ("Case Studies", "Insights"):
            v.delete(node["id"])
        elif node["type"] == "heading":
            session.edit_prop(node["id"], "text", BRAND)
            if "vw" in str(node.get("style", {}).get("font_size", "")):
                from template_kit import fit_text
                session.edit_style(node["id"], "font_size", fit_text(BRAND, v.doc["tokens"]["fonts"]["heading"], 12))
        elif text.startswith("©"):
            session.edit_prop(node["id"], "text", f"© {COMPANY}  ·  {ADDRESS}  ·  {EMAIL}")
    session.end_gesture()

    session.edit_design("Site details", lambda doc: doc["meta"].update(
        description="CHITNAS Enterprises Ltd, Ndola: ICT managed services, cyber security, business intelligence, security systems, renewable energy and mining parts.",
        author=COMPANY))
    session.set_page("home")
    session.save()
    return project.folder


def export(folder: Path, out: Path) -> list[str]:
    from mulusa_theme_studio.core.project import Project
    project = Project.open(folder)
    wp = WordPressExporter().export(project.document, project.folder, out, ExportOptions(theme_name=project.name, author=COMPANY))
    st = StaticExporter().export(project.document, project.folder, out, StaticOptions(site_name=project.name, form_email=EMAIL))
    lines = [f"WordPress {wp.output.name} + {wp.plugin.name if wp.plugin else 'no plugin'}; {len(wp.issues)} note(s)"]
    lines += [f"    {i.severity}: {i}" for i in wp.issues]
    lines += [f"static {st.output.name}; {len(st.issues)} note(s)"] + [f"    {i.severity}: {i}" for i in st.issues]
    return lines


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    app = QCoreApplication.instance() or QCoreApplication([])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "samples" / "CHITNAS"
    target.mkdir(parents=True, exist_ok=True)
    settings = Settings.load()
    settings.author = COMPANY
    existing = target / "CHITNAS"
    if existing.exists() and (existing / "project.json").is_file():
        shutil.rmtree(existing)
    with tempfile.TemporaryDirectory() as temp:
        folder = site(Session(settings, TemplateLibrary()), target, prepare_photos(Path(sys.argv[1]), Path(temp)))
    print("built", folder)
    print("\n".join(export(folder, target / "exports")))
