# Importing resources

Open the library (rail button **Library** or Ctrl+Shift+L) and choose **Import a package…**. Pick a file or a folder. The studio inspects it first and shows:

- what kind of package it is;
- its pages, stylesheets and images;
- its licence;
- the expected result (fully compatible, partially compatible or reference only);
- any problems.

Nothing is imported until you press **Import**.

## What can be imported

| Package | How it is recognised | Result |
|---|---|---|
| HTML/CSS website (ZIP or folder) | `.html` files; `index.html` first, up to 30 pages | A template. Each page becomes a page; header, navigation and footer are rebuilt; styles are applied. |
| Single `.html` file | file type | A one-page template |
| WordPress block theme | `style.css` with `Theme Name:` plus `templates/*.html` | A template built from front-page, home or index (whichever is richest), plus every pattern in `patterns/` as its own section |
| WordPress block patterns | `.php` or `.html` files with `<!-- wp:` markup, or Pattern Directory JSON | Sections |
| Mulusa template, project or section JSON | `schema: mulusa.*` | A template or section, fully compatible |
| Image collection | only images | An image set that can be added to Media |
| Classic (PHP) WordPress theme | `style.css` without block templates | Kept for reference only. Its pages are produced by PHP at run time and can't be converted without running it. |

The original package is always kept unchanged in the item's `original/` folder. **Show the original package** opens it.

## Safety

A package is treated as untrusted:

- **Never executed.** JavaScript and PHP are never run. PHP is only read as text: translation calls such as `esc_html_e('Hello')` become their text, and the rest is removed. Inline `on…` handlers, `<script>` and `javascript:` links are removed.
- **ZIP extraction refuses:**
  - absolute paths and `..` escapes;
  - symbolic links and device files;
  - encrypted archives;
  - more than 4,000 files;
  - files over 60 MB or totals over 400 MB;
  - suspicious compression ratios (zip bombs).
- **Sizes are re-checked while copying,** in case the headers lie.
- **Only website file types are extracted.** Executables, scripts such as `.sh` and other files are skipped and listed.
- **Images are re-encoded through Pillow** before use. Unreadable images are reported.
- **Remote images are not downloaded during import.** They become placeholders you can replace.

## What is converted, and what is reported

Converted:

- headings, paragraphs and rich text;
- lists, quotes and tables (as text);
- images, galleries and https video embeds;
- buttons and links, with internal page links kept;
- grid and flex layouts as columns, with tablet and phone stacking;
- section backgrounds with an overlay, colours, spacing, typography and borders;
- CSS custom properties;
- `@media` rules, as tablet and phone overrides;
- WordPress spacing presets, palette slugs and cover blocks;
- media and text blocks, details (as FAQ items) and `core/pattern` references.

Each import lists what it could not carry over. That report is shown after the import and in the item's details:

- scripts and event handlers;
- hover and focus states (the editor's hover layer is used instead);
- `@keyframes` animations and `@font-face` for fonts that aren't bundled;
- remote images and SVG files;
- attribute and sibling selectors;
- form actions (forms become the editor's contact form);
- dynamic WordPress blocks: query loops, navigation and template parts.

## Duplicates

Importing the same file again, or a folder with identical contents, is detected by its sha256. The existing item is shown and nothing new is added.

## Finding resources online

**Find online** searches the WordPress.org Pattern Directory, the WordPress.org Theme Directory (block themes) and GitHub repositories tagged `wordpress-block-theme` or `html-template`.

- Results are cached for 24 hours and are still shown while offline.
- Nothing downloads until you press **Import into my library**.
- A GitHub repository without a recognised open licence is offered as a link only.
- The *Other sources* list links to places where you download a package yourself and then import it. Webflow, Framer, Awwwards and Codrops are listed as inspiration only.

## After importing

Imported items appear under **My imports**. From the details panel you can:

- start a new project from a template;
- insert its home page sections into the open page;
- insert a single section;
- add images to Media;
- rename the item, move it to a folder, add it to favourites, open the source page or delete it.

Deleting an item from the library does not affect projects that already use it, because inserted content is copied into the project.
