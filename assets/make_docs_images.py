#!/usr/bin/env python3
"""Generate docs images for pyfloor: favicon.ico and og-image.png."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (13, 17, 23)
CYAN = (57, 208, 216)
WHITE = (230, 237, 243)
GRAY = (139, 148, 158)
DARK = (22, 27, 34)

SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def draw_glyph(d, cx, cy, s, color):
    """Draw a floor/steps glyph: three ascending blocks (a 'floor' motif)."""
    step = s / 3.0
    # Bottom step.
    d.rectangle(
        [cx - s * 0.45, cy - step * 0.5, cx + s * 0.45, cy + step * 0.5],
        fill=color,
    )
    # Middle step (right-shifted, lower).
    d.rectangle(
        [cx - s * 0.05, cy - step * 1.1, cx + s * 0.85, cy - step * 0.5],
        fill=color,
    )
    # Top step (higher, shorter).
    d.rectangle(
        [cx + s * 0.15, cy - step * 1.7, cx + s * 0.85, cy - step * 1.1],
        fill=color,
    )


def make_favicon(out_path):
    s = 32
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)
    draw_glyph(d, s / 2, s / 2 + 1, s * 0.72, CYAN)
    img.save(out_path, format="ICO", sizes=[(32, 32), (16, 16)])
    return s, s


def make_og_image(out_path):
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # Subtle accent bar on the left.
    d.rectangle([0, 0, 14, h], fill=CYAN)

    font_big = ImageFont.truetype(SANS_BOLD, 130)
    font_sub = ImageFont.truetype(SANS, 46)
    font_small = ImageFont.truetype(MONO, 30)

    # Draw the glyph on the right.
    draw_glyph(d, w - 220, 250, 190, CYAN)

    # Title.
    d.text((80, 190), "pyfloor", fill=WHITE, font=font_big)

    # Tagline.
    d.text(
        (80, 360),
        "Audit the Python version floor",
        fill=CYAN,
        font=font_sub,
    )
    d.text((80, 420), "of your project.", fill=GRAY, font=font_sub)

    # CLI hint at the bottom.
    d.text((80, 520), "$ pyfloor check .", fill=(63, 185, 80), font=font_small)

    img.save(out_path)
    return w, h


def main():
    here = Path(__file__).resolve().parent
    print("favicon: %dx%d" % make_favicon(here / "favicon.ico"))
    print("og-image: %dx%d" % make_og_image(here / "og-image.png"))


if __name__ == "__main__":
    main()
