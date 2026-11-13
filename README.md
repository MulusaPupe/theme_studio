# MULUSA THEME STUDIO

A visual website and theme development environment by Mulusa Innovations.

*Design visually. Customise freely. Export professionally.*

**Status: Stages 01 to 06 built (2026-11-12), awaiting the owner's approval.** Choose one of 69 templates, edit everything visually (text, images, colours, fonts, spacing), manage pages and the menu, design each device separately, and export either a WordPress block theme or a static website. Stages 07 (optional AI) and 08 (packaging) are not started. The Template & Creative Resource Library milestone (2026-11-13) is built and tested; see `PROJECT_STATE.md`.

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
| 69 templates in 16 categories (14 one-page launch and maintenance pages), with search and filter | Working |
| Animated illustrations, countdown, progress bar, glass and living backgrounds | Working |
| Home button (back to the start screen) and start-up splash screen | Working |
| Creative Resource Library (Ctrl+Shift+L): 72 sections, 15 headers, 10 footers, palettes, type pairings, fonts, icons, patterns, gradients | Working |
| Import HTML/CSS sites, WordPress block themes and patterns, Mulusa files and images, safely, with a loss report and licence | Working |
| Find online: WordPress.org patterns and themes, GitHub, cached for offline use | Working (finished panel not yet tried on the live network) |
| Template preview, including every page | Working |
| Desktop, tablet and mobile preview at true device widths, plus zoom | Working |
| New, open, save, autosave and crash recovery | Working |
| Undo and redo | Working |
| Open the website in your browser | Working |
| Click to select any element on the canvas | Working |
| 30 components and prebuilt sections: drag on or double-click | Working |
| Rearrange, duplicate, delete, move, copy and paste | Working |
| Layers: expand, navigate, and stay in step with the canvas | Working |
| Property editor, media library with crop, global colours, fonts and spacing | Working |
| Pages and menu: add, rename, reorder, delete, homepage, post templates | Working |
| Separate tablet and mobile design, hiding elements per device | Working |
| Live post lists (filled with real posts in WordPress) | Working |
| Static website export (HTML and CSS for any host) | Working |
| WordPress block theme export, with an optional content plugin | Working |
| Canvas resize handles | Not built: use the width and height fields |
| Optional AI assistant | Stage 07 |
| Installer and packaging | Stage 08 |

Unbuilt features are disabled or labelled in the interface, with the stage that delivers them.

## Tests and tools

```bash
.venv/bin/python -m pytest                       # all automated tests, six in parallel (about 2 minutes)
.venv/bin/python -m pytest -n 0 tests/test_x.py  # one file, in a single process
.venv/bin/python tools/build_templates.py        # regenerate template.json files from the specs
.venv/bin/python tools/build_thumbnails.py       # thumbnails, plus the layout audit of every page at 3 widths
.venv/bin/python tools/screenshots.py OUT_DIR    # screenshots of the real window
.venv/bin/python tools/site_screenshots.py SITE OUT   # full-page desktop and phone shots of an exported static site
tests/wordpress/check_exports.sh EXPORTS SLUG...      # install exported themes in a throwaway WordPress (Podman) and check them
```

## Worked example: three sites for a real client

`tools/build_vicreations.py` turns the Vicreations Investment Limited business profile (PDF) into three design variations of the full company website (Bold, Corporate, Editorial), each from a different template and each covering all four divisions, using only the editor's own commands. It shows the whole workflow: choose a template, add photos to the media library, change colours, rewrite text, remove sections, rename pages and the menu, set a phone-only style, add a live posts list, then export as WordPress and as a static site. See `docs/vicreations-walkthrough.md`; the results are in `samples/Vicreations/` and the screenshots in `docs/screenshots/vicreations/`.

See `PROJECT_CONTEXT.md` for architecture and decisions, and `DEVELOPMENT_LOG.md` for the history.
