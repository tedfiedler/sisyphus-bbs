"""The opening-screen picture is generated (admin/login_art.py), not hand-edited."""

import importlib.util
import re
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


def _cells(screen, colours):
    return [(y, x) for y, row in enumerate(screen.px) for x, c in enumerate(row) if c in colours]


def test_the_picture_is_what_it_says_it_is():
    s = login_art.compose()
    hill = _cells(s, {login_art.GREEN, login_art.LGREEN})
    stone = _cells(s, {login_art.LGREY, login_art.DGREY})
    man = _cells(s, set(login_art.HERO_COLOURS.values()) | {login_art.TAN})
    # The subtitle is light grey too; the stone is what is below the text.
    stone = [(y, x) for y, x in stone if y > 56]
    # The hillside rises to the right.
    assert min(y for y, x in hill if x < 4) > min(y for y, x in hill if x > login_art.SW - 4) + 60
    # He is below and to the left of the stone, and his hands reach it.
    assert max(x for _, x in man) + 1 >= min(x for _, x in stone)
    assert min(x for _, x in man) < min(x for _, x in stone)
    # His feet are on the hill.
    foot_y, foot_x = max(man)
    assert any(abs(y - foot_y) <= 2 and abs(x - foot_x) <= 4 for y, x in hill)
    # The stone is whole: nothing was drawn over its left edge.
    left_edge = {y: min(x for yy, x in stone if yy == y) for y in {y for y, _ in stone}}
    assert all(s.px[y][x] in (login_art.LGREY, login_art.DGREY) for y, x in left_edge.items())
    # And it is lit from the upper left.
    assert s.px[min(left_edge) + 6][left_edge[min(left_edge) + 6] + 8] == login_art.LGREY


def test_he_has_a_face():
    eye = [(y, x) for y, row in enumerate(login_art.HERO) for x, ch in enumerate(row) if ch == "k"]
    hair = [(y, x) for y, row in enumerate(login_art.HERO) for x, ch in enumerate(row) if ch == "h"]
    skin = [(y, x) for y, row in enumerate(login_art.HERO) for x, ch in enumerate(row) if ch == "f"]
    assert eye and hair and skin
    assert min(y for y, _ in hair) < min(y for y, _ in skin)          # hair on top
    assert all((y, x - 1) in skin or (y, x + 1) in skin for y, x in eye)        # the eye is in the face
    assert set(login_art.HERO_COLOURS) == {"h", "f", "k", "w"}


def test_the_title_spells_the_name_in_the_pc_font():
    for ch in login_art.TITLE + login_art.SUBTITLE:
        assert ch in login_art.GLYPHS and len(login_art.GLYPHS[ch]) == 8, ch
    s = login_art.compose()
    # The title's top row of pixels is yellow and nothing else is on that row.
    row = s.px[10 + 3]
    assert set(c for c in row if c is not None) == {login_art.YELLOW}
    # The word sits in a centred span of eight three-times glyph cells.
    inked = [x for x, c in enumerate(row) if c is not None]
    span = len(login_art.TITLE) * 8 * 3
    assert (login_art.SW - span) // 2 <= inked[0] and inked[-1] < (login_art.SW + span) // 2


def test_only_the_palette_is_used_and_nothing_is_inline():
    svg = login_art.as_svg(login_art.compose())
    fills = set(re.findall(r'fill="(#[0-9A-Fa-f]{6})"', svg))
    assert fills <= set(login_art.PALETTE)
    assert "style=" not in svg and "<script" not in svg
    assert 'shape-rendering="crispEdges"' in svg and 'viewBox="0 0 320 200"' in svg


def test_the_stylesheet_gives_the_picture_its_size():
    css = (config.STATIC_DIR / "style.css").read_text()
    rule = css[css.index(".login-art svg {"):]
    rule = rule[:rule.index("}")]
    assert f"max-width: {login_art.DISPLAY_WIDTH}px" in rule and "height: auto" in rule


@pytest.mark.asyncio
async def test_the_page_serves_the_art_intact():
    async with anon_client() as client:
        page = (await client.get("/")).text
    svg = re.search(r"<svg.*?</svg>", page, re.DOTALL).group(0)
    assert "{%" not in svg and "login-art:" not in svg                 # Jinja's markers are gone
    assert svg == login_art.as_svg(login_art.compose())
    assert 'role="img"' in svg and "pushing his boulder" in svg
