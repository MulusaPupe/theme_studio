"""The design pass (2026-11-13): motion and finish in base.css, and what the template kit no longer makes."""
from __future__ import annotations

import re

from mulusa_theme_studio.core.document import walk_document
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.render.site import BASE_CSS, write_site

CSS = BASE_CSS.read_text(encoding="utf-8")
EXCLUDE = "body:not(.mts-editing):not(.editor-styles-wrapper)"


def test_the_editor_canvas_is_marked_so_motion_never_runs_while_designing(tmp_path):
    doc = TemplateLibrary().load("construction/heavy-civil")
    editing = write_site(doc, tmp_path / "e", editor=True)
    published = write_site(doc, tmp_path / "p", editor=False)
    assert "mts-editing" in editing.body_class
    assert "mts-editing" not in published.body_class
    assert "mts-editing" not in (tmp_path / "p" / "index.html").read_text(encoding="utf-8")


# Looping "living" elements are meant to be seen moving while designing: a redraw only restarts a loop,
# it never hides content the way a half-played entrance would. Everything else stays out of the editors.
LIVING_LOOPS = ("mts-loading", "mts-aurora", "mts-scanline", "mts-twinkle", "mts-wave")


def test_every_animation_is_kept_out_of_both_editors():
    # Any rule that starts an entrance or scroll animation must carry the exclusion for the canvas and the block editor.
    for rule, name in re.findall(r"([^{}]+)\{[^{}]*\banimation(?:-name)?:\s*(mts-[a-z-]+)", CSS):
        if name in LIVING_LOOPS:
            assert "mts-editing" not in rule
            continue
        assert EXCLUDE in rule, rule.strip()


def test_motion_respects_reduced_motion_and_never_needs_script():
    assert "@media (prefers-reduced-motion:no-preference)" in CSS
    reduce = CSS[CSS.index("@media (prefers-reduced-motion:reduce)"):]
    assert "animation:none!important" in reduce and "transition-duration:0s!important" in reduce
    assert "<script" not in CSS and "javascript:" not in CSS
    # Scroll-linked motion only where the browser supports it, so older browsers get a still page.
    assert "animation-timeline" not in CSS.split("@supports (animation-timeline:view())")[0]


def test_browser_surfaces_are_themed():
    for piece in ("::selection{", ":focus-visible{", "caret-color:", "scrollbar-color:", "text-wrap:balance"):
        assert piece in CSS, piece


def test_templates_carry_no_eyebrow_labels():
    for info in TemplateLibrary().templates:
        doc = TemplateLibrary().load(info.id)
        assert not [n["id"] for n in walk_document(doc) if n.get("name") == "Eyebrow"], info.id


def test_redesigned_templates_use_the_new_sections():
    roles = {tid: [n["props"].get("role") for n in TemplateLibrary().load(tid)["pages"][0]["nodes"]]
             for tid in ("construction/heavy-civil", "corporate/modern-consulting", "art/design-studio")}
    assert all("statement" in r for r in roles.values())
    assert "statistics" not in roles["construction/heavy-civil"]
