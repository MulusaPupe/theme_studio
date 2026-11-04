# MULUSA THEME STUDIO: development log

Newest stage first.

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

Final full test run: 677 passed, 15 warnings in 247.22s (0:04:07)

Added: core/styles.py, core/properties.py, core/design.py, core/media.py, ui/fields.py, ui/richtext.py, ui/media_widgets.py, ui/panels/design_panel.py, tools/screenshots_stage03.py, tests test_properties/test_design/test_media/test_property_editor, docs/screenshots/stage03.

Decisions: no new library (Pillow and Qt suffice). History merge keys plus seal() make one gesture one undo step. Live edits patch the page DOM (mtsPatch); structural edits and undo/redo still reload. Rename changes the display name, not the file. Crop makes a new asset with a parent link; a GIF crop uses the first frame. Used assets cannot be deleted. Files of deleted assets go to assets/.trash and are reconciled on undo, redo and open. Border is a composed shorthand. font_family is stored as a bare family name. Sections have no gap control because they are not flex containers.

Faults found and fixed: dark theme left multi-line boxes and spinners white with pale text (seen only in screenshots; regression test added). Unset line height displayed 0.80, now Auto. Tone control did not lock when a photo arrived on an open form. Picker opened for elements that cannot show an image. Replace hint showed only on hover, now also on a selected placeholder.

Real Wayland acceptance walk (scripted, 2026-11-04): criteria 1-9, 11, 12 passed. Criterion 10: changes reach the canvas, median 163 ms and max 198 ms from edit to computed style on a 6 page, 327 node document, measured with polling overhead included. That missed the 150 ms target set in the walk script. Not profiled or optimised.

Limitations: no canvas resize handles (width and height fields instead). Header menu editing left to Stage 04. Device overrides are preparation only. Clicking a placeholder opens the picker on each click. Stage 02 real mouse drag from the library is still unconfirmed by a person; the Wayland walk used scripted input and synthetic clicks.
