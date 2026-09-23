#!/usr/bin/env python3
"""Generate the picture on the opening screen.

It is a 1987 Sierra-style picture: sixteen EGA colours (plus one tan the EGA
never had), a 160-wide picture of double-wide pixels, and the IBM PC 8x8 font
for the title. It is composed here on a pixel grid and written out as an SVG
of rectangles, which is why it is crisp at any size: no font is involved in
drawing it, and the site's Content-Security-Policy is happy because colours
are SVG attributes, not styles.

Do not edit the art in frontend/templates/login.html by hand. Change the
sprite or the scene here, then:

    python admin/login_art.py            # a rough look at it as text
    python admin/login_art.py --write    # put it into login.html

tests/test_login_art.py fails if the template and this file disagree.
"""
import sys
from pathlib import Path

# The EGA palette, index 0..15, and one extra.
PALETTE = [
    "#000000", "#0000AA", "#00AA00", "#00AAAA", "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
    "#555555", "#5555FF", "#55FF55", "#55FFFF", "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
    "#CC8844",   # 16: a tan, between EGA's brown and its light red
]
(BLACK, BLUE, GREEN, CYAN, RED, MAGENTA, BROWN, LGREY,
 DGREY, LBLUE, LGREEN, LCYAN, LRED, LMAGENTA, YELLOW, WHITE, TAN) = range(17)

# The IBM PC 8x8 font (public domain, from dhepper/font8x8): one byte per row,
# least significant bit leftmost. Only the letters the screen uses.
GLYPHS = {
    " ": b"\x00\x00\x00\x00\x00\x00\x00\x00",
    "H": b"333?333\x00", "I": b"\x1e\x0c\x0c\x0c\x0c\x0c\x1e\x00", "P": b"?ff>\x06\x06\x0f\x00",
    "S": b"\x1e3\x07\x0e83\x1e\x00", "U": b"333333?\x00", "Y": b"333\x1e\x0c\x0c\x1e\x00",
    "a": b"\x00\x00\x1e0>3n\x00", "b": b"\x07\x06\x06>ff;\x00", "d": b"800>33n\x00",
    "e": b"\x00\x00\x1e3?\x03\x1e\x00", "i": b"\x0c\x00\x0e\x0c\x0c\x0c\x1e\x00",
    "l": b"\x0e\x0c\x0c\x0c\x0c\x0c\x1e\x00", "m": b"\x00\x003\x7f\x7fkc\x00",
    "n": b"\x00\x00\x1f3333\x00", "o": b"\x00\x00\x1e333\x1e\x00", "r": b"\x00\x00;nf\x06\x0f\x00",
    "s": b"\x00\x00>\x03\x1e0\x1f\x00", "t": b"\x08\x0c>\x0c\x0c,\x18\x00",
    "u": b"\x00\x003333n\x00", "y": b"\x00\x00333>0\x1f",
}

TITLE, SUBTITLE = "SISYPHUS", "bulletin board system"
LABEL = "Sisyphus bulletin board system: Sisyphus pushing his boulder up the mountain under the stars"

SW, SH = 320, 200            # the screen, in screen pixels
PW, PH = SW // 2, SH         # the picture, in double-wide picture pixels
DISPLAY_WIDTH = 480          # CSS pixels on the page: 1.5x, which is 3x on a retina display

# Sisyphus in profile, leaning into the stone. Sprite pixels, doubled below.
# h hair, f skin, k eye, w loincloth.
HERO = """
........hhhh....
.......hhhhhh...
.......hhffff...
.......hhffkf...
.......hfffff...
........ffff....
.........ff.....
.......fffffffff
.......fffffffff
......ffff......
.....fffffffffff
.....fffffffffff
....ffff........
...wwwww........
...wwwww........
...wwwww........
..fff..ff.......
.fff...fff......
.ff.....ff......
ff......ffff....
ff..............
ff..............
fff.............
""".strip("\n").split("\n")
# Twice the size of an AGI walker: close to the camera, so the face reads.
HERO = ["".join(ch * 2 for ch in row) for row in HERO for _ in range(2)]
HERO_COLOURS = {"h": DGREY, "f": TAN, "k": BLACK, "w": WHITE}

STARS = [(6, 62), (30, 70), (52, 60), (75, 66), (100, 61), (120, 72), (140, 64),
         (18, 84), (44, 92), (66, 80), (150, 78), (10, 104), (34, 110), (58, 100)]

STONE_CENTRE, STONE_RADIUS = 108, 24     # picture px; the radius is the vertical one
SLOPE = 0.66                             # picture rows per picture column


