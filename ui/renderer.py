from rich.console import Console
from rich.theme import Theme

AGENT_THEME = Theme(
    {
        "info": "rgb(49,106,197)",           # taskbar blue
        "warning": "rgb(255,192,0)",         # xp yellow
        "error": "bold rgb(200,40,40)",      # error red
        "success": "rgb(70,150,52)",         # start button green
        "dim": "dim",
        "muted": "rgb(150,150,150)",         # gray
        "border": "rgb(0,84,227)",           # title bar blue
        "highlight": "bold rgb(255,224,0)",  # selection gold

        "user": "bold rgb(0,84,227)",        # title bar blue
        "assistant": "rgb(236,233,216)",     # tahoma beige

        "tool": "bold rgb(70,150,52)",       # start button green
        "tool.read": "rgb(49,106,197)",      # taskbar blue
        "tool.write": "rgb(255,192,0)",      # yellow
        "tool.shell": "rgb(128,128,128)",    # cmd.exe gray
        "tool.network": "rgb(0,153,204)",    # ie blue
        "tool.memory": "rgb(70,150,52)",     # green
        "tool.mcp": "rgb(153,102,204)",      # luna purple

        "code": "rgb(236,233,216)",          # beige panel
    }
)

_console: Console | None = None

def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    
    return _console

class TUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or get_console()
    
    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="", markup=False)