#!/usr/bin/env python3
"""Generate pyfloor README/docs screenshots from REAL tool output.

Renders the actual stdout of `pyfloor check` (broken + clean samples) and
`pyfloor --help` as dark-terminal mockups. Nothing here is fabricated:
every line comes from running the tool itself via subprocess.

Outputs (written next to this script):
    terminal.png   - `pyfloor check samples/broken`  (~1100x600)
    cli-help.png   - `pyfloor --help`                (~1100x600)
    clean.png      - `pyfloor check samples/good`    (~1100x600)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---- Colors (GitHub-dark inspired) -----------------------------------------
BG = (13, 17, 23)  # #0d1117
BG_TERM = (22, 27, 34)  # #161b22 slightly lighter panel
TITLE_BAR = (13, 17, 23)
WHITE = (230, 237, 243)  # #e6edf3
GRAY = (139, 148, 158)  # #8b949e
CYAN = (57, 208, 216)  # #39d0d8
GREEN = (63, 185, 80)  # #3fb950
RED = (248, 81, 73)  # #f85149
ORANGE = (255, 107, 53)  # #ff6b35 (accent, page only)

MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
SANS_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _first_existing(candidates):
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


def load_fonts():
    mono = _first_existing(MONO_CANDIDATES)
    bold = _first_existing(BOLD_CANDIDATES) or mono
    sans = _first_existing(SANS_CANDIDATES)
    if not mono:
        print(
            "WARNING: no monospace font found; falling back to default", file=sys.stderr
        )
    return mono, bold, sans


def run_cli(args, cwd):
    """Run pyfloor CLI and return its real stdout as text."""
    proc = subprocess.run(
        [sys.executable, "-m", "pyfloor.cli"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    out = proc.stdout
    return out


def color_for_line(line):
    """Pick a color for one line of tool output."""
    if line.startswith("[FAIL]"):
        return RED
    if line.startswith("[WARN]"):
        return ORANGE
    if "Declared floor" in line or "Findings:" in line or "Declaration sites:" in line:
        return WHITE
    if line.startswith("pyfloor audit"):
        return CYAN
    # Header/table rows.
    if line.startswith("SOURCE") or set(line.strip()) == {"-"}:
        return CYAN
    # Version output line.
    if line.startswith("pyfloor "):
        return WHITE
    if line.startswith("usage:"):
        return CYAN
    if "no problematic features" in line:
        return GREEN
    return WHITE


def render_terminal(
    output_lines,
    prompt,
    title,
    out_path,
    font_path,
    bold_path,
    sans_path,
    size=1100,
    line_h=None,
):
    """Render a terminal mockup with the given output lines."""
    # Measure with the actual font at a fixed size.
    fs = 20
    font = ImageFont.truetype(font_path, fs) if font_path else ImageFont.load_default()
    bold = ImageFont.truetype(bold_path, fs) if bold_path else font
    sans = ImageFont.truetype(sans_path, 15) if sans_path else font

    pad_x = 36
    pad_top = 88  # room for title bar
    pad_bottom = 30
    line_h = line_h or (fs + 10)

    # Build display rows: (text, color, is_prompt). Wrap long lines to
    # keep the terminal mockup a sane width.
    max_chars = 74
    rows = []
    rows.append((prompt, GREEN, True))
    for line in output_lines:
        if not line.strip():
            rows.append(("", GRAY, False))
            continue
        text = line.rstrip()
        col = color_for_line(line)
        # Wrap on word boundaries so long messages don't break mid-word.
        while len(text) > max_chars:
            cut = text.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            rows.append((text[:cut], col, False))
            text = text[cut:].lstrip()
        rows.append((text, col, False))

    # Pre-measure width.
    max_w = 0
    for text, _c, _p in rows:
        max_w = max(max_w, font.getlength(text))
    w = max(size, int(min(max_w + pad_x * 2, size + 160)))
    h = pad_top + pad_bottom + len(rows) * line_h

    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # Title bar: three traffic-light dots + centered label.
    d.rectangle([0, 0, w, 44], fill=TITLE_BAR)
    dot_y = 22
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 20 + i * 22
        d.ellipse([cx, dot_y - 6, cx + 12, dot_y + 6], fill=col)
    label = "pyfloor — bash"
    d.text((w - sans.getlength(label) - 20, 15), label, fill=GRAY, font=sans)

    # Body panel.
    body_top = 44
    d.rectangle([0, body_top, w, h], fill=BG)

    # Prompt arrow.
    arrow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arrow)

    y = pad_top
    for text, col, is_prompt in rows:
        if is_prompt:
            # Render "~$ " prompt prefix in green.
            d.text((pad_x, y), "~$ ", fill=GREEN, font=bold)
            d.text((pad_x + font.getlength("~$ "), y), text, fill=WHITE, font=font)
        else:
            d.text((pad_x, y), text, fill=col, font=font)
        y += line_h

    img.save(out_path)
    return w, h, len(rows)


def main():
    here = Path(__file__).resolve().parent
    repo = here.parent
    font_path, bold_path, sans_path = load_fonts()

    # Real outputs.
    broken = run_cli(["check", "samples/broken"], repo)
    good = run_cli(["check", "samples/good"], repo)
    help_out = run_cli(["--help"], repo)

    broken_lines = broken.splitlines()
    good_lines = good.splitlines()
    help_lines = help_out.splitlines()

    # terminal.png: broken sample (findings).
    w, h, n = render_terminal(
        broken_lines,
        "pyfloor check samples/broken",
        "pyfloor — broken sample",
        here / "terminal.png",
        font_path,
        bold_path,
        sans_path,
    )
    print(f"terminal.png: {w}x{h}, {n} rows")

    # cli-help.png
    w, h, n = render_terminal(
        help_lines,
        "pyfloor --help",
        "pyfloor — help",
        here / "cli-help.png",
        font_path,
        bold_path,
        sans_path,
    )
    print(f"cli-help.png: {w}x{h}, {n} rows")

    # clean.png
    w, h, n = render_terminal(
        good_lines,
        "pyfloor check samples/good",
        "pyfloor — clean project",
        here / "clean.png",
        font_path,
        bold_path,
        sans_path,
    )
    print(f"clean.png: {w}x{h}, {n} rows")


if __name__ == "__main__":
    main()
