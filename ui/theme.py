from rich.theme import Theme

PALETTE = {
    "accent": "rgb(130,150,180)",
    "sand": "rgb(200,170,120)",
    "red": "rgb(200,90,90)",
    "teal": "rgb(120,170,160)",
    "graphite": "rgb(120,124,132)",
    "silver": "rgb(176,180,188)",
    "slate": "rgb(88,94,104)",
    "bright": "rgb(224,226,232)",
    "violet": "rgb(150,150,168)",
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
    return value


def textual_variables() -> dict[str, str]:
    return {f"relay-{name}": _css_rgb(value) for name, value in PALETTE.items()}


def tool_colour(tool_kind: str | None) -> str:
    return {
        "read": PALETTE["read"],
        "write": PALETTE["silver"],
        "shell": PALETTE["graphite"],
        "network": PALETTE["teal"],
        "memory": PALETTE["violet"],
        "mcp": PALETTE["violet"],
    }.get(tool_kind or "", PALETTE["accent"])
