"""The built-in component presets.

Sections follow one pattern: section > container (content width) > their content.
Columns stack on mobile by default (render/html.py), and sizes use design tokens and
clamp() so a preset takes on the look of whichever template it joins. Sample text is
written to be replaced: editing it arrives with the property editor in Stage 03.
"""
from __future__ import annotations

from typing import Any

from ..core.document import Node, new_id
from .registry import ComponentDef, register

STRUCTURE, CONTENT, SECTIONS = "Structure", "Content", "Prebuilt sections"
CONTACT = {"page": "contact"}  # Falls back to "#" if a site has no such page.


def n(type_: str, props: dict | None = None, style: dict | None = None, children: list | None = None, *, name: str = "", responsive: dict | None = None) -> Node:
    node: Node = {"id": new_id(), "type": type_, "props": props or {}, "style": style or {}}
    if name:
        node["name"] = name
    if responsive:
        node["responsive"] = responsive
    if type_ in ("section", "container", "columns", "row"):
        node["children"] = children or []
    return node


def box(*children, width: str = "", name: str = "", **style) -> Node:
    return n("container", {"width": width} if width else {}, style, list(children), name=name)


def stack(*children, gap: str = "14px", name: str = "", **style) -> Node:
    return box(*children, name=name, gap=gap, **style)


def column(*children, gap: str = "14px", **style) -> Node:
    return box(*children, name="Column", gap=gap, **style)


def cols(count: Any, *children, gap: str = "$gap", align: str = "", tablet: Any = None, mobile: Any = None) -> Node:
    style = {"gap": gap}
    if align:
        style["align_items"] = align
    responsive: dict[str, Any] = {}
    if tablet is not None:
        responsive["tablet"] = {"props": {"columns": tablet}}
    if mobile is not None:
        responsive["mobile"] = {"props": {"columns": mobile}}
    return n("columns", {"columns": count}, style, list(children), responsive=responsive or None)


def row(*children, gap: str = "14px", **style) -> Node:
    return n("row", {}, {"gap": gap, **style}, list(children))


def h(text: str, level: int = 2, **style) -> Node:
    return n("heading", {"text": text, "level": level}, style)


def p(text: str, muted: bool = True, **style) -> Node:
    props: dict[str, Any] = {"text": text}
    if muted:
        props["muted"] = True
    return n("text", props, style)


def img(label: str, ratio: float = 1.5, subject: str = "abstract", **style) -> Node:
    style.setdefault("border_radius", "$radius")
    media = {"kind": "placeholder", "seed": new_id(), "subject": subject, "ratio": ratio, "label": label}
    return n("image", {"media": media, "alt": label, "ratio": ratio}, style)


def btn(label: str, variant: str = "primary", **style) -> Node:
    return n("button", {"label": label, "href": CONTACT, "variant": variant}, style)


def icon(name: str, **style) -> Node:
    style.setdefault("font_size", "28px")
    return n("icon", {"name": name}, style)


def section(role: str, *children, tone: str = "", **style) -> Node:
    props = {"role": role}
    if tone:
        props["tone"] = tone
    return n("section", props, style, list(children))


def content(*children, gap: str = "") -> Node:
    return box(*children, width="content", **({"gap": gap} if gap else {}))


def title(text: str, sub: str = "", center: bool = False) -> Node:
    style: dict[str, str] = {"margin_bottom": "44px", "max_width": "720px"}
    if center:
        style.update(text_align="center", align_items="center", margin_inline="auto")
    parts = [h(text)] + ([p(sub, font_size="1.08rem")] if sub else [])
    return box(*parts, name="Section heading", gap="12px", **style)


def card(*children, gap: str = "12px", **style) -> Node:
    return box(*children, name="Card", gap=gap, border="1px solid $c-border", border_radius="$card-radius", padding="28px", **style)


# Structure -------------------------------------------------------------------
def _section() -> Node:
    return section("section", content())


def _container() -> Node:
    return box(width="content", gap="$gap")


def _two_columns() -> Node:
    return cols(2, column(), column())


def _three_columns() -> Node:
    return cols(3, column(), column(), column())


def _row() -> Node:
    return row()


def _divider() -> Node:
    return n("divider", {}, {"margin_block": "24px"})


# Content ---------------------------------------------------------------------
def _heading() -> Node:
    return h("Your heading here")


def _paragraph() -> Node:
    return p("Write a sentence or two here. Say what matters to the person reading, in plain words.", False)


def _rich_text() -> Node:
    return n("richtext", {"html": "<p>Write formatted text here, with <strong>emphasis</strong> and lists.</p><ul><li>First point</li><li>Second point</li></ul>"})


def _image() -> Node:
    return img("Image description")


def _gallery() -> Node:
    items = [{"kind": "placeholder", "seed": new_id(), "subject": "abstract", "ratio": 1, "label": f"Gallery image {i + 1}"} for i in range(6)]
    return n("gallery", {"items": items, "columns": 3}, {"gap": "10px"}, responsive={"mobile": {"props": {"columns": 2}}})


