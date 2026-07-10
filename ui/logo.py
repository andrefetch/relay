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

# One pixel is two cells wide, or the letters come out squashed: terminal
# cells are about twice as tall as they are wide.
_PIXEL = "██"
_LETTER_GAP = 1

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
