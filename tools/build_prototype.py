"""Builds the five-page Mulusa Innovations sample through the editor's own commands.

Every change goes through Session, the same calls the editor's buttons make, and the exporter
knows nothing about this site. All text is sample copy, marked as such. Run: python tools/build_prototype.py [folder]
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw
from PySide6.QtCore import QCoreApplication

from mulusa_theme_studio.core.document import find_node, find_page, walk_nodes
from mulusa_theme_studio.core.settings import Settings
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.ui.session import Session

NOTE = "Sample content: replace before publishing"
EMAIL = "hello@example.com"


def art(path: Path, a: str, b: str, seed: int, size=(1600, 1100)) -> Path:
    """A plain generated picture, so the sample uses real image files without borrowing anyone's photos."""
    image = Image.new("RGB", size, a)
    draw = ImageDraw.Draw(image)
    w, h = size
    for y in range(h):
        mix = y / h
        draw.line((0, y, w, y), fill=tuple(int(int(a[i:i + 2], 16) * (1 - mix) + int(b[i:i + 2], 16) * mix) for i in (1, 3, 5)))
    for index in range(7):
        x = (seed * 211 + index * 263) % w
        y = (seed * 137 + index * 173) % h
        r = 90 + (seed * 53 + index * 71) % 230
        draw.ellipse((x - r, y - r, x + r, y + r), outline="#ffffff", width=3)
    image.save(path, quality=92)
    return path


def logo(path: Path) -> Path:
    image = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 156, 156), 32, fill="#16325c")
    draw.line(((38, 118), (38, 44), (80, 92), (122, 44), (122, 118)), fill="#ffffff", width=14, joint="curve")
    image.save(path)
    return path


class Builder:
    def __init__(self, session: Session) -> None:
        self.s = session

    @property
    def doc(self):
        return self.s.document

    def in_page(self, page_id: str):
        return list(walk_nodes(find_page(self.doc, page_id)["nodes"]))

    def section(self, page_id: str, role: str) -> dict:
        return next(n for n in find_page(self.doc, page_id)["nodes"] if n.get("props", {}).get("role") == role)

    def delete(self, node: dict) -> None:
        self.s.select(node["id"])
        self.s.delete_selected()

    def texts(self, page_id: str, changes: dict[str, str]) -> None:
        nodes = self.in_page(page_id)
        for old, new in changes.items():
            hits = [n for n in nodes if n.get("props", {}).get("text") == old or n.get("props", {}).get("label") == old]
            assert hits, old
            for node in hits:
                self.s.edit_prop(node["id"], "text" if node["props"].get("text") == old else "label", new)
                self.s.end_gesture()


