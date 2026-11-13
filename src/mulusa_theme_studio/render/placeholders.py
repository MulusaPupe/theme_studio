"""Generated placeholder artwork.

A placeholder is a reference in the document, such as
``{"kind": "placeholder", "seed": "hero", "subject": "portrait", "ratio": 1.5}``.
It is drawn from the current colour tokens as an SVG each time a page is rendered,
so it follows the palette, is never baked into a design, and is replaced simply by
pointing the reference at a media asset.
"""
from __future__ import annotations

import random
import urllib.parse


def _mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _is_dark(color: str) -> bool:
    red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return .299 * red + .587 * green + .114 * blue < 60


def _portrait(w, h, fg, r):
    cx = w * r.uniform(.42, .58)
    head = min(w, h) * .19
    cy = h * .42
    return (
        f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{head:.0f}" ry="{head * 1.2:.0f}" fill="{fg}"/>'
        f'<path d="M{cx - head * 2.5:.0f} {h} C{cx - head * 2.4:.0f} {cy + head * 1.7:.0f} {cx - head:.0f} {cy + head * 1.35:.0f} {cx:.0f} {cy + head * 1.35:.0f} '
        f'C{cx + head:.0f} {cy + head * 1.35:.0f} {cx + head * 2.4:.0f} {cy + head * 1.7:.0f} {cx + head * 2.5:.0f} {h}Z" fill="{fg}"/>'
    )


def _building(w, h, fg, r):
    parts, x = [], -10.0
    while x < w:
        bw = w * r.uniform(.11, .2)
        bh = h * r.uniform(.32, .82)
        parts.append(f'<rect x="{x:.0f}" y="{h - bh:.0f}" width="{bw:.0f}" height="{bh:.0f}" fill="{fg}" opacity="{r.uniform(.45, 1):.2f}"/>')
        for wy in range(int(h - bh) + 16, int(h) - 8, 26):
            for wx in range(int(x) + 8, int(x + bw) - 10, 20):
                if r.random() > .45:
                    parts.append(f'<rect x="{wx}" y="{wy}" width="9" height="13" fill="#fff" opacity=".16"/>')
        x += bw + w * .012
    return "".join(parts)


def _food(w, h, fg, r):
    cx, cy, rad = w * .5, h * .52, min(w, h) * .36
    dots = "".join(
        f'<circle cx="{cx + r.uniform(-.5, .5) * rad:.0f}" cy="{cy + r.uniform(-.5, .5) * rad:.0f}" r="{rad * r.uniform(.07, .19):.0f}" fill="#fff" opacity="{r.uniform(.14, .34):.2f}"/>'
        for _ in range(7)
    )
    return (
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad * 1.12:.0f}" fill="{fg}" opacity=".5"/>'
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad * .82:.0f}" fill="{fg}"/>{dots}'
    )


def _garment(w, h, fg, r):
    cx, top, s = w * .5, h * .14, min(w, h) * .0052
    return (
        f'<g transform="translate({cx:.0f} {top:.0f}) scale({s:.2f})" fill="{fg}">'
        '<path d="M-22 0 C-10 14 10 14 22 0 L52 12 L46 62 L30 56 C34 92 50 124 72 150 L-72 150 C-50 124 -34 92 -30 56 L-46 62 L-52 12Z"/></g>'
    )


def _vinyl(w, h, fg, r):
    cx, cy, rad = w * r.uniform(.42, .6), h * .52, min(w, h) * .4
    rings = "".join(
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad * t:.0f}" fill="none" stroke="#fff" stroke-opacity=".1" stroke-width="1.5"/>'
        for t in (.5, .58, .66, .74, .82, .9)
    )
    return (
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad:.0f}" fill="{fg}"/>{rings}'
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad * .3:.0f}" fill="#fff" opacity=".28"/>'
        f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad * .05:.0f}" fill="#000" opacity=".6"/>'
    )


def _landscape(w, h, fg, r):
    sun = f'<circle cx="{w * r.uniform(.2, .8):.0f}" cy="{h * .3:.0f}" r="{min(w, h) * .1:.0f}" fill="#fff" opacity=".35"/>'
    hills = ""
    for i, op in enumerate((.45, .7, 1)):
        y = h * (.55 + i * .14)
        hills += (
            f'<path d="M0 {y:.0f} C{w * .25:.0f} {y - h * r.uniform(.08, .2):.0f} {w * .55:.0f} {y + h * .1:.0f} {w} {y - h * r.uniform(.02, .14):.0f} '
            f'L{w} {h} L0 {h}Z" fill="{fg}" opacity="{op}"/>'
        )
    return sun + hills


def _interior(w, h, fg, r):
    floor = h * .72
    return (
        f'<rect y="{floor:.0f}" width="{w}" height="{h - floor:.0f}" fill="{fg}" opacity=".55"/>'
        f'<rect x="{w * .6:.0f}" y="{h * .14:.0f}" width="{w * .28:.0f}" height="{floor - h * .14:.0f}" fill="#fff" opacity=".2"/>'
        f'<rect x="{w * .1:.0f}" y="{floor - h * .2:.0f}" width="{w * .42:.0f}" height="{h * .2:.0f}" rx="12" fill="{fg}"/>'
        f'<rect x="{w * .13:.0f}" y="{floor - h * .28:.0f}" width="{w * .36:.0f}" height="{h * .12:.0f}" rx="12" fill="{fg}" opacity=".75"/>'
        f'<circle cx="{w * .25:.0f}" cy="{h * .24:.0f}" r="{min(w, h) * .07:.0f}" fill="#fff" opacity=".3"/>'
    )


