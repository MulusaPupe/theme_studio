# MULUSA THEME STUDIO

A visual website and theme development environment by Mulusa Innovations.

*Design visually. Customise freely. Export professionally.*

**Status: Stage 02 of 8 complete.** You can browse 50 templates, create projects, select any element on the canvas, drag in components and prebuilt sections, rearrange, duplicate, delete, and undo. Editing text and styles, and export, are not built yet; see the table below.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/mulusa-theme-studio
```

Needs Python 3.12 or newer. Tested on Fedora Linux with Python 3.14 and PySide6 6.12.

## What works today

| Area | Status |
| --- | --- |
| Main window, design system, dark and light appearance | Working |
| 50 templates in 10 categories, with search and filter | Working |
| Template preview, including every page | Working |
| Desktop, tablet and mobile preview at true device widths, plus zoom | Working |
| New, open, save, autosave and crash recovery | Working |
| Undo and redo | Working |
| Open the website in your browser | Working |
| Click to select any element on the canvas | Working |
| 30 components and prebuilt sections: drag on or double-click | Working |
| Rearrange, duplicate, delete, move, copy and paste | Working |
| Layers: expand, navigate, and stay in step with the canvas | Working |
| Resize handles, editing properties, media library, global design controls | Stage 03 |
| Managing pages, responsive editing | Stage 04 |
| Static website export | Stage 05 |
| WordPress block theme export | Stage 06 |
| Optional AI assistant | Stage 07 |
| Installer and packaging | Stage 08 |

Unbuilt features are disabled or labelled in the interface, with the stage that delivers them.

## Tests and tools

```bash
.venv/bin/python -m pytest                       # automated tests
.venv/bin/python tools/build_templates.py        # regenerate template.json files from the specs
.venv/bin/python tools/build_thumbnails.py       # thumbnails, plus the layout audit of every page at 3 widths
.venv/bin/python tools/screenshots.py OUT_DIR    # screenshots of the real window
```

See `PROJECT_CONTEXT.md` for architecture and decisions, and `DEVELOPMENT_LOG.md` for the history.

**Status (2026-11-04):** Stage 03 complete, awaiting approval. Canvas resize handles were not built; use the width and height fields.
