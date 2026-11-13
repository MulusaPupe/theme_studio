"""Writes pictures for the test posts, using only generated shapes."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for index, (a, b) in enumerate((("#16325c", "#b58a3c"), ("#2c3e50", "#8aa4bd"), ("#3a5a78", "#d7b46a"), ("#20406f", "#a0522d"))):
    image = Image.new("RGB", (1400, 900), a)
    draw = ImageDraw.Draw(image)
    draw.rectangle((180 + index * 90, 160, 1200, 760), fill=b)
    draw.ellipse((300, 240, 900 - index * 60, 840 - index * 60), outline="#ffffff", width=8)
    image.save(out / f"post-{index + 1}.jpg", quality=90)
