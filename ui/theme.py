"""One palette, consumed as a rich Theme and as Textual CSS variables."""

from rich.theme import Theme

# Raw palette. Textual CSS can't read a rich Theme, so both are built from here.
PALETTE = {
    "accent": "rgb(130,150,180)",   # slate blue
    "sand": "rgb(200,170,120)",     # warnings
    "red": "rgb(200,90,90)",        # errors
    "teal": "rgb(120,170,160)",     # success
    "graphite": "rgb(120,124,132)", # muted
    "silver": "rgb(176,180,188)",   # secondary text
    "slate": "rgb(88,94,104)",      # borders
    "bright": "rgb(224,226,232)",   # primary text
    "violet": "rgb(150,150,168)",   # memory / mcp
    "read": "rgb(140,158,184)",
}

AGENT_THEME = Theme(
    {
        "info": PALETTE["accent"],
        "warning": PALETTE["sand"],
        "error": f"bold {PALETTE['red']}",
        "success": PALETTE["teal"],
        "dim": "dim",
        "muted": PALETTE["graphite"],
        "subtitle": PALETTE["silver"],
        "border": PALETTE["slate"],
        "highlight": f"bold {PALETTE['bright']}",

        "user": f"bold {PALETTE['bright']}",
        "assistant": PALETTE["silver"],

        "tool": f"bold {PALETTE['accent']}",
        "tool.read": PALETTE["read"],
        "tool.write": PALETTE["silver"],
        "tool.shell": PALETTE["graphite"],
        "tool.network": PALETTE["teal"],
        "tool.memory": PALETTE["violet"],
        "tool.mcp": PALETTE["violet"],

        "code": PALETTE["silver"],
    }
)


def _css_rgb(value: str) -> str:
    """`rgb(1,2,3)` -> `rgb(1,2,3)`; Textual accepts this form directly."""
    return value


def textual_variables() -> dict[str, str]:
    """Palette exposed to Textual CSS as `$relay-<name>`."""
    return {f"relay-{name}": _css_rgb(value) for name, value in PALETTE.items()}


def tool_colour(tool_kind: str | None) -> str:
    """Accent colour for a tool kind, as a raw rgb() string."""
    return {
        "read": PALETTE["read"],
        "write": PALETTE["silver"],
        "shell": PALETTE["graphite"],
        "network": PALETTE["teal"],
        "memory": PALETTE["violet"],
        "mcp": PALETTE["violet"],
    }.get(tool_kind or "", PALETTE["accent"])
