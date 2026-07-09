from rich.console import Console, Group
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich import box
from rich.syntax import Syntax

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory

from config.config import Config
from utils.paths import display_path_relative_to_cwd
from typing import Any, Tuple
from pathlib import Path
import asyncio
import math
import random
import re
import time

from utils.text import truncate_text

AGENT_THEME = Theme(
    {
        "info": "rgb(130,150,180)",          # slate-blue accent
        "warning": "rgb(200,170,120)",       # muted sand (warnings)
        "error": "bold rgb(200,90,90)",      # kept red for legibility
        "success": "rgb(120,170,160)",       # muted teal
        "dim": "dim",
        "muted": "rgb(120,124,132)",         # graphite grey
        "subtitle": "rgb(176,180,188)",      # soft silver (dimmer than highlight)
        "border": "rgb(88,94,104)",          # dim slate border
        "highlight": "bold rgb(224,226,232)", # bright silver

        "user": "bold rgb(224,226,232)",     # bright silver
        "assistant": "rgb(176,180,188)",     # soft grey

        "tool": "bold rgb(130,150,180)",     # slate-blue accent
        "tool.read": "rgb(140,158,184)",     # lighter slate
        "tool.write": "rgb(176,180,188)",    # soft grey
        "tool.shell": "rgb(120,124,132)",    # graphite
        "tool.network": "rgb(120,170,160)",  # muted teal
        "tool.memory": "rgb(150,150,168)",   # cool silver-violet
        "tool.mcp": "rgb(150,150,168)",      # cool silver-violet

        "code": "rgb(176,180,188)",          # soft grey
    }
)

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08

RELAY_VERSION = "0.1"

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

_console: Console | None = None

def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    
    return _console

def random_thinking_text() -> str:

    thinking_text = [
        'Thinking…',
        'Working…',
        'Fluctuating…',
        'Writing…',
        'Typing…',
        'Helping…',
    ]

    return random.choice(thinking_text)

