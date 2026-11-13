"""Animated illustrations: original drawings, made in code, coloured by the site and moved by CSS.

Every drawing uses a 240 x 180 canvas and only these classes, defined in base.css:

    fills    fm (primary) fh (accent) fk (ink) fp (panel) fs (soft) fd (deep) fg (glow) fn (none)
    strokes  sm sh sk sl sg sd             opacity  o2 o3 o5 o7
    motion   a-spin a-spinr a-slow a-float a-bob a-pulse a-blink a-glow a-eq a-grow a-growy a-dash
             a-flow a-rise a-flick a-swing a-pan a-lift a-cable a-ripple a-twinkle a-scan a-stack
             a-shackle a-flash a-fly a-hit a-search     delays d1..d6
    origin   vb (rotate about the point given in the element's own transform-origin)

The colours follow the section's tone, so one drawing works on light, dark, brand and photo
backgrounds. Nothing here is user content: names are looked up, never interpolated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Illustration:
    name: str
    title: str
    group: str
    tags: tuple[str, ...]
    body: str


# Drawing helpers ---------------------------------------------------------------------------------------
def _a(cls: str, sw: float = 0, extra: str = "") -> str:
    out = f' class="{cls}"' if cls else ""
    if sw:
        out += f' stroke-width="{sw:g}"'
    return out + (f" {extra}" if extra else "")


def rect(x, y, w, h, rx=0, cls="", sw=0, extra="") -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"' + (f' rx="{rx:g}"' if rx else "") + _a(cls, sw, extra) + "/>"


def circle(cx, cy, r, cls="", sw=0, extra="") -> str:
    return f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}"' + _a(cls, sw, extra) + "/>"


def ellipse(cx, cy, rx, ry, cls="", sw=0, extra="") -> str:
    return f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}"' + _a(cls, sw, extra) + "/>"


def path(d, cls="", sw=0, extra="") -> str:
    return f'<path d="{d}"' + _a(cls, sw, extra) + "/>"


def line(x1, y1, x2, y2, cls="sl", sw=3, extra="") -> str:
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}"' + _a(cls, sw, extra) + "/>"


def poly(points, cls="", sw=0, extra="") -> str:
    return f'<polygon points="{points}"' + _a(cls, sw, extra) + "/>"


def g(inner: str, cls: str = "", origin: tuple[float, float] | None = None) -> str:
    style = f' style="transform-origin:{origin[0]:g}px {origin[1]:g}px"' if origin else ""
    return f"<g{_a(cls)}{style}>{inner}</g>"


def gear(cx, cy, r, teeth, cls, depth=None) -> str:
    depth = depth or r * .24
    pts = []
    step = 2 * math.pi / teeth
    for i in range(teeth):
        a = i * step
        for frac, rad in ((0, r), (.18, r + depth), (.5, r + depth), (.68, r)):
            ang = a + frac * step
            pts.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
    return poly(" ".join(pts), cls)


def sparkle(x, y, s, cls="fh a-twinkle", extra="") -> str:
    d = f"M{x:g} {y - s:g} Q{x:g} {y:g} {x + s:g} {y:g} Q{x:g} {y:g} {x:g} {y + s:g} Q{x:g} {y:g} {x - s:g} {y:g} Q{x:g} {y:g} {x:g} {y - s:g}Z"
    return path(d, cls, extra=extra)


def ground(y=158, x1=24, x2=216) -> str:
    return line(x1, y, x2, y, "sl", 3)


def _dash_len(n: int) -> str:
    return f'style="--len:{n}"'


# The drawings ----------------------------------------------------------------------------------------------
def _gears() -> str:
    return "".join([
        rect(14, 24, 150, 104, 10, "fp sl", 3), rect(26, 36, 126, 80, 5, "fd"),
        rect(38, 50, 62, 6, 3, "fg o5 a-grow"), rect(38, 64, 90, 6, 3, "fg o5 a-grow d2"),
        rect(38, 78, 46, 6, 3, "fh a-grow d3"), rect(38, 92, 74, 6, 3, "fg o5 a-grow d4"),
        rect(78, 128, 22, 14, 0, "fs"), rect(56, 142, 66, 6, 3, "fs"),
        g(gear(180, 98, 28, 10, "fh") + circle(180, 98, 10, "fd"), "a-spin"),
        g(gear(212, 140, 15, 8, "fm") + circle(212, 140, 5.5, "fd"), "a-spinr"),
        sparkle(210, 56, 6), sparkle(148, 20, 4, "fh a-twinkle d3"),
    ])


def _growth() -> str:
    bars = "".join(rect(40 + i * 38, 150 - h, 26, h, 5, ("fh" if i == 3 else "fm") + f" a-growy d{i + 1}") for i, h in enumerate((38, 60, 82, 108)))
    return "".join([
        rect(18, 18, 204, 148, 16, "fp"), line(30, 150, 210, 150, "sl", 3), bars,
        path("M42 118 L86 98 L124 78 L176 42", "sh fn a-dash", 5, _dash_len(170)),
        poly("176,42 160,42 176,58", "fh a-pulse"),
        circle(198, 34, 9, "fh a-bob"), circle(198, 34, 4, "fg a-bob"),
    ])


def _target() -> str:
    arrow = g(line(196, 34, 132, 84, "sk", 5) + poly("196,34 186,26 206,24 204,44", "fh") + poly("132,84 146,82 134,72", "fk"), "a-hit")
    return "".join([
        circle(120, 92, 62, "fp sl", 3), circle(120, 92, 46, "fs"), circle(120, 92, 31, "fm"), circle(120, 92, 15, "fh a-pulse"),
        circle(120, 92, 62, "fn sh a-ripple", 2), arrow, sparkle(50, 40, 6), sparkle(204, 136, 5, "fh a-twinkle d4"),
    ])


def _server() -> str:
    out = []
    for x in (46, 132):
        out.append(rect(x, 22, 62, 132, 8, "fd"))
        for i in range(5):
            y = 34 + i * 23
            out.append(rect(x + 7, y, 48, 16, 3, "fg o2"))
            out.append(line(x + 13, y + 8, x + 33, y + 8, "sg o5", 2))
            out.append(circle(x + 44, y + 8, 2.6, ("fh" if (i + x) % 2 else "fm") + f" a-blink d{(i + x // 40) % 6 + 1}"))
    out += [path("M108 62 C120 62 120 104 132 104", "sh fn a-flow", 3), path("M108 128 C120 128 120 84 132 84", "sm fn a-flow d3", 3),
            ground(158, 30, 210)]
    return "".join(out)


def _cloud() -> str:
    cloud = circle(92, 96, 30, "fm") + circle(130, 80, 38, "fm") + circle(168, 100, 26, "fm") + rect(66, 98, 128, 30, 15, "fm")
    arrows = g(path("M110 102 a18 18 0 0 1 30 -14", "sg fn", 5) + poly("140,80 146,94 132,92", "fg")
               + path("M150 102 a18 18 0 0 1 -30 14", "sg fn", 5) + poly("120,124 114,110 128,112", "fg"), "a-spin a-slow vb", (130, 102))
    rising = "".join(rect(x, 146, 6, 12, 3, f"fh a-rise d{i + 1}") for i, x in enumerate((96, 122, 148)))
    return cloud + arrows + rising + sparkle(46, 52, 6) + sparkle(204, 46, 5, "fh a-twinkle d3")


def _code() -> str:
    lines = [(48, 70, "fh"), (60, 96, "fg o5"), (60, 58, "fg o5"), (72, 84, "fm"), (60, 44, "fg o5"), (48, 30, "fh")]
    rows = "".join(rect(x, 60 + i * 14, w, 6, 3, f"{c} a-grow d{i + 1}") for i, (x, w, c) in enumerate(lines))
    return "".join([
        rect(22, 24, 196, 132, 12, "fd"), rect(22, 24, 196, 24, 12, "fg o2"),
        circle(38, 36, 4, "fh"), circle(52, 36, 4, "fm"), circle(66, 36, 4, "fg o5"),
        rows, rect(110, 128, 3, 12, 1, "fh a-blink"),
        path("M172 92 l-14 12 l14 12 M196 92 l14 12 l-14 12", "sh fn", 4), line(190, 88, 180, 120, "sg o7", 4),
    ])


def _network() -> str:
    nodes = [(48, 46), (196, 42), (210, 128), (40, 132), (124, 160)]
    out = []
    for x, y in nodes:
        out.append(line(120, 92, x, y, "sl", 3))
    for i, (x, y) in enumerate(nodes):
        out.append(line(120, 92, x, y, f"sh a-flow d{i + 1}", 3))
    out.append(circle(120, 92, 22, "fn sm a-ripple", 3))
    out.append(circle(120, 92, 20, "fm"))
    out.append(circle(120, 92, 8, "fg"))
    for i, (x, y) in enumerate(nodes):
        out.append(circle(x, y, 11, ("fh" if i % 2 else "fp sl") + f" a-pulse d{i + 1}", 3 if i % 2 == 0 else 0))
    return "".join(out)


def _shield() -> str:
    shield = "M120 22 L170 40 V86 C170 120 148 144 120 158 C92 144 70 120 70 86 V40 Z"
    return "".join([
        circle(120, 90, 66, "fn sh a-ripple", 2), circle(120, 90, 66, "fn sl a-ripple d3", 2),
        path(shield, "fm"), path("M120 34 L160 48 V86 C160 112 143 132 120 144 Z", "fg o2"),
        path("M98 90 L114 106 L144 74", "sg fn a-dash", 9, _dash_len(80)),
        rect(56, 40, 128, 3, 1.5, "fh a-scan o7"),
    ])


def _lock() -> str:
    return "".join([
        g(path("M94 84 V62 a26 26 0 0 1 52 0 V84", "sk fn", 10), "a-shackle"),
        rect(76, 80, 88, 70, 14, "fm"), circle(120, 108, 9, "fg"), rect(116, 110, 8, 20, 3, "fg"),
        "".join(circle(84 + i * 18, 168, 4.5, f"fh a-blink d{i + 1}") for i in range(5)),
        sparkle(186, 48, 7), sparkle(52, 54, 5, "fh a-twinkle d3"),
    ])


def _cctv() -> str:
    head = g(poly("88,52 18,22 18,142 88,70", "fh o3") + rect(100, 44, 82, 30, 9, "fm") + rect(84, 48, 22, 22, 5, "fd")
             + circle(92, 59, 6, "fg") + circle(170, 52, 3.2, "fh a-blink") + rect(118, 40, 40, 6, 3, "fd"), "a-pan vb", (184, 58))
    return "".join([rect(190, 22, 26, 18, 4, "fk"), line(202, 40, 184, 58, "sk", 7), head, ground(160, 30, 210)])


def _radar() -> str:
    rings = "".join(circle(120, 90, r, "fn sl", 2.5) for r in (24, 46, 68))
    wedge = g(path("M120 90 L120 22 A68 68 0 0 1 172 46 Z", "fh o5"), "a-spin vb", (120, 90))
    blips = circle(152, 64, 4.5, "fh a-twinkle") + circle(86, 118, 4, "fm a-twinkle d3") + circle(140, 132, 3.5, "fh a-twinkle d5")
    return circle(120, 90, 70, "fp") + rings + line(52, 90, 188, 90, "sl", 2) + line(120, 22, 120, 158, "sl", 2) + wedge + blips + circle(120, 90, 5, "fk")


def _equalizer() -> str:
    bars = "".join(rect(40 + i * 18, 60, 12, 84, 6, ("fh" if i % 3 == 1 else "fm") + f" a-eq d{i % 6 + 1}") for i in range(9))
    return rect(24, 30, 192, 132, 18, "fp") + bars + line(36, 150, 204, 150, "sl", 3) + sparkle(200, 22, 6) + sparkle(30, 20, 4, "fh a-twinkle d3")


def _note(x, y, cls) -> str:
    return path(f"M{x} {y} v-18 l12 -4 v18", "sk fn", 3) + ellipse(x - 4, y, 5, 4, cls) + ellipse(x + 8, y - 4, 5, 4, cls)


def _vinyl() -> str:
    record = g(circle(104, 96, 48, "fd") + "".join(circle(104, 96, r, "fn sg o2", 1.5) for r in (40, 32, 24)) + circle(104, 96, 15, "fh")
               + rect(100, 84, 8, 6, 2, "fg o5") + circle(104, 96, 3, "fg"), "a-spin")
    arm = g(line(184, 50, 150, 102, "sk", 5) + rect(140, 98, 16, 10, 3, "fk") + circle(184, 50, 8, "fs sl", 2), "a-swing vb", (184, 50))
    notes = g(_note(196, 118, "fh"), "a-rise") + g(_note(214, 100, "fm"), "a-rise d3")
    return rect(30, 40, 180, 112, 14, "fp sl", 3) + record + arm + notes


def _microphone() -> str:
    grille = "".join(line(104, 44 + i * 10, 136, 44 + i * 10, "sg o5", 2) for i in range(5))
    waves = "".join(
        path(f"M{120 - d} {58 - d / 2} a{d * 1.4} {d * 1.4} 0 0 0 0 {d + 40}", f"sh fn a-glow d{i + 1}", 4)
        + path(f"M{120 + d} {58 - d / 2} a{d * 1.4} {d * 1.4} 0 0 1 0 {d + 40}", f"sh fn a-glow d{i + 1}", 4)
        for i, d in enumerate((54, 70)))
    return "".join([
        waves, rect(98, 28, 44, 70, 22, "fm"), grille,
        path("M84 76 a36 36 0 0 0 72 0", "sk fn", 5), line(120, 112, 120, 140, "sk", 5), rect(92, 140, 56, 8, 4, "fk"),
    ])


def _headphones() -> str:
    beat = path("M72 96 H96 L104 76 L116 118 L126 64 L136 108 L144 96 H168", "sh fn a-dash", 4, _dash_len(170))
    return "".join([
        path("M58 108 V92 a62 62 0 0 1 124 0 V108", "sk fn", 9),
        rect(42, 96, 32, 56, 14, "fm a-bob"), rect(166, 96, 32, 56, 14, "fm a-bob d2"),
        rect(52, 104, 12, 40, 6, "fh"), rect(176, 104, 12, 40, 6, "fh"), beat,
        g(_note(36, 50, "fh"), "a-rise"), g(_note(200, 46, "fm"), "a-rise d4"),
    ])


def _crane() -> str:
    mast = rect(62, 34, 14, 124, 0, "fh") + "".join(line(62, 40 + i * 20, 76, 54 + i * 20, "sd o5", 2) for i in range(6))
    return "".join([
        rect(150, 112, 70, 46, 4, "fp sl", 3), rect(160, 122, 12, 12, 2, "fs"), rect(184, 122, 12, 12, 2, "fs"), rect(160, 140, 12, 12, 2, "fs"),
        mast, rect(26, 30, 178, 8, 2, "fh"), rect(26, 38, 22, 16, 2, "fd"), rect(66, 40, 18, 14, 3, "fm"),
        line(69, 30, 120, 14, "sl", 2.5), line(69, 30, 40, 18, "sl", 2.5), rect(146, 36, 18, 6, 2, "fk"),
        line(155, 42, 155, 120, "sk a-cable", 2.5), g(rect(139, 120, 32, 22, 3, "fm") + line(146, 120, 155, 112, "sk", 2) + line(164, 120, 155, 112, "sk", 2), "a-lift"),
        ground(158, 20, 220),
    ])


def _building() -> str:
    floors = []
    for i in range(6):
        y = 136 - i * 20
        cls = "fm" if i % 2 == 0 else "fh"
        win = "".join(rect(86 + j * 18, y + 6, 10, 8, 2, "fg o7") for j in range(4))
        floors.append(g(rect(76, y, 88, 20, 2, cls) + win, f"a-stack d{i + 1}"))
    return circle(186, 40, 16, "fh a-pulse") + rect(30, 108, 36, 48, 3, "fp sl", 3) + rect(174, 96, 36, 60, 3, "fp sl", 3) + "".join(floors) + ground(158, 20, 220)


def _rocket() -> str:
    rocket = g("".join([
        path("M106 124 Q120 172 134 124 Z", "fh a-flick vb", extra='style="transform-origin:120px 124px"'),
        path("M112 124 Q120 154 128 124 Z", "fg a-flick d2 vb", extra='style="transform-origin:120px 124px"'),
        path("M120 20 C142 40 148 70 148 100 V126 H92 V100 C92 70 98 40 120 20 Z", "fm"),
        circle(120, 70, 13, "fd"), circle(120, 70, 8, "fg o5"),
        path("M92 98 L72 128 H92 Z", "fh"), path("M148 98 L168 128 H148 Z", "fh"), rect(110, 112, 20, 14, 3, "fd"),
    ]), "a-float")
    stars = sparkle(44, 40, 7) + sparkle(196, 60, 6, "fh a-twinkle d2") + sparkle(60, 120, 4, "fh a-twinkle d4") + circle(200, 130, 3, "fs a-twinkle d3") + circle(34, 84, 2.5, "fs a-twinkle d5")
    smoke = circle(98, 166, 10, "fs a-pulse") + circle(120, 170, 12, "fs a-pulse d2") + circle(142, 166, 10, "fs a-pulse d3")
    return stars + smoke + rocket


def _camera() -> str:
    blades = g(poly("120,86 137,96 137,116 120,126 103,116 103,96", "fg o3"), "a-spin a-slow")
    burst = g(line(166, 46, 166, 34, "sh", 4) + line(180, 52, 190, 44, "sh", 4) + line(152, 52, 142, 44, "sh", 4), "a-flash")
    return "".join([
        rect(80, 42, 50, 22, 8, "fm"), rect(36, 58, 168, 98, 18, "fm"), rect(154, 66, 26, 12, 4, "fg a-flash"), burst,
        circle(120, 106, 38, "fd"), circle(120, 106, 27, "fn sg o5", 3), blades, circle(108, 94, 6, "fg o7"),
        rect(52, 70, 22, 8, 4, "fd"),
    ])


def _coffee() -> str:
    steam = "".join(path(f"M{x} 66 c-10 -12 10 -20 0 -34", f"sl fn a-rise d{i + 1}", 4) for i, x in enumerate((96, 120, 144)))
    return "".join([
        steam, ellipse(120, 150, 78, 12, "fs"), path("M66 76 H174 L164 136 a18 18 0 0 1 -18 14 H94 a18 18 0 0 1 -18 -14 Z", "fm"),
        ellipse(120, 78, 54, 8, "fd"), path("M172 92 a18 18 0 0 1 0 34", "sm fn", 9), ellipse(98, 104, 6, 9, "fg o3"),
    ])


def _pan() -> str:
    food = circle(100, 70, 9, "fh a-hop") + circle(124, 60, 7, "fm a-hop d2") + circle(144, 72, 8, "fh a-hop d4")
    flames = "".join(path(f"M{x} 160 q-10 -16 0 -30 q10 14 0 30Z", f"fh a-flick d{i + 1} vb", extra=f'style="transform-origin:{x}px 160px"') for i, x in enumerate((96, 120, 144)))
    return food + ellipse(120, 112, 62, 18, "fd") + ellipse(120, 106, 56, 12, "fp") + rect(176, 100, 52, 10, 5, "fk") + flames


def _heartbeat() -> str:
    grid = "".join(line(30, y, 210, y, "sg o2", 1) for y in (60, 84, 108, 132))
    ecg = path("M34 104 H80 L90 84 L100 128 L114 52 L126 116 L134 98 H206", "sh fn a-dash", 4, _dash_len(260))
    heart = path("M180 50 c-6 -12 -24 -10 -24 4 c0 12 24 26 24 26 s24 -14 24 -26 c0 -14 -18 -16 -24 -4Z", "fh a-pulse")
    return rect(20, 28, 200, 128, 14, "fd") + grid + ecg + heart + rect(96, 156, 48, 8, 3, "fs")


def _solar() -> str:
    rays = g("".join(line(60 + 30 * math.cos(a), 50 + 30 * math.sin(a), 60 + 40 * math.cos(a), 50 + 40 * math.sin(a), "sh", 4)
                     for a in (i * math.pi / 4 for i in range(8))), "a-spin a-slow vb", (60, 50))
    cells = "".join(line(98 + i * 20, 150 - i * 0, 132 + i * 20, 88, "sg o5", 2) for i in range(1, 4))
    return "".join([
        rays, circle(60, 50, 22, "fh a-pulse"), poly("88,150 196,150 216,88 112,88", "fm"), cells, line(100, 119, 206, 119, "sg o5", 2),
        line(150, 150, 150, 168, "sk", 5), path("M196 34 L184 58 H198 L188 80", "sh fn a-glow", 4), ground(168, 60, 220),
    ])


def _mine() -> str:
    wheel = lambda cx: g(circle(cx, 36, 14, "fn sk", 4) + line(cx - 14, 36, cx + 14, 36, "sk", 2.5) + line(cx, 22, cx, 50, "sk", 2.5), "a-spin vb", (cx, 36))
    return "".join([
        path("M60 158 L104 36 L148 158", "fn sk", 6), line(78, 110, 130, 110, "sk", 4), line(90, 76, 118, 76, "sk", 4),
        wheel(104), wheel(140), line(104, 50, 104, 100, "sk a-cable", 2.5), g(rect(92, 100, 24, 22, 3, "fh"), "a-lift"),
        line(140, 50, 182, 130, "sl", 2.5), rect(170, 128, 40, 30, 4, "fm"), path("M24 158 Q60 128 96 158 Z", "fp"),
        circle(176, 160, 6, "fk"), circle(204, 160, 6, "fk"), ground(164, 20, 220),
    ])


def _graduation() -> str:
    cap = g(poly("120,38 186,62 120,86 54,62", "fd") + path("M84 72 V96 c0 10 72 10 72 0 V72 L120 86 Z", "fd")
            + g(line(176, 66, 176, 100, "sh", 3) + circle(176, 104, 5, "fh"), "a-swing vb", (176, 66)), "a-float")
    books = rect(56, 132, 128, 16, 4, "fm") + rect(66, 116, 110, 16, 4, "fh") + rect(60, 148, 120, 14, 4, "fp sl", 2)
    return cap + books + sparkle(40, 40, 6) + sparkle(204, 34, 5, "fh a-twinkle d3") + sparkle(206, 118, 4, "fh a-twinkle d5")


def _shopping() -> str:
    tag = g(line(156, 64, 170, 84, "sk", 2) + poly("162,84 186,80 196,104 172,110", "fh") + circle(172, 90, 3, "fg"), "a-swing vb", (156, 64))
    return "".join([
        path("M98 62 V50 a22 22 0 0 1 44 0 V62", "sk fn", 6), path("M70 62 H170 L178 156 H62 Z", "fm"), tag,
        circle(56, 52, 16, "fh a-pulse"), path("M50 58 L62 46", "sg", 3), circle(51, 47, 2.5, "fg"), circle(61, 57, 2.5, "fg"),
        sparkle(204, 40, 6), ellipse(120, 162, 70, 6, "fs"),
    ])


def _calendar() -> str:
    cells = "".join(rect(42 + c * 26, 74 + r * 22, 18, 14, 3, "fs") for r in range(3) for c in range(5))
    hands = g(line(172, 128, 172, 104, "sk", 4), "a-spin vb", (172, 128)) + g(line(172, 128, 188, 128, "sk", 4), "a-spin a-slow vb", (172, 128))
    return "".join([
        rect(30, 34, 150, 120, 12, "fp sl", 3), rect(30, 34, 150, 28, 12, "fm"), rect(56, 26, 8, 18, 4, "fk"), rect(146, 26, 8, 18, 4, "fk"),
        cells, rect(94, 96, 18, 14, 3, "fh a-pulse"), circle(172, 128, 32, "fd"), circle(172, 128, 26, "fg o2"), hands, circle(172, 128, 4, "fh"),
    ])


def _pin() -> str:
    pin = g(path("M120 30 a32 32 0 0 1 32 32 c0 26 -32 60 -32 60 s-32 -34 -32 -60 a32 32 0 0 1 32 -32Z", "fh") + circle(120, 62, 12, "fg"), "a-bob")
    return "".join([
        poly("26,70 82,54 158,72 214,56 214,150 158,166 82,148 26,164", "fp sl", 3), line(82, 54, 82, 148, "sl", 2), line(158, 72, 158, 166, "sl", 2),
        path("M44 140 C70 110 100 150 120 124", "sm fn a-flow", 4), ellipse(120, 128, 22, 7, "fn sh a-ripple", 3), pin,
    ])


def _search() -> str:
    page = rect(40, 24, 118, 138, 10, "fp sl", 3) + "".join(rect(56, 46 + i * 16, w, 6, 3, "fs") for i, w in enumerate((70, 86, 54, 80, 62, 40)))
    glass = g(circle(150, 96, 30, "fg o3") + circle(150, 96, 30, "fn sk", 8) + line(172, 118, 200, 146, "sk", 12), "a-search")
    return page + glass + sparkle(206, 40, 6) + circle(30, 150, 3, "fh a-twinkle d3")


def _plane() -> str:
    plane = g(poly("70,96 196,44 140,138 124,104", "fm") + poly("124,104 196,44 110,124", "fh") + poly("124,104 140,138 126,116", "fd"), "a-fly")
    trail = path("M20 150 C50 130 60 118 84 112", "sl fn a-flow", 3)
    return circle(54, 50, 14, "fs") + circle(70, 46, 18, "fs") + rect(40, 46, 50, 18, 9, "fs") + circle(190, 132, 10, "fs") + rect(180, 126, 36, 16, 8, "fs") + trail + plane


def _car() -> str:
    wheel = lambda cx: g(circle(cx, 126, 18, "fd") + circle(cx, 126, 7, "fg") + line(cx - 12, 126, cx + 12, 126, "sg o5", 3) + line(cx, 114, cx, 138, "sg o5", 3), "a-spin vb", (cx, 126))
    return "".join([
        "".join(line(14, y, 44, y, f"sl a-blink d{i + 1}", 3) for i, y in enumerate((84, 100, 116))),
        path("M50 120 V102 c0 -8 6 -12 14 -14 l26 -6 l26 -26 h48 c10 0 18 6 22 14 l12 24 c10 2 16 8 16 18 V120 Z", "fm"),
        path("M98 80 l22 -20 h38 c6 0 10 4 12 8 l8 16 Z", "fg o7"), line(136, 60, 136, 84, "sm", 4), rect(196, 104, 12, 8, 3, "fh a-glow"),
        wheel(84), wheel(172), line(20, 146, 220, 146, "sl", 3), line(20, 158, 220, 158, "sl a-flow", 4),
    ])


def _community() -> str:
    person = lambda x, y, s, cls, d: g(circle(x, y, 13 * s, cls) + path(f"M{x - 24 * s} {y + 56 * s} a{24 * s} {26 * s} 0 0 1 {48 * s} 0 Z", cls), f"a-bob {d}")
    heart = lambda x, y, cls: path(f"M{x} {y} c-4 -8 -16 -7 -16 3 c0 8 16 17 16 17 s16 -9 16 -17 c0 -10 -12 -11 -16 -3Z", cls)
    return "".join([
        ellipse(120, 150, 92, 10, "fs"), person(72, 90, .9, "fm", "d2"), person(168, 90, .9, "fm", "d4"), person(120, 76, 1.15, "fh", ""),
        g(heart(120, 34, "fh"), "a-rise"), g(heart(184, 50, "fm"), "a-rise d3"), g(heart(56, 54, "fh"), "a-rise d5"),
    ])


def _hanger() -> str:
    dress = path("M104 76 L92 96 L104 104 L84 158 H156 L136 104 L148 96 L136 76 Q120 86 104 76Z", "fm")
    return g(path("M120 30 a10 10 0 1 1 10 10 v8", "sk fn", 4) + path("M120 48 L60 76 H180 Z", "fn sk", 5) + dress + rect(112, 120, 16, 4, 2, "fh"),
             "a-swing vb", (120, 30)) + sparkle(42, 40, 6) + sparkle(200, 120, 5, "fh a-twinkle d3")


def _lightbulb() -> str:
    rays = "".join(line(120 + 58 * math.cos(a), 78 + 58 * math.sin(a), 120 + 72 * math.cos(a), 78 + 72 * math.sin(a), f"sh a-glow d{i % 6 + 1}", 5)
                   for i, a in enumerate(math.radians(d) for d in (200, 230, 270, 310, 340)))
    return "".join([
        rays, path("M120 34 a44 44 0 0 1 26 80 v14 h-52 v-14 a44 44 0 0 1 26 -80Z", "fh o3"),
        path("M120 34 a44 44 0 0 1 26 80 v14 h-52 v-14 a44 44 0 0 1 26 -80Z", "fn sk", 4),
        path("M106 104 l8 -24 l6 14 l6 -14 l8 24", "sh fn a-glow", 4), rect(98, 132, 44, 8, 4, "fs"), rect(102, 144, 36, 8, 4, "fs"), rect(110, 156, 20, 6, 3, "fk"),
    ])


def _palette() -> str:
    shape = "M118 34 c50 0 86 30 86 66 c0 26 -24 30 -40 24 c-14 -6 -26 4 -22 18 c4 14 -8 26 -26 26 c-48 0 -82 -30 -82 -66 c0 -38 36 -68 84 -68Z"
    brush = g(line(196, 30, 150, 96, "sk", 7) + path("M150 96 l-10 18 l18 -10 Z", "fh"), "a-swing vb", (196, 30))
    return "".join([
        path(shape, "fp sl", 3), circle(80, 76, 11, "fh"), circle(112, 60, 11, "fm"), circle(148, 66, 11, "fd"), circle(70, 112, 11, "fg sl", 2),
        ellipse(110, 112, 14, 11, "fs"), path("M44 162 C80 146 120 172 168 154", "sh fn a-dash", 7, _dash_len(140)), brush,
    ])


_DRAWINGS = (
    ("gears", "Maintenance gears", "Business", ("maintenance", "corporate", "engineering"), _gears),
    ("growth", "Growth chart", "Business", ("finance", "corporate", "consulting", "analytics"), _growth),
    ("target", "On target", "Business", ("strategy", "marketing", "corporate"), _target),
    ("server", "Server rack", "Technology", ("ict", "data", "hosting", "it"), _server),
    ("cloud", "Cloud sync", "Technology", ("ict", "saas", "cloud", "software"), _cloud),
    ("code", "Code editor", "Technology", ("software", "developer", "ict", "web"), _code),
    ("network", "Network", "Technology", ("ict", "networking", "telecoms", "connectivity"), _network),
    ("shield", "Shield scan", "Security", ("security", "cybersecurity", "protection", "insurance"), _shield),
    ("lock", "Padlock", "Security", ("security", "privacy", "cybersecurity", "login"), _lock),
    ("cctv", "CCTV camera", "Security", ("security", "surveillance", "guarding", "cctv"), _cctv),
    ("radar", "Radar", "Security", ("monitoring", "security", "detection", "defence"), _radar),
    ("equalizer", "Equaliser", "Music", ("music", "audio", "radio", "events"), _equalizer),
    ("vinyl", "Record player", "Music", ("music", "artist", "album", "dj"), _vinyl),
    ("microphone", "Microphone", "Music", ("music", "podcast", "radio", "speaker"), _microphone),
    ("headphones", "Headphones", "Music", ("music", "audio", "producer", "streaming"), _headphones),
    ("crane", "Tower crane", "Construction", ("construction", "engineering", "building"), _crane),
    ("building", "Rising building", "Construction", ("construction", "real estate", "property", "architecture"), _building),
    ("mine", "Mine headframe", "Industry", ("mining", "industry", "resources", "engineering"), _mine),
    ("solar", "Solar power", "Industry", ("energy", "solar", "power", "green"), _solar),
    ("rocket", "Rocket launch", "Launch", ("launch", "startup", "coming soon", "saas"), _rocket),
    ("plane", "Paper plane", "Launch", ("newsletter", "contact", "travel", "send"), _plane),
    ("search", "Page search", "Launch", ("404", "not found", "search"), _search),
    ("camera", "Camera", "Creative", ("photography", "studio", "film", "media"), _camera),
    ("palette", "Paint palette", "Creative", ("art", "design", "creative", "studio"), _palette),
    ("lightbulb", "Bright idea", "Creative", ("ideas", "innovation", "agency", "consulting"), _lightbulb),
    ("hanger", "Fashion hanger", "Creative", ("fashion", "boutique", "clothing"), _hanger),
    ("coffee", "Coffee", "Food and hospitality", ("cafe", "coffee", "restaurant", "hospitality"), _coffee),
    ("pan", "Chef's pan", "Food and hospitality", ("restaurant", "kitchen", "food", "catering"), _pan),
    ("heartbeat", "Heartbeat", "Health and community", ("health", "clinic", "medical", "fitness"), _heartbeat),
    ("community", "Community", "Health and community", ("ngo", "community", "charity", "church"), _community),
    ("graduation", "Graduation", "Health and community", ("education", "school", "training", "university"), _graduation),
    ("shopping", "Shopping bag", "Commerce and places", ("shop", "e-commerce", "retail", "sale"), _shopping),
    ("calendar", "Event calendar", "Commerce and places", ("events", "booking", "schedule", "conference"), _calendar),
    ("pin", "Map pin", "Commerce and places", ("location", "travel", "tourism", "contact"), _pin),
    ("car", "Car", "Commerce and places", ("automotive", "garage", "transport", "logistics"), _car),
)

ILLUSTRATIONS: dict[str, Illustration] = {name: Illustration(name, title, group, tags, "") for name, title, group, tags, _ in _DRAWINGS}
_BUILDERS = {name: build for name, *_, build in _DRAWINGS}
DEFAULT = "gears"


@lru_cache(maxsize=64)
def illustration_svg(name: str, label: str = "") -> str:
    """The drawing as inline SVG. Unknown names fall back to the default rather than failing."""
    key = name if name in _BUILDERS else DEFAULT
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return (f'<svg viewBox="0 0 240 180" xmlns="http://www.w3.org/2000/svg" stroke-linecap="round" stroke-linejoin="round" '
            f'focusable="false" {aria}>{_BUILDERS[key]()}</svg>')


_FILL = {"fm": "primary", "fh": "accent", "fk": "ink", "fp": "panel", "fs": "soft", "fd": "deep", "fg": "glow", "fn": "none"}
_STROKE = {"sm": "primary", "sh": "accent", "sk": "ink", "sl": "line", "sg": "glow", "sd": "deep"}
_OPACITY = {"o2": ".2", "o3": ".3", "o5": ".5", "o7": ".7"}


def static_svg(name: str, colors: dict[str, str], dark: bool = False) -> str:
    """A still copy with plain colour attributes, for previews drawn without a browser (no CSS classes)."""
    import re
    ink = colors.get("background" if dark else "text", "#16202b")
    palette = {
        "primary": colors.get("primary", "#1f3a5f"), "accent": colors.get("accent", "#d9822b"), "ink": ink,
        "panel": ink, "soft": ink, "line": ink, "deep": colors.get("secondary", "#16293f"), "glow": "#ffffff", "none": "none",
    }
    alpha = {"panel": ".09", "soft": ".2", "line": ".34"}

    def repaint(match: "re.Match[str]") -> str:
        attrs = []
        names = match.group(1).split()
        for cls in names:
            if cls in _FILL:
                role = _FILL[cls]
                attrs.append(f'fill="{palette[role]}"' + (f' fill-opacity="{alpha[role]}"' if role in alpha else ""))
            elif cls in _STROKE:
                role = _STROKE[cls]
                attrs.append(f'stroke="{palette[role]}"' + (f' stroke-opacity="{alpha[role]}"' if role in alpha else ""))
                if not any(c in _FILL for c in names):
                    attrs.append('fill="none"')
            elif cls in _OPACITY:
                attrs.append(f'opacity="{_OPACITY[cls]}"')
        return " ".join(attrs)

    svg = illustration_svg(name)
    svg = re.sub(r'\s*style="[^"]*"', "", svg)
    return re.sub(r'class="([^"]*)"', repaint, svg)


def names() -> list[str]:
    return list(ILLUSTRATIONS)