def build(parent: Path) -> Path:
    settings = Settings.load()
    settings.author = "Mulusa Innovations"
    session = Session(settings, TemplateLibrary())
    project = session.create_project("Mulusa Innovations", "corporate/corporate-classic", parent)
    b = Builder(session)

    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        pictures = {name: art(folder / f"{name}.jpg", a, c, seed) for name, a, c, seed in (
            ("hero", "#16325c", "#b58a3c", 3), ("about", "#20406f", "#5f7fa8", 5), ("strategy", "#16325c", "#3f6aa0", 7),
            ("systems", "#2c3e50", "#b58a3c", 11), ("support", "#3a5a78", "#8aa4bd", 13),
        )}
        pictures["logo"] = logo(folder / "mulusa-logo.png")
        assets = {path.stem: session.upload_media([path])[0]["id"] for path in pictures.values()}

    # Pages: five, in the owner's order.
    insights = find_page(b.doc, "blog")
    session.set_page(insights["id"])
    session.delete_page(insights["id"])
    projects = "portfolio"
    session.rename_page(projects, "Projects")
    session.set_page_slug(projects, "projects")
    session.set_page_details("home", description="Sample site for Mulusa Innovations, built with Mulusa Theme Studio.")
    session.set_page_details(projects, description="Sample project stories, published as WordPress posts.")

    # Shared header and menu.
    header = b.doc["site"]["header"]["id"]
    session.edit_prop(header, "brand", "Mulusa Innovations")
    session.set_node_media(header, assets["mulusa-logo"], "logo")
    session.edit_prop(header, "cta", {"label": "Contact us", "href": {"page": "contact"}})
    session.edit_prop(header, "sticky", True)
    for item in list(b.doc["navigation"]["primary"]):
        if item.get("page") == projects:
            session.update_nav_item(item["id"], label="Projects")
    home_item = session.add_nav_item("Home", {"page": "home"})
    for _ in range(len(b.doc["navigation"]["primary"]) - 1):
        session.move_nav_item(home_item, -1)

    # Home: static sections, with live posts between them.
    session.set_page("home")
    b.delete(b.section("home", "statistics"))
    b.delete(b.section("home", "testimonials"))
    blog = b.section("home", "blog")
    index = find_page(b.doc, "home")["nodes"].index(blog)
    b.delete(blog)
    session.insert_component("latest-posts", "page:home", index)
    b.texts("home", {
        "Advisory since 2004": NOTE, "Sound advice for decisions that matter": "Practical digital tools for real work",
        "A partner-led advisory firm helping established organisations plan, grow and manage risk.": "This is sample copy for Mulusa Innovations. It shows how a homepage reads, and makes no claim about clients or results.",
        "Book a consultation": "See our projects", "Our services": "Our services",
        "Services shaped around your organisation": "Three kinds of work", "Strategy advisory": "Planning",
        "Clear direction for growth, new markets and major decisions.": "Sample text describing how a project is planned.",
        "Risk and compliance": "Building", "Practical frameworks that protect the business without slowing it down.": "Sample text describing how software is built.",
        "Financial planning": "Support", "Forecasting and capital planning your board can rely on.": "Sample text describing how work is looked after.",
        "Built on long relationships and straight answers": "A short introduction",
        "Latest posts": "Latest projects", "Ready for a clearer way forward?": "Have something to build?", "Start a conversation": "Get in touch",
    })
    texts = [n for n in b.in_page("home") if n["type"] == "text" and n["props"]["text"].startswith(("For two decades", "Our advisers"))]
    session.edit_prop(texts[0]["id"], "text", "Sample paragraph. Replace it with a real introduction to the company and what it does.")
    b.delete(texts[1])
    hero_buttons = [n for n in b.in_page("home") if n["type"] == "button"]
    session.edit_prop(hero_buttons[0]["id"], "href", {"page": projects})
    session.edit_prop(hero_buttons[1]["id"], "href", {"page": "services"})
    images = [n for n in b.in_page("home") if n["type"] == "image"]
    session.set_node_media(images[0]["id"], assets["hero"])
    session.set_node_media(images[1]["id"], assets["about"])
    query = next(n for n in b.in_page("home") if n["type"] == "query")
    session.edit_query(query["id"], count=3, columns=3, categories=["projects"], hide=["author", "categories"])

    # Device-specific design, set the way the device tabs set it.
    heading = next(n for n in b.in_page("home") if n["type"] == "heading")
    session.set_edit_scope("tablet")
    session.edit_style(heading["id"], "font_size", "3rem")
    session.set_device_columns(next(n for n in b.in_page("home") if n["type"] == "columns" and n["props"].get("columns") == 3)["id"], 3)
    session.set_edit_scope("mobile")
    session.edit_style(heading["id"], "font_size", "2.25rem")
    session.edit_style(heading["id"], "text_align", "center")
    session.set_device_hidden(images[1]["id"], True)
    session.set_viewport("desktop")
    session.set_edit_scope("")

    # About.
    session.set_page("about")
    for role in ("statistics", "team", "testimonials"):
        b.delete(b.section("about", role))
    b.texts("about", {
        "Who we are, how we work and what we stand for.": NOTE, "Built on long relationships and straight answers": "Who we are",
        "Our story": "See our projects",
    })
    for node in b.in_page("about"):
        if node["type"] == "text" and node["props"]["text"].startswith(("For two decades", "Our advisers")):
            session.edit_prop(node["id"], "text", "Sample paragraph. Replace it with the company's own story.")
        if node["type"] == "link":
            session.edit_prop(node["id"], "href", {"page": projects})
        if node["type"] == "image":
            session.set_node_media(node["id"], assets["about"])

    # Services.
    session.set_page("services")
    b.delete(b.section("services", "pricing"))
    b.texts("services", {
        "Advisory services for organisations that want lasting results.": NOTE, "Services shaped around your organisation": "Three kinds of work",
        "Strategy advisory": "Planning", "Clear direction for growth, new markets and major decisions.": "Sample text describing how a project is planned.",
        "Risk and compliance": "Building", "Practical frameworks that protect the business without slowing it down.": "Sample text describing how software is built.",
        "Financial planning": "Support", "Forecasting and capital planning your board can rely on.": "Sample text describing how work is looked after.",
        "Learn more": "Ask about this", "Ready for a clearer way forward?": "Have something to build?", "Start a conversation": "Get in touch",
    })
    for node in b.in_page("services"):
        if node["type"] in ("link", "button"):
            session.edit_prop(node["id"], "href", {"page": "contact"})
    for node, name in zip([n for n in b.in_page("services") if n["type"] == "image"], ("strategy", "systems", "support")):
        session.set_node_media(node["id"], assets[name])
        session.edit_prop(node["id"], "alt", f"Abstract sample picture: {name}")
    for index, node in enumerate(n for n in b.in_page("services") if n["type"] == "faq_item"):
        session.edit_prop(node["id"], "question", f"Sample question {index + 1}")
        session.edit_prop(node["id"], "answer", "Sample answer. Replace it with a real one.")

    # Projects: a dynamic list, so publishing a post adds a project.
    session.set_page(projects)
    b.delete(b.section(projects, "portfolio"))
    session.insert_component("latest-posts", f"page:{projects}", 1)
    b.texts(projects, {"Case Studies": "Projects", "A selection of recent engagements and their outcomes.": NOTE, "Latest posts": "All projects", "Ready for a clearer way forward?": "Have something to build?", "Start a conversation": "Get in touch"})
    for node in b.in_page(projects):
        if node["type"] == "button":
            session.edit_prop(node["id"], "href", {"page": "contact"})
    query = next(n for n in b.in_page(projects) if n["type"] == "query")
    session.edit_query(query["id"], count=6, columns=2, categories=["projects"], pagination=True, hide=["author"])

    # Contact. Example addresses only.
    session.set_page("contact")
    b.delete(b.section("contact", "faq"))
    b.texts("contact", {
        "Tell us about your organisation and how we can help.": NOTE, "Speak with a partner": "Get in touch",
        "Tell us what you are working on. A partner will reply within two working days.": "Sample text. The details below are examples, not real contact information.",
    })

    # Shared footer: edited once, shown everywhere.
    footer = list(walk_nodes([b.doc["site"]["footer"]]))
    for node in footer:
        props_ = node.get("props", {})
        if node["type"] == "heading" and props_.get("text") == "Halden & Partners":
            session.edit_prop(node["id"], "text", "Mulusa Innovations")
        elif node["type"] == "text" and props_.get("text", "").startswith("For two decades"):
            session.edit_prop(node["id"], "text", "Sample site. Replace this text before publishing.")
        elif node["type"] == "text" and props_.get("text", "").startswith("©"):
            session.edit_prop(node["id"], "text", "© Mulusa Innovations. Sample content.")
        elif node["type"] == "link" and props_.get("label") == "Insights":
            b.delete(node)
        elif node["type"] == "link" and props_.get("label") == "Case Studies":
            session.edit_prop(node["id"], "label", "Projects")

    # Post templates, designed like any page.
    session.open_role_page("single")
    session.open_role_page("archive")
    session.set_page("home")
    session.save()
    assert project.folder.is_dir()
    return project.folder


if __name__ == "__main__":
    app = QCoreApplication.instance() or QCoreApplication([])
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples"
    existing = target / "Mulusa Innovations"
    if existing.exists() and (existing / "project.json").is_file():
        shutil.rmtree(existing)
    target.mkdir(parents=True, exist_ok=True)
    print(build(target))
