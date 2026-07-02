from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box

from utils.paths import display_path_relative_to_cwd
from typing import Any, Tuple
from pathlib import Path

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

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_console: Console | None = None

def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    
    return _console

class TUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or get_console()
        self._assistant_stream_open = False
        self.tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self.cwd = Path.cwd()
        self._spinner_index = 0
        self._spinner_timer = None
    
    def begin_assistant(self) -> None:
        self.console.print()
        self.console.print(Rule(Text("Assistant", style="assistant")))
        self._assistant_stream_open = True
    
    def end_assistant(self) -> None:
        if self._assistant_stream_open:
            self.console.print()
        self._assistant_stream_open = False
    
    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="", markup=False)
    
    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[Tuple]:
        _ORDER = {
            'read_File': ['path', 'offset', 'limit']
        }

        preferred = _ORDER.get(tool_name, [])
        ordered: list[Tuple[str, Any]] = []
        seen = set() # added a set so the LLM can't hallucinate and add the same thing twice, a set automatically removes duplicates

        for key in preferred:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
        
        remaining_keys = set(args.keys() - seen)
        ordered.extend((key, args[key]) for key in remaining_keys)

        return ordered


    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style='muted', justify='right', no_wrap=True)
        table.add_column(style='code', overflow="fold")

        for key, value in self._ordered_args(tool_name, args):
            table.add_row(key, value)
        
        return table

    def tool_call_start(
            self,
            call_id: str,
            name: str, 
            tool_kind: str | None,
            arguments: dict[str, Any],
            ) -> None:
        self.tool_args_by_call_id[call_id] = arguments
        border_style = f"tool.{tool_kind}" if tool_kind else "tool"

        title = Text.assemble(
            ("● ", "muted"),
            (f"{name}:", "tool"),
            (" ", "muted"),
            (f"#{call_id[:8]}", "muted"),
        )

        display_args = dict(arguments)
        for key in ('path', 'cwd'):
            val = display_args.get(key) 
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(display_path_relative_to_cwd(val, self.cwd))

        panel = Panel(
            self._render_args_table(name, display_args) if display_args else Text('(no arguments)', style='muted'),
            title=title,
            title_align="left",
            subtitle=Text('running', style='muted'),
            subtitle_align='right',
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print()
        self.console.print(panel)