def _video() -> Node:
    poster = {"kind": "placeholder", "seed": new_id(), "subject": "abstract", "ratio": 1.78, "label": "Video poster"}
    return n("video", {"poster": poster, "ratio": 1.78, "title": "Play video"}, {"border_radius": "$radius"})


def _button() -> Node:
    return btn("Get in touch", align_self="flex-start")


def _icon() -> Node:
    return icon("star", font_size="32px")


def _link() -> Node:
    return n("link", {"label": "Learn more", "href": CONTACT, "arrow": True}, {"align_self": "flex-start"})


def _spacer() -> Node:
    return box(name="Spacer", height="48px")


# Prebuilt sections -----------------------------------------------------------
def _hero() -> Node:
    copy = column(
        h("A clear headline that says what you do", 1, font_size="clamp(2.6rem,6vw,4.6rem)"),
        p("One or two sentences that explain who this is for and why it matters to them.", font_size="1.16rem", max_width="56ch"),
        row(btn("Get started"), btn("Learn more", "secondary"), margin_top="10px"),
        gap="20px",
    )
    return section("hero", n("columns", {"columns": "6fr 5fr", "width": "content"}, {"gap": "60px", "align_items": "center"},
                             [copy, img("Hero image", .95)], responsive={"tablet": {"props": {"columns": 1}}}))


def _about() -> Node:
    copy = column(h("About us"), p("Tell your story here: where you started, what you care about and how you work."),
                  p("A second paragraph can say what makes you different, and why people choose you."), gap="16px")
    return section("about", n("columns", {"columns": 2, "width": "content"}, {"gap": "64px", "align_items": "center"},
                              [img("About image", 1.1), copy], responsive={"tablet": {"props": {"columns": 1}}}))


def _offer_cards(items: list[tuple[str, str, str]]) -> list[Node]:
    return [card(icon(i), h(t, 3, font_size="1.25rem"), p(x)) for t, x, i in items]


def _services() -> Node:
    cards = _offer_cards([("First service", "A short, plain description of what this service gives people.", "briefcase-business"),
                          ("Second service", "A short, plain description of what this service gives people.", "compass"),
                          ("Third service", "A short, plain description of what this service gives people.", "award")])
    return section("services", content(title("What we do", "A sentence that sums up how you help."), cols(3, *cards, tablet=1)))


def _features() -> Node:
    items = [row(icon("circle-check", font_size="20px"), p(text, False, flex="1", min_width="0"), gap="12px", flex_wrap="nowrap", align_items="flex-start")
             for text in ("The first reason to choose you", "The second reason to choose you", "The third reason to choose you", "The fourth reason to choose you")]
    copy = column(h("Why choose us"), p("A sentence that introduces what sets you apart."), *items)
    return section("features", n("columns", {"columns": 2, "width": "content"}, {"gap": "64px", "align_items": "center"},
                                 [copy, img("Feature image", 1)], responsive={"tablet": {"props": {"columns": 1}}}))


def _testimonials() -> Node:
    quotes = [card(p("“A sentence from a happy client, in their own words.”", False), stack(p("Client name", False, font_weight=600), p("Their role or company", font_size=".9rem"), gap="0", margin_top="auto"), gap="18px")
              for _ in range(3)]
    return section("testimonials", content(title("What people say"), cols(3, *quotes, tablet=1)))


def _team() -> Node:
    people = [column(img(f"Portrait of team member {i}", .85, "portrait"), h("Team member", 3, font_size="1.15rem", margin_top="6px"), p("Their role", font_size=".93rem"), gap="6px") for i in range(1, 5)]
    return section("team", content(title("Meet the team"), cols(4, *people, tablet=2, mobile=2)))


def _pricing() -> Node:
    def plan(name: str, price: str, note: str, variant: str) -> Node:
        lines = [p(f"✓  Plan feature {i}", font_size=".95rem") for i in (1, 2, 3)]
        return card(h(name, 3, font_size="1.2rem"), h(price, 2), p(note, font_size=".92rem"), *lines, btn("Choose plan", variant, margin_top="auto", align_self="stretch"), gap="10px")

    plans = [plan("Basic", "$00", "Who this plan suits.", "secondary"), plan("Standard", "$00", "Who this plan suits.", "primary"), plan("Premium", "$00", "Who this plan suits.", "secondary")]
    return section("pricing", content(title("Pricing", "Simple, clear prices. Replace these with your own.", center=True), n("columns", {"columns": 3}, {"gap": "20px", "align_items": "stretch"}, plans, responsive={"tablet": {"props": {"columns": 1}}})))


def _statistics() -> Node:
    figures = [stack(h("00", 2, font_size="clamp(2.2rem,4vw,3.2rem)"), p(label, font_size=".93rem"), gap="4px") for label in ("Your first figure", "Your second figure", "Your third figure", "Your fourth figure")]
    return section("statistics", content(cols(4, *figures, tablet=4, mobile=2)), padding_block="56px")


def _portfolio() -> Node:
    work = [column(img(f"Project {i}", 1.25), h(f"Project {i}", 3, font_size="1.15rem", margin_top="4px"), p("A short description", font_size=".92rem"), gap="6px") for i in range(1, 7)]
    return section("portfolio", content(title("Selected work"), cols(3, *work, gap="32px 24px", tablet=2)))


