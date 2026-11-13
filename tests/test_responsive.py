"""Device overrides in the document and in what the renderer and exporter write."""
import pytest

from mulusa_theme_studio.core import properties as props
from mulusa_theme_studio.core.document import validate_document, walk_document
from mulusa_theme_studio.core.errors import StudioError
from mulusa_theme_studio.core.templates import TemplateLibrary
from mulusa_theme_studio.exporters.wordpress.translate import Rules
from mulusa_theme_studio.render.html import RenderContext, render_node


@pytest.fixture
def doc():
    return TemplateLibrary().load("corporate/corporate-classic")


def first(doc, kind):
    return next(n for n in walk_document(doc) if n.get("type") == kind)


def test_a_mobile_override_leaves_desktop_alone(doc):
    node = first(doc, "heading")
    before = dict(node.get("style") or {})
    props.set_style(doc, node["id"], "font_size", "20px", "mobile")
    assert node["style"] == before
    assert node["responsive"]["mobile"]["style"]["font_size"] == "20px"


@pytest.mark.parametrize("scope,own", [("tablet", "tablet"), ("mobile", "mobile")])
def test_origin_reports_an_override(doc, scope, own):
    node = first(doc, "heading")
    assert props.style_origin(node, "font_size", scope)[1] == ""
    props.set_style(doc, node["id"], "font_size", "20px", scope)
    assert props.style_origin(node, "font_size", scope) == ("20px", own)


def test_mobile_inherits_through_tablet_because_a_phone_matches_both_rules(doc):
    node = first(doc, "heading")
    props.set_style(doc, node["id"], "font_size", "30px", "tablet")
    assert props.style_origin(node, "font_size", "mobile") == ("30px", "tablet")
    props.set_style(doc, node["id"], "font_size", "20px", "mobile")
    assert props.style_origin(node, "font_size", "mobile") == ("20px", "mobile")


def test_resetting_one_style_returns_to_inherited_and_leaves_no_empty_override(doc):
    node = first(doc, "heading")
    props.set_style(doc, node["id"], "font_size", "20px", "mobile")
    props.set_style(doc, node["id"], "font_size", None, "mobile")
    assert props.style_origin(node, "font_size", "mobile")[1] == ""
    assert "responsive" not in node or "mobile" not in node["responsive"]


def test_reset_device_clears_styles_columns_and_visibility(doc):
    node = first(doc, "columns")
    props.set_style(doc, node["id"], "gap", "4px", "mobile")
    props.set_device_columns(doc, node["id"], "mobile", 2)
    props.set_hidden(doc, node["id"], "mobile", True)
    props.reset_device(doc, node["id"], "mobile")
    assert "mobile" not in (node.get("responsive") or {})
    assert validate_document(doc) == []


def test_hidden_and_columns_need_a_device(doc):
    node = first(doc, "columns")
    with pytest.raises(StudioError):
        props.set_hidden(doc, node["id"], "", True)
    with pytest.raises(StudioError):
        props.set_device_columns(doc, node["id"], "", 2)
    with pytest.raises(StudioError):
        props.set_device_columns(doc, first(doc, "heading")["id"], "mobile", 2)


def _rendered_css(doc, node):
    ctx = RenderContext(doc=doc, editor=False, current_page=doc["pages"][0]["id"])
    render_node(node, ctx)
    return ctx


def test_the_renderer_writes_overrides_inside_the_right_query(doc):
    node = first(doc, "heading")
    props.set_style(doc, node["id"], "font_size", "21px", "mobile")
    props.set_style(doc, node["id"], "font_size", "33px", "tablet")
    ctx = _rendered_css(doc, node)
    assert any("21px" in r for r in ctx.responsive["mobile"]) and not any("21px" in r for r in ctx.responsive["tablet"])
    assert any("33px" in r for r in ctx.responsive["tablet"])
    assert not any("21px" in r or "33px" in r for r in ctx.rules)


def test_the_renderer_hides_only_on_that_device(doc):
    node = first(doc, "heading")
    props.set_hidden(doc, node["id"], "mobile", True)
    ctx = _rendered_css(doc, node)
    assert any("display:none" in r for r in ctx.responsive["mobile"])
    assert not any("display:none" in r for r in ctx.rules + ctx.responsive["tablet"])


def test_columns_set_for_tablet_still_stack_on_a_phone_in_the_export(doc):
    """Found on the real site: an !important tablet rule beat the phone's default, unlike on the canvas."""
    node = first(doc, "columns")
    props.set_device_columns(doc, node["id"], "tablet", 3)
    rules = Rules()
    rules.add("n-a", {}, node=node)
    rules.column_defaults("n-a", node)
    css = rules.css()
    mobile = css[css.index("@media (max-width:640px)"):]
    assert "grid-template-columns:minmax(0,1fr)!important" in mobile


def test_the_exported_css_keeps_devices_apart(doc):
    node = first(doc, "heading")
    props.set_style(doc, node["id"], "font_size", "21px", "mobile")
    props.set_hidden(doc, first(doc, "image")["id"], "tablet", True)
    rules = Rules()
    rules.add("n-a", node.get("style") or {}, node=node)
    rules.add("n-b", {}, node=first(doc, "image"))
    css = rules.css()
    mobile = css[css.index("@media (max-width:640px)"):]
    tablet = css[css.index("@media (max-width:1024px)"):css.index("@media (max-width:640px)")]
    assert "21px" in mobile and "21px" not in tablet
    assert "display:none" in tablet and "display:none" not in mobile
