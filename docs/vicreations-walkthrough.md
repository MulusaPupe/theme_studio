# Worked example: Vicreations, one company website in three design variations

Vicreations Investment Limited (Luanshya, Zambia) sent an 18-page PDF company profile. This example turns it into one complete company website in three design variations, with Mulusa Theme Studio. Every variation covers the whole company: engineering and construction, branding and signage, print and promotion, and design, supplies and ICT. Only the look and the arrangement differ, so the client can choose.

The sites were built by `tools/build_vicreations.py`. That script makes the same calls the editor's buttons and panels make (`Session`), so everything below can be done by hand in the app, in the same order.

| Variation | Template | Look | Pages |
| --- | --- | --- | --- |
| Vicreations Bold | Construction / Heavy Civil | Dark charcoal and Vicreations orange, condensed capitals, full-height site photograph | Home, About, Services, Our work, News, Contact |
| Vicreations Corporate | Corporate / Modern Consulting | Navy and orange, rounded and calm, a framed hero photograph | Home, About, Services, Our work, Contact |
| Vicreations Editorial | Art / Design Studio | White space, giant black type, orange-red, the DMC wall sign as the hero | Home, About, Services, Work, Contact |

What each one carries, from the profile: all four divisions; the full product and service catalogue (about 40 items); how a project runs (consult, interpret, deliver, report, from the profile's own description); values, mission and vision; the team; the three ministries as clients; and the credentials a tender buyer checks (ZPPA registered supplier to October 2027, ZRA tax clearance, NAPSA and Workers' Compensation compliance for 2026, citizen owned, incorporated 14 May 2018). Certificate, registration and tax numbers are not published.

Results: `samples/Vicreations/` (the three projects, which open in the app), `samples/Vicreations/exports/` (WordPress theme, content plugin and static site for each), and `docs/screenshots/vicreations/` (every page at desktop and phone width).

## Design pass (2026-11-13)

The sites were rebuilt after a design pass that used the installed design skills together (impeccable, taste-skill, scroll-craft and Emil Kowalski's motion skills, run through the `design-suite` skill). What changed, and where:

* **Every template** (`render/base.css`): the hero arrives once on load (headline, then its supporting line, then the buttons; the photo settles from a slight zoom), one photograph further down drifts as the page scrolls past it, buttons step up and press down, links and menu items draw their underline, FAQ answers open smoothly, and selection, focus rings, caret and scrollbars take the site's colours. All of it is CSS, so it works the same in the static site and in WordPress. It never runs in the editor, and it stops completely for visitors who ask their system for less motion.
* **Every template** (the template kit): no small labels above headings, and no 01/02/03 numbers on service rows.
* **New sections in the kit:** division panels with photographs to the page edge, a four-column catalogue, a credentials band, a numbered "how a project runs" sequence, a values, mission and vision trio, a clients list in large type, and a nine-piece work wall.
* **The three templates used here** have new home pages: a full-height photograph hero with the headline across the lower left (Heavy Civil), an editorial services index whose heading holds its place while the list passes, a balanced project mosaic, and a full-width photo statement (all three).
* **Photographs:** the two full-resolution site photographs in the profile (culvert works, the DMC wall sign) lead the Bold, Corporate and Editorial heroes and photo bands. The other photos in the profile are small (600 to 800 px wide), so they are used at card size rather than full width.

## The rule for content

Only facts from the profile go on the sites. Template sample content that has no source in the profile is **removed, not reworded**: testimonials, price lists, invented statistics and sample blog posts. The three facts with numbers in the profile (incorporated 2018, four divisions, more than 40 listed products and services) appear on the Bold and Corporate About pages; the Bold hero says "since 2018". The home pages have no statistics band. Bank details, tax numbers and staff phone numbers are left out of the sites; the company's sales email and main numbers are used instead. The profile has no staff portraits, so the team cards show names and roles with no placeholder pictures.

Photos are Vicreations' own site and branding work from the profile. The stock mock-ups in it (billboards with other brands, hazard symbols, product shots) are not used.

## Steps, as done in the app

1. **New project from a template.** Templates tab, choose the template, New project. The project starts as a copy; the template is never changed.
2. **Media library.** Media tab, Add images: the photos taken from the PDF (`pdfimages` was used to get them out). Each one is stored in the project's `assets/` folder.
3. **Brand colours.** Design tab, Colours. Bold: accent `#f26522` (the orange of the Vicreations logo). Corporate: primary navy `#2b3990` from the profile's headings, accent orange. Editorial: primary `#e8481c`, accent navy. Every section takes the new colours because the template uses design tokens.
4. **Header.** Click the header: brand text `VICREATIONS`, the button label and where it goes (Contact).
5. **Text, section by section.** Click a heading or paragraph and type, or edit it in the Properties panel. Buttons and links: set the label and choose the page they go to.
6. **Photos.** Click an image, Replace, pick from the library, and write the alt text. For a section with a background photo (the Bold hero and page headers), select the section and set its background image.
7. **Remove what does not apply.** Select a section (testimonials, pricing) and press Delete. In repeated cards, delete the extra cards.
8. **Pages and menu.** Pages tab: rename "Projects" to "Our work" and its address to `our-work`; delete the blog page on the Corporate and Editorial variations. Menu labels follow.
9. **Phone-only design.** Bold: switch the canvas to Mobile, select the hero and set a shorter minimum height. Desktop and tablet keep theirs.
10. **Live posts.** Bold's News page: delete the sample articles and insert "Latest posts (live)" from Components. In WordPress it lists real posts as they are published.
11. **Footer.** Edit it once; it is shared by every page.
12. **Export.** Export button. *WordPress block theme*: theme name and author, Check, Export ZIP, giving the theme and the content plugin. *Static website*: a form email (`sales@vi-creations.com`) or a form handler address, then Export, giving a ZIP and the unpacked folder.

## What the exporters reported

* WordPress: no errors on any of the three. Notes: contact forms need the content plugin and a server that can send email; the corporate and branding sites have no posts list, so posts appear only on the blog archive.
* Static: no errors. The Bold News page is left with only its title, because a static site has no posts; the exporter says so. For a static launch, remove News from the menu first, or publish that site on WordPress.

The themes were also installed in a real WordPress (7.1, PHP 8.3, Podman) with `tests/wordpress/check_exports.sh`. Every page answered 200 with no PHP messages, a published test post appeared on the Bold News page, and Gutenberg found 0 invalid blocks on all three sites. That check found one fault on the first run (a photo section with a gradient overlay), which was fixed in the exporter; see the development log.

## Rebuilding

```bash
.venv/bin/python tools/build_vicreations.py "Vicreations Business Profile 2026.pdf"
for s in bold corporate editorial; do
  .venv/bin/python tools/site_screenshots.py samples/Vicreations/exports/vicreations-$s-site docs/screenshots/vicreations/$s
done
```

Needs `pdfimages` (poppler-utils). Rebuilding replaces the three projects in `samples/Vicreations/`.