class Screen:
    """A grid of palette indexes, None where nothing has been drawn."""

    def __init__(self):
        self.px = [[None] * SW for _ in range(SH)]

    def dot(self, x, y, c):
        if 0 <= x < SW and 0 <= y < SH:
            self.px[y][x] = c

    def pic(self, x, y, c):
        """A picture pixel: two screen pixels wide."""
        self.dot(2 * x, y, c)
        self.dot(2 * x + 1, y, c)

    def pic_at(self, x, y):
        return self.px[y][2 * x] if 0 <= x < PW and 0 <= y < PH else None

    def text(self, s, x, y, c, scale=1):
        for i, ch in enumerate(s):
            for r, byte in enumerate(GLYPHS[ch]):
                for b in range(8):
                    if byte >> b & 1:
                        for dy in range(scale):
                            for dx in range(scale):
                                self.dot(x + (i * 8 + b) * scale + dx, y + r * scale + dy, c)


def surface(x):
    """The hillside's row at a picture column: it rises to the right."""
    return int(PH - 1 - x * SLOPE)


def compose():
    s = Screen()

    s.text(TITLE, (SW - len(TITLE) * 8 * 3) // 2, 10, YELLOW, scale=3)
    s.text(SUBTITLE, (SW - len(SUBTITLE) * 8) // 2, 40, LGREY)

    for x, y in STARS:
        s.pic(x, y, WHITE if (x + y) % 3 else YELLOW)

    for x in range(PW):
        top = surface(x)
        for y in range(top, PH):
            s.pic(x, y, LGREEN if y == top else GREEN)

    # The stone: a circle on screen, so an ellipse in picture pixels; lit from
    # the upper left, the way Sierra shaded things.
    cx, r = STONE_CENTRE, STONE_RADIUS
    cy = surface(cx) - r + 1
    for y in range(PH):
        for x in range(PW):
            dx, dy = (x - cx) * 2, (y - cy)
            if dx * dx + dy * dy <= (2 * r) ** 2:
                lit = (dx + 12) ** 2 + (dy + 12) ** 2 <= (2 * r - 10) ** 2
                s.pic(x, y, LGREY if lit else DGREY)

    # Sisyphus, walked to the right until his hands meet the stone.
    cells = [(dy, dx, ch) for dy, row in enumerate(HERO) for dx, ch in enumerate(row) if ch != "."]
    fh, fw = len(HERO), len(HERO[0])
    fx = cx - r - fw
    for _ in range(fw):
        fy = surface(fx) - fh + 1
        if any(s.pic_at(fx + dx + 1, fy + dy) in (LGREY, DGREY) for dy, dx, _ in cells):
            break
        fx += 1
    for dy, dx, ch in cells:
        s.pic(fx + dx, fy + dy, HERO_COLOURS[ch])
    return s


def as_svg(screen: Screen) -> str:
    """Every run of same-coloured pixels on a row is one rectangle."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SW} {SH}" '
        f'width="{DISPLAY_WIDTH}" height="{DISPLAY_WIDTH * SH // SW}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{LABEL}">'
    ]
    for y in range(SH):
        x = 0
        while x < SW:
            c = screen.px[y][x]
            if c is None:
                x += 1
                continue
            run = 1
            while x + run < SW and screen.px[y][x + run] == c:
                run += 1
            parts.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{PALETTE[c]}"/>')
            x += run
    parts.append("</svg>")
    return "".join(parts)


def as_text(screen: Screen) -> str:
    """A rough preview: one character per picture pixel, hex digit of its colour."""
    rows = []
    for y in range(0, SH, 2):                          # halve the height so it is roughly to scale
        rows.append("".join("0123456789abcdeft"[c] if (c := screen.pic_at(x, y)) is not None else " "
                            for x in range(PW)).rstrip())
    return "\n".join(rows)


TEMPLATE = Path(__file__).resolve().parent.parent / "frontend" / "templates" / "login.html"
BEGIN, END = "{# login-art:begin #}", "{# login-art:end #}"


def in_template(template_text: str) -> str:
    """The art currently in the template, between its markers."""
    return template_text[template_text.index(BEGIN) + len(BEGIN):template_text.index(END)]


def block() -> str:
    """What belongs between the markers. {% raw %} keeps Jinja's hands off the art."""
    return "{% raw %}" + as_svg(compose()) + "{% endraw %}"


if __name__ == "__main__":
    if "--write" in sys.argv:
        text = TEMPLATE.read_text(encoding="utf-8")
        text = text[:text.index(BEGIN) + len(BEGIN)] + block() + text[text.index(END):]
        TEMPLATE.write_text(text, encoding="utf-8")
        print(f"wrote {TEMPLATE}")
    else:
        print(as_svg(compose()) if "--svg" in sys.argv else as_text(compose()))
