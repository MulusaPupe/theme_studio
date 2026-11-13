# Template and Creative Resource Library: architecture

The library extends the studio. It does not replace anything. Templates, the editor, undo and the exporters work as before. The library adds a catalogue of reusable resources, a safe importer and a window for using both.

## Layers

```
ui/library_window.py     LibraryWindow, DetailPanel, ImportDialog, OnlinePanel, ResponsivePreview (Qt)
ui/session.py            insert_resource, apply_resource, create_project_from_resource: all edits go through History
ui/main_window.py        "Library" rail button, Ctrl+Shift+L, project_from_resource
        │
library/                 plain Python, no Qt (enforced by tests/test_architecture.py)
  model.py               Resource, kinds, compatibility levels, licence table, identify_licence
  store.py               ResourceStore: JSON index + state, item folders, cache (no database)
  catalogue.py           Library: built-in collection + user store; search, filters, discover
  safezip.py             safe ZIP extraction
  packages.py            inspect_package / import_package: classify, convert, file the result
  html_import.py, css.py HTML/CSS → universal document
  blocks.py              WordPress block markup → universal document
  convert.py             shared builders, the loss Report, document finishing and validation
  apply.py               pure document functions: adopt sections, apply header/footer/gradient/pattern
  patterns.py            generated background patterns and token-based gradients
  remote.py              official-API discovery with a cache; downloads only on request
  sections/              72 sections, 15 headers, 10 footers (JSON + PNG previews)
        │
core/ render/ exporters/ unchanged contracts: universal document, validation, write_site, exporters
```

WordPress-format knowledge lives only in `library/` (for import) and `exporters/wordpress` (for export). `core`, `render`, `components` and the canvas still never mention it.

## Resource model

Each `Resource` has an id, name, kind, category, description, tags, source, source URL, author, licence and format. It also has a compatibility level, responsive notes, an origin (builtin, imported or remote), a folder, a path, a preview, an added date, a sha256, a data dict and a report (what was not carried over).

- **Kinds:** template, section, header, footer, palette, type_pair, font, icon, pattern, image, package.
- **Compatibility:**
  - `full`: converts with nothing lost.
  - `partial`: editable, with listed losses.
  - `reference`: kept but not convertible, for example a classic PHP theme.
  - `unsupported`.
- Only `full` and `partial` resources can be inserted.

## Storage

The library lives in `$MTS_DATA_DIR`, or `$XDG_DATA_HOME/mulusa-theme-studio/library` when that is not set.

```
library/index.json        list of imported resources (atomic writes)
library/state.json        favourites, recently used, folders
library/items/<id>/       original/ (the untouched package), project/ (project.json + assets/), preview.*
library/cache/api/        API answers, 24 h fresh, used as a fallback while offline
library/cache/downloads/  downloaded packages
library/cache/patterns/   pattern thumbnails
```

The built-in collection is read from the application folder and is never copied. A damaged index loads as empty instead of crashing.

## Built-in collection

- **55 website templates in 15 template categories.** The Discover groups map them onto the 18 categories in the brief plus News.
  - The 5 new starters are Personal Portfolio, Family Clinic, Community NGO, Auto Garage and Online Store.
  - Every brief category has templates, including the 8 required starter types: corporate, construction, creative agency, SaaS, music artist, photography, restaurant and personal portfolio.
- **Sections:**
  - 72 sections harvested from the templates by `tools/build_sections.py`;
  - 15 headers and 10 footers;
  - each one rendered to a preview PNG by the real renderer.
- **Design resources:**
  - a palette per template (55);
  - 49 type pairings and 30 bundled fonts;
  - 144 Lucide icons;
  - 8 generated patterns and 5 token gradients.

## Using a resource

Every insertion is a single `Session._edit` call, so one insertion is one undo step and is validated like any other edit.

- **Section or template home page:** `apply.adopt` clones the trees with fresh ids. It copies referenced images into the project's `assets/`, re-using an image that is already there (same sha256) and putting a placeholder where a file is missing. `ops.insert_tree` then places the result after the selection.
- **Palette, type pair, font:** `edit_design`.
- **Header:** layout and behaviour only. The site's own name and button stay.
- **Footer:** the design is replaced. The sample brand name becomes the site's name, and links to pages that don't exist become `#`.
- **Pattern:** rendered in the site's dark colours, added to Media and set as the section's photo with an overlay.
- **Gradient:** set as the section background. It replaces any photo, which stays in Media.
- **Icon:** inserted at the selection.
- **Images:** uploaded to Media.
- **New project:**
  - a built-in template uses the normal New Project dialog;
  - an imported template goes through `create_project_from_resource`, which copies the converted document and its assets into a new project folder.

## Window

The left navigation lists: Discover, Website templates, Sections, Headers, Footers, Colour palettes, Type pairings, Fonts, Icons, Patterns and gradients, Images, My imports, Favourites, Recently used, Find online.

- **Centre:** search with a 180 ms debounce, category, tag and folder filters, and a grid with lazy thumbnails. Only items on screen are drawn, 24 per tick.
- **Right:** the details panel shows metadata, licence, compatibility, the import report and buttons for the actions that apply. Actions that can't run (no project open, for example) are disabled and the tooltip says why.
- **Previews:** palettes, type pairings, fonts, icons and gradients are drawn by the window; nothing is downloaded.
- **Responsive preview:** writes the resource with the normal renderer and shows it at 1280, 820 and 390 px.
