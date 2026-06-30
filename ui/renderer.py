from rich.console import Console
from rich.theme import Theme

AGENT_THEME = Theme(
    {
        # General
        "info": "tan",
        "warning": "orange3",
        "error": "bold dark_red",
        "success": "dark_sea_green4",
        "dim": "dim",
        "muted": "grey50",
        "border": "rgb(120,85,60)",
        "highlight": "bold rgb(210,150,90)",

        # Roles
        "user": "bold rgb(196,148,92)",      # warm tan/camel
        "assistant": "rgb(222,184,135)",     # burlywood

        # Tools
        "tool": "bold rgb(184,134,80)",      # mid brown
        "tool.read": "rgb(160,120,85)",
        "tool.write": "rgb(196,160,90)",     # ochre-ish
        "tool.shell": "rgb(139,90,60)",      # dark brown
        "tool.network": "rgb(180,140,100)",
        "tool.memory": "dark_sea_green4",
        "tool.mcp": "rgb(205,170,125)",

        # Code / blocks
        "code": "rgb(230,210,180)",          # cream
    }
)

_console: Console | None = None

def get_console() -> Console:
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    
    return _console

class TUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or get_console()
    
    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="", markup=False)