class TUI:
    def __init__(self, config: Config, console: Console | None = None) -> None:
        self.console = console or get_console()
        self._assistant_stream_open = False
        self.tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self.tool_started_at: dict[str, float] = {}
        self.config = config
        self.cwd = self.config.cwd
        self._thinking_live: Live | None = None
        self._thinking_task: asyncio.Task | None = None
        self._thinking_frame = 0
        self._thinking_label = ""
        self._max_block_tokens = 240

        self._prompt_style = Style.from_dict(
            {
                "border": "#585e68",
                "arrow": "#e0e2e8 bold",
                "hint": "#787c84",
            }
        )
        self._prompt_session: PromptSession = PromptSession(
            history=InMemoryHistory(),
            style=self._prompt_style,
        )
    
    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        if seconds < 1:
            return f"{seconds * 1000:.0f}ms"
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes}m{secs:02d}s"

    def _thinking_renderable(self) -> Text:
        frame = SPINNER_FRAMES[self._thinking_frame % len(SPINNER_FRAMES)]
        return Text.assemble((f"{frame} ", "muted"), (self._thinking_label, "muted"))

    async def _animate_thinking(self) -> None:
        try:
            while True:
                await asyncio.sleep(SPINNER_INTERVAL)
                self._thinking_frame += 1
                if self._thinking_live is not None:
                    self._thinking_live.update(self._thinking_renderable())
        except asyncio.CancelledError:
            pass

    def start_thinking(self, label: str | None = None) -> None:
        if self._thinking_live is not None:
            return
        self._thinking_frame = 0
        self._thinking_label = label if label is not None else random_thinking_text()
        self._thinking_live = Live(
            self._thinking_renderable(),
            console=self.console,
            refresh_per_second=1 / SPINNER_INTERVAL,
            transient=True,
        )
        self._thinking_live.start()
        self._thinking_task = asyncio.create_task(self._animate_thinking())

    def stop_thinking(self) -> None:
        if self._thinking_task is not None:
            self._thinking_task.cancel()
            self._thinking_task = None
        if self._thinking_live is not None:
            self._thinking_live.stop()
            self._thinking_live = None

    async def prompt(self) -> str:
        """Read one line of user input inside a bordered box.

        prompt_toolkit owns the input line, so the left/right borders stay
        intact as the text grows — unlike readline, which can't keep a right
        edge and made the old box look cut off. Uses the async variant since
        we're already inside the asyncio event loop.
        """
        width = max(self.console.width, 24)
        inner = width - 2

        self.console.print()
        self.console.print(f"[border]╭{'─' * inner}╮[/border]")

        message = HTML("<border>│</border> <arrow>❯</arrow> ")
        rprompt = HTML("<border>│</border>")

        try:
            text = await self._prompt_session.prompt_async(message, rprompt=rprompt)
        finally:
            self.console.print(f"[border]╰{'─' * inner}╯[/border]")

        return text

    def _gradient_logo(self) -> Text:
        """Render the braille logo with a radial white→silver gradient.

        Brightest (near white) at the center, fading to silver at the edges
        all around, so the butterfly appears lit from the middle.
        """
        white = (255, 255, 255)
        silver = (168, 174, 186)

        rows = RELAY_LOGO.split("\n")
        height = len(rows)
        width = max((len(r) for r in rows), default=1)
        cx = (width - 1) / 2
        cy = (height - 1) / 2
        max_dist = math.hypot(cx, cy) or 1.0

        text = Text(justify="center")
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                t = min(math.hypot(x - cx, y - cy) / max_dist, 1.0)
                r = round(white[0] + (silver[0] - white[0]) * t)
                g = round(white[1] + (silver[1] - white[1]) * t)
                b = round(white[2] + (silver[2] - white[2]) * t)
                text.append(ch, style=f"rgb({r},{g},{b})")
            if y != height - 1:
                text.append("\n")
        return text

    def welcome(self, model: str | None = None) -> None:
        lines = [self._gradient_logo(), Text("")]
        lines.append(Text.assemble(("relay", "bold highlight"), (f" — v{RELAY_VERSION}", "muted"), justify="center"))
        lines.append(Text(f"cwd: {self.cwd}", style="subtitle", justify="center"))
        if model:
            lines.append(Text(f"model: {model}", style="subtitle", justify="center"))
        lines.append(Text("commands: /help /config /approval /model /exit", style="subtitle", justify="center"))

        panel = Panel(
            Group(*lines),
            border_style="border",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print(panel)

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
            'read_file': ['path', 'offset', 'limit'],
            'write_file': ['path', 'create_directories', 'content']
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

    def _extract_read_file_code(self, text: str) -> tuple[int, str] | None:
        body = text
        header_match = re.match(r"^showing lines (\d+)-(\d+) of (\d+)\n\n", text)

        if header_match:
            body = text[header_match.end() :]
        
        code_lines: list[str] = []
        start_line: int | None = None

        for line in body.splitlines():
            m = re.match(r"^\s*(\d+)\|(.*)$", line)
            if not m:
                return None
            line_number = int(m.group(1))
            if start_line is None:
                start_line = line_number
            code_lines.append(m.group(2))
        
        if start_line is None:
            return None

        return start_line, "\n".join(code_lines)
    
    def _guess_language(self, path: str | None) -> str:
        if not path:
            return "text"
        suffix = Path(path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".json": "json",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".swift": "swift",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".css": "css",
            ".html": "html",
            ".xml": "xml",
            ".sql": "sql",
        }.get(suffix, "text")

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style='muted', justify='right', no_wrap=True)
        table.add_column(style='code', overflow="fold")

        for key, value in self._ordered_args(tool_name, args):
            if isinstance(value, str):
                if key in {
                    'content', 
                    'old_string',
                    'new_string'
                    }:
                    line_count = len(value.splitlines()) or 0
                    byte_count = len(value.encode('utf-8', errors='replace'))
                    value = f"{line_count} lines ┈ {byte_count} bytes"
            table.add_row(key, str(value))
        
        return table

    def tool_call_start(
            self,
            call_id: str,
            name: str, 
            tool_kind: str | None,
            arguments: dict[str, Any],
            ) -> None:
        self.tool_args_by_call_id[call_id] = arguments
        self.tool_started_at[call_id] = time.monotonic()
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

    def tool_call_complete(
            self,
            call_id: str,
            name: str, 
            tool_kind: str | None,
            success: bool,
            output: str,
            error: str | None,
            metadata: dict[str, Any] | None,
            truncated: bool,
            diff: str | None
            ) -> None:
        border_style = f"tool.{tool_kind}" if tool_kind else "tool"
        status_icon = '✓' if success else '✖'
        status_style = 'success' if success else 'error'

        started_at = self.tool_started_at.pop(call_id, None)
        elapsed = self._format_elapsed(time.monotonic() - started_at) if started_at is not None else None

        status_word = 'done' if success else 'failed'
        subtitle = Text.assemble((status_word, status_style))
        if elapsed:
            subtitle.append(" · ", style="muted")
            subtitle.append(elapsed, style="muted")

        title = Text.assemble(
            (f"{status_icon} ", f"{status_style}"),
            (f"{name}:", "tool"),
            (" ", "muted"),
            (f"#{call_id[:8]}", "muted"),
        )

        primary_path = None
        blocks = []
        if isinstance(metadata, dict) and isinstance(metadata.get('path'), str):
            primary_path = metadata.get('path')

        if name == "read_file" and success:
            if primary_path:
                result = self._extract_read_file_code(output)
                if result is None:
                    start_line, code = 1, output
                else:
                    start_line, code = result

                shown_start = metadata.get('shown_start')
                shown_end = metadata.get('shown_end')
                total_lines = metadata.get('total_lines')
                programming_lang = self._guess_language(primary_path)

                header_parts = [str(display_path_relative_to_cwd(primary_path, self.cwd)), " ● "]
                if shown_start and shown_end and total_lines:
                    header_parts.append(f"lines {shown_start} - {shown_end} of {total_lines}")
                header = "".join(header_parts)

                blocks.append(Text(header, style='muted'))
                blocks.append(Syntax(
                    code,
                    programming_lang,
                    theme='nord',
                    line_numbers=True,
                    start_line=start_line,
                    word_wrap=False,
                ))
            else:
                output_display = truncate_text(output, "", self._max_block_tokens, )
                blocks.append(Syntax(
                    output_display,
                    'text',
                    theme='nord',
                    word_wrap=False
                ))

        elif name == "write_file" and success:
            output_line = output.strip() if output.strip() else 'Completed'
            blocks.append(Text(output_line, style='muted'))
            if diff:
                diff_display = truncate_text(
                    diff,
                    self.config.model_name,
                    self._max_block_tokens,
                )

                blocks.append(
                    Syntax(
                        diff_display,
                        'diff',
                        theme='nord',
                        word_wrap=True
                    )
                )
            
        if truncated:
            blocks.append(Text('Tool output was truncated', style='warning'))

        panel = Panel(
            Group(
                *blocks,
            ),
            title=title,
            title_align="left",
            subtitle=subtitle,
            subtitle_align='right',
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print()
        self.console.print(panel)

    def render_usage(self, usage: dict[str, Any] | None) -> None:
        """Print a dim one-line context/usage gauge after a turn completes."""
        if not usage:
            return

        prompt_tokens = usage.get('prompt_tokens', 0) or 0
        completion_tokens = usage.get('completion_tokens', 0) or 0
        cached_tokens = usage.get('cached_tokens', 0) or 0
        context_window = self.config.model.context_window

        line = Text()
        line.append("context ", style="muted")
        line.append(f"{prompt_tokens:,}", style="subtitle")
        line.append(f" / {context_window:,}", style="muted")

        if context_window:
            pct = prompt_tokens / context_window * 100
            line.append(f"  ({pct:.1f}%)", style="info")

        line.append("   ·   ", style="muted")
        line.append(f"{completion_tokens:,} out", style="muted")
        if cached_tokens:
            line.append("   ·   ", style="muted")
            line.append(f"{cached_tokens:,} cached", style="muted")

        self.console.print()
        self.console.print(line)