def _circuit(w, h, fg, r):
    parts = []
    for _ in range(11):
        x, y = r.uniform(0, w), r.uniform(0, h)
        x2, y2 = x + r.choice((-1, 1)) * r.uniform(40, w * .4), y + r.choice((-1, 1)) * r.uniform(30, h * .35)
        parts.append(f'<path d="M{x:.0f} {y:.0f} H{x2:.0f} V{y2:.0f}" fill="none" stroke="{fg}" stroke-width="3" opacity=".8"/>')
        parts.append(f'<circle cx="{x2:.0f}" cy="{y2:.0f}" r="7" fill="#fff" opacity=".5"/>')
    side = min(w, h) * .3
    parts.append(f'<rect x="{w * .5 - side / 2:.0f}" y="{h * .5 - side / 2:.0f}" width="{side:.0f}" height="{side:.0f}" rx="14" fill="{fg}"/>')
    return "".join(parts)


def _books(w, h, fg, r):
    parts, x = [], w * .12
    base = h * .82
    while x < w * .86:
        bw = w * r.uniform(.035, .07)
        bh = h * r.uniform(.34, .62)
        parts.append(f'<rect x="{x:.0f}" y="{base - bh:.0f}" width="{bw:.0f}" height="{bh:.0f}" fill="{fg}" opacity="{r.uniform(.55, 1):.2f}"/>')
        x += bw + 4
    parts.append(f'<rect x="{w * .07:.0f}" y="{base:.0f}" width="{w * .86:.0f}" height="7" fill="{fg}"/>')
    return "".join(parts)


def _shapes(w, h, fg, r):
    parts = []
    for _ in range(r.randint(3, 5)):
        x, y, s = r.uniform(0, w), r.uniform(0, h), min(w, h) * r.uniform(.14, .42)
        op = r.uniform(.3, .85)
        if r.random() < .5:
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{s:.0f}" fill="{fg}" opacity="{op:.2f}"/>')
        else:
            angle = r.choice((0, 15, 45, -20))
            parts.append(f'<rect x="{x - s / 2:.0f}" y="{y - s / 2:.0f}" width="{s:.0f}" height="{s:.0f}" fill="{fg}" opacity="{op:.2f}" transform="rotate({angle} {x:.0f} {y:.0f})"/>')
    return "".join(parts)


def _crane(w, h, fg, r):
    x = w * r.uniform(.3, .6)
    lattice = "".join(f'<path d="M{x - 8:.0f} {y} L{x + 8:.0f} {y + 16}" stroke="#fff" stroke-opacity=".3" stroke-width="2"/>' for y in range(int(h * .22), int(h), 16))
    return (
        _building(w, h, fg, r).replace('opacity="', 'data-o="').replace("data-o=", 'opacity=".4" data-o=')
        + f'<rect x="{x - 10:.0f}" y="{h * .2:.0f}" width="20" height="{h * .8:.0f}" fill="{fg}"/>{lattice}'
        + f'<rect x="{x - w * .14:.0f}" y="{h * .18:.0f}" width="{w * .5:.0f}" height="11" fill="{fg}"/>'
        + f'<path d="M{x + w * .3:.0f} {h * .19:.0f} V{h * .45:.0f}" stroke="{fg}" stroke-width="3"/>'
        + f'<rect x="{x + w * .27:.0f}" y="{h * .45:.0f}" width="{w * .06:.0f}" height="{h * .05:.0f}" fill="{fg}"/>'
    )


_SUBJECTS = {
    "portrait": _portrait, "building": _building, "food": _food, "garment": _garment, "vinyl": _vinyl,
    "landscape": _landscape, "interior": _interior, "circuit": _circuit, "books": _books,
    "abstract": _shapes, "crane": _crane,
}


def placeholder_svg(ref: dict, colors: dict, art: str = "gradient") -> str:
    ratio = float(ref.get("ratio") or 1.5)
    w = 900
    h = round(w / max(ratio, .2))
    r = random.Random(str(ref.get("seed", "x")))
    primary, secondary, accent = colors["primary"], colors["secondary"], colors["accent"]
    pairs = [(primary, secondary), (secondary, accent), (accent, primary), (primary, accent)]
    a, b = r.choice(pairs)
    if art == "mono":
        ink = colors["text"] if r.random() < .6 else colors["muted"]
        a, b = _mix(ink, colors["background"], .16), _mix(ink, colors["background"], .5)
    elif art == "soft":
        a, b = _mix(a, colors["background"], .55), _mix(b, colors["background"], .7)
    elif art == "flat":
        b = a
    fg = _mix(a, colors["text"], .35) if art == "soft" else _mix(a, "#000000", .3)
    if a == b and _is_dark(a):
        # A flat near-black panel would hide its subject, so lift the panel and the subject.
        a = b = _mix(a, "#ffffff", .1)
        fg = _mix(a, "#ffffff", .22)
    elif _is_dark(a) and art != "soft":
        fg = _mix(a, "#ffffff", .16)
    subject = _SUBJECTS.get(str(ref.get("subject", "abstract")), _shapes)(w, h, fg, r)
    extra = ""
    if art == "line":
        extra = "".join(f'<path d="M0 {y} H{w}" stroke="#fff" stroke-opacity=".07"/>' for y in range(0, h, 18))
    angle_x, angle_y = r.choice(((0, 1), (1, 1), (1, 0), (.2, 1)))
    glow = (
        f'<circle cx="{r.uniform(0, w):.0f}" cy="{r.uniform(0, h * .5):.0f}" r="{min(w, h) * .55:.0f}" fill="url(#g)"/>'
        if art != "flat" else ""
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">'
        f'<defs><linearGradient id="b" x1="0" y1="0" x2="{angle_x}" y2="{angle_y}"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'
        '<radialGradient id="g"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
        f'<rect width="{w}" height="{h}" fill="url(#b)"/>{glow}{extra}{subject}</svg>'
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="/:=' ,.-()")
