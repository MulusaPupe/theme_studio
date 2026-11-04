# MULUSA THEME STUDIO: project context

The permanent reference. Read it with `DEVELOPMENT_LOG.md` at the start of every stage, and update it when requirements or decisions change.

Last updated: Stage 02, 2026-11-04.

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

Python 3.12+, PySide6 with Qt WebEngine, JSON, Pillow (thumbnails now, cropping in Stage 03), zipfile (from Stage 05). Tests: pytest and pytest-qt. Nothing else at runtime.

## 4. Architecture

```
src/mulusa_theme_studio/
  core/        pure Python: document, structure rules, operations, validation, history, project storage, template library, settings
  components/  the component registry and built-in presets
  render/      document -> HTML and CSS: css, html, placeholders, fonts, site, base.css
  exporters/   Exporter contract and registry (no exporters yet)
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

01 foundation (done). 02 canvas selection and drag and drop (done, awaiting approval). 03 property editor, media library, global design. 04 page management, responsive editing. 05 static exporter. 06 WordPress block theme exporter and validation. 07 optional AI assistant. 08 testing, optimisation, packaging, installer.

## Stage 03 decisions (2026-11-04)

Stage 03 is complete and awaiting approval. New core modules: `core/styles.py` (safe style vocabulary), `core/properties.py`, `core/design.py`, `core/media.py`. `History.apply(label, change, merge=key)` remains the only document route; one gesture is one undo step. Live edits patch the canvas; structural edits reload it. Crops are new assets and originals are never altered.
