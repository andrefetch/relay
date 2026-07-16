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
        "tool.git": PALETTE["accent"],
        "tool.subagent": PALETTE["sand"],

        "code": PALETTE["silver"],
    }
)


def hex_colour(name: str) -> str:
    """`rgb(r,g,b)` from PALETTE as `#rrggbb`, for consumers that need hex."""
    r, g, b = (int(part) for part in PALETTE[name][4:-1].split(","))
    return f"#{r:02x}{g:02x}{b:02x}"


def tool_colour(tool_kind: str | None) -> str:
    return {
        "read": PALETTE["read"],
        "write": PALETTE["silver"],
        "shell": PALETTE["graphite"],
        "network": PALETTE["teal"],
        "memory": PALETTE["violet"],
        "mcp": PALETTE["violet"],
        "git": PALETTE["accent"],
        "subagent": PALETTE["sand"],
    }.get(tool_kind or "", PALETTE["accent"])
