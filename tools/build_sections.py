"""Builds the bundled section collection of the Creative Resource Library.

Every section is real, editable document content taken from the built-in templates: one for each
section design the template kit can make, plus the distinct site headers and footers. Each gets a
preview rendered in the browser engine with the design of the template it comes from.

Run after build_templates.py:   .venv/bin/python tools/build_sections.py [--no-previews]
Output: src/mulusa_theme_studio/library/sections/{index.json, <id>.json, previews/<id>.png}
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_templates  # noqa: E402  (fills build_templates.T with the template specs)
from mulusa_theme_studio.core.templates import TemplateLibrary  # noqa: E402

OUT = ROOT / "src" / "mulusa_theme_studio" / "library" / "sections"
PAGE_KEYS = ("about", "services", "portfolio", "blog", "contact")

# kit method -> (name, library category, description)
INFO = {
    "hero_split": ("Split hero", "hero", "Headline and actions beside a large image."),
    "hero_split_rev": ("Split hero, image left", "hero", "Image first, then the headline and actions."),
    "hero_bleed": ("Edge-to-edge split hero", "hero", "A split hero whose image runs to the edge of the screen."),
    "hero_center": ("Centred typographic hero", "hero", "A centred headline with no image: type does the work."),
    "hero_stacked": ("Stacked hero with wide image", "hero", "Centred headline above a wide product or scene image."),
    "hero_overlay": ("Full-screen image hero", "hero", "A full-height photograph with the headline over it."),
    "hero_overlay_center": ("Full-screen centred image hero", "hero", "A centred headline over a full-height photograph."),
    "hero_giant": ("Giant type hero", "hero", "An oversized headline that fills the width of the screen."),
    "hero_mosaic": ("Image collage hero", "hero", "Headline beside a playful collage of images."),
    "hero_poster": ("Poster hero", "hero", "Bold poster-style type over colour, for events and street brands."),
    "hero_framed": ("Framed hero card", "hero", "A photograph with the headline on a card that overlaps it."),
    "hero_lead": ("Lead story hero", "hero", "A news-style lead story with its picture."),
    "hero_search": ("Search hero", "hero", "Headline and a search-style call to action over an image."),
    "hero_stats": ("Hero with figures", "hero", "Headline beside a column of key figures."),
    "hero_marquee": ("Marquee hero", "hero", "Huge, wide type for agencies and studios."),
    "hero_cinematic": ("Cinematic hero", "hero", "A full-bleed photograph with a gradient and an oversized headline."),
    "about_split": ("About with image", "about", "Story text beside a photograph."),
    "about_split_rev": ("About with image, image left", "about", "Photograph first, then the story."),
    "about_statement": ("Statement", "about", "One large sentence that says what you stand for."),
    "about_columns": ("About in two columns", "about", "A heading and two columns of text."),
    "values_trio": ("Values, mission and vision", "about", "Three short statements side by side."),
    "photo_band": ("Photo band with statement", "media", "A full-width photograph with one line over it."),
    "services_cards": ("Service cards", "services", "Three service cards with icons."),
    "services_cards4": ("Service cards, four across", "services", "Four compact service cards."),
    "services_rows": ("Service rows", "services", "Services as a list of rows: name on the left, description on the right."),
    "services_alt": ("Alternating services", "services", "Services with images, alternating sides."),
    "services_icons": ("Services with icons", "services", "An icon grid of six services."),
    "services_bento": ("Bento services grid", "services", "A large featured service with smaller ones around it."),
    "services_index": ("Services index", "services", "A sticky heading with numbered service rows."),
    "services_panels": ("Service panels", "services", "Two image-and-text panels for the main services."),
    "catalogue": ("Full catalogue", "services", "Four columns listing everything you offer."),
    "features_check": ("Feature checklist", "features", "A checklist of benefits beside an image."),
    "process_steps": ("Process steps", "features", "Four numbered steps: how a project runs."),
    "credentials": ("Credentials", "features", "Registrations, certificates and other proof in five cells."),
    "stats_strip": ("Statistics strip", "statistics", "Four figures in a row."),
    "stats_big": ("Big statistics", "statistics", "Three very large figures with labels."),
    "stats_cards": ("Statistics cards", "statistics", "Three figures on cards."),
    "quote_single": ("Single testimonial", "testimonials", "One large quotation."),
    "quote_cards": ("Testimonial cards", "testimonials", "Three quotations on cards."),
    "quote_side": ("Testimonial with image", "testimonials", "A quotation beside a portrait."),
    "team_grid": ("Team grid", "team", "Team members with portraits in a grid."),
    "team_circles": ("Team with round portraits", "team", "Round portraits, names and roles."),
    "team_rows": ("Team list", "team", "Team members as rows of names and roles."),
    "pricing_cards": ("Pricing cards", "pricing", "Three plans on cards with features."),
    "pricing_rows": ("Price list", "pricing", "A list of items and prices."),
    "portfolio_grid3": ("Portfolio grid", "portfolio", "Three columns of projects."),
    "portfolio_grid2": ("Large portfolio grid", "portfolio", "Two columns of large project images."),
    "portfolio_mosaic": ("Portfolio mosaic", "portfolio", "Projects in a mosaic of different sizes."),
    "portfolio_rows": ("Case study rows", "portfolio", "Case studies as rows with images."),
    "portfolio_stack": ("Stacked projects", "portfolio", "Full-width projects one after another."),
    "portfolio_gallery": ("Image gallery", "portfolio", "A tight gallery of images."),
    "portfolio_wall": ("Project wall", "portfolio", "A dense wall of nine project images with captions."),
    "clients_type": ("Clients as type", "clients", "Client and partner names set as large type."),
    "blog_cards": ("Blog cards", "blog", "Recent articles on cards."),
    "blog_list": ("Blog list", "blog", "Recent articles as a list."),
    "blog_magazine": ("Magazine layout", "blog", "A lead article with smaller ones beside it."),
    "products_grid4": ("Product grid", "products", "Four products across with prices."),
    "products_grid3": ("Product grid, three across", "products", "Three larger products with prices."),
    "products_feature": ("Featured product", "products", "One product shown large with its options."),
    "events_rows": ("Event list", "events", "Dates, events and places as rows."),
    "events_cards": ("Event cards", "events", "Upcoming events on cards."),
    "video_wide": ("Wide video", "media", "A full-width video with a title."),
    "cta_band": ("Call-to-action band", "call_to_action", "A coloured band with one action."),
    "cta_center": ("Centred call to action", "call_to_action", "A centred heading and button."),
    "cta_box": ("Call-to-action box", "call_to_action", "A rounded panel with heading, text and button."),
    "cta_giant": ("Giant call to action", "call_to_action", "An oversized closing line and button."),
    "cta_image": ("Call to action over image", "call_to_action", "A closing call to action over a photograph."),
    "faq_single": ("FAQ", "faq", "Questions and answers in one column."),
    "faq_split": ("FAQ with heading", "faq", "A heading on the left and questions on the right."),
    "contact_split": ("Contact with details", "contact", "Contact details beside the form."),
    "contact_card": ("Contact card", "contact", "The form on a card."),
    "contact_image": ("Contact with image", "contact", "A form beside a photograph."),
}


def harvest(library: TemplateLibrary) -> dict[str, list[tuple[str, dict]]]:
    """kit method -> [(template id, section node)] across all templates."""
    found: dict[str, list[tuple[str, dict]]] = {}
    for spec in build_templates.T:
        tid = f"{spec['category']}/{spec['slug']}"
        doc = library.load(tid)
        pages = {p["id"]: p for p in doc["pages"]}
        plans = [("home", spec["home"], 0)] + [(k, spec["inner"][k], 1) for k in PAGE_KEYS]
        for page_id, methods, skip in plans:
            page = pages.get(page_id)
            if page is None:
                continue
            nodes = page["nodes"][skip:]
            if len(nodes) != len(methods):
                continue
            for word, node in zip(methods, nodes):
                found.setdefault(word.split("@")[0], []).append((tid, node))
    return found


def choose(found) -> list[tuple[str, str, dict]]:
    """One section per kit method, spreading the picks over as many templates as possible."""
    used: Counter[str] = Counter()
    out = []
    for method in INFO:
        options = found.get(method, [])
        if not options:
            continue
        tid, node = min(options, key=lambda o: (used[o[0]], options.index(o)))
        used[tid] += 1
        out.append((method, tid, node))
    return out


def headers_and_footers(library: TemplateLibrary):
    headers, footers = {}, {}
    for info in library.templates:
        doc = library.load(info.id)
        h = doc["site"]["header"]
        hp = h.get("props", {})
        hkey = (hp.get("layout", "classic"), bool(hp.get("overlay")), hp.get("nav_style", ""), bool(hp.get("sticky")), hp.get("tone", ""), bool(hp.get("caps")))
        headers.setdefault(hkey, (info, h))
        f = doc["site"]["footer"]
        sig = (f.get("props", {}).get("tone", ""), tuple(n["type"] for n in _walk([f]))[:14])
        footers.setdefault(sig, (info, f, hp.get("brand", "")))
    return list(headers.values()), list(footers.values())


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children", []))


HEADER_NAMES = {"classic": "Classic navigation", "split": "Split navigation", "centered": "Centred navigation", "masthead": "Masthead navigation", "minimal": "Minimal navigation"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args()
    library = TemplateLibrary()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "previews").mkdir(parents=True)
    index, renders = [], []
    for method, tid, node in choose(harvest(library)):
        name, category, description = INFO[method]
        info = library.get(tid)
        sid = method.replace("_", "-")
        (OUT / f"{sid}.json").write_text(json.dumps({"schema": "mulusa.section/1", "nodes": [node], "source_template": tid}, ensure_ascii=False), encoding="utf-8")
        index.append({"id": sid, "name": name, "kind": "section", "category": category, "description": f"{description} Shown in the {info.name} design.",
                      "tags": [category, info.category], "file": f"{sid}.json", "preview": f"previews/{sid}.png", "source_template": tid})
        renders.append(("section", sid, tid, node))
    headers, footers = headers_and_footers(library)
    seen = Counter()
    for info, h in headers:
        layout = h.get("props", {}).get("layout", "classic")
        base = HEADER_NAMES.get(layout, "Navigation")
        if h["props"].get("overlay"):
            base = "Transparent " + base[0].lower() + base[1:]
        seen[base] += 1
        name = base if seen[base] == 1 else f"{base} ({info.name})"
        sid = f"header-{info.id.replace('/', '-')}"
        (OUT / f"{sid}.json").write_text(json.dumps({"schema": "mulusa.section/1", "nodes": [h], "source_template": info.id}), encoding="utf-8")
        desc = ("Over the first section, for photo heroes. " if h["props"].get("overlay") else "") + \
               ("Stays at the top while scrolling. " if h["props"].get("sticky") else "") + f"Layout and behaviour from {info.name}; your site name and button stay. Collapses to a menu button on phones."
        index.append({"id": sid, "name": name, "kind": "header", "category": "header", "description": desc, "tags": ["navigation", layout],
                      "file": f"{sid}.json", "preview": f"previews/{sid}.png", "source_template": info.id})
        renders.append(("header", sid, info.id, h))
    for info, f, brand in footers[:10]:
        sid = f"footer-{info.id.replace('/', '-')}"
        kinds = {n["type"] for n in _walk([f])}
        name = "Multi-column footer" if sum(1 for n in _walk([f]) if n["type"] == "columns") else "Minimal footer"
        if any(n["type"] == "heading" and "vw" in str(n.get("style", {}).get("font_size", "")) for n in _walk([f])):
            name = "Wordmark footer"
        if "contact_form" in kinds:
            name = "Footer with form"
        name = f"{name} ({info.name})"
        (OUT / f"{sid}.json").write_text(json.dumps({"schema": "mulusa.section/1", "nodes": [f], "source_template": info.id, "sample_brand": brand}), encoding="utf-8")
        index.append({"id": sid, "name": name, "kind": "footer", "category": "footer", "description": f"The footer design of {info.name}. Its sample name is replaced by yours.",
                      "tags": ["footer"], "file": f"{sid}.json", "preview": f"previews/{sid}.png", "source_template": info.id, "sample_brand": brand})
        renders.append(("footer", sid, info.id, f))
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"sections: {sum(e['kind'] == 'section' for e in index)}, headers: {sum(e['kind'] == 'header' for e in index)}, footers: {sum(e['kind'] == 'footer' for e in index)}")
    if not args.no_previews:
        render_previews(library, renders)
    return 0


def render_previews(library: TemplateLibrary, renders) -> None:
    from PIL import Image
    from PySide6.QtCore import QBuffer, Qt
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    from build_thumbnails import Silent, load, run_js, wait
    from mulusa_theme_studio.render.site import write_site

    app = QApplication.instance() or QApplication(sys.argv[:1])
    view = QWebEngineView()
    view.setPage(Silent(view))
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
    view.show()
    with tempfile.TemporaryDirectory(prefix="mts-sections-") as temp:
        for i, (kind, sid, tid, node) in enumerate(renders, 1):
            doc = copy.deepcopy(library.load(tid))
            home = next(p for p in doc["pages"] if p["home"])
            others = [p for p in doc["pages"] if not p["home"] and p.get("nodes")]
            if kind == "section":
                home["nodes"] = [node]
            else:
                home["nodes"] = [home["nodes"][0]] if kind == "header" else (others[0]["nodes"][:1] if others else home["nodes"][-1:])
            out = write_site(doc, Path(temp) / sid)
            view.resize(1440, 900)
            load(view, out.pages[home["id"]])
            run_js(view, "document.body.classList.add('mts-editing');1")   # no entrance motion in previews
            wait(350)
            if kind == "section":
                rect = json.loads(run_js(view, "JSON.stringify((function(){var s=document.querySelector('main .mts-section, .mts-section');var r=s.getBoundingClientRect();return [r.top+scrollY,r.height]})())") or "[0,900]")
            elif kind == "header":
                rect = json.loads(run_js(view, "JSON.stringify((function(){var s=document.querySelector('header');var r=s.getBoundingClientRect();return [0,Math.max(r.height,90)+260]})())") or "[0,360]")
            else:
                rect = json.loads(run_js(view, "JSON.stringify((function(){var s=document.querySelector('footer');var r=s.getBoundingClientRect();return [r.top+scrollY,r.height]})())") or "[0,400]")
            top, height = int(rect[0]), max(240, min(int(rect[1]), 1400))
            view.resize(1440, top + height)
            wait(250)
            image = view.grab().toImage()
            buffer = QBuffer()
            buffer.open(QBuffer.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            pil = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGB").crop((0, top, 1440, top + height))
            pil.thumbnail((560, 560))
            pil.save(OUT / "previews" / f"{sid}.png", optimize=True)
            print(f"[{i}/{len(renders)}] {sid}", flush=True)
    view.close()


if __name__ == "__main__":
    sys.exit(main())
