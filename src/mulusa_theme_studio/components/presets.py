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

STRUCTURE, CONTENT, SECTIONS, POST_TEMPLATE = "Structure", "Content", "Prebuilt sections", "Post template"
MOTION = "Motion and graphics"
GLASS = {"background": "rgba(255,255,255,0.1)", "border": "1px solid rgba(255,255,255,0.18)", "backdrop_filter": "blur(14px) saturate(140%)",
         "box_shadow": "0 24px 70px rgba(0,0,0,0.35)", "border_radius": "22px"}
CONTACT = {"page": "contact"}  # Falls back to "#" if a site has no such page.


def n(type_: str, props: dict | None = None, style: dict | None = None, children: list | None = None, *, name: str = "", responsive: dict | None = None) -> Node:
    node: Node = {"id": new_id(), "type": type_, "props": props or {}, "style": style or {}}
    if name:
        node["name"] = name
    if responsive:
        node["responsive"] = responsive
    if type_ in ("section", "container", "columns", "row", "query"):
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


def field(name: str, *, props: dict | None = None, **style) -> Node:
    return n("post_field", {"field": name, **(props or {})}, style)


def post_card() -> Node:
    """The design repeated for each post. It stays ordinary elements, so all of it can be restyled."""
    text = stack(
        field("categories", font_size=".82rem"),
        field("title", props={"level": 3, "link": True}, font_size="1.25rem"),
        field("excerpt", props={"words": 24}, font_size=".97rem"),
        row(field("date", font_size=".82rem"), field("author", font_size=".82rem"), gap="10px"),
        field("read_more", props={"label": "Read more"}),
        gap="10px",
    )
    return box(field("featured_image", props={"ratio": 1.5, "link": True}, border_radius="$radius"), text, name="Post card", gap="14px")


def query_node(count: int = 3, columns: int = 3, **settings: Any) -> Node:
    props = {"source": {"kind": "posts", "count": count, "order_by": "date", "order": "desc", "categories": []}, "layout": "grid", "columns": columns, "image_position": "top", "pagination": False, "empty_text": "No posts yet.", "hide": []}
    props.update(settings)
    return n("query", props, {}, [post_card()], name="Posts list")


def _posts_list() -> Node:
    return query_node()


def _latest_posts() -> Node:
    return section("posts", content(title("Latest posts"), query_node()))


def _post_title() -> Node:
    return field("title", props={"level": 1})


def _post_image() -> Node:
    return field("featured_image", props={"ratio": 1.8}, border_radius="$radius")


def _post_body() -> Node:
    return field("content")


def _post_meta() -> Node:
    return row(field("date", font_size=".9rem"), field("author", font_size=".9rem"), field("categories", font_size=".9rem"), gap="14px")


def default_single_nodes() -> list[Node]:
    """A plain post template, so a site always has one that follows its design."""
    return [section("post", box(_post_meta(), _post_title(), _post_image(), field("content", margin_top="12px"), field("tags", font_size=".9rem"), width="narrow", gap="18px"))]


def default_archive_nodes() -> list[Node]:
    return [section("posts", content(query_node(count=9, pagination=True, source={"kind": "posts", "follow_page": True})))]


def default_not_found_nodes() -> list[Node]:
    return [section("not_found", box(h("Page not found", 1), p("That address does not lead anywhere. Try the homepage instead."), btn("Go to the homepage"), width="narrow", gap="16px", align_items="flex-start"))]


PAGE_STARTERS = {
    "blank": ("Blank", lambda: []),
    "content": ("Hero and text", lambda: [_hero(), _about()]),
    "services": ("Services", lambda: [_hero(), _services(), _cta()]),
    "posts": ("Posts list", lambda: [_hero(), _latest_posts()]),
    "contact": ("Contact", lambda: [_contact()]),
}
ROLE_STARTERS = {"single": default_single_nodes, "archive": default_archive_nodes, "not_found": default_not_found_nodes}


