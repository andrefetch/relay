"""The relay wordmark and butterfly, as a rich renderable."""

from rich.text import Text
import math

RELAY_VERSION = "0.2"

RELAY_LOGO = """\
⣠⣤⣤⡤⠤⢤⣤⣀⡀⠀⠐⠒⡄⠀⡠⠒⠀⠀⢀⣀⣤⠤⠤⣤⣤⣤⡄
⠈⠻⣿⡤⠤⡏⠀⠉⠙⠲⣄⠀⢰⢠⠃⢀⡤⠞⠋⠉⠈⢹⠤⢼⣿⠏⠀
⠀⠀⠘⣿⡅⠓⢒⡤⠤⠀⡈⠱⣄⣼⡴⠋⡀⠀⠤⢤⡒⠓⢬⣿⠃⠀⠀
⠀⠀⠀⠹⣿⣯⣐⢷⣀⣀⢤⡥⢾⣿⠷⢥⠤⣀⣀⣞⣢⣽⡿⠃⠀⠀⠀
⠀⠀⠀⠀⠈⢙⣿⠝⠀⢁⠔⡨⡺⡿⡕⢔⠀⡈⠐⠹⣟⠋⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢼⣟⢦⢶⢅⠜⢰⠃⠀⢹⡌⢢⣸⠦⠴⣿⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠘⣿⣇⡬⡌⢀⡟⠀⠀⠀⢷⠀⣧⢧⣵⣿⠂⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠈⢻⠛⠋⠉⠀⠀⠀⠀⠈⠉⠙⢻⡏⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢰⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠄⠀⠀⠀⠀⠀⠀"""

_WHITE = (255, 255, 255)
_SILVER = (168, 174, 186)

# 8-row pixel font. Rows 0-1 are the ascender band (only `l` reaches up),
# rows 2-6 the x-height, row 7 the descender (only `y` reaches down).
_GLYPHS: dict[str, list[str]] = {
    "r": [
        "....",
        "....",
        "#.##",
        "##..",
        "#...",
        "#...",
        "#...",
        "....",
    ],
    "e": [
        ".....",
        ".....",
        ".###.",
        "#...#",
        "#####",
        "#....",
        ".###.",
        ".....",
    ],
    "l": [
        "##.",
        ".#.",
        ".#.",
        ".#.",
        ".#.",
        ".#.",
        ".##",
        "...",
    ],
    "a": [
        ".....",
        ".....",
        ".###.",
        "....#",
        ".####",
        "#...#",
        ".####",
        ".....",
    ],
    "y": [
        ".....",
        ".....",
        "#...#",
        "#...#",
        ".####",
        "....#",
        "....#",
        "####.",
    ],
}

# One pixel is two cells wide, or the letters come out squashed: terminal
# cells are about twice as tall as they are wide.
_PIXEL = "██"
_LETTER_GAP = 1

_WORDMARK_DIM = (88, 94, 104)
_WORDMARK_BRIGHT = (224, 226, 232)


def wordmark(word: str = "relay", justify: str = "center") -> Text:
    """`word` in block letters, lit by a left-to-right slate→silver ramp."""
    glyphs = [_GLYPHS[char] for char in word if char in _GLYPHS]
    if not glyphs:
        return Text()

    height = len(next(iter(_GLYPHS.values())))
    rows: list[str] = []
    for y in range(height):
        rows.append((" " * _LETTER_GAP).join(glyph[y] for glyph in glyphs))

    width = max(len(row) for row in rows)
    text = Text(justify=justify, no_wrap=True)
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell != "#":
                text.append("  ")
                continue
            t = x / max(width - 1, 1)
            r = round(_WORDMARK_DIM[0] + (_WORDMARK_BRIGHT[0] - _WORDMARK_DIM[0]) * t)
            g = round(_WORDMARK_DIM[1] + (_WORDMARK_BRIGHT[1] - _WORDMARK_DIM[1]) * t)
            b = round(_WORDMARK_DIM[2] + (_WORDMARK_BRIGHT[2] - _WORDMARK_DIM[2]) * t)
            text.append(_PIXEL, style=f"rgb({r},{g},{b})")
        if y != height - 1:
            text.append("\n")
    return text


def small_wordmark(justify: str = "center") -> Text:
    """A quiet, letter-spaced `relay` to sit under the butterfly."""
    r, g, b = _SILVER
    return Text(" ".join("relay"), style=f"rgb({r},{g},{b})", justify=justify, no_wrap=True)


def gradient_logo(justify: str = "center") -> Text:
    """The braille butterfly with a radial white→silver gradient.

    Brightest at the centre, fading to silver at the edges all around, so the
    butterfly appears lit from the middle.
    """
    rows = RELAY_LOGO.split("\n")
    height = len(rows)
    width = max((len(row) for row in rows), default=1)
    cx = (width - 1) / 2
    cy = (height - 1) / 2
    max_dist = math.hypot(cx, cy) or 1.0

    text = Text(justify=justify, no_wrap=True)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            t = min(math.hypot(x - cx, y - cy) / max_dist, 1.0)
            r = round(_WHITE[0] + (_SILVER[0] - _WHITE[0]) * t)
            g = round(_WHITE[1] + (_SILVER[1] - _WHITE[1]) * t)
            b = round(_WHITE[2] + (_SILVER[2] - _WHITE[2]) * t)
            text.append(char, style=f"rgb({r},{g},{b})")
        if y != height - 1:
            text.append("\n")
    return text
