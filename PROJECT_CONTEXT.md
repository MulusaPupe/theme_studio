# MULUSA THEME STUDIO: project context

The permanent reference. Read it with `DEVELOPMENT_LOG.md` at the start of every stage, and update it when requirements or decisions change.

Last updated: Stages 04-06, 2026-11-12.

## 1. Vision

A desktop application, developed under Mulusa Innovations, where a person selects a template, modifies it visually, adds and rearranges sections, replaces images, creates pages, previews on different screens and exports a working WordPress theme, without writing code. Advanced users may still customise code. It is a theme development platform, not a mockup generator.

## 2. Standing requirements

1. WordPress is an exporter, never the foundation. The editor works only on the universal document.
2. No fake functionality. A button either works or is disabled and labelled with the stage that delivers it.
3. Templates are independent folders, addable without touching the application core.
4. Placeholders are never embedded in a design.
5. Generated sites are genuinely responsive, not shrunken desktop layouts.
6. AI is optional and must never be required. It will change the document through the same route as any other edit.
7. Work proceeds in stages. At the end of each: test, list what is incomplete, fix major bugs, confirm earlier work, update these documents, report. The next stage waits for the owner's go-ahead.

## 3. Stack

Python 3.12+, PySide6 with Qt WebEngine, JSON, Pillow (thumbnails now, cropping in Stage 03), zipfile (from Stage 05). Tests: pytest, pytest-qt and pytest-xdist (runs six workers by default). Nothing else at runtime.

## 4. Architecture

```
src/mulusa_theme_studio/
  core/        pure Python: document, structure rules, operations, validation, history, project storage, template library, settings
  components/  the component registry and built-in presets
  render/      document -> HTML and CSS: css, html, placeholders, fonts, site, base.css
  exporters/   Exporter contract, shared Issue type and registry; wordpress/ and static/
  templates/   categories.json and <category>/<slug>/{template.json, thumbnail.png}
  resources/   bundled fonts and icons
  ui/          session, bridge, main_window, canvas, selection_bar, dialogs, theme, widgets, panels/
tools/         authoring and checking tools; never used at runtime
```

Dependencies only point downward: `ui -> exporters/render/components -> core`. `tests/test_architecture.py` enforces this, and also that no platform knowledge enters core, render or the canvas.

`ui/session.py` holds what is open. Panels observe its signals and never talk to each other.

## 5. Key decisions

**Sections are trees of primitive nodes, not opaque blocks.** A hero is a `section` with `props.role = "hero"` containing columns, headings and images. Every element is selectable; a future AI request such as "make the hero more modern" has precise targets; and it maps naturally onto WordPress blocks and other CMS structures. A "component" in the catalogue will be a preset that inserts a tree (Stage 02).

**One render route.** Canvas, browser preview and thumbnails all use `render/site.py`, and the static exporter must too, so what you see is what you export. Editor mode only adds `data-mts-id` attributes and the selection script.

**A controlled style vocabulary.** Element styles use allowed properties only (`render/css.py`), and unsafe values are dropped. `$name` means design token `--mts-name`, which is how global changes reach everything.

**Tones.** A section declares `tone`: default, surface, inverse, primary, accent or image. It sets the scoped colours (`--mts-c-text`, `-muted`, `-card`, `-btn`, and so on), so contents stay readable on any background. Any section over a photo must use `image`, and a test enforces this.

**Snapshot undo.** `History.apply(label, change)` is the only way to change a document. Snapshots are JSON strings, and a failed change restores the document. Simple and reliable, and fast enough for documents of this size (re-check in Stage 03 when edits become frequent).

**One project.json rather than a pages/ folder.** This differs from the brief's suggested layout, which allowed for improvement. One atomic write means a crash can never leave pages from different moments.

**Autosave never overwrites the project.** It writes `.autosave.json`; opening offers recovery. `project.json` changes only on an explicit save.

**Bundled fonts (30 families, OFL).** The canvas works offline and exports need no call to Google, which also helps visitors' privacy. Latin subset only for now.

**Canvas sizing.** The view is sized to device width times zoom and the engine zoom is set, so media queries see the true device width at any zoom. Scrollbars are off in the canvas, because they would take 15 px from that width.

**Generated template JSON.** `tools/template_kit.py` (layouts), `template_packs.py` (sample content) and `build_templates.py` (the 50 specs) produce standalone folders. The application never imports them. Hand-written templates are equally valid.

**Structure rules live in core.** `core/structure.py` says which node may contain which. `validate_document` enforces it and the canvas receives the same rules as generated data, so the indicator and the final check cannot disagree. Only sections sit at page level. Header and footer are shared by every page: never moved, copied or deleted.

