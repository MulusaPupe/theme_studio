# Test report: Template and Creative Resource Library milestone

Date: 2026-11-13. Machine: Fedora 44, Python 3.14.3, PySide6 with QtWebEngine, offscreen platform. Command:

```
.venv/bin/python -m pytest tests -q -n 6
```

**Afterwards:** all 69 thumbnails were rebuilt (layout audit: 0 problems), and `test_templates.py`, `test_living.py` and `test_library.py` were run again: 523 passed. In real WordPress (Podman, `check_exports.sh`), CHITNAS, Vicreations Corporate and two one-page themes had every page at HTTP 200 with no PHP messages and 0 invalid blocks. The countdown script was served and ticked down live.

**Update, part 3, Home and splash (same day): 1125 passed, 1 failed in 18 min (run with 2 workers because memory was short).** The failure was `test_editor.py::test_the_outline_survives_a_burst_of_edits`, a timing test. It then passed 3 times out of 3 when run on its own, so it is load-sensitive rather than broken; it is not marked as passed here. New tests: Home (closing a project with Cancel and Discard, leaving a preview), the splash progress bar, and motion rules for the full templates (one living background per page, none on photographs, drawings all or nothing per grid).

**Update, living elements (same day): 1067 passed, 0 failed in 250 s.** This adds `tests/test_living.py` (64 tests). It also scopes the full-website template rules to full websites and adds rules for the 14 one-page templates. See DEVELOPMENT_LOG.md.

**Result of the milestone's last full run: 902 passed, 0 failed, 15 warnings in 123.32 s.** The warnings come from existing tests and are unrelated to the library. Before the milestone the suite was 829 tests. The library's own tests (`tests/test_library.py`, 46 tests) and the architecture tests were run again after the last code change (the template screenshot preview): 52 passed.

Every number on this page comes from a run that actually happened. No test was skipped or marked passed by hand.

## Coverage of the 18 required areas

| # | Area | Tests (tests/test_library.py unless noted) |
|---|---|---|
| 1 | Resource indexing | `test_builtin_collection_is_indexed_and_complete`, `test_every_builtin_section_exists_validates_and_has_a_preview` |
| 2 | Search | `test_search_matches_every_word_across_name_description_and_tags` |
| 3 | Filtering | `test_filters_combine` (category, tags, favourites, compatibility, kind) |
| 4 | Metadata | `test_metadata_round_trips_through_json`, `test_store_persists_and_manages_items`, `test_a_damaged_index_does_not_crash_the_library` |
| 5 | Import validation | `test_inspection_classifies_packages`, `test_a_package_with_nothing_usable_is_refused_and_leaves_nothing` |
| 6 | ZIP safety | `test_path_traversal_is_refused` (4 cases), `test_symlinks_are_refused`, `test_zip_bombs_are_refused`, `test_unwanted_files_are_skipped_not_extracted` |
| 7 | HTML import | `test_html_site_imports_as_an_editable_template` (pages, nav links, columns, mobile overrides, images, scripts and handlers removed, original kept) |
| 8 | CSS parsing | `test_css_parser_computes_specificity_vars_and_media`, `test_css_parser_survives_garbage` |
| 9 | Block pattern import | `test_block_markup_parses_and_converts`, `test_pattern_file_imports_as_a_section` (PHP read as text, not run) |
| 10 | Block theme recognition | `test_block_theme_imports_with_patterns_and_palette`, plus classic theme kept as reference in `test_inspection_classifies_packages` |
| 11 | Asset import | `test_image_collection_imports_as_media`, `test_imported_sections_bring_their_images` |
| 12 | Duplicate detection | `test_the_same_package_imports_once`, image dedupe in `test_imported_sections_bring_their_images` |
| 13 | Licence metadata | `test_licences_are_identified_and_unknown_is_never_redistributable`, `test_unlicensed_repositories_are_links_only` |
| 14 | Document conversion | validation asserted in the HTML, theme, pattern and project tests |
| 15 | Undo/redo after insertion | `test_inserting_a_section_is_one_undo_step`, `test_inserted_ids_are_fresh_each_time`, `test_design_resources_apply_and_undo`, `test_patterns_and_gradients_need_a_section_and_then_apply` |
| 16 | Responsive previews | `test_every_builtin_section_renders_with_responsive_rules`, `test_html_site_imports_as_an_editable_template` (mobile overrides) |
| 17 | Export compatibility | `test_a_project_starts_from_an_imported_template_and_exports` (static ZIP), `test_documents_with_inserted_sections_export_to_wordpress` (theme checker: no errors); `tests/test_wordpress_export.py::test_all_fifty_five_templates_export_with_no_errors` |
| 18 | Offline use | `test_remote_search_caches_and_works_offline`, `test_the_library_works_with_no_network_at_all` (sockets blocked), `test_only_official_https_hosts_are_fetched` (5 cases) |
| — | Failure cases, malformed packages | `test_malformed_packages_fail_cleanly` (empty, not a ZIP, truncated ZIP), traversal, symlink and bomb tests |
| — | Window | `test_library_window_views_and_insert` (every view fills, insert from the grid, empty search) |
| — | Architecture | `tests/test_architecture.py::test_the_resource_library_has_no_qt_and_no_editor_dependency`, `test_imported_code_is_never_executed` |

## Changed existing tests

The template count went from 50 to 55, so these were updated:

- `test_templates.py::test_fifty_five_templates_in_fifteen_categories`: the original 10 categories keep 5 templates each, and the 5 new categories have 1 each;
- the distinct-thumbnail count;
- `test_ui.py`: the panel and dialog counts;
- `test_wordpress_export.py::test_all_fifty_five_templates_export_with_no_errors`: it now exports and checks all 55 templates, including the 5 new ones.

`conftest.py` now also isolates `MTS_DATA_DIR`, so tests never touch the user's real library.

## Checked by hand, not by pytest

- **Live network**, earlier in the session before the network went down:
  - a WordPress.org Pattern Directory search and import;
  - a Twenty Twenty-Four download and import (8 sections on its home page, 35 pattern sections);
  - a GitHub search that returned an empty result without error.
- **Not exercised live:** the finished **Find online** panel was not run against the live APIs after it was built, because the network was down. Its logic is covered by the fake-fetcher tests above.
- **Offscreen screenshots** of the window (Discover, Sections, Templates, Palettes, Patterns, Find online) and an import dialog run on a sample HTML ZIP with an MIT licence. This found and fixed a white grid background and stale buttons in the details panel.
- **Not walked by a person on a real display:** the library window, including mouse interaction and the file dialogs.
