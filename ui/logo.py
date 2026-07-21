from rich.text import Text

from ui.theme import PALETTE

RELAY_VERSION = "0.0.2 (beta-alpha)"

CLOUD_PIXELS = (
    "..###...",
    ".######.",
    "########",
)
_PIXEL = "██"

RELAY_BLOB = tuple(
    "".join(_PIXEL if cell == "#" else "  " for cell in row) for row in CLOUD_PIXELS
)

LOGO_WIDTH = max(len(row) for row in RELAY_BLOB)
LOGO_HEIGHT = len(RELAY_BLOB)

_BODY = PALETTE["bright"]

_SILVER = (168, 174, 186)


def small_wordmark(justify: str = "center") -> Text:
    r, g, b = _SILVER
    return Text(" ".join("relay"), style=f"rgb({r},{g},{b})", justify=justify, no_wrap=True)


def logo() -> Text:
    text = Text(no_wrap=True)
    for i, row in enumerate(RELAY_BLOB):
        for char in row:
            text.append(char, style=_BODY if char != " " else None)
        if i != LOGO_HEIGHT - 1:
            text.append("\n")
    return text
