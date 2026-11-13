"""Original background patterns and gradients.

Patterns are drawn with Pillow from a few parameters and the site's own colours, then added
to the project as an ordinary image asset, so they export everywhere a photo does.
Gradients are CSS gradients made of the site's colour tokens, so they follow palette changes.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PATTERNS = {
    "dots": {"name": "Dot grid", "description": "Even dots on the section colour."},
    "grid": {"name": "Blueprint grid", "description": "Fine grid lines, like drafting paper."},
    "diagonal": {"name": "Diagonal lines", "description": "Thin 45 degree stripes."},
    "cross": {"name": "Cross stitch", "description": "Small plus signs in a lattice."},
    "circles": {"name": "Concentric rings", "description": "Rings radiating from one corner."},
    "chevron": {"name": "Chevrons", "description": "Repeating chevron rows."},
    "waves": {"name": "Waves", "description": "Soft horizontal wave lines."},
    "triangles": {"name": "Triangles", "description": "A tessellation of triangles in two tones."},
}

GRADIENTS = {
    "primary-secondary": {"name": "Primary to secondary", "description": "A diagonal blend of the two main colours.",
                          "css": "linear-gradient(135deg,$c-primary,$c-secondary)"},
    "primary-accent": {"name": "Primary to accent", "description": "A bold blend toward the accent colour.",
                       "css": "linear-gradient(120deg,$c-primary,$c-accent)"},
    "surface-fade": {"name": "Surface fade", "description": "A quiet fade from surface to background.",
                     "css": "linear-gradient(180deg,$c-surface,$c-background)"},
    "spotlight": {"name": "Spotlight", "description": "A soft radial light on the primary colour.",
                  "css": "radial-gradient(circle at 30% 20%,$c-accent,$c-primary 60%)"},
    "dusk": {"name": "Dusk", "description": "Secondary into text colour, for dark sections.",
             "css": "linear-gradient(160deg,$c-secondary,$c-text)"},
}

SIZE = (1600, 900)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def render_pattern(key: str, background: str, ink: str, target: Path, size: tuple[int, int] = SIZE) -> Path:
    """Draws a pattern into a PNG file and returns its path."""
    if key not in PATTERNS:
        raise KeyError(key)
    bg, fg = _rgb(background), _rgb(ink)
    line = _mix(bg, fg, 0.22)
    image = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(image)
    w, h = size
    if key == "dots":
        for y in range(16, h, 32):
            for x in range(16, w, 32):
                d.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=line)
    elif key == "grid":
        for x in range(0, w, 40):
            d.line((x, 0, x, h), fill=_mix(bg, fg, 0.12 if x % 200 else 0.25), width=1)
        for y in range(0, h, 40):
            d.line((0, y, w, y), fill=_mix(bg, fg, 0.12 if y % 200 else 0.25), width=1)
    elif key == "diagonal":
        for x in range(-h, w, 22):
            d.line((x, h, x + h, 0), fill=line, width=2)
    elif key == "cross":
        for y in range(20, h, 40):
            for x in range(20 + (20 if (y // 40) % 2 else 0), w, 40):
                d.line((x - 5, y, x + 5, y), fill=line, width=2)
                d.line((x, y - 5, x, y + 5), fill=line, width=2)
    elif key == "circles":
        for r in range(40, int((w ** 2 + h ** 2) ** 0.5), 34):
            d.ellipse((w - r, h - r, w + r, h + r), outline=line, width=2)
    elif key == "chevron":
        for y in range(-20, h + 40, 36):
            pts = []
            for i, x in enumerate(range(0, w + 40, 40)):
                pts.append((x, y + (14 if i % 2 else 0)))
            d.line(pts, fill=line, width=3, joint="curve")
    elif key == "waves":
        import math
        for y0 in range(10, h, 30):
            pts = [(x, y0 + 8 * math.sin(x / 60 + y0 / 90)) for x in range(0, w + 10, 10)]
            d.line(pts, fill=line, width=2)
    elif key == "triangles":
        s = 80
        alt = _mix(bg, fg, 0.08)
        for row, y in enumerate(range(0, h + s, s)):
            for col, x in enumerate(range(-s, w + s, s // 2 * 2)):
                up = (row + col) % 2 == 0
                tri = [(x, y + s), (x + s // 2 * 2, y + s), (x + s // 2, y)] if up else [(x, y), (x + s, y), (x + s // 2, y + s)]
                d.polygon(tri, fill=alt if up else bg, outline=_mix(bg, fg, 0.14))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, optimize=True)
    return target
