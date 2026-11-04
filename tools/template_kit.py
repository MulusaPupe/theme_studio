"""Authoring kit for the built-in template library (a development tool, not used at runtime).

A template spec chooses tokens, a card and heading treatment, and an ordered list
of section layouts such as ``hero:split`` or ``stats:strip@primary``. The kit
expands those into universal-document trees of primitive nodes. The application
only ever sees the resulting template.json files.
"""
from __future__ import annotations

import re
from typing import Any

PAGE_IDS = ("home", "about", "services", "portfolio", "blog", "contact")


# Colour helpers ---------------------------------------------------------------
def _rgb(c: str) -> list[int]:
    return [int(c[i : i + 2], 16) for i in (1, 3, 5)]


def mix(a: str, b: str, t: float) -> str:
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(_rgb(a), _rgb(b)))


def luminance(c: str) -> float:
    def f(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= .03928 else ((s + .055) / 1.055) ** 2.4

    r, g, b = _rgb(c)
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def contrast(a: str, b: str) -> float:
    x, y = sorted((luminance(a), luminance(b)), reverse=True)
    return (x + .05) / (y + .05)


def on(color: str, *candidates: str) -> str:
    """The most readable of the candidates (then black or white) on a colour."""
    options = [*candidates, "#ffffff", "#0b0b0d"]
    for option in candidates:
        if contrast(option, color) >= 4.5:
            return option
    return max(options, key=lambda o: contrast(o, color))


def legible(color: str, *candidates: str) -> tuple[str, str]:
    """A colour and the text to put on it, adjusting the colour slightly if neither quite reaches 4.5:1."""
    label = on(color, *candidates)
    while contrast(label, color) < 4.5:
        color = mix(color, "#000000" if luminance(label) > luminance(color) else "#ffffff", .03)
    return color, label


def palette(bg: str, text: str, primary: str, accent: str, secondary: str | None = None, surface: str | None = None) -> dict[str, str]:
    primary, on_primary = legible(primary, bg, text)
    accent, on_accent = legible(accent, bg, text)
    muted = mix(text, bg, .28)
    while contrast(muted, bg) < 4.6:
        muted = mix(muted, text, .2)
    surface = surface or mix(bg, text, .045)
    while contrast(muted, surface) < 4.5:
        muted = mix(muted, text, .2)
    return {
        "primary": primary,
        "on_primary": on_primary,
        "secondary": secondary or mix(primary, text, .35),
        "accent": accent,
        "on_accent": on_accent,
        "background": bg,
        "surface": surface,
        "text": text,
        "muted": muted,
        "border": mix(bg, text, .16),
    }


def R(mobile: dict | None = None, tablet: dict | None = None) -> dict:
    """Responsive style overrides."""
    out = {}
    if tablet:
        out["tablet"] = {"style": tablet}
    if mobile:
        out["mobile"] = {"style": mobile}
    return out


WHITE = "#ffffff"

# Average glyph width in em, used to size display type so its longest word fits.
_GLYPH = {"Unbounded": .86, "Syne": 1.0, "Archivo": .68, "Sora": .66, "Space Grotesk": .62, "JetBrains Mono": .62, "Outfit": .6, "Anton": .47, "Bebas Neue": .42, "Oswald": .5}


def fit_text(text: str, family: str, max_rem: float, upper: bool = False, room: float = 84) -> str:
    """A font size no larger than max_rem that keeps the longest word inside the page."""
    longest = max(len(word) for word in text.split()) or 1
    width = _GLYPH.get(family, .58) * (1.14 if upper else 1)
    return f"min({room / (longest * width):.2f}vw,{max_rem}rem)"


class Kit:
    def __init__(self, spec: dict, pack: dict) -> None:
        self.s = spec
        self.p = pack
        self.colors = spec["colors"]
        self.n = 0
        self.seed = 0
        self.card_kind = spec.get("card", "bordered")
        self.heads = spec.get("heads", "left")
        self.eyebrow_kind = spec.get("eyebrow", "caps")
        self.hero_size = spec.get("display", "clamp(2.7rem,7vw,5.6rem)")
        self.overlay = bool(spec.get("overlay"))
        self.offset = spec.get("offset", 0)

    # Primitives ---------------------------------------------------------------
    def node(self, type_: str, props: dict | None = None, style: dict | None = None, children: list | None = None,
             name: str | None = None, responsive: dict | None = None) -> dict:
        self.n += 1
        out: dict[str, Any] = {"id": f"e{self.n}", "type": type_, "props": props or {}, "style": style or {}}
        if name:
            out["name"] = name
        if responsive:
            out["responsive"] = responsive
        if type_ in ("section", "container", "columns", "row", "footer"):
            out["children"] = children or []
        return out

    def box(self, *children, style=None, width=None, tone=None, responsive=None, name=None) -> dict:
        props = {}
        if width:
            props["width"] = width
        if tone:
            props["tone"] = tone
        return self.node("container", props, style, list(children), name, responsive)

    def stack(self, *children, gap="16px", **style) -> dict:
        responsive = style.pop("responsive", None)
        return self.box(*children, style={"gap": gap, **style}, responsive=responsive)

    def w(self, *children, width="content", gap=None, style=None) -> dict:
        merged = dict(style or {})
        if gap:
            merged["gap"] = gap
        return self.box(*children, width=width, style=merged)

    def cols(self, columns, *children, gap=None, align=None, tablet=None, mobile=None, width=None, style=None) -> dict:
        merged = dict(style or {})
        if gap:
            merged["gap"] = gap
        if align:
            merged["align_items"] = align
        props: dict[str, Any] = {"columns": columns}
        if width:
            props["width"] = width
        responsive: dict[str, Any] = {}
        if tablet is not None:
            responsive["tablet"] = {"props": {"columns": tablet}}
        if mobile is not None:
            responsive["mobile"] = {"props": {"columns": mobile}}
        return self.node("columns", props, merged, list(children), None, responsive or None)

    def row(self, *children, gap=None, **style) -> dict:
        if gap:
            style["gap"] = gap
        return self.node("row", {}, style, list(children))

    def h(self, text: str, level: int = 2, **style) -> dict:
        return self.node("heading", {"text": text, "level": level}, style)

    def t(self, text: str, muted: bool = True, **style) -> dict:
        props = {"text": text}
        if muted:
            props["muted"] = True
        return self.node("text", props, style)

    def btn(self, label: str, page: str = "contact", variant: str = "primary", **style) -> dict:
        return self.node("button", {"label": label, "href": {"page": page}, "variant": variant}, style)

    def link(self, label: str, page: str = "portfolio", **style) -> dict:
        return self.node("link", {"label": label, "href": {"page": page}, "arrow": True}, style)

    def icon(self, name: str, **style) -> dict:
        style.setdefault("font_size", "28px")
        style.setdefault("color", "$c-accent" if self._accent_ok() else "currentColor")
        return self.node("icon", {"name": name}, style)

    def img(self, subject: str | None = None, ratio: float = 1.5, label: str = "Image", radius: bool = True, **style) -> dict:
        self.seed += 1
        subject = subject or self.p["subject"]
        media = {"kind": "placeholder", "seed": f"{self.s['slug']}-{self.seed}", "subject": subject, "ratio": ratio, "label": label}
        if radius:
            style.setdefault("border_radius", "$radius")
        return self.node("image", {"media": media, "alt": label, "ratio": ratio}, style)

    def rule(self, **style) -> dict:
        return self.node("divider", {}, style)

    def _accent_ok(self) -> bool:
        return contrast(self.colors["accent"], self.colors["background"]) >= 4.5 and contrast(self.colors["accent"], self.colors["surface"]) >= 4.5

    def eyebrow(self, text: str) -> dict | None:
        kind = self.eyebrow_kind
        if kind == "none" or not text:
            return None
        color = "$c-accent" if self._accent_ok() else "$c-muted"
        style = {"font_size": ".76rem", "font_weight": 600, "letter_spacing": ".16em", "text_transform": "uppercase", "color": color}
        if kind == "mono":
            style = {"font_size": ".8rem", "font_family": "'JetBrains Mono',monospace", "color": color}
            text = f"/ {text}"
        elif kind == "rule":
            style.update({"border_top": "2px solid currentColor", "padding_top": "10px", "align_self": "flex-start"})
        elif kind == "italic":
            style = {"font_family": "$font-heading", "font_style": "italic", "font_size": "1.15rem", "color": color}
        return self.node("text", {"text": text}, style, name="Eyebrow")

    def _clean(self, *items):
        return [i for i in items if i]

    def head(self, eyebrow: str, title: str, sub: str = "", align: str | None = None) -> dict:
        align = align or self.heads
        if align == "split" and sub:
            return self.cols("5fr 6fr", self.stack(*self._clean(self.eyebrow(eyebrow), self.h(title)), gap="12px"),
                             self.t(sub, font_size="1.08rem"), gap="48px", align="end", tablet=1, style={"margin_bottom": "52px"})
        style = {"gap": "14px", "margin_bottom": "48px"}
        if align == "center":
            style.update({"align_items": "center", "text_align": "center", "max_width": "720px", "margin_inline": "auto"})
        else:
            style["max_width"] = "760px"
        return self.box(*self._clean(self.eyebrow(eyebrow), self.h(title), self.t(sub, font_size="1.08rem") if sub else None), style=style)

    def card(self, *children, gap="12px", **extra) -> dict:
        kind = self.card_kind
        style: dict[str, Any] = {"gap": gap}
        if kind == "bordered":
            style.update({"border": "1px solid $c-border", "border_radius": "$card-radius", "padding": "30px"})
        elif kind == "shadow":
            style.update({"background": "$c-card", "border_radius": "$card-radius", "padding": "30px", "box_shadow": "0 18px 44px rgba(10,14,28,.1)"})
        elif kind == "tint":
            style.update({"background": "$c-card", "border_radius": "$card-radius", "padding": "30px"})
        elif kind == "rule":
            style.update({"border_top": "2px solid currentColor", "padding_top": "20px"})
        style.update(extra)
        return self.box(*children, style=style)

    def sec(self, role: str, children: list, tone: str | None = None, style: dict | None = None, bg: dict | None = None,
            responsive: dict | None = None) -> dict:
        props: dict[str, Any] = {"role": role}
        if bg:
            tone = "image"  # Text over a photo must stay readable whatever the palette.
        if tone:
            props["tone"] = tone
        if bg:
            props["background"] = bg
        return self.node("section", props, style, children, responsive=responsive)

    def items(self, key: str, count: int) -> list:
        pool = self.p[key]
        start = self.offset % len(pool)
        rotated = pool[start:] + pool[:start]
        return [rotated[i % len(rotated)] for i in range(count)]

    def bg_image(self, subject: str | None = None, overlay: str = "rgba(8,10,16,.55)") -> dict:
        self.seed += 1
        return {
            "media": {"kind": "placeholder", "seed": f"{self.s['slug']}-{self.seed}", "subject": subject or self.p["subject"], "ratio": 1.78, "label": "Background image"},
            "overlay": overlay, "alt": "",
        }

    def h1(self, text: str, **style) -> dict:
        style.setdefault("font_size", self.hero_size)
        return self.h(text, 1, **style)

    def actions(self, *buttons, **style) -> dict:
        return self.row(*buttons, gap="14px", margin_top="10px", **style)

    def hero_copy(self, **style) -> dict:
        s = self.s
        gap = style.pop("gap", "20px")
        return self.box(
            *self._clean(
                self.eyebrow(s.get("kicker", "")),
                self.h1(s["headline"]),
                self.t(s["sub"], font_size="1.16rem", max_width="60ch"),
                self.actions(self.btn(s.get("action", "Get in touch")), self.btn(s.get("action2", "See our work"), "portfolio", s.get("action2_kind", "secondary"))),
            ),
            style={"gap": gap, **style},
        )

    # Hero ---------------------------------------------------------------------
    def hero_split(self, tone=None):
        return self.sec("hero", [self.cols("6fr 5fr", self.hero_copy(), self.img(ratio=.92, label="Hero image"), gap="64px", align="center", width="content", tablet=1)], tone)

    def hero_split_rev(self, tone=None):
        return self.sec("hero", [self.cols("5fr 6fr", self.img(ratio=1.12, label="Hero image"), self.hero_copy(), gap="72px", align="center", width="content", tablet=1)], tone)

    def hero_bleed(self, tone=None):
        """Text in a padded half; image running to the page edge."""
        copy = self.box(self.hero_copy(), style={"padding": "clamp(36px,7vw,110px) clamp(22px,5vw,80px)", "justify_content": "center"})
        image = self.img(ratio=.95, label="Hero image", radius=False, height="100%")
        return self.sec("hero", [self.cols("1fr 1fr", copy, image, gap="0", width="full", tablet=1)], tone, {"padding_block": "0"})

    def hero_center(self, tone=None):
        copy = self.hero_copy(align_items="center", text_align="center", max_width="880px", margin_inline="auto")
        return self.sec("hero", [self.w(copy)], tone, {"padding_block": "clamp(90px,14vw,190px)"})

    def hero_stacked(self, tone=None):
        """Centred copy above one wide image."""
        copy = self.hero_copy(align_items="center", text_align="center", max_width="840px", margin_inline="auto", margin_bottom="56px")
        return self.sec("hero", [self.w(copy, self.img(ratio=2.2, label="Hero image"))], tone)

    def hero_overlay(self, tone=None):
        copy = self.hero_copy(max_width="760px", color=WHITE)
        return self.sec("hero", [self.w(copy, style={"justify_content": "flex-end", "min_height": "inherit"})], tone,
                        {"min_height": "clamp(560px,86vh,860px)", "display": "flex", "align_items": "flex-end", "padding_block": "150px 80px", "color": WHITE},
                        self.bg_image(overlay="linear-gradient(180deg,rgba(6,8,14,.45),rgba(6,8,14,.72))"))

    def hero_overlay_center(self, tone=None):
        copy = self.hero_copy(max_width="900px", align_items="center", text_align="center", margin_inline="auto", color=WHITE)
        return self.sec("hero", [self.w(copy)], tone,
                        {"min_height": "clamp(600px,92vh,920px)", "display": "flex", "align_items": "center", "padding_block": "150px 90px", "color": WHITE},
                        self.bg_image(overlay="rgba(6,8,14,.58)"))

    def hero_giant(self, tone=None):
        """Oversized type across the page, a thin rule, then copy and image."""
        s = self.s
        lower = self.cols("4fr 8fr",
                          self.stack(self.t(s["sub"], font_size="1.05rem"), self.link(s.get("action2", "See our work")), gap="20px"),
                          self.img(ratio=2, label="Hero image"), gap="48px", tablet=1, style={"margin_top": "44px"})
        return self.sec("hero", [self.w(self.h1(s["headline"], font_size=self.s.get("giant", "clamp(3.2rem,12vw,11rem)"), line_height=".94"),
                                        self.rule(margin_top="36px"), lower)], tone, {"padding_block": "64px 80px"})

    def hero_mosaic(self, tone=None):
        grid = self.cols(2, self.img(ratio=.72, label="Image one", grid_row="span 2", height="100%"), self.img(ratio=1.25, label="Image two"), self.img(ratio=1.25, label="Image three"), gap="14px", mobile=2)
        return self.sec("hero", [self.cols("1fr 1fr", self.hero_copy(), grid, gap="64px", align="center", width="content", tablet=1)], tone)

    def hero_poster(self, tone=None):
        s = self.s
        return self.sec("hero", [self.w(
            self.t(s.get("kicker", ""), False, font_weight=600, letter_spacing=".2em", text_transform="uppercase", font_size=".8rem"),
            self.h1(s["headline"], font_size=s.get("giant", "clamp(3.6rem,15vw,14rem)"), line_height=".88"),
            self.row(self.t(s["sub"], False, max_width="46ch", font_size="1.1rem"), self.btn(s.get("action", "Get in touch")), justify_content="space-between", align_items="flex-end", gap="28px"),
            gap="30px", style={"justify_content": "flex-end"})], tone,
            {"min_height": "clamp(560px,88vh,900px)", "display": "flex", "align_items": "flex-end", "padding_block": "60px"})

    def hero_framed(self, tone=None):
        """A wide image with a card overlapping its lower edge."""
        s = self.s
        card = self.box(*self._clean(self.eyebrow(s.get("kicker", "")), self.h1(s["headline"], font_size=s.get("display", "clamp(2.4rem,5vw,4.4rem)")), self.t(s["sub"]),
                                     self.actions(self.btn(s.get("action", "Get in touch")))), tone="default",
                        style={"gap": "16px", "padding": "clamp(26px,4vw,52px)", "max_width": "680px", "margin_top": "-180px", "margin_left": "clamp(0px,5vw,64px)", "border_radius": "$radius", "z_index": "2", "box_shadow": "0 24px 60px rgba(10,14,28,.16)"},
                        responsive=R(mobile={"margin_top": "-48px", "margin_left": "0"}))
        return self.sec("hero", [self.w(self.img(ratio=2.05, label="Hero image"), card)], tone, {"padding_block": "32px 80px"})

    def hero_lead(self, tone=None):
        """Newspaper front page: lead story with a running list beside it."""
        s = self.s
        side = []
        for title, meta, _ in self.items("posts", 4):
            side += [self.stack(self.t(meta, font_size=".76rem", text_transform="uppercase", letter_spacing=".1em"), self.h(title, 4), gap="6px"), self.rule()]
        lead = self.stack(self.img(ratio=1.7, label="Lead story image"), *self._clean(self.eyebrow(s.get("kicker", ""))), self.h1(s["headline"]), self.t(s["sub"], font_size="1.12rem"), gap="16px")
        return self.sec("hero", [self.cols("8fr 4fr", lead, self.stack(self.h("Latest", 5, text_transform="uppercase", letter_spacing=".14em", border_bottom="3px solid currentColor", padding_bottom="10px"), *side, gap="16px"), gap="44px", width="content", tablet=1)], tone, {"padding_block": "36px 64px"})

    def hero_search(self, tone=None):
        s = self.s
        fields = self.p.get("search", ("Location", "Type", "Budget"))
        bar = self.cols("1fr 1fr 1fr auto", *[self.stack(self.t(f, False, font_size=".74rem", font_weight=600, text_transform="uppercase", letter_spacing=".1em"), self.t(v, False, font_size="1rem"), gap="4px") for f, v in fields],
                        self.btn(s.get("action", "Search")), gap="22px", align="center", tablet=2,
                        style={"background": "$background", "color": "$text", "padding": "20px 24px", "border_radius": "$radius", "margin_top": "30px", "box_shadow": "0 22px 50px rgba(0,0,0,.22)"})
        copy = self.box(*self._clean(self.eyebrow(s.get("kicker", "")), self.h1(s["headline"], color=WHITE), self.t(s["sub"], False, color=WHITE, font_size="1.15rem", max_width="60ch")), style={"gap": "16px"})
        return self.sec("hero", [self.w(copy, bar)], tone, {"min_height": "clamp(560px,82vh,780px)", "display": "flex", "align_items": "flex-end", "padding_block": "140px 70px", "color": WHITE},
                        self.bg_image(overlay="linear-gradient(180deg,rgba(6,8,14,.3),rgba(6,8,14,.72))"))

    def hero_stats(self, tone=None):
        figures = self.cols(len(self.items("stats", 4)), *[self.stack(self.h(n, 2), self.t(l, font_size=".92rem"), gap="4px") for n, l in self.items("stats", 4)], gap="28px", tablet=4, mobile=2,
                            style={"margin_top": "64px", "padding_top": "30px", "border_top": "1px solid $c-border"})
        return self.sec("hero", [self.w(self.hero_copy(max_width="860px"), figures)], tone, {"padding_block": "clamp(80px,11vw,150px) 64px"})

    def hero_marquee(self, tone=None):
        """Three tall images in a row beneath a headline line: magazine or portfolio opening."""
        s = self.s
        strip = self.cols(3, self.img(ratio=.72, label="Image one"), self.img(ratio=.72, label="Image two", margin_top="48px"), self.img(ratio=.72, label="Image three"), gap="18px", mobile=1)
        top = self.cols("8fr 4fr", self.h1(s["headline"]), self.stack(self.t(s["sub"]), self.btn(s.get("action", "Get in touch"), align_self="flex-start"), gap="18px"), gap="48px", align="end", tablet=1, style={"margin_bottom": "48px"})
        return self.sec("hero", [self.w(top, strip)], tone, {"padding_block": "64px 80px"})

    # About --------------------------------------------------------------------
    def about_split(self, tone=None):
        p = self.p
        return self.sec("about", [self.cols("1fr 1fr", self.img(ratio=1.1, label="About image"),
                                            self.stack(*self._clean(self.eyebrow("About"), self.h(self.s.get("about_title", p["about_title"])), self.t(p["about"]), self.t(p["about2"]), self.link("Our story", "about", margin_top="6px")), gap="16px"),
                                            gap="68px", align="center", width="content", tablet=1)], tone)

    def about_split_rev(self, tone=None):
        p = self.p
        return self.sec("about", [self.cols("6fr 5fr", self.stack(*self._clean(self.eyebrow("About"), self.h(self.s.get("about_title", p["about_title"])), self.t(p["about"]), self.t(p["about2"])), gap="16px"),
                                            self.img(ratio=.86, label="About image"), gap="80px", align="center", width="content", tablet=1)], tone)

    def about_statement(self, tone=None):
        return self.sec("about", [self.w(*self._clean(self.eyebrow("About"), self.h(self.s.get("statement", self.p["about"]), 2, font_size="clamp(1.8rem,3.8vw,3.2rem)", line_height="1.22", max_width="24em")), gap="22px")], tone)

    def about_columns(self, tone=None):
        p = self.p
        return self.sec("about", [self.w(self.head("About", self.s.get("about_title", p["about_title"])),
                                         self.cols(2, self.t(p["about"], font_size="1.08rem"), self.t(p["about2"], font_size="1.08rem"), gap="48px"),
                                         self.img(ratio=2.6, label="About image", margin_top="48px"))], tone)

    # Services -----------------------------------------------------------------
    def _svc_head(self):
        return self.head(self.p.get("services_eyebrow", "What we do"), self.p["services_title"], self.p.get("services_sub", ""))

    def services_cards(self, tone=None):
        cards = [self.card(self.icon(i), self.h(t, 3, font_size="1.3rem"), self.t(x)) for t, x, i in self.items("services", 3)]
        return self.sec("services", [self.w(self._svc_head(), self.cols(3, *cards))], tone)

    def services_cards4(self, tone=None):
        cards = [self.card(self.icon(i), self.h(t, 3, font_size="1.15rem"), self.t(x, font_size=".95rem")) for t, x, i in self.items("services", 4)]
        return self.sec("services", [self.w(self._svc_head(), self.cols(4, *cards, tablet=2))], tone)

    def services_rows(self, tone=None):
        rows = []
        for index, (t, x, _) in enumerate(self.items("services", 4), 1):
            rows.append(self.cols("80px 4fr 6fr", self.t(f"{index:02d}", font_family="$font-heading", font_size="1.1rem"), self.h(t, 3, font_size="clamp(1.3rem,2.4vw,2rem)"), self.t(x), gap="24px",
                                  tablet="60px 1fr 1fr", mobile=1, style={"padding_block": "28px", "border_top": "1px solid $c-border"}))
        return self.sec("services", [self.w(self._svc_head(), *rows)], tone)

    def services_alt(self, tone=None):
        blocks = []
        for index, (t, x, _) in enumerate(self.items("services", 3)):
            copy = self.stack(self.h(t, 3), self.t(x, font_size="1.05rem"), self.link("Learn more", "services"), gap="14px")
            image = self.img(ratio=1.5, label=t)
            blocks.append(self.cols("1fr 1fr", *((copy, image) if index % 2 else (image, copy)), gap="64px", align="center", tablet=1, style={"margin_top": "56px" if index else "0"}))
        return self.sec("services", [self.w(self._svc_head(), *blocks)], tone)

    def services_icons(self, tone=None):
        items = [self.stack(self.icon(i, font_size="34px"), self.h(t, 4), self.t(x, font_size=".97rem"), gap="10px") for t, x, i in self.items("services", 6)]
        return self.sec("services", [self.w(self._svc_head(), self.cols(3, *items, gap="46px 40px", tablet=2))], tone)

    def services_bento(self, tone=None):
        s = self.items("services", 4)
        big = self.box(self.icon(s[0][2], font_size="40px"), self.h(s[0][0], 3, font_size="clamp(1.6rem,3vw,2.4rem)", margin_top="auto"), self.t(s[0][1]), tone="primary",
                       style={"gap": "14px", "padding": "36px", "border_radius": "$radius", "grid_row": "span 2", "min_height": "400px"},
                       responsive=R(mobile={"min_height": "280px", "grid_row": "auto"}))
        rest = [self.card(self.icon(i), self.h(t, 3, font_size="1.2rem"), self.t(x, font_size=".95rem")) for t, x, i in s[1:3]]
        wide = self.card(self.icon(s[3][2]), self.h(s[3][0], 3, font_size="1.2rem"), self.t(s[3][1], font_size=".95rem"), grid_column="span 2")
        wide["responsive"] = R(mobile={"grid_column": "auto"})
        return self.sec("services", [self.w(self._svc_head(), self.cols(3, big, *rest, wide, gap="18px", tablet=3))], tone)

    def features_check(self, tone=None):
        checks = [self.row(self.icon("circle-check", font_size="20px"), self.t(t, False, flex="1", min_width="0"), gap="12px", flex_wrap="nowrap", align_items="flex-start") for t, _, _ in self.items("services", 5)]
        copy = self.stack(*self._clean(self.eyebrow("Why choose us"), self.h(self.p.get("features_title", "The standard we hold ourselves to")), self.t(self.p["about2"]), *checks), gap="14px")
        return self.sec("features", [self.cols("1fr 1fr", copy, self.img(ratio=.95, label="Feature image"), gap="72px", align="center", width="content", tablet=1)], tone)

    # Stats --------------------------------------------------------------------
    def stats_strip(self, tone=None):
        figures = [self.stack(self.h(n, 2, font_size="clamp(2.2rem,4vw,3.2rem)"), self.t(l, font_size=".93rem"), gap="4px") for n, l in self.items("stats", 4)]
        return self.sec("statistics", [self.w(self.cols(4, *figures, tablet=4, mobile=2))], tone, {"padding_block": "56px"})

    def stats_big(self, tone=None):
        rows = []
        for n, l in self.items("stats", 3):
            rows.append(self.row(self.h(n, 2, font_size="clamp(3.4rem,10vw,8rem)", line_height="1"), self.t(l, font_size="1.1rem", max_width="26ch"), justify_content="space-between", align_items="flex-end", padding_block="20px", border_bottom="1px solid $c-border", gap="24px"))
        return self.sec("statistics", [self.w(*rows)], tone)

    def stats_cards(self, tone=None):
        cards = [self.card(self.h(n, 2), self.t(l), gap="6px") for n, l in self.items("stats", 3)]
        return self.sec("statistics", [self.w(self.cols(3, *cards))], tone, {"padding_block": "64px"})

    # Testimonials -------------------------------------------------------------
    def quote_single(self, tone=None):
        q, who, role = self.items("quotes", 1)[0]
        return self.sec("testimonials", [self.w(self.h(f"“{q}”", 2, font_size="clamp(1.6rem,3.4vw,2.8rem)", line_height="1.25", font_weight="inherit"),
                                                self.t(f"{who}, {role}", font_size=".95rem"), width="narrow", gap="24px", style={"text_align": "center"})], tone)

    def quote_cards(self, tone=None):
        cards = [self.card(self.t(f"“{q}”", False), self.stack(self.t(who, False, font_weight=600), self.t(role, font_size=".88rem"), gap="0", margin_top="auto"), gap="20px") for q, who, role in self.items("quotes", 3)]
        return self.sec("testimonials", [self.w(self.head("Testimonials", "What people say"), self.cols(3, *cards))], tone)

    def quote_side(self, tone=None):
        q, who, role = self.items("quotes", 1)[0]
        return self.sec("testimonials", [self.cols("4fr 7fr", self.img("portrait", ratio=.9, label=who), self.stack(self.h(f"“{q}”", 3, font_size="clamp(1.4rem,2.8vw,2.2rem)", line_height="1.3"), self.t(f"{who}, {role}"), gap="20px"), gap="60px", align="center", width="content", tablet=1)], tone)

    # Team ---------------------------------------------------------------------
    def team_grid(self, tone=None):
        people = [self.stack(self.img("portrait", ratio=.82, label=n), self.h(n, 4, margin_top="6px"), self.t(r, font_size=".93rem"), gap="6px") for n, r in self.items("team", 4)]
        return self.sec("team", [self.w(self.head("Team", self.p.get("team_title", "The people behind the work")), self.cols(4, *people, tablet=2, mobile=2))], tone)

    def team_circles(self, tone=None):
        people = [self.stack(self.img("portrait", ratio=1, label=n, radius=False, border_radius="50%", width="140px"), self.h(n, 4), self.t(r, font_size=".93rem"), gap="8px", align_items="center", text_align="center") for n, r in self.items("team", 4)]
        return self.sec("team", [self.w(self.head("Team", self.p.get("team_title", "The people behind the work"), align="center"), self.cols(4, *people, tablet=2, mobile=2))], tone)

    def team_rows(self, tone=None):
        rows = [self.row(self.h(n, 3, font_size="clamp(1.3rem,2.6vw,2.1rem)"), self.t(r), justify_content="space-between", padding_block="20px", border_top="1px solid $c-border") for n, r in self.items("team", 4)]
        return self.sec("team", [self.cols("4fr 8fr", self.stack(*self._clean(self.eyebrow("Team"), self.h(self.p.get("team_title", "The people behind the work"))), gap="12px"), self.box(*rows), gap="48px", width="content", tablet=1)], tone)

    # Pricing ------------------------------------------------------------------
    def pricing_cards(self, tone=None):
        cards = []
        for index, (name, price, note, feats) in enumerate(self.items("plans", 3)):
            lines = [self.t(f"✓  {f}", font_size=".95rem") for f in feats]
            inner = (self.h(name, 4), self.h(price, 2), self.t(note, font_size=".92rem"), self.rule(margin_block="8px"), *lines, self.btn("Choose plan", variant="primary" if index == 1 else "secondary", margin_top="auto", align_self="stretch"))
            if index == 1:
                cards.append(self.box(*inner, tone="primary", style={"gap": "10px", "padding": "32px", "border_radius": "$radius"}))
            else:
                cards.append(self.box(*inner, style={"gap": "10px", "padding": "32px", "border_radius": "$radius", "border": "1px solid $c-border"}))
        return self.sec("pricing", [self.w(self.head(self.p.get("plans_eyebrow", "Pricing"), self.p.get("plans_title", "Simple, clear pricing"), align="center"), self.cols(3, *cards, align="stretch", gap="20px", tablet=1))], tone)

    def pricing_rows(self, tone=None):
        """A price list: suits menus, tuition and fee schedules."""
        rows = []
        for name, price, note, _ in self.items("plans", 6):
            rows.append(self.stack(self.row(self.h(name, 4), self.h(price, 4), justify_content="space-between", flex_wrap="nowrap", gap="20px"), self.t(note, font_size=".95rem"), gap="4px", padding_block="18px", border_bottom="1px solid $c-border"))
        return self.sec("pricing", [self.w(self.head(self.p.get("plans_eyebrow", "Pricing"), self.p.get("plans_title", "Simple, clear pricing"), align="center"), self.cols(2, *rows, gap="0 64px", tablet=1), width="content")], tone)

    # Portfolio ----------------------------------------------------------------
    def _work_head(self):
        return self.head(self.p.get("work_eyebrow", "Selected work"), self.p["work_title"], self.p.get("work_sub", ""))

    def _work_item(self, title, meta, ratio=1.25, subject=None):
        return self.stack(self.img(subject or self.p.get("work_subject"), ratio=ratio, label=title), self.h(title, 4, margin_top="4px"), self.t(meta, font_size=".92rem"), gap="6px")

    def portfolio_grid3(self, tone=None):
        return self.sec("portfolio", [self.w(self._work_head(), self.cols(3, *[self._work_item(t, m) for t, m in self.items("projects", 6)], tablet=2, gap="36px 26px"))], tone)

    def portfolio_grid2(self, tone=None):
        return self.sec("portfolio", [self.w(self._work_head(), self.cols(2, *[self._work_item(t, m, 1.45) for t, m in self.items("projects", 4)], gap="48px 32px"))], tone)

    def portfolio_mosaic(self, tone=None):
        it = self.items("projects", 5)
        return self.sec("portfolio", [self.w(self._work_head(), self.cols("7fr 5fr", self._work_item(*it[0], 1.3), self._work_item(*it[1], .95), self._work_item(*it[2], .95), self._work_item(*it[3], 1.3), gap="44px 28px", tablet="1fr 1fr"))], tone)

    def portfolio_rows(self, tone=None):
        rows = []
        for index, (t, m) in enumerate(self.items("projects", 5), 1):
            rows.append(self.cols("3fr 7fr 2fr", self.img(self.p.get("work_subject"), ratio=1.6, label=t), self.stack(self.h(t, 3, font_size="clamp(1.4rem,3vw,2.5rem)"), self.t(m), gap="6px"), self.link("View", "portfolio", justify_self="end"), gap="30px", align="center", tablet="3fr 7fr 2fr", style={"padding_block": "22px", "border_top": "1px solid $c-border"}))
        return self.sec("portfolio", [self.w(self._work_head(), *rows)], tone)

    def portfolio_stack(self, tone=None):
        """Large single pieces one after another, with captions beside them."""
        blocks = []
        for t, m in self.items("projects", 3):
            blocks.append(self.stack(self.img(self.p.get("work_subject"), ratio=2.1, label=t), self.row(self.h(t, 3), self.t(m), justify_content="space-between", gap="20px"), gap="16px", margin_bottom="48px"))
        return self.sec("portfolio", [self.w(self._work_head(), *blocks)], tone)

    def portfolio_gallery(self, tone=None):
        self.seed += 6
        items = [{"kind": "placeholder", "seed": f"{self.s['slug']}-g{i}", "subject": self.p.get("work_subject") or self.p["subject"], "ratio": 1, "label": f"Gallery image {i + 1}"} for i in range(8)]
        gallery = self.node("gallery", {"items": items, "columns": 4}, {"gap": "6px"}, responsive={"mobile": {"props": {"columns": 2}}})
        return self.sec("portfolio", [self.w(self._work_head()), gallery], tone, {"padding_bottom": "0"})

    # Blog ---------------------------------------------------------------------
    def _blog_head(self):
        return self.head(self.p.get("blog_eyebrow", "Journal"), self.p.get("blog_title", "Notes and insights"))

    def blog_cards(self, tone=None):
        cards = [self.stack(self.img(self.p.get("post_subject"), ratio=1.55, label=t), self.t(m, font_size=".84rem"), self.h(t, 3, font_size="1.3rem"), self.t(x, font_size=".97rem"), gap="10px") for t, m, x in self.items("posts", 3)]
        return self.sec("blog", [self.w(self._blog_head(), self.cols(3, *cards, gap="32px"))], tone)

    def blog_list(self, tone=None):
        rows = [self.cols("2fr 7fr 3fr", self.t(m, font_size=".88rem"), self.stack(self.h(t, 3, font_size="clamp(1.25rem,2.4vw,1.8rem)"), self.t(x), gap="6px"), self.link("Read", "blog", justify_self="end"), gap="24px", tablet="2fr 7fr 3fr", style={"padding_block": "26px", "border_top": "1px solid $c-border"}) for t, m, x in self.items("posts", 4)]
        return self.sec("blog", [self.w(self._blog_head(), *rows)], tone)

    def blog_magazine(self, tone=None):
        it = self.items("posts", 5)
        lead = self.stack(self.img(self.p.get("post_subject"), ratio=1.5, label=it[0][0]), self.t(it[0][1], font_size=".84rem"), self.h(it[0][0], 2), self.t(it[0][2], font_size="1.05rem"), gap="12px")
        side = self.cols(2, *[self.stack(self.img(self.p.get("post_subject"), ratio=1.3, label=t), self.t(m, font_size=".8rem"), self.h(t, 4, font_size="1.08rem", line_height="1.22"), gap="8px") for t, m, _ in it[1:5]], gap="26px 22px", mobile=1)
        return self.sec("blog", [self.w(self._blog_head(), self.cols("6fr 6fr", lead, side, gap="44px", tablet=1))], tone)

    # Products -----------------------------------------------------------------
    def _product(self, name, price, meta, ratio):
        return self.stack(self.img(self.p.get("product_subject", "abstract"), ratio=ratio, label=name), self.row(self.h(name, 4), self.t(price, False, font_weight=600), justify_content="space-between", flex_wrap="nowrap", gap="12px", margin_top="6px"), self.t(meta, font_size=".9rem"), gap="4px")

    def _prod_head(self):
        return self.head(self.p.get("products_eyebrow", "Shop"), self.p.get("products_title", "New arrivals"))

    def products_grid4(self, tone=None):
        return self.sec("products", [self.w(self._prod_head(), self.cols(4, *[self._product(n, pr, m, .8) for n, pr, m in self.items("products", 4)], tablet=2, mobile=2, gap="32px 22px"))], tone)

    def products_grid3(self, tone=None):
        return self.sec("products", [self.w(self._prod_head(), self.cols(3, *[self._product(n, pr, m, 1.3) for n, pr, m in self.items("products", 6)], tablet=2, gap="38px 26px"))], tone)

    def products_feature(self, tone=None):
        it = self.items("products", 3)
        return self.sec("products", [self.w(self._prod_head(), self.cols("2fr 1fr 1fr", self._product(*it[0], 1.25), self._product(*it[1], .68), self._product(*it[2], .68), gap="24px", tablet=1))], tone)

    # Events (music, education, hospitality) -----------------------------------
    def events_rows(self, tone=None):
        rows = []
        for d, t, place in self.items("events", 5):
            rows.append(self.cols("2fr 6fr 3fr auto", self.h(d, 4), self.h(t, 3, font_size="clamp(1.2rem,2.4vw,1.8rem)"), self.t(place), self.btn(self.p.get("event_action", "Tickets"), variant="secondary"), gap="14px 22px", align="center", tablet="1fr 3fr", style={"padding_block": "20px", "border_top": "1px solid $c-border"}))
        return self.sec("events", [self.w(self.head(self.p.get("events_eyebrow", "Dates"), self.p.get("events_title", "Upcoming events")), *rows)], tone)

    def events_cards(self, tone=None):
        cards = [self.card(self.h(d, 3, font_size="1.5rem"), self.h(t, 4), self.t(place, font_size=".94rem")) for d, t, place in self.items("events", 3)]
        return self.sec("events", [self.w(self.head(self.p.get("events_eyebrow", "Dates"), self.p.get("events_title", "Upcoming events")), self.cols(3, *cards, tablet=1))], tone)

    # Video --------------------------------------------------------------------
    def video_wide(self, tone=None):
        self.seed += 1
        poster = {"kind": "placeholder", "seed": f"{self.s['slug']}-v{self.seed}", "subject": self.p["subject"], "ratio": 1.78, "label": "Video poster"}
        video = self.node("video", {"poster": poster, "ratio": 1.78, "title": "Play video"}, {"border_radius": "$radius"})
        return self.sec("video", [self.w(self.head(self.p.get("video_eyebrow", "Watch"), self.p.get("video_title", "See it in motion"), align="center"), video)], tone)

    # Call to action -----------------------------------------------------------
    def _cta_title(self):
        return self.s.get("cta", self.p["cta"])

    def cta_band(self, tone="primary"):
        return self.sec("call_to_action", [self.w(self.row(self.h(self._cta_title(), 2, max_width="20em", flex="1 1 320px"), self.btn(self.s.get("cta_action", "Start a conversation")), justify_content="space-between", gap="28px"))], tone, {"padding_block": "64px"})

    def cta_center(self, tone=None):
        return self.sec("call_to_action", [self.w(self.h(self._cta_title(), 2, font_size="clamp(2.2rem,5.6vw,4.6rem)"), self.t(self.p["cta_sub"], font_size="1.1rem"), self.btn(self.s.get("cta_action", "Start a conversation"), margin_top="8px"), width="narrow", gap="18px", style={"align_items": "center", "text_align": "center"})], tone)

    def cta_box(self, tone=None):
        box = self.box(self.h(self._cta_title(), 2), self.t(self.p["cta_sub"], font_size="1.05rem", max_width="50ch"), self.btn(self.s.get("cta_action", "Start a conversation"), align_self="flex-start", margin_top="8px"), tone="primary", style={"gap": "16px", "padding": "clamp(32px,6vw,72px)", "border_radius": "$radius"})
        return self.sec("call_to_action", [self.w(box)], tone)

    def cta_giant(self, tone=None):
        return self.sec("call_to_action", [self.w(self.h(self._cta_title(), 2, font_size="clamp(2.8rem,9vw,8rem)", line_height=".98"), self.row(self.t(self.p["cta_sub"], max_width="44ch"), self.btn(self.s.get("cta_action", "Start a conversation")), justify_content="space-between", gap="24px", margin_top="30px"))], tone)

    def cta_image(self, tone=None):
        return self.sec("call_to_action", [self.w(self.h(self._cta_title(), 2), self.t(self.p["cta_sub"], False, font_size="1.08rem", color=WHITE), self.btn(self.s.get("cta_action", "Start a conversation"), margin_top="8px"), width="narrow", gap="16px", style={"align_items": "center", "text_align": "center"})], tone,
                        {"color": WHITE, "padding_block": "120px"}, self.bg_image(overlay="rgba(6,8,14,.62)"))

    # FAQ ----------------------------------------------------------------------
    def _faqs(self):
        return [self.node("faq_item", {"question": q, "answer": a, "open": i == 0}) for i, (q, a) in enumerate(self.items("faqs", 4))]

    def faq_single(self, tone=None):
        return self.sec("faq", [self.w(self.head("FAQ", "Common questions", align="center"), *self._faqs(), width="narrow")], tone)

    def faq_split(self, tone=None):
        return self.sec("faq", [self.cols("4fr 7fr", self.stack(*self._clean(self.eyebrow("FAQ"), self.h("Common questions"), self.t(self.p["cta_sub"])), gap="12px"), self.box(*self._faqs()), gap="60px", width="content", tablet=1)], tone)

    # Contact ------------------------------------------------------------------
    def _form(self):
        return self.node("contact_form", {
            "fields": self.p.get("form", [{"label": "Your name", "type": "text"}, {"label": "Email address", "type": "email"}, {"label": "Message", "type": "textarea"}]),
            "submit": self.p.get("form_submit", "Send message"),
        })

    def _details(self):
        return [self.row(self.icon(i, font_size="20px"), self.t(x, False), gap="12px", flex_wrap="nowrap") for i, x in (("map-pin", self.p.get("address", "100 Example Road, Your City")), ("phone", "+000 000 000 000"), ("mail", "hello@example.com"))]

    def contact_split(self, tone=None):
        return self.sec("contact", [self.cols("5fr 6fr", self.stack(*self._clean(self.eyebrow("Contact"), self.h(self.p.get("contact_title", "Let’s talk")), self.t(self.p["cta_sub"]), *self._details()), gap="16px"), self._form(), gap="72px", width="content", tablet=1)], tone)

    def contact_card(self, tone=None):
        panel = self.card(self._form(), padding="clamp(24px,4vw,44px)")
        return self.sec("contact", [self.w(self.head("Contact", self.p.get("contact_title", "Let’s talk"), self.p["cta_sub"], align="center"), panel, width="narrow")], tone)

    def contact_image(self, tone=None):
        return self.sec("contact", [self.cols("1fr 1fr", self.img(self.p["subject"], ratio=1, label="Location image"), self.stack(*self._clean(self.eyebrow("Contact"), self.h(self.p.get("contact_title", "Let’s talk")), *self._details(), self.rule(margin_block="8px"), self._form()), gap="14px"), gap="60px", width="content", tablet=1)], tone)

    # Inner page banners -------------------------------------------------------
    def banner(self, kind: str, title: str, sub: str) -> dict:
        if self.overlay or kind == "image":
            return self.sec("page_header", [self.w(self.h(title, 1), self.t(sub, False, font_size="1.15rem", max_width="60ch", color=WHITE), gap="14px")], None,
                            {"padding_block": "170px 80px", "color": WHITE}, self.bg_image(overlay="rgba(6,8,14,.6)"))
        if kind == "tone":
            return self.sec("page_header", [self.w(self.h(title, 1), self.t(sub, font_size="1.15rem", max_width="60ch"), gap="14px")], self.s.get("banner_tone", "primary"), {"padding_block": "90px"})
        if kind == "giant":
            return self.sec("page_header", [self.w(self.h(title, 1, font_size=self._fit(title, 10), line_height=".95"), self.rule(margin_block="26px 14px"), self.t(sub, font_size="1.1rem"))], None, {"padding_block": "56px 30px"})
        if kind == "center":
            return self.sec("page_header", [self.w(self.h(title, 1), self.t(sub, font_size="1.15rem"), width="narrow", gap="14px", style={"text_align": "center", "align_items": "center"})], "surface", {"padding_block": "96px"})
        return self.sec("page_header", [self.w(self.h(title, 1), self.t(sub, font_size="1.15rem", max_width="60ch"), gap="14px")], None, {"padding_block": "72px 12px"})

    def _fit(self, text: str, max_rem: float) -> str:
        return fit_text(text, self.s["fonts"][0], max_rem, self.s["type"].get("heading_transform") == "uppercase")

    # Header and footer --------------------------------------------------------
    def header(self) -> dict:
        h = self.s.get("header", {})
        props: dict[str, Any] = {"layout": h.get("layout", "classic"), "brand": self.s["brand"]}
        if h.get("tone"):
            props["tone"] = h["tone"]
        if h.get("caps"):
            props["nav_style"] = "caps"
        if h.get("sticky"):
            props["sticky"] = True
        if self.overlay:
            props["overlay"] = True
        if h.get("cta"):
            props["cta"] = {"label": h["cta"], "href": {"page": "contact"}}
        style: dict[str, Any] = {}
        if self.overlay:
            style["color"] = WHITE
        elif h.get("rule", True) and h.get("layout") != "masthead":
            style["border_bottom"] = "1px solid $c-border"
        return self.node("header", props, style, name="Site header")

    def _nav_links(self):
        return [self.node("link", {"label": label, "href": {"page": page}}, {"font_weight": 400}) for page, label in zip(PAGE_IDS[1:], self.s["labels"][1:])]

    def footer(self) -> dict:
        kind = self.s.get("footer", "columns")
        tone = self.s.get("footer_tone", "inverse")
        legal = f"© {self.s['brand']}. All rights reserved."
        padding = {"padding_block": "64px 30px"}
        if kind == "simple":
            inner = self.w(self.row(self.h(self.s["brand"], 4), self.row(*self._nav_links(), gap="20px"), justify_content="space-between", gap="20px"), self.rule(margin_block="20px 14px"), self.t(legal, font_size=".84rem"))
            padding = {"padding_block": "40px 26px"}
        elif kind == "wordmark":
            inner = self.w(self.row(*self._nav_links(), gap="26px"), self.h(self.s["brand"], 2, font_size=self._fit(self.s["brand"], 12), line_height="1", margin_block="34px 20px"), self.t(legal, font_size=".84rem"))
        else:
            about = self.stack(self.h(self.s["brand"], 3, font_size="1.5rem"), self.t(self.s.get("footer_line", self.p["about"][:96].rsplit(" ", 1)[0] + "."), font_size=".95rem", max_width="34ch"), gap="10px")
            nav = self.stack(self.h("Explore", 5), *self._nav_links(), gap="8px")
            reach = self.stack(self.h("Contact", 5), self.t(self.p.get("address", "100 Example Road, Your City"), font_size=".95rem"), self.t("hello@example.com", font_size=".95rem"), gap="8px")
            inner = self.w(self.cols("5fr 3fr 4fr", about, nav, reach, gap="40px", tablet="5fr 3fr 4fr"), self.rule(margin_block="40px 14px"), self.t(legal, font_size=".84rem"))
        return self.node("footer", {"tone": tone}, padding, [inner], name="Site footer")

    # Pages --------------------------------------------------------------------
    def expand(self, item: str) -> dict:
        match = re.fullmatch(r"([a-z_0-9]+)(?:@([a-z]+))?", item)
        if not match:
            raise ValueError(item)
        name, tone = match.groups()
        method = getattr(self, name)
        return method(tone) if tone else method()

    def page(self, page_id: str, slug: str, title: str, items: list[str], *, home: bool = False) -> dict:
        return {"id": page_id, "slug": slug, "title": title, "home": home, "layout": "default", "nodes": [self.expand(i) for i in items]}

    def build(self) -> dict:
        s = self.s
        labels = s["labels"]
        banner = s.get("banner", "plain")
        pick = s["inner"]
        pages = [self.page("home", "home", labels[0], s["home"], home=True)]
        titles = self.p["page_subs"]
        for page_id, label in zip(PAGE_IDS[1:], labels[1:]):
            page = self.page(page_id, re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"), label, pick[page_id])
            page["nodes"].insert(0, self.banner(banner, label, titles[page_id]))
            pages.append(page)
        doc = {
            "schema": "mulusa.theme/1",
            "meta": {"id": f"{s['category']}/{s['slug']}", "template_name": s["name"], "name": s["brand"], "description": s["desc"], "author": "Mulusa Innovations", "version": "1.0.0"},
            "tokens": {
                "colors": s["colors"],
                "fonts": {"heading": s["fonts"][0], "body": s["fonts"][1], "extra": s.get("font_extra", [])},
                "type": s["type"],
                "shape": s["shape"],
                "spacing": s["spacing"],
            },
            "palettes": [{"name": s["name"], "colors": s["colors"]}],
            "type_pairs": [{"name": f"{s['fonts'][0]} / {s['fonts'][1]}", "heading": s["fonts"][0], "body": s["fonts"][1]}],
            "site": {"header": self.header(), "footer": self.footer()},
            "navigation": {"primary": [{"label": label, "page": pid} for pid, label in zip(PAGE_IDS[1:], labels[1:])]},
            "pages": pages,
            "media": {"art": s.get("art", "gradient"), "assets": []},
            "reusable": [],
        }
        return doc
