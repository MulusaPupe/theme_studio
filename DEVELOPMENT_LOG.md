# MULUSA THEME STUDIO: development log

Newest stage first.

## Part 3: motion in the samples and the best templates, plus Home and a splash screen (2026-11-13)

Status: done, awaiting the owner's look. Asked as "yes go ahead with part 3, also one feature to go back to home when software launches and lets add splash screen". Nothing committed.

- **Home**: a Home button in the top bar (and Ctrl+Shift+H) closes the project, after offering to save, or leaves a template preview, and shows the start screen with recent projects. The studio already starts on that screen and never reopens a project by itself. `Session.close_project()` is new.
- **Splash screen** (`ui/splash.py`): the Mulusa mark, name, tagline, version and a progress bar that moves with the real loading steps: fonts and settings, templates ("Loaded 69 templates"), then the canvas engine. It stays at least 0.9 s so it never just flashes. It is skipped offscreen and with `MTS_NO_SPLASH=1`. On this machine it showed for about 5 s on a real display.
- **CHITNAS** (`tools/build_chitnas.py`): the six division cards now carry animated drawings (server rack, shield, growth chart, CCTV, solar, gears) instead of icons. There is a grid background on the forensics band and the Services page header, and an aurora behind the closing call to action.
- **Vicreations Corporate**: the four division cards carry drawings (crane, palette, hanger, code). **Bold** keeps its icons, because its compact list has a narrow icon column where drawings overlapped the headings. Bold and Corporate get a grid on the credentials band and an aurora on the call to action. **Editorial** gets waves on its call to action.
- **Templates**: 18 full templates get motion (`MOTION` in `tools/build_templates.py`):
  - **Drawings:** each card's drawing is chosen from what its icon stands for (`ICON_ART` in `tools/template_kit.py`). It is all or nothing per grid, so a grid with a card the drawings can't honestly show keeps its icons. The first try used fixed lists in card order and gave mismatches such as a shield on "Developer API"; that was caught in screenshots and replaced.
  - **Backgrounds:** at most one living background per page, never on a photo section.
- **Real WordPress** (`tests/wordpress/check_exports.sh`, WordPress 7.1 in Podman): CHITNAS, Vicreations Corporate and two one-page themes (ICT with a countdown, music). Every page returned HTTP 200 with no PHP messages, and Gutenberg found 0 invalid blocks in every page and pattern. On the ICT theme, `mulusa.js` is enqueued with `defer` and served (HTTP 200), and the countdown ticked down live in a browser.
- **Thumbnails**: all 69 rebuilt; the layout audit found 0 problems.
- **Fixes found on the way:**
  - Aurora blobs were sized in viewport units and swamped tall sections. They are now sized to the section and softer on light sections.
  - Drawings on primary-coloured cards used a dark "deep" colour that disappeared; it is now lightened on primary.
  - Waves were invisible on accent sections.
  - Drawings in cards now sit at the left, in line with the text.

## Living elements and one-page templates, parts 1 and 2 (2026-11-13)

Status: parts 1 and 2 done, awaiting the owner's look before part 3. The owner pointed to the vi-creations.com maintenance page ("very attractive on its own with a simple page") and asked for that quality in "a variety yes music, ict, security, corporate etc everything". Nothing committed.

- **New elements**, editable in the inspector and exported to static and WordPress:
  - **Animated illustration**: 35 original SVG drawings in 11 groups (business, technology, security, music, construction, industry, launch, creative, food, health and community, commerce). They take the site's colours and animate with CSS only. They stay still for visitors who turn off animations.
  - **Countdown**: a date, time and time zone, with labels and a "done" message. The time left is worked out when the page is written and kept live by `assets/mulusa.js`. This is the only script the studio writes, and only on pages that have a countdown. WordPress enqueues it with `defer`. The static checker allows that exact script with its exact content and nothing else.
  - **Progress bar**: a value or a loading animation.
  - **Glass blur** (`backdrop_filter`, a closed list of blur/saturate/brightness values) and a **living background** on sections: aurora, grid, stars or waves. On WordPress, a living background on a photo section is reported, not exported.
  - Ten new components under "Motion and graphics", including Coming soon, Maintenance and Under construction pages.
