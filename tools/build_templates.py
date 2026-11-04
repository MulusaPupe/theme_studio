"""Generates the 50 built-in templates into src/mulusa_theme_studio/templates.

Run: .venv/bin/python tools/build_templates.py
Each result is a self-contained folder; the application does not use this script.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from template_kit import Kit, palette  # noqa: E402
from template_packs import CATEGORIES, DEFAULT_LABELS, PACKS  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "mulusa_theme_studio" / "templates"


def ty(weight=700, transform="none", tracking="-0.01em", line=1.1, base=17, ratio=1.3):
    return {"heading_weight": weight, "heading_transform": transform, "heading_tracking": tracking, "heading_line": line, "base": base, "ratio": ratio}


def sh(radius="8px", btn=None, style="solid", transform="none", tracking="0", size=".97rem"):
    return {"radius": radius, "button_radius": btn or radius, "button_style": style, "button_transform": transform, "button_tracking": tracking, "button_size": size}


def sp(section="96px", gap="28px", width="1180px"):
    return {"section": section, "gap": gap, "width": width}


def inner(about, services, portfolio, blog, contact):
    return {"about": about.split(), "services": services.split(), "portfolio": portfolio.split(), "blog": blog.split(), "contact": contact.split()}


T: list[dict] = []


def t(cat, slug, name, desc, brand, headline, sub, colors, fonts, type_, shape, spacing, home, inner_pages, **kw):
    T.append(dict(category=cat, slug=slug, name=name, desc=desc, brand=brand, headline=headline, sub=sub, colors=colors,
                  fonts=fonts, type=type_, shape=shape, spacing=spacing, home=home.split(), inner=inner_pages, **kw))


# CORPORATE -------------------------------------------------------------------
t("corporate", "corporate-classic", "Corporate Classic", "Trusted navy and serif headings, with a traditional split hero.",
  "Halden & Partners", "Sound advice for decisions that matter", "A partner-led advisory firm helping established organisations plan, grow and manage risk.",
  palette("#ffffff", "#14233b", "#14325c", "#b08a3e", surface="#f4f6f9"), ("Source Serif 4", "Inter"), ty(600), sh("3px"), sp(),
  "hero_split stats_strip@surface services_cards about_split_rev quote_single@primary blog_cards cta_band",
  inner("about_split stats_cards team_grid quote_single@surface", "services_alt pricing_cards faq_single cta_band", "portfolio_grid3 cta_band", "blog_list", "contact_split faq_single@surface"),
  kicker="Advisory since 2004", header={"cta": "Book a consultation"}, action="Book a consultation", action2="Our services", card="bordered", banner="tone", footer="columns", heads="left")

t("corporate", "modern-consulting", "Modern Consulting", "Bold teal, confident grotesque type and a bento services grid.",
  "Northline", "Change that actually sticks", "We work inside your teams to turn strategy into new habits, better numbers and momentum you can measure.",
  palette("#f6f8f6", "#0e2a2a", "#0b6e69", "#f2a33a", surface="#e9f0ec"), ("Bricolage Grotesque", "DM Sans"), ty(700, tracking="-0.025em", line=1.02), sh("18px", "999px"), sp("104px", "24px", "1240px"),
  "hero_stats services_bento portfolio_mosaic@surface quote_cards faq_split cta_box",
  inner("about_statement team_circles stats_cards@surface", "services_rows features_check@surface pricing_cards", "portfolio_rows quote_side@surface", "blog_cards", "contact_card"),
  kicker="Management consulting", header={"cta": "Talk to us", "rule": False}, action="Talk to us", action2="See results", card="tint", banner="plain", footer="wordmark", footer_tone="primary", display="clamp(3rem,8vw,6.6rem)", offset=1)

t("corporate", "executive-minimal", "Executive Minimal", "A quiet, narrow, largely typographic layout with wide margins.",
  "Lindqvist", "Counsel for senior leaders", "Discreet, independent guidance for chief executives and boards at moments of change.",
  palette("#fbfaf7", "#1b1b1a", "#1b1b1a", "#8c6a3f", surface="#f1eee7"), ("Cormorant Garamond", "Figtree"), ty(500, line=1.08, ratio=1.36), sh("0", style="underline"), sp("128px", "36px", "980px"),
  "hero_center@surface about_statement services_rows team_rows quote_single cta_center",
  inner("about_columns team_rows", "services_rows faq_single", "portfolio_stack", "blog_list", "contact_split"),
  kicker="", header={"layout": "minimal", "rule": False, "caps": True}, action="Arrange a conversation", action2="How we work", action2_kind="ghost", card="flat", heads="center", eyebrow="italic", banner="center", footer="simple", footer_tone="default", display="clamp(3rem,7.4vw,6rem)", offset=2, art="mono")

t("corporate", "professional-agency", "Professional Agency", "Energetic coral, large imagery and a mosaic of case studies.",
  "Foundry & Co", "Brands that make people look twice", "Strategy, design and campaigns for ambitious organisations that have outgrown playing it safe.",
  palette("#ffffff", "#1e1a2b", "#e8492f", "#2a2a72", surface="#fbf1ec"), ("Syne", "Manrope"), ty(800, tracking="-0.03em", line=1), sh("12px", "10px"), sp("100px", "22px", "1260px"),
  "hero_marquee services_cards4@surface portfolio_grid2 stats_big quote_side@surface cta_giant",
  inner("about_split_rev stats_strip@surface team_grid", "services_alt pricing_cards@surface", "portfolio_mosaic", "blog_magazine", "contact_image"),
  kicker="Creative agency", header={"cta": "Start a project"}, action="Start a project", card="shadow", banner="giant", footer="wordmark", display="clamp(2.8rem,7vw,6rem)", offset=3)

t("corporate", "corporate-dark", "Corporate Dark", "A dark, data-led identity with gold details and an overlay hero.",
  "Meridian Capital", "Long-term capital for serious builders", "We partner with management teams to create durable value across infrastructure, energy and industry.",
  palette("#0d1117", "#eef1f5", "#d4af6a", "#d4af6a", secondary="#39465a", surface="#161c25"), ("Outfit", "Inter"), ty(600, tracking="-0.015em"), sh("4px", transform="uppercase", tracking=".08em", size=".84rem"), sp("112px", "26px", "1220px"),
  "hero_overlay stats_strip@surface about_split services_icons portfolio_rows@surface quote_single cta_image",
  inner("about_statement stats_cards team_circles@surface", "services_cards pricing_rows@surface", "portfolio_rows", "blog_list", "contact_split"),
  kicker="Private investment", overlay=True, header={"caps": True, "cta": "Enquire"}, action="Enquire", action2="Our approach", card="bordered", eyebrow="rule", footer="columns", footer_tone="surface", offset=4)

# FASHION ---------------------------------------------------------------------
t("fashion", "luxury-editorial", "Luxury Editorial", "Dramatic full-page imagery, high-contrast Bodoni type and black and ivory.",
  "MAISON ORÉ", "The art of restraint", "An autumn study in line, weight and shadow. Forty-one pieces, made in small numbers.",
  palette("#f7f3ec", "#111111", "#111111", "#8d7147", surface="#ece6db"), ("Bodoni Moda", "Jost"), ty(400, "uppercase", ".02em", 1.04, 16, 1.34), sh("0", style="outline", transform="uppercase", tracking=".18em", size=".74rem"), sp("120px", "18px", "1320px"),
  "hero_overlay_center about_statement portfolio_mosaic products_feature@surface quote_single video_wide cta_image",
  inner("about_columns team_rows quote_single@surface", "pricing_rows services_icons@surface", "portfolio_stack", "blog_magazine", "contact_image"),
  kicker="Collection 09", overlay=True, header={"layout": "split", "caps": True, "cta": "Appointments"}, action="View the collection", action2="Book an appointment", card="flat", heads="center", eyebrow="caps", footer="wordmark", display="clamp(3rem,9.5vw,8.4rem)", art="mono", font_extra=[])

t("fashion", "modern-boutique", "Modern Boutique", "Warm blush tones, rounded shapes and a friendly shop-first layout.",
  "Rosewater", "Pieces you will reach for every day", "Soft tailoring and easy dresses, designed in small batches in our own studio.",
  palette("#fff8f4", "#3a2420", "#b4533e", "#2f5d50", surface="#f9e9e1"), ("Fraunces", "DM Sans"), ty(500, tracking="-0.02em", line=1.06), sh("20px", "999px"), sp("88px", "24px", "1200px"),
  "hero_split products_grid4@surface about_split services_cards4 quote_cards@surface blog_cards cta_center",
  inner("about_split_rev team_circles", "services_icons pricing_rows@surface faq_single", "portfolio_grid3", "blog_cards", "contact_card@surface"),
  kicker="New season", header={"layout": "centered", "rule": True}, action="Shop new arrivals", action2="Lookbook", card="tint", heads="center", eyebrow="italic", banner="center", footer="columns", footer_tone="primary", art="soft", offset=1)

t("fashion", "streetwear", "Streetwear", "Loud condensed type, acid accent and hard edges on black.",
  "BLOCK—09", "Drop 09 is live", "Heavyweight basics and limited graphics. When it's gone, it's gone.",
  palette("#0a0a0a", "#f2f2ee", "#d7ff3e", "#d7ff3e", secondary="#3b3b3b", surface="#161616"), ("Anton", "Space Grotesk"), ty(400, "uppercase", ".01em", .98, 16, 1.36), sh("0", transform="uppercase", tracking=".06em", size=".86rem"), sp("80px", "12px", "1400px"),
  "hero_poster@accent products_grid4 stats_strip@primary portfolio_gallery events_cards@surface cta_giant",
  inner("about_statement team_grid", "services_cards pricing_rows", "portfolio_gallery portfolio_grid3", "blog_cards", "contact_split"),
  kicker="Limited run, no restocks", header={"caps": True, "cta": "Shop drop", "tone": "default"}, action="Shop the drop", card="bordered", eyebrow="mono", banner="giant", footer="wordmark", footer_tone="accent", art="flat", giant="clamp(4.4rem,19vw,17rem)", offset=2,
  font_extra=["JetBrains Mono"], events_title="Next drops")

t("fashion", "minimal-fashion", "Minimal Fashion", "Clean white space and small type around big single garments.",
  "SOLEN", "Less, but better", "Eleven essential shapes in the finest natural fibres, available all year.",
  palette("#ffffff", "#222222", "#222222", "#7a7a72", surface="#f5f5f2"), ("Jost", "Jost"), ty(300, tracking="0", line=1.14, base=16, ratio=1.28), sh("0", style="outline", size=".84rem"), sp("116px", "20px", "1260px"),
  "hero_stacked products_grid3 about_columns@surface services_rows cta_center",
  inner("about_split team_rows", "services_rows pricing_rows", "portfolio_grid2", "blog_list", "contact_split"),
  kicker="", header={"layout": "minimal", "rule": False}, action="Shop essentials", action2="Our approach", action2_kind="ghost", card="flat", heads="left", eyebrow="none", footer="simple", footer_tone="default", display="clamp(2.6rem,5vw,4.2rem)", art="mono", offset=3)

t("fashion", "fashion-magazine", "Fashion Magazine", "A front cover masthead, a magazine grid and striking red.",
  "VERVE", "The new shape of power dressing", "Inside: the designers rewriting the suit, plus twelve looks to wear now.",
  palette("#fffefb", "#141414", "#d11f2f", "#141414", surface="#f4efe7"), ("Playfair Display", "Work Sans"), ty(800, tracking="-0.02em", line=1.03), sh("0", transform="uppercase", tracking=".12em", size=".76rem"), sp("76px", "22px", "1280px"),
  "hero_lead blog_magazine@surface portfolio_grid3 quote_single@primary products_grid4 cta_band@accent",
  inner("about_statement team_grid", "services_cards pricing_cards", "portfolio_mosaic", "blog_magazine blog_cards@surface", "contact_split"),
  kicker="The Style Issue", header={"layout": "masthead", "caps": True}, card="rule", eyebrow="rule", banner="giant", footer="columns", cta_action="Subscribe", offset=4, blog_title="This issue")

# MUSIC -----------------------------------------------------------------------
t("music", "artist-portfolio", "Artist Portfolio", "Moody violet, one big portrait and tour dates up front.",
  "Kaya Bright", "Night Transit, the new album", "Twelve songs recorded live over eleven days. Out now everywhere, and on tour this winter.",
  palette("#120d1d", "#f3eefc", "#b28dff", "#ff6fa3", secondary="#3c2a6a", surface="#1d1630"), ("Sora", "Inter"), ty(700, tracking="-0.03em", line=1), sh("10px", "999px"), sp("96px", "26px", "1160px"),
  "hero_overlay events_rows video_wide@surface portfolio_grid3 quote_single products_grid4@surface cta_center",
  inner("about_split team_circles@surface", "services_cards pricing_cards@surface", "portfolio_grid2", "blog_cards", "contact_split"),
  subject_override="portrait", kicker="Out now", overlay=True, header={"cta": "Tickets"}, action="Listen now", action2="Tour dates", card="tint", footer="wordmark", footer_tone="surface", offset=0, art="gradient", cta_action="Get tickets")

t("music", "record-label", "Record Label", "An archive look: catalogue rows, mono details and off-white paper.",
  "Copperbelt Records", "Independent since 2011", "A small label for restless artists. Thirty-eight releases, and we still press every record ourselves.",
  palette("#efece3", "#16130e", "#16130e", "#c4502c", surface="#e4dfd2"), ("Archivo", "Space Mono"), ty(800, "uppercase", "-0.02em", .98, 15, 1.34), sh("0", transform="uppercase", tracking=".06em", size=".8rem"), sp("84px", "20px", "1280px"),
  "hero_giant portfolio_rows stats_strip@primary team_rows@surface blog_list products_grid3 cta_band@accent",
  inner("about_columns team_rows", "services_rows pricing_rows", "portfolio_rows", "blog_list", "contact_split"),
  kicker="", header={"caps": True, "rule": True}, action2="Browse the catalogue", card="rule", eyebrow="mono", banner="giant", footer="columns", giant="clamp(2.7rem,10.4vw,10rem)", offset=1, art="flat", font_extra=["JetBrains Mono"], team_title="The roster")

t("music", "concert-events", "Concert and Events", "High-energy poster type in hot orange, built around the next show.",
  "AFTERGLOW FEST", "Three days. Forty acts. One field.", "Lineup out now. Early bird tickets on sale until the end of the month.",
  palette("#111014", "#fff6ea", "#ff5a1f", "#ffd23e", secondary="#3a2230", surface="#1e1b22"), ("Bebas Neue", "Figtree"), ty(400, "uppercase", ".015em", .96, 17, 1.42), sh("6px", transform="uppercase", tracking=".06em"), sp("88px", "16px", "1280px"),
  "hero_poster@primary events_rows stats_big@surface portfolio_gallery pricing_cards faq_split@surface cta_image",
  inner("about_statement stats_cards@surface", "pricing_cards faq_single@surface", "portfolio_gallery", "blog_cards", "contact_split"),
  kicker="14 to 16 August, Lake Grounds", header={"cta": "Tickets", "caps": True, "sticky": True}, action="Buy tickets", card="tint", eyebrow="caps", banner="tone", footer="wordmark", footer_tone="primary", giant="clamp(4rem,14vw,13rem)", offset=2, art="gradient", cta_action="Buy tickets", plans_title="Tickets")

t("music", "music-magazine", "Music Magazine", "Editorial serif headlines with reviews and cards in electric blue.",
  "THE LISTENING POST", "The year's best new voices, ranked", "Fifty artists, twelve critics, a lot of arguing. Here is what you should be hearing.",
  palette("#ffffff", "#101426", "#2740ff", "#ff4f64", surface="#eef0fb"), ("Newsreader", "Inter"), ty(600, tracking="-0.015em", line=1.08), sh("2px"), sp("72px", "24px", "1240px"),
  "hero_lead blog_cards@surface about_statement portfolio_grid3 video_wide@surface blog_list cta_box",
  inner("about_columns team_grid@surface", "services_cards pricing_cards", "portfolio_mosaic", "blog_magazine blog_list", "contact_split"),
  kicker="Feature", header={"layout": "masthead"}, card="flat", eyebrow="rule", banner="plain", footer="columns", offset=3, cta_action="Subscribe", statement="Serious writing about music, for people who listen to whole albums.", blog_title="Reviews and features", blog_eyebrow="Latest")

t("music", "dj-producer", "DJ and Producer", "Neon on near-black, wide type and a glowing, technical feel.",
  "DEE/LWANGA", "Sound built for the last hour", "DJ, producer and sound designer. Club, festival and studio.",
  palette("#050608", "#e9fff7", "#21f3b1", "#7a5cff", secondary="#123b34", surface="#0e1216"), ("Unbounded", "Space Grotesk"), ty(600, "uppercase", "-0.01em", 1.06, 16, 1.26), sh("0", transform="uppercase", tracking=".14em", size=".76rem"), sp("92px", "18px", "1300px"),
  "hero_center services_rows@surface events_cards portfolio_rows pricing_cards@surface cta_giant",
  inner("about_split_rev stats_strip@surface", "services_rows pricing_cards@surface", "portfolio_rows", "blog_list", "contact_split"),
  kicker="", header={"layout": "minimal", "caps": True}, action="Book a set", action2="Latest mixes", card="bordered", eyebrow="mono", banner="giant", footer="wordmark", display="clamp(2.2rem,6.4vw,5.4rem)", offset=4, art="line", font_extra=["JetBrains Mono"], cta_action="Book a set")

# ART -------------------------------------------------------------------------
t("art", "gallery-white", "Gallery White", "A white-cube gallery: pure white, tiny type, works given full space.",
  "Zanele Khoza", "Paintings and installations", "Recent work about memory and place. Solo exhibition opens this spring.",
  palette("#ffffff", "#1a1a1a", "#1a1a1a", "#6b6b6b", surface="#f6f6f6"), ("Inter", "Inter"), ty(400, tracking="-0.01em", line=1.2, base=15, ratio=1.22), sh("0", style="underline", size=".88rem"), sp("120px", "28px", "1320px"),
  "hero_stacked portfolio_stack about_columns@surface events_rows cta_center",
  inner("about_columns events_rows", "services_rows pricing_rows", "portfolio_stack portfolio_grid2", "blog_list", "contact_split"),
  kicker="", header={"layout": "minimal", "rule": False}, action="View the work", action2="Exhibitions", action2_kind="ghost", card="flat", eyebrow="none", heads="left", footer="simple", footer_tone="default", display="clamp(1.9rem,3.2vw,2.6rem)", art="soft", event_action="Details")

t("art", "illustrator-playful", "Illustrator Playful", "Bright colour-blocks, chunky type and a cheerful sketchbook feel.",
  "Pilar Draws", "Pictures that make people smile", "Editorial illustration, picture books and murals, for clients who want a little more joy.",
  palette("#fff7e0", "#21215a", "#ff5d73", "#21215a", secondary="#ffc53a", surface="#ffe9ad"), ("Bricolage Grotesque", "Figtree"), ty(800, tracking="-0.03em", line=1), sh("26px", "999px"), sp("90px", "22px", "1180px"),
  "hero_mosaic@surface portfolio_grid3 services_bento quote_cards@surface products_grid4 cta_box",
  inner("about_split team_circles", "services_icons pricing_cards@surface", "portfolio_mosaic", "blog_cards", "contact_card"),
  kicker="Hello there", header={"cta": "Commission me", "rule": False, "tone": "surface"}, action="Commission me", action2="See drawings", card="tint", eyebrow="italic", banner="tone", footer="wordmark", footer_tone="primary", art="flat", offset=1, cta_action="Say hello")

t("art", "photographer-dark", "Photographer Dark", "Black, edge-to-edge images and a quiet serif caption line.",
  "Marc Lindqvist", "Light, wherever it falls", "Portraits and landscapes, on commission and in print.",
  palette("#0b0b0b", "#ededea", "#ededea", "#b9a27c", surface="#161616"), ("EB Garamond", "Jost"), ty(400, tracking="0", line=1.14, base=17, ratio=1.32), sh("0", style="outline", size=".84rem"), sp("100px", "8px", "1400px"),
  "hero_overlay_center portfolio_gallery about_statement portfolio_grid2 quote_single@surface contact_split",
  inner("about_split events_rows@surface", "services_rows pricing_rows@surface", "portfolio_gallery portfolio_stack", "blog_list", "contact_image"),
  subject_override="landscape", work_override="landscape", kicker="", overlay=True, header={"layout": "minimal", "caps": True}, action="View portfolio", action2="Prints", card="flat", eyebrow="italic", footer="simple", footer_tone="default", display="clamp(2.8rem,7.5vw,6.4rem)", art="mono", offset=2, statement="I photograph people and places slowly, and only print what I would hang on my own wall.")

t("art", "design-studio", "Design Studio", "A Swiss grid in strict red, black and white, numbered and systematic.",
  "Studio Form", "Form follows thinking", "An independent studio for identity, books and exhibition design.",
  palette("#ffffff", "#000000", "#e4002b", "#000000", surface="#f2f2f2"), ("Archivo", "Archivo"), ty(700, tracking="-0.035em", line=.98, base=16, ratio=1.38), sh("0", size=".88rem"), sp("80px", "16px", "1400px"),
  "hero_giant services_rows portfolio_grid2 stats_strip@primary team_rows blog_list cta_band@inverse",
  inner("about_statement team_rows", "services_rows pricing_rows", "portfolio_grid2 portfolio_rows", "blog_list", "contact_split"),
  kicker="", header={"rule": True}, action2="Selected projects", card="rule", eyebrow="none", banner="giant", footer="columns", footer_tone="default", giant="clamp(3.4rem,14vw,13.5rem)", art="flat", offset=3, cta="Have a brief? We would like to read it.", team_title="Studio members")

t("art", "creative-collective", "Creative Collective", "Earthy terracotta and olive, with serif italics and a warm hand-made air.",
  "Red Earth Collective", "Made together, on purpose", "Six artists sharing one studio, one kiln and a belief in things that are made by hand.",
  palette("#f4ebdd", "#2c2118", "#a4492a", "#4f5b33", surface="#eadcc6"), ("Fraunces", "Work Sans"), ty(500, tracking="-0.02em", line=1.06, ratio=1.32), sh("4px", "999px"), sp("100px", "26px", "1220px"),
  "hero_split_rev about_statement@surface portfolio_mosaic team_circles events_cards@surface products_grid3 cta_center",
  inner("about_split_rev team_circles@surface", "services_cards pricing_cards", "portfolio_mosaic", "blog_cards", "contact_image"),
  kicker="An artist-run studio", header={"layout": "centered"}, action="Visit the studio", action2="See the work", eyebrow="italic", card="bordered", heads="center", banner="center", footer="columns", footer_tone="primary", art="soft", offset=4, team_title="The collective")

# NEWS ------------------------------------------------------------------------
t("news", "daily-broadsheet", "Daily Broadsheet", "A traditional newspaper: masthead, black rules and serif columns.",
  "The Daily Record", "Parliament passes landmark transparency bill after marathon session", "The vote, which ran past midnight, ends a two-year fight over public access to government contracts.",
  palette("#ffffff", "#111111", "#111111", "#a4161a", surface="#f5f3ee"), ("Playfair Display", "Source Serif 4"), ty(800, tracking="-0.005em", line=1.08, base=17, ratio=1.26), sh("0", size=".88rem"), sp("56px", "26px", "1240px"),
  "hero_lead blog_cards blog_list@surface stats_strip cta_band@primary",
  inner("about_columns team_rows stats_strip@surface", "pricing_cards services_icons@surface faq_single", "portfolio_rows", "blog_magazine blog_list@surface", "contact_split"),
  kicker="Breaking", header={"layout": "masthead"}, card="rule", eyebrow="caps", banner="plain", footer="columns", display="clamp(2.2rem,4.4vw,3.8rem)", art="mono", cta_action="Subscribe")

t("news", "modern-news", "Modern News", "A clean sans news site with bright blue and card-based stories.",
  "Current", "What the rate decision means for your money", "Mortgage, savings and business lending, explained clearly in five minutes.",
  palette("#f5f7fb", "#101828", "#0a58ff", "#e11d48", surface="#ffffff"), ("Plus Jakarta Sans", "Inter"), ty(800, tracking="-0.025em", line=1.08), sh("14px", "10px"), sp("64px", "20px", "1240px"),
  "hero_framed blog_cards blog_magazine@surface services_cards4 quote_cards pricing_cards@surface",
  inner("about_split team_grid", "pricing_cards faq_single@surface", "portfolio_grid3", "blog_cards blog_list@surface", "contact_card"),
  kicker="Explainer", header={"cta": "Subscribe", "sticky": True}, action="Read the story", card="shadow", banner="plain", footer="columns", footer_tone="primary", offset=1, display="clamp(2.2rem,4.6vw,3.8rem)", services_title="Ways to stay informed")

t("news", "longform-journal", "Longform Journal", "Calm and bookish, in a single narrow column for reading at length.",
  "The Long View", "The town that decided to stop waiting", "When the factory closed, nobody came to help. So they built their own economy, one co-op at a time.",
  palette("#faf6ee", "#26221b", "#7b2d26", "#44614f", surface="#f1eadb"), ("Newsreader", "Newsreader"), ty(500, tracking="-0.012em", line=1.12, base=19, ratio=1.3), sh("2px", style="underline"), sp("104px", "30px", "880px"),
  "hero_center about_statement@surface portfolio_stack quote_single blog_list cta_center@surface",
  inner("about_columns team_rows@surface", "pricing_rows faq_single", "portfolio_stack", "blog_list", "contact_card"),
  kicker="Issue 41, Long read", header={"layout": "centered", "rule": True}, action="Read the essay", action2="This issue", action2_kind="ghost", card="flat", eyebrow="italic", heads="center", banner="center", footer="simple", footer_tone="default", art="soft", offset=2, display="clamp(2.6rem,6vw,5rem)", statement="One long story every week, reported for months and edited until it is right.", cta_action="Subscribe")

t("news", "tv-broadcast", "TV Broadcast", "A bold channel look, with live-red banners and video up front.",
  "ZNC 24", "Live: Regional summit opens as leaders arrive", "Watch continuing coverage and analysis from our correspondents on the ground.",
  palette("#0f1b2d", "#ffffff", "#e8112d", "#ffc400", secondary="#1b3254", surface="#172741"), ("Oswald", "Inter"), ty(600, "uppercase", ".005em", 1.04, 16, 1.32), sh("2px", transform="uppercase", tracking=".06em", size=".84rem"), sp("64px", "16px", "1300px"),
  "hero_overlay video_wide blog_cards@surface events_rows portfolio_grid3@surface cta_band",
  inner("about_split_rev team_grid@surface", "services_cards events_cards@surface", "portfolio_grid3", "blog_cards", "contact_split"),
  kicker="Live now", overlay=True, header={"cta": "Watch live", "caps": True}, action="Watch live", action2="Schedule", card="tint", eyebrow="rule", footer="columns", footer_tone="surface", offset=3, display="clamp(2.6rem,6.2vw,5.2rem)", video_title="Now on air", video_eyebrow="Live", events_title="Schedule", events_eyebrow="On air", event_action="Remind me")

t("news", "tech-newsletter", "Tech Newsletter", "A sign-up-first newsletter site with mono labels and lime accents.",
  "Signal Weekly", "The week in technology, without the noise", "One email every Friday. Read by 80,000 engineers and founders who would rather be building.",
  palette("#fdfdf8", "#15180f", "#15180f", "#5d7c0b", surface="#eef2d9"), ("Space Grotesk", "Inter"), ty(600, tracking="-0.03em", line=1.04), sh("10px", "8px"), sp("80px", "20px", "1040px"),
  "hero_stats@surface blog_list quote_cards@surface pricing_cards faq_single cta_box",
  inner("about_statement team_rows@surface", "pricing_cards faq_single@surface", "portfolio_rows", "blog_list", "contact_card"),
  kicker="Free, every Friday", header={"cta": "Subscribe"}, action="Subscribe free", action2="Read past issues", card="bordered", eyebrow="mono", banner="plain", footer="simple", footer_tone="default", art="line", offset=4, font_extra=["JetBrains Mono"], cta_action="Subscribe free", blog_title="Past issues", blog_eyebrow="Archive")

# CONSTRUCTION ----------------------------------------------------------------
t("construction", "heavy-civil", "Heavy Civil", "Hi-vis yellow on charcoal, with heavy uppercase type and project numbers.",
  "IRONBRIDGE", "We build what others call difficult", "Bridges, roads and earthworks for the projects that keep the region moving.",
  palette("#ffffff", "#17191c", "#17191c", "#ffc20e", surface="#f2f3f4"), ("Oswald", "Inter"), ty(700, "uppercase", ".005em", 1.03, 17, 1.34), sh("0", transform="uppercase", tracking=".06em", size=".86rem"), sp("92px", "22px", "1260px"),
  "hero_overlay stats_strip@accent services_cards portfolio_grid3@surface features_check quote_single@inverse cta_band@accent",
  inner("about_split stats_cards@surface team_grid", "services_alt features_check@surface pricing_rows", "portfolio_grid3 stats_strip@accent", "blog_cards", "contact_split"),
  kicker="Civil engineering contractors", overlay=True, header={"cta": "Get a quote", "caps": True}, action="Request a quote", action2="View projects", card="bordered", eyebrow="rule", footer="columns", display="clamp(3rem,8.4vw,7rem)", offset=0, cta_action="Request a quote")

t("construction", "architects-builders", "Architects and Builders", "Refined stone tones and elegant serif, with big architectural photos.",
  "Stone & Line", "Considered buildings, carefully built", "A design-and-build practice for homes and workplaces that will outlast us all.",
  palette("#f6f4ef", "#23241f", "#3e4a3a", "#a26a3f", surface="#ebe7dd"), ("Cormorant Garamond", "Manrope"), ty(500, line=1.06, ratio=1.36), sh("0", style="underline"), sp("116px", "28px", "1260px"),
  "hero_framed about_statement@surface portfolio_stack services_rows team_rows@surface cta_center",
  inner("about_columns team_rows", "services_rows faq_split@surface", "portfolio_stack", "blog_list", "contact_image"),
  subject_override="building", kicker="Design and build", header={"layout": "minimal", "caps": True, "rule": False}, action="Discuss a project", eyebrow="italic", card="flat", banner="plain", footer="simple", footer_tone="primary", art="soft", offset=1, display="clamp(2.6rem,5.6vw,4.8rem)", statement="We believe the best buildings come from architects and builders sitting at the same table, from the very first sketch.")

t("construction", "engineering-firm", "Engineering Firm", "A technical blue blueprint feel, with precise data and clear rows.",
  "Vector Engineers", "Precision at every scale", "Structural, civil and geotechnical engineering for complex projects across the region.",
  palette("#f7f9fc", "#0c2340", "#0c4a8a", "#00a3a1", surface="#e8eef6"), ("IBM Plex Sans" if False else "Work Sans", "Work Sans"), ty(600, tracking="-0.015em", line=1.1), sh("4px"), sp("96px", "24px", "1240px"),
  "hero_stats@primary services_icons portfolio_rows@surface team_grid faq_split@surface blog_cards cta_band",
  inner("about_split_rev stats_cards team_grid@surface", "services_icons pricing_cards@surface faq_split", "portfolio_rows", "blog_list", "contact_split"),
  kicker="Consulting engineers", header={"cta": "Contact an engineer"}, action="Contact an engineer", action2="Our capability", card="bordered", eyebrow="mono", banner="tone", footer="columns", footer_tone="primary", art="line", offset=2, font_extra=["JetBrains Mono"])

t("construction", "residential-builder", "Residential Builder", "Friendly green and warm white, focused on families building a home.",
  "Homestead Builders", "The home you've been picturing, built right", "Family-run home builders with fixed quotes, one point of contact and no surprises.",
  palette("#fffdf8", "#1f2c24", "#27613f", "#e38b29", surface="#eff4ec"), ("Manrope", "Manrope"), ty(800, tracking="-0.02em", line=1.08), sh("16px", "999px"), sp("88px", "24px", "1180px"),
  "hero_split services_cards@surface portfolio_grid2 stats_cards@surface quote_cards pricing_cards@surface faq_single cta_box",
  inner("about_split team_circles@surface", "services_cards pricing_cards@surface faq_single", "portfolio_grid2", "blog_cards", "contact_card"),
  subject_override="interior", work_override="interior", kicker="Family-run since 1995", header={"cta": "Free quote"}, action="Get a free quote", action2="See our homes", card="shadow", heads="center", banner="center", footer="columns", offset=3, art="soft", cta_action="Get a free quote")

t("construction", "industrial-steel", "Industrial Steel", "Dark steel, safety orange and a sharp, angular industrial feel.",
  "Foundry Steel Works", "Steel, fabricated and erected", "From shop drawings to site erection: structural steel for warehouses, plants and towers.",
  palette("#14171a", "#f1f3f4", "#ff6b1a", "#ff6b1a", secondary="#3a4047", surface="#1e2226"), ("Barlow" if False else "Archivo", "Inter"), ty(800, "uppercase", "-0.01em", 1, 16, 1.34), sh("0", transform="uppercase", tracking=".08em", size=".82rem"), sp("88px", "14px", "1320px"),
  "hero_giant stats_big portfolio_mosaic@surface services_rows products_grid3@surface cta_giant",
  inner("about_split team_rows@surface", "services_rows products_grid3@surface", "portfolio_mosaic", "blog_cards", "contact_split"),
  subject_override="crane", kicker="", header={"cta": "Get a price", "caps": True}, action2="View fabrication work", card="bordered", eyebrow="mono", banner="giant", footer="wordmark", footer_tone="primary", giant="clamp(3rem,10.5vw,10rem)", art="flat", offset=4, font_extra=["JetBrains Mono"], cta_action="Get a price")

# EDUCATION -------------------------------------------------------------------
t("education", "university-classic", "University Classic", "Heritage maroon and traditional serif for an established institution.",
  "Kingsway University", "A tradition of asking better questions", "Over fifty years of teaching, research and public service, on one historic campus.",
  palette("#ffffff", "#20161a", "#7a1b2e", "#b7913e", surface="#f7f2ec"), ("Libre Baskerville", "Source Serif 4"), ty(700, tracking="-0.012em", line=1.18, base=17, ratio=1.25), sh("2px"), sp("92px", "26px", "1220px"),
  "hero_overlay stats_strip@primary services_cards about_split@surface events_rows blog_cards cta_band",
  inner("about_columns team_grid@surface stats_cards", "services_rows pricing_rows@surface faq_single", "portfolio_grid3", "blog_cards", "contact_split"),
  kicker="Applications open", overlay=True, header={"cta": "Apply"}, action="Apply now", action2="Explore courses", card="bordered", eyebrow="caps", footer="columns", footer_tone="primary", display="clamp(2.4rem,5.6vw,4.6rem)", subject_override="building", cta_action="Apply now")

t("education", "modern-academy", "Modern Academy", "Bright indigo and rounded cards for a fresh, inclusive online school.",
  "Learnwell", "Learn something new this term", "Live classes, friendly tutors and certificates that employers respect.",
  palette("#f8f7ff", "#17163a", "#4338ca", "#f97316", surface="#ecebff"), ("Plus Jakarta Sans", "Plus Jakarta Sans"), ty(800, tracking="-0.03em", line=1.08), sh("22px", "14px"), sp("88px", "22px", "1200px"),
  "hero_split services_bento stats_cards@surface pricing_cards quote_cards@surface faq_single cta_box",
  inner("about_split_rev team_circles@surface", "services_cards4 pricing_cards@surface faq_single", "portfolio_grid3", "blog_cards", "contact_card"),
  kicker="Start this term", header={"cta": "Enrol", "rule": False}, action="Browse courses", action2="See how it works", card="shadow", heads="center", banner="center", footer="columns", footer_tone="primary", offset=1, art="soft", subject_override="portrait", cta_action="Enrol now")

t("education", "primary-school", "Primary School", "Playful, colourful and warm, with rounded shapes for young families.",
  "Sunnyfield School", "Where curious children grow", "A caring primary school with small classes, big playgrounds and a love of learning.",
  palette("#fffdf3", "#1b3a57", "#0f8a8a", "#f25f5c", secondary="#ffd25a", surface="#fff3c9"), ("Bricolage Grotesque", "Figtree"), ty(700, tracking="-0.02em", line=1.06, ratio=1.28), sh("28px", "999px"), sp("80px", "24px", "1160px"),
  "hero_mosaic@surface services_icons about_split@surface events_cards team_circles@surface faq_split cta_center",
  inner("about_split team_circles@surface", "services_icons pricing_rows@surface faq_single", "portfolio_grid3", "blog_cards", "contact_card"),
  kicker="Welcome", header={"layout": "centered", "cta": "Book a visit", "rule": False}, action="Book a visit", action2="Our school", card="tint", eyebrow="italic", heads="center", banner="tone", footer="columns", footer_tone="primary", art="flat", offset=2, subject_override="abstract", cta_action="Book a visit", team_title="Our teachers")

t("education", "professional-training", "Professional Training", "Corporate slate with sharp orange, for courses and certification.",
  "CertifyPro", "Skills your next employer will ask for", "Accredited courses in project management, finance and engineering, delivered by working experts.",
  palette("#ffffff", "#1c2733", "#1c2733", "#d9480f", surface="#f1f4f7"), ("Outfit", "DM Sans"), ty(700, tracking="-0.02em", line=1.06), sh("6px"), sp("88px", "22px", "1240px"),
  "hero_stats services_cards4@surface events_rows pricing_rows@surface quote_side faq_split@surface cta_band",
  inner("about_split_rev team_grid@surface", "services_alt pricing_rows@surface", "portfolio_grid3", "blog_list", "contact_split"),
  kicker="Accredited training", header={"cta": "View courses"}, action="View courses", action2="For employers", card="bordered", eyebrow="rule", banner="tone", banner_tone="inverse", footer="columns", offset=3, event_action="Enrol", events_title="Next course dates", events_eyebrow="Timetable")

t("education", "research-institute", "Research Institute", "A sober, academic layout in deep green, led by publications.",
  "The Zambezi Institute", "Evidence for better public decisions", "Independent research on water, energy and agriculture across Southern Africa.",
  palette("#fbfbf7", "#16211b", "#114b3a", "#8a6d1d", surface="#eef1e8"), ("Lora", "Inter"), ty(600, tracking="-0.01em", line=1.14, ratio=1.27), sh("2px", style="outline", size=".9rem"), sp("88px", "28px", "1100px"),
  "hero_giant about_columns@surface blog_list team_rows stats_strip@primary portfolio_rows@surface cta_center",
  inner("about_columns team_rows@surface", "services_rows faq_single", "portfolio_rows", "blog_list", "contact_split"),
  kicker="", header={"layout": "centered", "rule": True}, action2="Read our research", card="flat", eyebrow="caps", banner="plain", footer="simple", footer_tone="primary", art="mono", subject_override="landscape", giant="clamp(2.6rem,7.6vw,6.4rem)", offset=4, team_title="Our researchers", blog_title="Publications", blog_eyebrow="Research", work_title="Current research programmes", work_eyebrow="Programmes", cta="Read our latest annual report", cta_action="Download")

# HOSPITALITY -----------------------------------------------------------------
t("hospitality", "fine-dining", "Fine Dining", "Candlelit black and gold, with an elegant serif and a wide photo hero.",
  "Maison Kunda", "An evening to remember", "A seven-course tasting menu, drawn from the season and served without hurry.",
  palette("#0f0d0b", "#f2ebdc", "#c9a96a", "#c9a96a", secondary="#3a3024", surface="#1a1612"), ("Cormorant Garamond", "Jost"), ty(500, tracking=".005em", line=1.06, base=17, ratio=1.36), sh("0", style="outline", transform="uppercase", tracking=".2em", size=".72rem"), sp("120px", "24px", "1120px"),
  "hero_overlay_center about_statement pricing_rows@surface portfolio_gallery quote_single cta_image",
  inner("about_split_rev team_rows@surface", "pricing_rows services_cards@surface", "portfolio_gallery", "blog_cards", "contact_image"),
  kicker="Dinner, Wednesday to Sunday", overlay=True, header={"layout": "split", "caps": True, "cta": "Reserve"}, action="Reserve a table", action2="View the menu", card="flat", heads="center", eyebrow="italic", footer="simple", footer_tone="surface", display="clamp(3rem,8.4vw,7rem)", art="soft", statement="We cook only what the season gives us, and we would rather serve fewer tables well.")

t("hospitality", "rustic-bistro", "Rustic Bistro", "Warm paper and tomato red, with a chalkboard menu and handmade charm.",
  "Tomato & Vine", "Good food. Loud table. Come hungry.", "Wood-fired plates, natural wine and a menu that changes when the market does.",
  palette("#f8f0e0", "#2e2015", "#b5361c", "#2f5233", surface="#efe2c8"), ("DM Serif Display", "Lora"), ty(400, line=1.04, ratio=1.34), sh("6px"), sp("84px", "24px", "1160px"),
  "hero_split_rev pricing_rows@surface about_split events_cards@surface quote_cards portfolio_grid3 cta_band",
  inner("about_split team_circles@surface", "pricing_rows services_icons@surface", "portfolio_grid3", "blog_cards", "contact_split"),
  kicker="Open daily from noon", header={"layout": "centered"}, action="Book a table", action2="See the menu", card="bordered", eyebrow="italic", banner="center", footer="columns", footer_tone="primary", offset=1, art="soft", cta_action="Book a table")

t("hospitality", "boutique-hotel", "Boutique Hotel", "Calm sage and soft sand, with long horizontal views and room cards.",
  "The Riverhouse", "Slow down by the water", "Twelve rooms, one long table and all the time you need.",
  palette("#f6f3ec", "#232a24", "#4b6650", "#a06c47", surface="#e9e6dc"), ("Playfair Display", "Figtree"), ty(500, tracking="-0.01em", line=1.1, ratio=1.32), sh("2px", "2px", transform="uppercase", tracking=".1em", size=".78rem"), sp("108px", "26px", "1240px"),
  "hero_search products_grid3 about_split_rev@surface services_icons portfolio_gallery quote_single cta_center@surface",
  inner("about_split team_rows@surface", "services_alt pricing_rows@surface", "portfolio_gallery", "blog_cards", "contact_image"),
  subject_override="landscape", product_override="interior", work_override="interior", kicker="On the Zambezi", overlay=True, header={"layout": "classic", "caps": True, "cta": "Book"}, action="Check", card="flat", eyebrow="caps", footer="columns", footer_tone="primary", art="soft", offset=2, cta_action="Book your stay",
  pack_extra=dict(search=(("Arrive", "Choose a date"), ("Depart", "Choose a date"), ("Guests", "2 adults")), products_title="Rooms and suites", products_eyebrow="Stay", products=[("River Room", "$180", "Per night, sleeps 2"), ("Garden Suite", "$240", "Per night, sleeps 3"), ("Loft Room", "$160", "Per night, sleeps 2"), ("Family Suite", "$310", "Per night, sleeps 4"), ("The Boathouse", "$420", "Per night, sleeps 2"), ("Courtyard Room", "$140", "Per night, sleeps 2")]))

t("hospitality", "coffee-house", "Coffee House", "Coffee brown and cream, with big rounded type and a neighbourhood feel.",
  "Good Morning Coffee", "Your favourite part of the morning", "Single-origin coffee, fresh pastries and a seat by the window.",
  palette("#f7efe4", "#2a1a10", "#5a3418", "#d97c2b", surface="#efdfc9"), ("Outfit", "Figtree"), ty(700, tracking="-0.03em", line=1), sh("18px", "999px"), sp("80px", "22px", "1140px"),
  "hero_center@surface products_grid4 about_split pricing_rows@surface portfolio_grid3 contact_image",
  inner("about_split_rev team_circles", "pricing_rows services_icons@surface", "portfolio_grid3", "blog_cards", "contact_image"),
  kicker="Roasted in town", header={"layout": "classic", "cta": "Order ahead", "rule": False}, action="Order ahead", action2="Find us", card="tint", heads="center", banner="tone", footer="wordmark", footer_tone="primary", display="clamp(3rem,9vw,7.6rem)", offset=3, art="flat",
  pack_extra=dict(products_title="Beans and pastries", products_eyebrow="Fresh today", products=[("House Blend", "$14", "250 g, chocolate and cherry"), ("Ethiopia Natural", "$18", "250 g, blueberry and honey"), ("Almond Croissant", "$5", "Baked at seven"), ("Cinnamon Bun", "$4", "Warm, with icing"), ("Cold Brew", "$5", "Slow steeped"), ("Zambia Washed", "$17", "250 g, peach and tea")]))

t("hospitality", "street-food", "Street Food", "Hot chilli red and mustard, with loud type and a bold food-truck menu.",
  "BIG FLAME", "Hot. Fast. Dangerously good.", "Charcoal grills, secret sauces and the queue that's worth it. Find us at the market every weekend.",
  palette("#fff4d6", "#1d0f07", "#d72c16", "#1d0f07", secondary="#f3a712", surface="#ffdf85"), ("Anton", "DM Sans"), ty(400, "uppercase", ".01em", 1, 17, 1.36), sh("10px", transform="uppercase", tracking=".05em", size=".88rem"), sp("72px", "18px", "1180px"),
  "hero_poster@primary pricing_rows events_rows@surface portfolio_gallery quote_cards@surface cta_giant",
  inner("about_statement team_grid@surface", "pricing_rows faq_split@surface", "portfolio_gallery", "blog_cards", "contact_split"),
  kicker="Saturdays at Old Market Square", header={"cta": "Find the truck", "caps": True, "rule": False}, action="See the menu", card="bordered", eyebrow="none", banner="tone", footer="wordmark", footer_tone="accent", art="flat", giant="clamp(3.6rem,13vw,12rem)", offset=4, event_action="Directions", events_title="Where to find us", cta_action="Order now", cta="Hungry yet?")

# TECHNOLOGY ------------------------------------------------------------------
t("technology", "saas-launch", "SaaS Launch", "A clean product launch with soft gradients, wide image and pricing.",
  "Flowbase", "Automate the work nobody wants to do", "Connect your tools, build workflows in minutes and give your team its time back.",
  palette("#ffffff", "#0f172a", "#4f46e5", "#06b6d4", surface="#f3f4fd"), ("Manrope", "Inter"), ty(800, tracking="-0.035em", line=1.04), sh("14px", "10px"), sp("96px", "24px", "1180px"),
  "hero_stacked stats_strip services_bento@surface quote_cards pricing_cards@surface faq_single cta_box",
  inner("about_split team_grid@surface", "services_alt features_check@surface pricing_cards", "portfolio_grid3 quote_cards@surface", "blog_cards", "contact_card"),
  kicker="New: workflow templates", header={"cta": "Start free", "sticky": True}, action="Start for free", action2="Watch demo", card="shadow", heads="center", banner="center", footer="columns", offset=0, art="gradient")

t("technology", "developer-tools", "Developer Tools", "Terminal-dark with monospace type, and a green that's easy on engineers.",
  "stackline", "Ship infrastructure like you ship code", "Declarative, typed and fast. Everything your platform needs, one command away.",
  palette("#0b0f0c", "#dcfce7", "#4ade80", "#4ade80", secondary="#14532d", surface="#121813"), ("JetBrains Mono", "Inter"), ty(600, tracking="-0.03em", line=1.1, base=16, ratio=1.26), sh("6px"), sp("88px", "16px", "1160px"),
  "hero_split services_icons@surface stats_strip portfolio_rows blog_list@surface pricing_cards cta_band@surface",
  inner("about_statement team_rows@surface", "services_cards4 pricing_cards@surface faq_single", "portfolio_rows", "blog_list", "contact_split"),
  kicker="v4.2 released", header={"cta": "Get started"}, action="Read the docs", action2="View on GitHub", card="bordered", eyebrow="mono", banner="plain", footer="simple", footer_tone="surface", art="line", offset=1, display="clamp(2.2rem,5vw,4rem)")

t("technology", "ai-startup", "AI Startup", "Deep space with iridescent pink and blue, and a big centred promise.",
  "Lumen AI", "Understand everything your business knows", "Ask questions in plain language and get answers from all of your documents, with sources.",
  palette("#08091a", "#f4f4ff", "#a78bfa", "#f472b6", secondary="#22d3ee", surface="#12142d"), ("Sora", "Manrope"), ty(600, tracking="-0.035em", line=1.04), sh("18px", "999px"), sp("112px", "22px", "1180px"),
  "hero_center video_wide@surface services_cards quote_side@surface stats_cards faq_split@surface cta_center",
  inner("about_statement team_circles@surface", "services_alt pricing_cards@surface", "portfolio_grid2", "blog_cards", "contact_card"),
  kicker="Now in public beta", header={"cta": "Request access", "rule": False}, action="Request access", action2="See it work", card="tint", heads="center", banner="center", footer="wordmark", footer_tone="surface", art="gradient", offset=2, display="clamp(3rem,8vw,6.6rem)", cta_action="Request access")

t("technology", "it-services", "IT Services", "Dependable blue and white, for managed services to local businesses.",
  "Orbit IT", "IT support that picks up the phone", "Managed IT, cybersecurity and cloud for growing businesses, for one fixed monthly price.",
  palette("#ffffff", "#10243e", "#0369a1", "#16a34a", surface="#eff6fb"), ("Figtree", "Figtree"), ty(700, tracking="-0.02em", line=1.1), sh("10px", "8px"), sp("84px", "24px", "1200px"),
  "hero_split_rev services_cards4 stats_strip@primary about_split@surface pricing_cards quote_cards@surface faq_split cta_band",
  inner("about_split_rev stats_cards@surface team_grid", "services_alt pricing_cards@surface faq_split", "portfolio_grid3", "blog_cards", "contact_split"),
  kicker="24/7 managed support", header={"cta": "Get a quote"}, action="Get a quote", action2="Our services", card="bordered", eyebrow="caps", banner="tone", footer="columns", offset=3, cta_action="Get a quote")

t("technology", "hardware-product", "Hardware Product", "An Apple-style reveal, with vast black, huge type and one product.",
  "VOLT ONE", "Power, redefined.", "A portable battery with the output of a wall socket, and the size of a paperback.",
  palette("#000000", "#f5f5f7", "#2997ff", "#2997ff", secondary="#1d1d1f", surface="#111113"), ("Inter", "Inter"), ty(700, tracking="-0.04em", line=1.02, ratio=1.32), sh("999px"), sp("140px", "20px", "1080px"),
  "hero_stacked stats_big video_wide@surface services_alt products_feature@surface faq_single cta_giant",
  inner("about_statement team_rows@surface", "services_alt pricing_cards@surface", "portfolio_grid2", "blog_cards", "contact_card"),
  kicker="", header={"layout": "minimal", "rule": False, "cta": "Pre-order"}, action="Pre-order", action2="Watch the film", action2_kind="ghost", card="flat", heads="center", eyebrow="none", banner="center", footer="simple", footer_tone="surface", art="gradient", offset=4, display="clamp(3.4rem,10vw,8rem)", product_override="circuit", cta_action="Pre-order", cta="Order yours.",
  pack_extra=dict(products_title="Choose your power", products=[("Volt One", "$299", "1,000 Wh"), ("Volt One Max", "$449", "2,000 Wh"), ("Solar Panel", "$189", "200 W"), ("Car Charger", "$39", "12 V"), ("Carry Case", "$49", "Weatherproof"), ("Wall Mount", "$29", "Steel")]))

# REAL ESTATE -----------------------------------------------------------------
t("real_estate", "luxury-estates", "Luxury Estates", "Deep green and brass, with grand serif and full-screen property imagery.",
  "Siame & Grand", "Exceptional homes, discreetly sold", "A private collection of the region's finest estates, shown by appointment.",
  palette("#f7f5ee", "#101f1a", "#12372a", "#a07f3c", surface="#ebe8dc"), ("Bodoni Moda", "Figtree"), ty(500, tracking="0", line=1.08, ratio=1.32), sh("0", transform="uppercase", tracking=".14em", size=".76rem"), sp("116px", "26px", "1280px"),
  "hero_overlay_center products_feature about_split_rev@surface portfolio_stack team_circles quote_single@primary cta_image",
  inner("about_split team_circles@surface", "services_rows pricing_rows@surface", "portfolio_stack", "blog_list", "contact_image"),
  kicker="By private appointment", overlay=True, header={"layout": "split", "caps": True, "cta": "Enquire"}, action="View the collection", action2="Sell with us", card="flat", heads="center", eyebrow="italic", footer="columns", footer_tone="primary", art="soft", display="clamp(2.8rem,7.4vw,6.2rem)", subject_override="interior")

t("real_estate", "city-agency", "City Agency", "A practical blue agency site, led by a property search bar.",
  "Metro Homes", "Find your next home", "Thousands of homes to buy and rent, with local agents to help you every step of the way.",
  palette("#ffffff", "#132238", "#1d4ed8", "#f59e0b", surface="#f1f5fb"), ("Plus Jakarta Sans", "Inter"), ty(800, tracking="-0.025em", line=1.08), sh("12px", "10px"), sp("80px", "22px", "1240px"),
  "hero_search products_grid3 services_cards@surface stats_strip quote_cards@surface blog_cards cta_band",
  inner("about_split team_grid@surface stats_cards", "services_cards pricing_cards@surface faq_single", "products_grid3 portfolio_grid3@surface", "blog_cards", "contact_split"),
  kicker="Search homes", overlay=True, header={"cta": "List your home"}, action="Search", card="shadow", footer="columns", offset=1, art="gradient", subject_override="building", cta_action="Book a valuation")

t("real_estate", "modern-architecture", "Modern Architecture", "A stark concrete-grey look with mono details and floor-plan precision.",
  "PLOT/1", "Architect-designed homes for sale", "A curated listing of the most interesting buildings on the market.",
  palette("#e9e8e4", "#141414", "#141414", "#c1401f", surface="#dddbd5"), ("Space Grotesk", "Space Grotesk"), ty(500, tracking="-0.03em", line=1.02, base=16, ratio=1.32), sh("0", size=".88rem"), sp("88px", "14px", "1340px"),
  "hero_giant products_grid3 about_statement@surface portfolio_rows blog_list@surface cta_band@accent",
  inner("about_columns team_rows@surface", "services_rows pricing_rows", "portfolio_rows", "blog_list", "contact_split"),
  subject_override="building", kicker="", header={"caps": True}, action2="All listings", card="rule", eyebrow="mono", banner="giant", footer="wordmark", art="mono", giant="clamp(3rem,10.5vw,10rem)", offset=2, font_extra=["JetBrains Mono"], statement="We only list buildings we would want to live in. Every home is visited, photographed and written about by us.", product_override="building")

t("real_estate", "family-homes", "Family Homes", "Warm, friendly terracotta and soft cream, for a neighbourhood agent.",
  "Hearth & Home", "Helping families find their place", "Local agents who know the schools, the parks and which streets get the morning sun.",
  palette("#fffaf3", "#33241b", "#bf5a2c", "#3a6b5d", surface="#fbecdc"), ("Fraunces", "Figtree"), ty(600, tracking="-0.02em", line=1.08), sh("20px", "14px"), sp("84px", "24px", "1160px"),
  "hero_split products_grid3@surface services_icons team_circles@surface quote_cards faq_single@surface cta_box",
  inner("about_split team_circles@surface", "services_icons pricing_rows@surface faq_single", "products_grid3", "blog_cards", "contact_card"),
  kicker="Your local agents", header={"cta": "Free valuation", "rule": False}, action="Browse homes", action2="Free valuation", card="tint", heads="center", eyebrow="italic", banner="center", footer="columns", footer_tone="primary", art="soft", offset=3, cta_action="Book a valuation")

t("real_estate", "property-developer", "Property Developer", "Sleek navy and copper, selling one new development off-plan.",
  "The Meridian Residences", "Life on the 24th floor", "Forty-eight new residences above the city, with sky gardens and a private club. Completing next year.",
  palette("#0e1726", "#f4efe7", "#c98a5a", "#c98a5a", secondary="#2b3a52", surface="#172236"), ("Outfit", "Manrope"), ty(500, tracking="-0.02em", line=1.04), sh("4px", "4px", transform="uppercase", tracking=".1em", size=".78rem"), sp("112px", "24px", "1260px"),
  "hero_bleed stats_strip@surface services_alt portfolio_gallery pricing_cards@surface video_wide cta_image",
  inner("about_split_rev stats_cards@surface team_grid", "services_alt pricing_cards@surface faq_split", "portfolio_gallery", "blog_cards", "contact_image"),
  subject_override="building", kicker="Now selling off-plan", header={"cta": "Register interest", "caps": True, "rule": False}, action="Register interest", action2="Floor plans", card="bordered", eyebrow="rule", banner="image", footer="columns", footer_tone="surface", art="gradient", offset=4, cta_action="Register interest", services_title_override="Designed around the way you live",
  pack_extra=dict(plans_title="Residences", plans_eyebrow="Availability", plans=[("One bedroom", "From $210k", "62 to 78 m²", ["City views", "Private balcony", "One parking bay"]), ("Two bedroom", "From $340k", "96 to 118 m²", ["Corner aspect", "Two bathrooms", "Two parking bays"]), ("Penthouse", "From $880k", "240 m²", ["Private terrace", "Sky garden", "Concierge"]), ("Studio", "From $150k", "44 m²", []), ("Garden suite", "From $290k", "88 m²", []), ("Sky villa", "From $640k", "180 m²", [])]))


def build_all() -> int:
    names = dict(CATEGORIES)
    kept = {"categories.json"}
    if OUT.exists():
        for child in OUT.iterdir():
            if child.is_dir() and child.name != "__pycache__":
                # Only remove generated template.json files; thumbnails are refreshed separately.
                for file in child.glob("*/template.json"):
                    file.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "categories.json").write_text(json.dumps([{"id": i, "name": n} for i, n in CATEGORIES], indent=1), encoding="utf-8")
    for spec in T:
        pack = dict(PACKS[spec["category"]])
        pack.update(spec.get("pack_extra", {}))
        if spec.get("subject_override"):
            pack["subject"] = spec["subject_override"]
        if spec.get("work_override"):
            pack["work_subject"] = spec["work_override"]
        if spec.get("product_override"):
            pack["product_subject"] = spec["product_override"]
        for key in ("team_title", "blog_title", "blog_eyebrow", "plans_title", "work_title", "work_eyebrow", "events_title", "events_eyebrow", "event_action", "services_title", "video_title", "video_eyebrow", "cta"):
            if spec.get(key):
                pack[key] = spec[key]
        if spec.get("services_title_override"):
            pack["services_title"] = spec["services_title_override"]
        spec.setdefault("labels", DEFAULT_LABELS[spec["category"]])
        if spec.get("eyebrow") == "mono":
            spec["font_extra"] = sorted({*spec.get("font_extra", []), "JetBrains Mono"})
        folder = OUT / spec["category"] / spec["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        doc = Kit(spec, pack).build()
        (folder / "template.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {len(T)} templates, categories={names and len(names)}")
    return len(T)


if __name__ == "__main__":
    build_all()