def _cta() -> Node:
    return section("call_to_action", content(row(h("Ready to take the next step?", max_width="20em", flex="1 1 320px"), btn("Get in touch"), justify_content="space-between", gap="28px")), tone="primary", padding_block="64px")


def _contact() -> Node:
    form = n("contact_form", {"fields": [{"label": "Your name", "type": "text"}, {"label": "Email address", "type": "email"}, {"label": "Message", "type": "textarea"}], "submit": "Send message"})
    details = column(h("Get in touch"), p("Tell people how soon you reply, and what to include."), p("hello@example.com", False), p("+000 000 000 000", False))
    return section("contact", n("columns", {"columns": "5fr 6fr", "width": "content"}, {"gap": "64px"}, [details, column(form)], responsive={"tablet": {"props": {"columns": 1}}}))


def _faq() -> Node:
    items = [n("faq_item", {"question": f"A question people often ask {i}?", "answer": "A short, direct answer to the question.", "open": i == 1}) for i in (1, 2, 3, 4)]
    return section("faq", box(title("Common questions", center=True), *items, width="narrow"))


def _blog() -> Node:
    posts = [column(img(f"Article {i} image", 1.55), p("Topic, date", font_size=".84rem"), h("A clear article title", 3, font_size="1.25rem"), p("One sentence that makes people want to read on.", font_size=".97rem"), gap="10px") for i in (1, 2, 3)]
    return section("blog", content(title("Latest articles"), cols(3, *posts, gap="30px", tablet=1)))


def _products() -> Node:
    items = [column(img(f"Product {i}", .85), row(h(f"Product {i}", 3, font_size="1.1rem"), p("$00", False, font_weight=600), justify_content="space-between", flex_wrap="nowrap", margin_top="6px"), p("A short description", font_size=".9rem"), gap="4px") for i in range(1, 5)]
    return section("products", content(title("Products"), cols(4, *items, gap="30px 20px", tablet=2, mobile=2)))


_CATALOGUE = (
    ("section", "Section", STRUCTURE, "square", "A full-width band of the page", _section),
    ("container", "Container", STRUCTURE, "box", "Groups elements and sets their width", _container),
    ("two-columns", "Two columns", STRUCTURE, "columns-2", "Two side-by-side columns that stack on mobile", _two_columns),
    ("three-columns", "Three columns", STRUCTURE, "columns-3", "Three side-by-side columns that stack on mobile", _three_columns),
    ("row", "Row", STRUCTURE, "rows-3", "A line of elements that wraps when short of room", _row),
    ("divider", "Divider", STRUCTURE, "minus", "A thin separating line", _divider),
    ("heading", "Heading", CONTENT, "heading-1", "A title", _heading),
    ("paragraph", "Paragraph", CONTENT, "pilcrow", "A block of plain text", _paragraph),
    ("rich-text", "Rich text", CONTENT, "text", "Formatted text with lists and links", _rich_text),
    ("image", "Image", CONTENT, "image", "One replaceable image", _image),
    ("gallery", "Gallery", CONTENT, "gallery-horizontal", "A grid of images", _gallery),
    ("video", "Video", CONTENT, "video", "A video with a poster image", _video),
    ("button", "Button", CONTENT, "mouse-pointer-click", "A call to action", _button),
    ("icon", "Icon", CONTENT, "star", "A symbol from the icon set", _icon),
    ("link", "Link", CONTENT, "link", "A text link", _link),
    ("spacer", "Spacer", CONTENT, "move-vertical", "Empty vertical space", _spacer),
    ("hero", "Hero", SECTIONS, "sparkles", "The opening of a page", _hero),
    ("about", "About", SECTIONS, "user-round", "Who you are", _about),
    ("services", "Services", SECTIONS, "briefcase-business", "What you offer", _services),
    ("features", "Features", SECTIONS, "list-checks", "Reasons to choose you", _features),
    ("testimonials", "Testimonials", SECTIONS, "star", "What people say", _testimonials),
    ("team", "Team", SECTIONS, "users-round", "The people involved", _team),
    ("pricing", "Pricing", SECTIONS, "badge-dollar-sign", "Plans and prices", _pricing),
    ("statistics", "Statistics", SECTIONS, "chart-column", "Key numbers", _statistics),
    ("portfolio", "Portfolio", SECTIONS, "images", "Selected work", _portfolio),
    ("cta", "Call to action", SECTIONS, "megaphone", "Ask the visitor to act", _cta),
    ("contact", "Contact", SECTIONS, "mail", "Details and a form", _contact),
    ("faq", "FAQ", SECTIONS, "circle-help", "Questions and answers", _faq),
    ("blog", "Blog posts", SECTIONS, "newspaper", "Recent articles", _blog),
    ("products", "Products", SECTIONS, "shopping-bag", "Items for sale", _products),
)
for _id, _label, _group, _icon_name, _text, _build in _CATALOGUE:
    register(ComponentDef(_id, _label, _group, _icon_name, _text, _build))
