"""The opening-screen art is generated (admin/login_art.py), not hand-edited."""

import importlib.util
import re
from html import unescape
from pathlib import Path

import pytest

from lib import config
from tests.helpers import anon_client

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("login_art", ROOT / "admin" / "login_art.py")
login_art = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(login_art)


def test_the_template_holds_exactly_what_the_generator_makes():
    template = (config.TEMPLATES_DIR / "login.html").read_text(encoding="utf-8")
    assert login_art.in_template(template) == login_art.block(), (
        "login.html and admin/login_art.py disagree; run: python admin/login_art.py --write"
    )


def test_the_art_fits_its_box_and_the_type_scales_to_fit_a_phone():
    lines = login_art.as_text(login_art.compose()).split("\n")
    widest = max(len(line) for line in lines)
    assert widest <= login_art.W == 60
    assert all(line == line.rstrip() for line in lines)
    assert "b u l l e t i n   b o a r d   s y s t e m" in lines[5]

    # The stylesheet's divisor must cover every column, or a phone scrolls sideways.
    css = (config.STATIC_DIR / "style.css").read_text()
    divisor = float(re.search(r"font-size: min\(11px, calc\(\(100vw - 40px\) / ([\d.]+)\)\)", css).group(1))
    assert divisor >= widest * 0.6


def test_the_title_spells_the_name():
    title = login_art.TITLE.split("\n")
    assert len(title) == 5 and len({len(row) for row in (r.ljust(54) for r in title)}) == 1
    # Each letter is its own column block; read the glyph widths back off the top row.
    assert "".join(ch for ch in "SISYPHUS") == "SISYPHUS"
    widths = [len(login_art._GLYPHS[ch][0]) for ch in "SISYPHUS"]
    assert sum(widths) == 54 and all(len(set(map(len, login_art._GLYPHS[ch]))) == 1 for ch in "SISYPHU")


def test_he_is_built_like_a_person():
    """A cell is twice as tall as wide, so compare in units of column-widths."""
    grid = login_art.compose()
    man = [(r, c) for r, row in enumerate(grid) for c, (_, layer) in enumerate(row) if layer == "man"]
    height = (max(r for r, _ in man) - min(r for r, _ in man) + 1) * 2
    arm_row = min(r for r, _ in man) + 2
    arms = max(c for r, c in man if r == arm_row) - min(c for r, c in man if r == arm_row)
    assert height >= 18
    assert arms <= height / 2, f"arms {arms} columns on a body {height} column-widths tall"


def test_the_picture_is_what_it_says_it_is():
    grid = login_art.compose()
    layers = {layer for row in grid for _, layer in row if layer}
    assert layers == {"title", "sub", "hill", "stone", "man", "star"}

    def cells(layer):
        return [(r, c) for r, row in enumerate(grid) for c, (_, l) in enumerate(row) if l == layer]

    hill, stone, man = cells("hill"), cells("stone"), cells("man")
    # The hillside rises to the right, as far as it can be seen before the stone hides it.
    last_visible = max(c for _, c in hill)
    assert min(r for r, c in hill if c < 8) > max(r for r, c in hill if c > last_visible - 4) + 4
    # He is below and to the left of the stone, and his hands reach it.
    assert max(c for _, c in man) + 1 >= min(c for _, c in stone)
    assert min(c for _, c in man) < min(c for _, c in stone)
    # His feet are on the hill: the lowest part of him touches a hill cell.
    foot_row, foot_col = max(man)
    assert any(abs(r - foot_row) <= 1 and abs(c - foot_col) <= 2 for r, c in hill)
    # The stone's outline is whole: nothing else was drawn over its left edge.
    left_edge = {r: min(c for rr, c in stone if rr == r) for r in {r for r, _ in stone}}
    assert all(grid[r][c][1] == "stone" for r, c in left_edge.items())


def test_every_layer_has_a_colour_and_none_is_inline():
    css = (config.STATIC_DIR / "style.css").read_text()
    for layer in ("title", "sub", "hill", "stone", "man", "star"):
        assert f".art-{layer}" in css, layer
    rule = css[css.index(".login-box pre {"):]
    rule = rule[:rule.index("}")]
    # Centring each line shears the art; table display eats the newlines between spans.
    assert "text-align: center" not in rule and "display: table" not in rule
    assert "style=" not in login_art.as_html(login_art.compose())


@pytest.mark.asyncio
async def test_the_page_serves_the_art_intact():
    async with anon_client() as client:
        page = (await client.get("/")).text
    pre = re.search(r"<pre[^>]*>(.*?)</pre>", page, re.DOTALL).group(1)
    assert "{%" not in pre and "login-art" not in pre          # Jinja's markers are gone
    shown = unescape(re.sub(r"<[^>]+>", "", pre))
    assert shown == login_art.as_text(login_art.compose())
    assert 'role="img"' in page and "pushing a boulder" in page
