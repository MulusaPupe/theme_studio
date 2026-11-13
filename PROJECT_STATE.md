# Project state

Updated 2026-11-13. A git repository (remote `origin`: GitHub `MulusaPupe/theme_studio`); this work is committed on the branch `living-elements`, not pushed.

## Where things stand

- **Stages 00–06:** complete. The editor, property editor, media, design, pages, WordPress block theme export and static export are working.
- **Milestone: Template & Creative Resource Library:** implemented and tested. 902 tests pass. See `docs/TEST_REPORT.md`.
- **Part 3, Home and splash:** done. Motion is in CHITNAS, Vicreations and 18 full templates; there is a Home button and a start-up splash screen.
- **Living elements and one-page templates (parts 1 and 2):** done. There are 35 animated illustrations, a countdown, a progress bar, glass blur and living backgrounds, plus 14 one-page templates. 1067 tests pass.
- **Samples:** Vicreations (3 variations) and the CHITNAS redesign proposal are in `samples/`.

## The library in one paragraph

A **Library** button in the rail (or Ctrl+Shift+L) opens the Creative Resource Library. It includes:

- 69 templates covering every category in the brief, 14 of them one-page launch and maintenance pages;
- 35 animated illustrations;
- 72 sections, 15 headers and 10 footers;
- palettes, type pairings, 30 fonts, 144 icons, patterns and gradients;
- an importer for HTML/CSS sites, WordPress block themes and patterns, Mulusa files and image collections;
- a "Find online" panel for the WordPress.org directories and GitHub.

Imports are inspected safely and never executed. Each import lists what was lost and records the licence it found. Inserting anything is one undo step.

Read more:

- `docs/TEMPLATE_LIBRARY_ARCHITECTURE.md`
- `docs/RESOURCE_IMPORT_GUIDE.md`
- `docs/RESOURCE_LICENSING_GUIDE.md`

## Known limitations

- **SVG files** in imported packages are reported, not imported. The media pipeline is Pillow-based and does not accept SVG.
- **Remote images** referenced by an imported site are not downloaded. They become placeholders.
- **The countdown** reads the visitor's clock. A wrong clock on the visitor's device shows a wrong time left. The date itself is printed under the numbers.
- **Not carried over:** JavaScript behaviour, CSS animations, hover and focus rules, attribute and sibling selectors, and `@font-face` fonts that aren't bundled. Each import report lists them.
- **Classic PHP WordPress themes** are stored for reference only.
- **Dynamic blocks** (query loops, navigation, template parts) in block themes are reported, not converted. The studio's own header and footer take their place.
- **The HTML importer guesses page structure** from headings, ids and class names. Unusual markup can produce plain stacked sections that need tidying in the editor.
- **Online discovery** needs the network the first time a search is made; after that the cached answer is used offline. GitHub's unauthenticated search allows a small number of searches per minute.
  - The finished Find online panel was not tried against the live APIs, because the network was down at the end of the milestone. Its logic is tested with a fake fetcher, and the underlying calls were tried live earlier.
- **No person has used the library window** on a real display yet. It was checked through tests and offscreen screenshots.
- **Imported templates** show the package's own screenshot when it has one (WordPress themes do); otherwise they show an icon. No preview is rendered for them yet.
- **Folders are one level deep.** Moving and renaming apply to imported items only; built-in items can be favourited but not renamed.

## Next steps (not started)

- A person walks through the library window on a real display.
- Try the online panel against the live APIs.
- Render previews for imported templates and sections.
- SVG support in the media library.