- **14 one-page templates** in a new "Launch & One-page" category (`tools/build_onepage.py`): maintenance, ICT, security, music, construction, SaaS waitlist, event, restaurant, link-in-bio, clinic, NGO, solar, mining and fashion. They use fictional businesses with example.com contacts. Total templates: 69.
- **Library**: an "Animated illustrations" view with previews in the open project's colours, "Insert this illustration", and a Discover row for one-page templates.
- **Tests**: 1067 pass (932 before). The new `tests/test_living.py` has 64 tests. In `test_templates.py`, the full-website rules (six pages, photos, unique home layout) now apply to full websites only, and the one-page templates have their own rules (one living page, distinct looks, the trades covered).
- **Not done yet (part 3)**: bringing the motion to CHITNAS, Vicreations and the best full templates.

## Vicreations as three variations of one company site (2026-11-13)

Status: done, awaiting the owner's approval. The owner rated the first redesign 7/10 ("still plain", engineering liked) and clarified that the three themes were meant as three variations of the whole company, not one site per division. Nothing committed.

- The previous Engineering, Corporate and Branding samples were replaced by **Bold** (Heavy Civil), **Corporate** (Modern Consulting) and **Editorial** (Design Studio). Each covers all four divisions.
- More from the profile: full division lists, the profile's description of how projects run, values, mission and vision, and the credentials (ZPPA, ZRA tax clearance, NAPSA, Workers' Compensation, citizen owned, incorporation date). Numbers from the certificates are not published.
- New kit sections: `services_panels`, `catalogue`, `credentials`, `process_steps`, `values_trio`, `clients_type`, `portfolio_wall`. The three templates use them on home and inner pages.
- `tools/site_screenshots.py` captures up to 12,000 px so long pages are complete.
- Checks: 829 tests pass; thumbnails and layout audit 0 problems; screenshots of every page with no broken images or sideways scroll; real WordPress: every page 200, no PHP messages, test post listed on Bold's News page, Gutenberg 0 invalid blocks on all three.

## Design pass: motion, finish and better templates (2026-11-13)

Status: done, awaiting the owner's approval. Requested as "do better templates and redo the Vicreations nicely like a 100K site". Nothing committed.

### Skills

Installed globally in `~/.claude/skills`: design-taste-frontend (Leonxlnx/taste-skill), impeccable (pbakaus/impeccable), scroll-craft (nateherkai/scroll-craft) and nine of Emil Kowalski's motion skills. A new `design-suite` skill runs them as one pass and settles their conflicts (no eyebrows; one or two scroll moments, not a scroll film; no paid kie.ai generation without the owner's go-ahead; Mulusa specifics: CSS-only motion, never in the editor).

### Built

- `render/base.css`, shared by the canvas, the static export and the WordPress theme, so all 50 templates get it:
  - Hero entrance once on load: headline, then supporting line, then actions (exponential ease-out, 0.8 s, 80 ms steps); the hero photo settles from 1.08; a hero image unveils.
  - One scroll moment: a background photograph in a later section drifts through it (`animation-timeline: view()` inside `@supports`).
  - Hover layer: buttons step up 1 px and press to 0.985; primary fill steps towards its text colour; links and menu items draw their underline; link arrows nudge 3 px; form fields get a soft focus ring.
  - Smooth FAQ opening (`::details-content`, `interpolate-size`) where supported.
  - Browser surfaces: selection, focus ring, caret, scrollbar, underline offset, balanced headings and pretty paragraphs.
  - Motion never runs in the editor (`mts-editing` on the canvas body, `.editor-styles-wrapper` in Gutenberg), and `prefers-reduced-motion: reduce` stops all of it.