**All structural edits go through `core/operations.py`, run inside `History.apply`.** The session's `_edit` also validates the whole document inside the change, so a failure restores the previous state and leaves no history entry. A completed drag is exactly one entry. Selection, hover and the clipboard are outside history.

**The page reports; Python decides.** `render/editor.js` runs in editor mode only and holds no design state. The bridge (`ui/bridge.py`) exposes only `reportReady`, `selectNode`, `clearSelection`, `requestInsert`, `requestMove` and `reportRefused`, and checks every argument. Never add a general-purpose call to it.

**Library drags use an overlay.** A transparent widget lies over the page only during a library drag and turns Qt drag events into page coordinates. Rearranging existing elements uses ordinary mouse events inside the page. Both share one target calculation in `editor.js`.

**Presets are trees, stored apart from the canvas.** `components/presets.py` builds primitive nodes with fresh ids, using design tokens, so a preset takes on the look of its template. `registry.register` adds a component with no editor change. Spacer and Column are named containers, not new node types.

**Clicks select; they never navigate.** Pages change from the Pages tab. Application shortcuts take priority over the engine because nothing on the page is edited by keyboard.

## 6. Universal document

Schema `mulusa.theme/1`, documented at the top of `core/document.py`: meta, tokens (colors, fonts, type, shape, spacing), palettes, type_pairs, site (header, footer), navigation, pages, media (art, assets), reusable. Nodes: id, type, name, props, style, responsive (desktop, tablet, mobile: style, props, hidden), children. Validated on open and save. Any change to the format needs a schema version and a migration.

Breakpoints: tablet up to 1024 px, mobile up to 640 px, mobile menu from 860 px. Preview widths: 1440, 820, 390.

## 7. Roadmap

01 foundation, 02 canvas selection and drag and drop, 03 property editor, media library, global design, 04 page management and responsive editing, 05 static exporter, 06 WordPress block theme exporter and validation: all built, 04-06 awaiting approval (2026-11-12). 07 optional AI assistant. 08 testing, optimisation, packaging, installer.

## Stage 03 decisions (2026-11-04)

Stage 03 is complete and awaiting approval. New core modules: `core/styles.py` (safe style vocabulary), `core/properties.py`, `core/design.py`, `core/media.py`. `History.apply(label, change, merge=key)` remains the only document route; one gesture is one undo step. Live edits patch the canvas; structural edits reload it. Crops are new assets and originals are never altered. `write_site` reuses each page's render until something it reads changes; anything new a page's render reads from the document outside `pages` is covered automatically, but new reads of other pages' fields must be added to the outline in `_render_page`.

## Stages 04-06 decisions (2026-11-12)

**The static exporter renders through `write_site`**, like the canvas, on a copy of the document. It never fakes what needs a server. Post templates are not exported, and sections containing a posts list are left out, with a warning per page (and a warning when that leaves a page with only its title). Contact forms need a form handler (`https://` only) or an email address (mailto); with neither, the export stops. `check_site` then verifies every local link and file, the stylesheet's `url()`s, no editor markup or script, and no form posting to `#`. Only the fonts the stylesheet uses are shipped. An existing output folder is replaced only if its README marks it as an earlier export.

**One `Issue` type for every exporter** lives in `exporters/__init__.py`; `exporters/wordpress/check.py` re-exports it for older imports.

**The export dialog offers both formats.** It shows only the fields that apply: author, version and the plugin for WordPress; form handler and form email for a static site.

**Tests run in parallel** with pytest-xdist (`-n 6 --dist load` in pyproject). Each test still gets its own window and config folder, so nothing is shared between tests; the suite went from about 6 minutes to under 2 with no test removed. Use `-n 0` to run in one process.

**Real-WordPress checks are test tooling.** `tests/wordpress/` (Podman) installs an exported theme and plugin, imports the pages, publishes a post and opens everything in Gutenberg. `check_exports.sh` does this for any exported slugs.

## Resource library decisions (2026-11-13)

- **Package:** a new `library/` package holds the import and resource logic. It has no Qt, does not import ui or exporters, and has no eval, exec or subprocess. This is enforced by tests. WordPress-format knowledge for import lives here; core, render and the canvas still never mention it.
- **Storage:** JSON only (index.json and state.json) in the user data directory, with `MTS_DATA_DIR` as an override. Built-in resources are read in place.
- **Untrusted packages:** imports are never executed. Every import keeps the original package and records a loss report and a licence. An unknown licence is never redistributable.
- **Discovery:** only through documented APIs (WordPress.org patterns and themes, GitHub search) on an https host allowlist, with a 24 h cache and offline fallback. Webflow, Framer, ThemeForest and showcase sites are inspiration links only.
- **Inserting:** a resource goes into the document through `Session._edit`, so one insertion is one undo step. Images are copied into the project, with duplicates reused by sha256.
