#!/usr/bin/env python3
"""Generate the ASCII art on the opening screen.

The art is composed on a character grid, so columns cannot drift, and every
cell remembers which layer drew it, so the output can be coloured with one CSS
class per layer (title, subtitle, hill, stone, man, star). No inline styles:
the site's Content-Security-Policy forbids them.

Do not edit the art in frontend/templates/login.html by hand. Change the
sprites here, then:

    python admin/login_art.py            # look at it as plain text
    python admin/login_art.py --write    # put it into login.html

tests/test_login_art.py fails if the template and this file disagree.

Sprites use "~" for "opaque but blank": it hides whatever is behind it, which
is how the stone covers the hillside passing behind it.
"""
import html
import sys
from pathlib import Path

W, H = 60, 20

# "SISYPHUS" in figlet's "standard" face, letter by letter so it can be checked.
_GLYPHS = {
    "S": (" ____  ", "/ ___| ", "\\___ \\ ", " ___) |", "|____/ "),
    "I": (" ___ ", "|_ _|", " | | ", " | | ", "|___|"),
    "Y": ("__   __", "\\ \\ / /", " \\ V / ", "  | |  ", "  |_|  "),
    "P": (" ____  ", "|  _ \\ ", "| |_) |", "|  __/ ", "|_|    "),
    "H": (" _   _ ", "| | | |", "| |_| |", "|  _  |", "|_| |_|"),
    "U": (" _   _ ", "| | | |", "| | | |", "| |_| |", " \\___/ "),
}
TITLE = "\n".join("".join(_GLYPHS[ch][row] for ch in "SISYPHUS").rstrip() for row in range(5))

SUBTITLE = "b u l l e t i n   b o a r d   s y s t e m"

BOULDER = r"""
        _..-------.._
     ,-'~~~~~~~~~~~~~`-.
   ,'~~~~~~~.~~~~~~~~~~~`.
  /~~~~'~~~~~~~~~~~~~,~~~~\
 |~~~~~~~~~~~~~~~~~~~~~~~~~|
 |~~~~~~~~~,~~~~~~~~~~~~~~~|
 |~~.~~~~~~~~~~~~~~~~~'~~~~|
  \~~~~~~~~~~~~~~~~~~~~~~~/
   `.~~~~~~~~'~~~~~~~~~~,'
     `-._~~~~~~~~~~~_.-'
         `--.....--'
""".strip("\n")

# Leaning into it: head forward, a solid back, both hands on the stone, the
# rear leg driving and the front knee bent with that foot a row higher up the
# hill. Nine rows tall with arms six columns long, so that he is built like a
# person: a character cell is twice as tall as it is wide, which is why the
# five-row version seemed all arms.
FIGURE = r"""
          __
         (~~)
         _\/____
        /~/----'
       /~/
      /_/
      / \
     /   \
    /    |
  _/
""".strip("\n")

STARS = (
    (0, 4, "*"), (1, 17, "."), (3, 10, "."), (2, 24, "*"), (5, 2, "."), (7, 13, "."),
    (4, 19, "."), (9, 5, "*"), (0, 57, "."), (2, 59, "*"), (11, 9, "."),
)


def canvas(height):
    return [[(" ", "")] * W for _ in range(height)]


def stamp(grid, row, col, sprite, layer):
    for dr, line in enumerate(sprite.split("\n")):
        for dc, ch in enumerate(line):
            if ch != " " and 0 <= row + dr < len(grid) and 0 <= col + dc < W:
                grid[row + dr][col + dc] = (" ", "") if ch == "~" else (ch, layer)


def slope_row(col):
    """The row of the hillside's surface at a column: one row up per four columns."""
    return (H - 1) - col // 4


def compose():
    title_lines = TITLE.split("\n")
    width = max(len(line) for line in title_lines)
    offset = (W - width) // 2

    head = canvas(len(title_lines) + 2)
    stamp(head, 0, offset, TITLE, "title")
    stamp(head, len(title_lines), offset + (width - len(SUBTITLE)) // 2, SUBTITLE, "sub")

    g = canvas(H)
    for col in range(0, W, 4):
        stamp(g, slope_row(col), col, "_.-'", "hill")
    stamp(g, 0, 32, BOULDER, "stone")
    stamp(g, 5, 18, FIGURE, "man")
    for row, col, ch in STARS:
        if g[row][col][0] == " ":
            g[row][col] = (ch, "star")
    return head + g


def as_text(grid):
    return "\n".join("".join(ch for ch, _ in row).rstrip() for row in grid)


def as_html(grid):
    lines = []
    for row in grid:
        while row and row[-1][0] == " ":
            row = row[:-1]
        out, run, layer = [], "", None
        for ch, cell_layer in row:
            # Blanks ride along with whatever run they are in; they have no colour to get wrong.
            if ch != " " and cell_layer != layer:
                if run:
                    out.append(f'<span class="art-{layer}">{html.escape(run)}</span>' if layer else html.escape(run))
                run, layer = "", cell_layer
            run += ch
        if run:
            out.append(f'<span class="art-{layer}">{html.escape(run)}</span>' if layer else html.escape(run))
        lines.append("".join(out))
    return "\n".join(lines)


TEMPLATE = Path(__file__).resolve().parent.parent / "frontend" / "templates" / "login.html"
BEGIN, END = "{# login-art:begin #}", "{# login-art:end #}"


def in_template(template_text: str) -> str:
    """The art currently in the template, between its markers."""
    return template_text[template_text.index(BEGIN) + len(BEGIN):template_text.index(END)]


def block() -> str:
    """What belongs between the markers. {% raw %} keeps Jinja's hands off the art."""
    return "{% raw %}" + as_html(compose()) + "{% endraw %}"


if __name__ == "__main__":
    if "--write" in sys.argv:
        text = TEMPLATE.read_text(encoding="utf-8")
        text = text[:text.index(BEGIN) + len(BEGIN)] + block() + text[text.index(END):]
        TEMPLATE.write_text(text, encoding="utf-8")
        print(f"wrote {TEMPLATE}")
    else:
        print(as_html(compose()) if "--html" in sys.argv else as_text(compose()))