- Template kit (`tools/template_kit.py`), regenerated into all 50 templates:
  - Eyebrow labels removed (impeccable's craft floor bans them); service rows lose their 01/02 numbers; statistics get hairlines.
  - New sections: `hero_cinematic`, `services_index` (sticky heading beside a hairline list) and `photo_band` (statement over a drifting photo).
  - `portfolio_mosaic` ratios now balance each row.
  - New home pages for Heavy Civil, Modern Consulting and Design Studio. Modern Consulting drops its stats-hero for a photo mosaic hero.
- Vicreations rebuilt on the new templates, with the two full-resolution photographs found in the profile (culvert works 2245 px, DMC wall sign 1706 px), resized to 2000 px for the web. Home pages no longer carry a statistics band. The corporate footer wordmark is refitted to the longer real name.
- `tools/site_screenshots.py`: waits for the entrance, and measures again after lazy images load (the old shots cut off the bottom of long pages).

### Checks

- Full suite: 829 passed (6 new in `tests/test_design_finish.py`).
- `tools/build_thumbnails.py`: 50 thumbnails, every page at three widths, 0 layout problems.
- Screenshots of every Vicreations page at 1440 and 390: no broken images, no sideways scroll; reviewed by eye.
- Real WordPress (check_exports.sh), all three sites: every page HTTP 200 with no PHP messages, the test post listed on the engineering News page and its own page opening, Gutenberg 0 invalid blocks.

### Known limitations

- Most profile photos are 600 to 800 px wide, so they stay at card size. Better photographs from the client would lift the sites the most.
- Motion needs a current browser (Chrome 115+, Safari 18+ for the scroll moment); older browsers show the same page without it.

## Stages 04 to 06: pages, export, static website, worked example (2026-11-12 to 2026-11-13)

Status: complete, awaiting the owner's approval. Done in one run at the owner's request. Nothing committed.

### Built

- WordPress block theme exporter with its content plugin (stage 04/05 backend, done earlier in this run) and a real-WordPress test kit in `tests/wordpress/` (Podman: WordPress 7.1.4, PHP 8.3, MariaDB 11).
- Static website exporter, `exporters/static/`. Renders through `render/site.py` like the canvas. Post templates and sections that list posts are left out with a warning. Contact forms need an https form handler or an email address, otherwise the export stops and says why. `check_site` checks every link, file and stylesheet `url()`, and looks for leftover editor markup, scripts and forms with nowhere to send. Only the fonts the CSS uses are shipped. A later export replaces only a folder it wrote itself (README.txt marker).
- Export dialog: a choice between "WordPress block theme" and "Static website", showing only the fields that apply. The toolbar button is now "Export".
- `Issue`, `ERROR` and `WARNING` are shared by both exporters (`exporters/__init__.py`).
- Faster tests: pytest-xdist (`-n 6 --dist load`). The full suite went from 6:08 to about 2 to 3 minutes, with no test removed.
- Worked example: three Vicreations sites from the company's PDF profile, built by `tools/build_vicreations.py` through `Session`, as a designer would in the app. See `docs/vicreations-walkthrough.md`.
- `tools/site_screenshots.py`: full-page desktop and phone screenshots of a static export, plus a contact sheet. It also reports broken images and sideways scrolling.
- `tests/wordpress/check_exports.sh`: installs each exported theme in a fresh WordPress, imports the content, checks every page and a test post, and runs Gutenberg's block validation.

### Faults found and fixed

1. **Invalid cover block in real WordPress (engineering home page).** A photo section with a gradient overlay is exported with `dimRatio` 0. Gutenberg's save() still adds `has-background-dim-0 has-background-dim` at 0, and the exporter left both out, so Gutenberg marked the block invalid. Fixed in `translate.py`, with a regression test. Earlier samples never had a gradient over a photo, so they did not show it.
2. Static News page left with only its title: the exporter now warns about it and says what to do.
3. Screenshots: a relative path did not load (now resolved to absolute), and a tall capture could come back blank (now retried).
4. Corporate About page: a long paragraph had been put in as a heading, and the subtitle promised content that was not on the page. Fixed in the builder.
5. `check_exports.sh` false alarms: `/?p=ID` redirects (301) to the pretty address, so the check now follows it. WordPress's draft privacy page answered 404, so only published pages are checked now.

### Checks

- Full suite: 823 passed (new: `tests/test_static_export.py` with 21 tests, two dialog tests in `test_site_editor.py`, one cover-block test in `test_wordpress_export.py`).
- Real WordPress, all three Vicreations themes: every page HTTP 200, no PHP messages, the test post is listed on the engineering News page and its own page opens, and Gutenberg finds **0 invalid blocks** across every page and pattern.
- Static exports: no errors. Warnings only for mailto forms and the engineering News page.
- Screenshots of every page at 1440 px and 390 px (`docs/screenshots/vicreations/`): no broken images and no sideways scroll.

### Known limitations

- No resize handles on the canvas; sizes are set in the Properties panel.
- Static sites cannot send forms themselves. A mailto form depends on the visitor's mail app, so a form handler service is better.
- Static sites have no posts: post lists are dropped.
- A photo section's gradient overlay comes from the theme stylesheet in WordPress, so it cannot be edited in the block editor's overlay control.
- The first WordPress run hung on MariaDB initialisation; removing the pod (`podman pod rm -f mts-wp`) and retrying fixed it.
- Still open from earlier: owner approval of Stage 03, and a check by hand of a real mouse drag on the canvas.

## Stage 02: canvas selection, components and drag and drop (2026-11-04)

Status: complete, awaiting the owner's approval. Stage 03 has not been started.

### Built

- Selection: click any element on the canvas. Outline, parent indication, hover outline, label, and name and type in the status strip and inspector. Selection lives in the session and never touches the document or history. Clicks never navigate or press anything on the page.
- Catalogue: 30 presets in `components/presets.py`, each a full tree of primitive nodes, registered through `components/registry.py`.
- Drag and drop: from the library with an insertion line, target outline and a "cannot go here" state; existing elements rearrange by dragging on the page.
- Operations: duplicate, delete, move up and down, copy, paste, from the selection bar and the keyboard. All are validated in `core/operations.py` and run through `History.apply`.
- Selection bar: clickable breadcrumb and actions with tooltips and honest disabled states.
- Layers: page, header, sections, children, footer; expand and collapse; two-way sync through the session.
- Bridge: `ui/bridge.py` exposes six narrow calls. JavaScript reports and asks; Python validates and mutates.

### Conflicts between the brief and the code, and how they were settled

1. No `spacer` node type exists. Spacer is a `container` named "Spacer" with a height. No schema change.
2. No `column` node type exists. A column is a `container` named "Column" inside `columns`, as all 50 templates already do.
3. The Stage 01 catalogue listed Header, Navigation and Footer as components. They are removed from the library because a site has exactly one of each, shared by every page. Rows, Rich text, Gallery, Video, Link, Blog and Products stay as extras beyond the brief's list.
4. Stage 01 made a click on a canvas link change page. The Stage 02 brief makes a click select. Pages now change from the Pages tab, and the Stage 01 test was rewritten.
5. Template previews stay read-only: selecting works, and any edit explains that a project is needed.

### Checks

- Full suite: 523 passed, including all Stage 01 and architecture tests. New files are `tests/test_operations.py`, `test_presets.py` and `test_editor.py`.
- The editor tests send real mouse and key input to the engine's input widget, and drag events to the top-level window so Qt's own hit-testing routes them.
- Real Wayland session: click, shortcuts with focus in the page, bursts of 5 presses at 0 to 250 ms apart (all applied), and start-up and quit through the real entry point.
- Screenshots reviewed by eye, dark and light: `docs/screenshots/stage02/`. All prebuilt sections were inspected at desktop, tablet and mobile.

### Faults found and fixed

- Once the page had focus, the engine took Ctrl+Z for itself, so undo silently did nothing straight after a click on the canvas. Found by a test with real input. The canvas now lets application shortcuts win.
- Every edit took about 870 ms, of which 660 ms was re-reading and re-rendering the same SVG icon for each Layers row. Icons are now cached: about 120 ms synchronous and 180 to 270 ms to a finished redraw.
- After a quick burst of edits the outline could be missing, because an interrupted load does not reliably report its end. The page now reports when it is ready.
- Choosing a preview left Ctrl+Z able to change the hidden project (a Stage 01 fault). Undo and redo are now refused during a preview.
- Stage 01 validation did not check parent and child types. `core/structure.py` now defines the rules, validation enforces them, and all 50 templates pass.
- Visual review: the drop line vanished on gold sections, selection tags shrank with the zoom, and a stray box with blue corners sat beside the selected Layers row. All fixed.

### Known limitations

- A real mouse drag from the library has not been run by a person or by automation. The headless platform has no drag loop, and Wayland cannot be driven from outside. Everything else in that path is tested. **The owner should try it.**
- One run of a scratch Wayland test script hung once and was killed by its timeout. It did not recur in 5 later runs and was not explained.
- The canvas redraws the whole page after each edit, in about 200 ms. There can be a brief flicker. Scroll position is kept.
- The clipboard is internal to the app and is lost on quit.
- Layers cannot be dragged to reorder; rearranging is done on the canvas or with move up and down.
- Links and menus inside the shared header and footer are not separately selectable, because those are rendered as a unit from the node's props. The same goes for FAQ items' inner parts and form fields.
- Preset buttons link to the page with the id `contact`, and go nowhere on a site without one. Sample text cannot be edited until Stage 03.
- Moving an element to another page is not supported, except by copy and paste.

## Stage 01: foundation, main window, design system, template library (2026-11-04)

### Built

- Core: universal document and validation, snapshot undo, project folders with atomic saves, autosave and recovery, template library, settings.
- Rendering: all 18 element types to responsive HTML and CSS, design tokens, tones, generated placeholder artwork, bundled fonts, rich text sanitising, a mobile menu that needs no JavaScript.
- Library: 50 templates across 10 categories, each with six pages and a real rendered thumbnail.
- Interface: toolbar, five-tab sidebar, canvas with device widths and zoom, inspector, status strip, welcome screen, new project and settings dialogs, dark and light appearance.
- Exporter contract and registry, with no exporters registered yet.

### Checks

- Automated tests cover architecture rules, validation, history, projects and recovery, rendering safety, template validity and distinctness, and the real window in a real browser engine.
- `tools/build_thumbnails.py`: every page of every template at 3 widths (900 page loads). Result: 0 layout problems.
- Launched through the real entry point and quit cleanly on the offscreen platform and on a real Wayland desktop.
- Screenshots reviewed by eye in dark and light: `docs/screenshots/stage01/`.

### Faults found and fixed

Found by tests:
- Clicking a link on the canvas crashed the application (core dump): a new load was started from inside the engine's navigation callback. The connection is now queued.
- Clicking a link then showed a false error, because the engine reports a blocked navigation as a failed load. Only a truly missing page is an error now.
- A resize timer could fire after shutdown. Shutdown now stops it, disconnects, and deletes the page before its profile.
- Three templates were just under 4.5:1 contrast; `palette()` now adjusts the colour until it passes.
- Two templates in one category shared a font pairing.

Found only by looking at renders, after automated checks had passed:
- Muted text over photo heroes was almost invisible. Fixed with the `image` tone; regression tests now measure the colour in the browser.
- A headline broke mid-word, hidden from the audit by the CSS safety wrap. The audit now measures without the wrap and names the offending text; display type is now sized from its longest word and the font's width.
- Flat placeholders on black palettes rendered solid black.
- A truncated "Components" label, banner text running under its buttons, a white scrollbar strip on the canvas and thumbnails, a weak selection outline and a toolbar device toggle that could go stale.

Lesson: review renders by eye at the end of every stage. Tests alone did not catch the worst visual faults.

### Known limitations

- Applying a template is the only edit so far, so undo and autosave have little to act on until Stage 03.
- The canvas shows the design but clicking on elements does not select them yet (Stage 02). Selection is from the Layers tab.
- Panning is by scrolling the page; drag-to-pan comes with the canvas work in Stage 02.
- Contact forms render, but do not send anything. Sending depends on the export target (Stages 05 and 06).
- Video elements show a poster. Only direct mp4 and webm links play inline; others are links.
- Fonts are the Latin subset, so some characters in other languages will fall back to a system font.
- Tested on Linux only. Windows and macOS are not yet tested. The interface font sizes and paths are written to be portable, but this is unproven until Stage 08.
- A change of appearance applies at the next start.
- Template text, names and prices are fictional samples.
- The file open dialog and the browser launch are exercised only up to the system call, not with a real dialog or browser.

### Next

Stage 02: canvas selection through a web channel, drag and drop from the component catalogue with presets, moving, duplicating and deleting, section rearrangement, selection handles, panning. To start after the owner's go-ahead.

## Stage 03: Property editor, media library, global design (2026-11-04)

Status: complete, awaiting approval. Stage 04 not started. Nothing committed (not a git repo).

Final full test run: 687 passed, 15 warnings in 285.22s (0:04:45)

Added: core/styles.py, core/properties.py, core/design.py, core/media.py, ui/fields.py, ui/richtext.py, ui/media_widgets.py, ui/panels/design_panel.py, tools/screenshots_stage03.py, tests test_properties/test_design/test_media/test_property_editor, docs/screenshots/stage03.

Decisions: no new library (Pillow and Qt suffice). History merge keys plus seal() make one gesture one undo step. Live edits patch the page DOM (mtsPatch); structural edits and undo/redo still reload. Rename changes the display name, not the file. Crop makes a new asset with a parent link; a GIF crop uses the first frame. Used assets cannot be deleted. Files of deleted assets go to assets/.trash and are reconciled on undo, redo and open. Border is a composed shorthand. font_family is stored as a bare family name. Sections have no gap control because they are not flex containers.

Faults found and fixed: dark theme left multi-line boxes and spinners white with pale text (seen only in screenshots; regression test added). Unset line height displayed 0.80, now Auto. Tone control did not lock when a photo arrived on an open form. Picker opened for elements that cannot show an image. Replace hint showed only on hover, now also on a selected placeholder.

Real Wayland acceptance walk (scripted, 2026-11-04): criteria 1-12 passed, using the walk script's own 150 ms target for criterion 10.

Live edit performance: on a 6 page, 327 node document the first walk measured a 163 ms median, edit to computed style, polling overhead included. Profiling showed write_site re-rendering every page on each edit (59 ms). render/site.py now reuses a page's render until something it reads changes; write_site with nothing changed fell to 13 ms. A second profile script went from 152 ms to 117 ms; the walk now measures a 125 ms median, 296 ms worst case. The first walk's worst case was 198 ms, so the occasional slow edit is not improved and its cause is unknown. Tests compare reused output with a fresh render across eight kinds of edit.

Limitations: no canvas resize handles (width and height fields instead). Header menu editing left to Stage 04. Device overrides are preparation only. Clicking a placeholder opens the picker on each click. Stage 02 real mouse drag from the library is still unconfirmed by a person; the Wayland walk used scripted input and synthetic clicks.

## 2026-11-13: CHITNAS redesign proposal
- New `tools/build_chitnas.py` builds a proposed site for CHITNAS Enterprises Ltd (chitnas.com) from Corporate / Modern Consulting, recoloured to the CHITNAS blue and logo red, through Session only. Output: `samples/CHITNAS/`, screenshots in `docs/screenshots/chitnas/`.
- Six divisions (bento grown to six cards with Duplicate), forensics band, energy and mining panels, product lifecycle steps, FAQ from the site's facts, full services catalogue. No invented figures, clients or projects; Case Studies and Insights pages removed.
- Photos are the current site's small stock pictures, as stand-ins. Real WordPress check: 0 invalid blocks, 0 PHP messages. 829 tests pass.

## 2026-11-13: Template & Creative Resource Library milestone
- New package `src/mulusa_theme_studio/library/` (no Qt):
  - resource model and licence table;
  - JSON store (index, favourites, recent, folders, item folders, cache);
  - built-in catalogue;
  - safe ZIP extraction;
  - package inspection and import (HTML/CSS sites, WordPress block themes and patterns, Mulusa files, images, classic themes kept for reference);
  - a CSS parser with media queries and custom properties;
  - a WordPress block converter;
  - document apply functions;
  - generated patterns and gradients;
  - official-API discovery with an offline cache.
- New `ui/library_window.py`: library window, import dialog, Find online panel and responsive preview. The Library rail button and Ctrl+Shift+L are in the main window. `Session` gained `insert_resource`, `apply_resource` and `create_project_from_resource`, each one undo step.
- Built-in collection:
  - 5 new starter templates (Personal Portfolio, Family Clinic, Community NGO, Auto Garage, Online Store), 55 in total;
  - `tools/build_sections.py` harvested 72 sections, 15 headers and 10 footers with rendered previews.
- **Tests:** 902 passed (was 829). There are 46 new library tests and 2 architecture tests. The template-count tests were updated for 55 templates.
- **Faults found and fixed during the milestone:**
  - ZIPs were read as single files;
  - the main wrapper group collapsed Twenty Twenty-Four into one section;
  - pattern licences came out Unknown from the API;
  - a gradient on a section with a pattern photo failed validation (the gradient now replaces the photo);
  - the white grid background and stale details buttons were seen in screenshots.
- **Network:** the network went down near the end. Live checks were made earlier: pattern import, Twenty Twenty-Four import, GitHub search. The finished online panel was not tried live.
- **Docs:** `PROJECT_STATE.md` and, in `docs/`, `TEMPLATE_LIBRARY_ARCHITECTURE.md`, `RESOURCE_IMPORT_GUIDE.md`, `RESOURCE_LICENSING_GUIDE.md` and `TEST_REPORT.md`.