# Motion and graphics ---------------------------------------------------------
def local_offset() -> str:
    """This computer's UTC offset, so a new countdown starts in the owner's own time zone."""
    from datetime import datetime
    minutes = round(datetime.now().astimezone().utcoffset().total_seconds() / 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def default_target(days: int = 30) -> str:
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%dT09:00")


def illustration(name: str, width: str = "260px", **style) -> Node:
    style.setdefault("max_width", width)
    style.setdefault("width", "100%")
    return n("illustration", {"name": name, "animate": True}, style)


def countdown(days: int = 30, **style) -> Node:
    return n("countdown", {"target": default_target(days), "utc_offset": local_offset(), "show_seconds": True, "done_text": "We are live."}, style)


def progress(mode: str = "loading", value: int = 60, label: str = "", **style) -> Node:
    props: dict[str, Any] = {"mode": mode, "value": value, "show_value": True}
    if label:
        props["label"] = label
    return n("progress", props, style)


def glass(*children, gap: str = "18px", **style) -> Node:
    merged = {**GLASS, "padding": "44px 36px", "gap": gap, "align_items": "center", "text_align": "center", **style}
    return box(*children, name="Glass card", **merged)


def _onepage(role: str, ambient: str, *children, tone: str = "inverse") -> Node:
    node = section(role, box(*children, width="narrow", align_items="center"), tone=tone, min_height="100vh", display="flex",
                   align_items="center", padding_block="72px")
    node["props"]["ambient"] = ambient
    return node


def _illustration() -> Node:
    return illustration("gears")


def _countdown() -> Node:
    return countdown()


def _progress() -> Node:
    return progress(label="Almost there")


def _glass_card() -> Node:
    return glass(h("A card of frosted glass", 3), p("Place it over a photo or a living background and it blurs what is behind it.", max_width="44ch"))


def _coming_soon() -> Node:
    form = n("contact_form", {"fields": [{"label": "Your email address", "type": "email"}], "submit": "Notify me"}, {"width": "100%", "max_width": "420px"})
    return _onepage("coming_soon", "aurora", glass(
        illustration("rocket", "220px"), h("Something new is coming", 1, font_size="clamp(2.1rem,5vw,3.4rem)"),
        p("We are putting the finishing touches to it. Leave your email and we will tell you the moment it opens.", max_width="46ch"),
        countdown(margin_block="6px"), form))


def _maintenance() -> Node:
    return _onepage("maintenance", "grid", glass(
        illustration("gears", "230px"), h("We are improving the site", 1, font_size="clamp(2rem,5vw,3.2rem)"),
        p("We are doing some work on the site right now. It will be back shortly. Thank you for your patience.", max_width="46ch"),
        progress(max_width="360px"), p("Need us urgently? hello@example.com", False, font_size=".95rem")))


def _launch_band() -> Node:
    copy = column(h("The doors open soon"), p("Mark the date. Everything you need to know arrives here first."), countdown(justify_content="flex-start"), gap="18px")
    return section("launch", n("columns", {"columns": "7fr 5fr", "width": "content"}, {"gap": "56px", "align_items": "center"},
                               [copy, illustration("calendar", "300px")], responsive={"tablet": {"props": {"columns": 1}}}), tone="primary")


def _illustrated_hero() -> Node:
    copy = column(h("A clear headline that says what you do", 1, font_size="clamp(2.6rem,6vw,4.4rem)"),
                  p("One or two sentences that explain who this is for and why it matters to them.", font_size="1.14rem", max_width="52ch"),
                  row(btn("Get started"), btn("Learn more", "secondary"), margin_top="8px"), gap="20px")
    node = section("hero", n("columns", {"columns": "6fr 5fr", "width": "content"}, {"gap": "56px", "align_items": "center"},
                             [copy, illustration("network", "420px")], responsive={"tablet": {"props": {"columns": 1}}}), tone="inverse")
    node["props"]["ambient"] = "aurora"
    return node


def _illustrated_services() -> Node:
    items = [card(illustration(name, "170px", margin_inline="0"), h(title_, 3, font_size="1.25rem"), p(text), gap="12px")
             for name, title_, text in (("server", "Infrastructure", "What you build and look after, in one sentence."),
                                        ("shield", "Security", "How you keep people and their data safe."),
                                        ("growth", "Growth", "The results you help your clients reach."))]
    return section("services", content(title("What we do"), cols(3, *items, tablet=1)))


def _under_construction() -> Node:
    return _onepage("under_construction", "waves", glass(
        illustration("crane", "240px"), h("Under construction", 1, font_size="clamp(2rem,5vw,3.2rem)"),
        p("Our new site is being built. Here is how far along we are.", max_width="44ch"),
        progress("value", 70, "Progress", max_width="380px"), row(btn("Contact us"), justify_content="center")))


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
    ("illustration", "Animated illustration", MOTION, "shapes", "A moving drawing in the site's colours: 35 to choose from", _illustration),
    ("countdown", "Countdown", MOTION, "clock", "Days, hours and minutes to a date, ticking live", _countdown),
    ("progress", "Progress bar", MOTION, "sliders-horizontal", "A loading slide, or a set percentage", _progress),
    ("glass-card", "Glass card", MOTION, "layers", "A frosted card for dark, photo or living backgrounds", _glass_card),
    ("illustrated-hero", "Illustrated hero", MOTION, "sparkles", "A headline beside a moving illustration, over a living background", _illustrated_hero),
    ("illustrated-services", "Illustrated services", MOTION, "briefcase-business", "Three services, each with its own moving drawing", _illustrated_services),
    ("launch-band", "Launch countdown", MOTION, "calendar", "A countdown band with a calendar drawing", _launch_band),
    ("coming-soon", "Coming soon page", MOTION, "rocket", "A full-screen glass card: rocket, countdown and sign-up", _coming_soon),
    ("maintenance", "Maintenance page", MOTION, "settings", "A full-screen notice with turning gears and a loading bar", _maintenance),
    ("under-construction", "Under construction page", MOTION, "hard-hat", "A crane, a progress bar and a way to get in touch", _under_construction),
    ("latest-posts", "Latest posts (live)", SECTIONS, "newspaper", "Real posts from the website, filled in when the site runs", _latest_posts),
    ("posts-list", "Posts list (live)", CONTENT, "list", "Real posts, filled in when the site runs", _posts_list),
)
for _id, _label, _group, _icon_name, _text, _build in _CATALOGUE:
    register(ComponentDef(_id, _label, _group, _icon_name, _text, _build))
for _id, _label, _icon_name, _text, _build in (
    ("post-title", "Post title", "heading-1", "The title of each post", _post_title),
    ("post-image", "Featured image", "image", "The image chosen for each post", _post_image),
    ("post-meta", "Post details", "rows-3", "Date, author and category", _post_meta),
    ("post-body", "Post body", "text", "The text of each post", _post_body),
):
    register(ComponentDef(_id, _label, POST_TEMPLATE, _icon_name, _text, _build, True))
