# Working notes (handoff scratchpad)

Short memory for sessions. The full record is PROJECT_CONTEXT.md and DEVELOPMENT_LOG.md.

## Rules that must not drift
- Layers: ui -> exporters/render/components -> core. Core has no Qt. tests/test_architecture.py enforces this.
- Every document change goes through History.apply. No WordPress in core, render or the canvas.
- Never load a page from inside acceptNavigationRequest (crashes the engine). It only refuses navigation now.
- JavaScript never changes the document. Bridge slots stay narrow and validate every argument.
- Structural edits go through Session._edit, core/operations.py and History.apply.
- Header and footer are shared: no move, copy, delete or preset.
- Sections over a photo use tone=image. Don't use muted text elsewhere without a tone behind it.
- After changing tools/template_*.py or build_templates.py: run build_templates.py, then build_thumbnails.py. Exit code non-zero means a layout fault.
- Review renders by eye at the end of each stage (build_thumbnails.py --sheet, tools/screenshots.py). Tests missed the worst visual faults in Stage 01.

## Testing patterns
- pytest-qt closes qtbot widgets before fixtures finish, so the window fixture closes the window itself.
- no_dialogs fixture fails on any unexpected modal.
- page.runJavaScript returns arrays as empty: return JSON.stringify and parse.
- body has class mts-tone-default, so `closest('[class*=mts-tone-]')` can match body.
- Offscreen WebEngine needs QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu; grab() then returns real pixels.
- Real input: QTest on view.focusProxy(), with coordinates multiplied by canvas.zoom. Set focus there to test shortcuts as a user meets them.
- Offscreen drops window activation when the engine redraws, so shortcuts stop firing; call activateWindow() after an edit. Wayland does not do this (checked).
- Offscreen has no drag loop: QDrag.exec returns at once. Send drag events to windowHandle() to exercise hit-testing.
- Very tall grab() captures can leave images blank. Check naturalWidth before believing it.
- After an edit wait for loadFinished and window.mtsReady.
- Don't style QTreeWidget::branch: it removes the expand arrows.
- Profile before guessing on slowness: Stage 02's 870 ms edit was SVG icons, not rendering.

## Status
Stage 02 done, awaiting approval. Stage 03 must not start without the owner's go-ahead. Still to confirm by hand: a real mouse drag from the library.

## Status 2026-11-04
Stage 03 done, awaiting approval. Last run: 677 passed, 15 warnings in 247.22s (0:04:07). Open: live edit median 163 ms (unprofiled); real mouse drag from library unconfirmed. See DEVELOPMENT_LOG.md.
