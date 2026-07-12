from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text
from rich.segment import Segment
from rich.table import Table
from rich.live import Live
from rich.syntax import Syntax

from config.config import Config
from ui.format import (
    extract_read_file_code,
    format_elapsed,
    guess_language,
    headline as headline_of,
    ordered_args,
    secondary_args,
    summarise_value,
)
from ui.theme import AGENT_THEME
from utils.paths import display_path_relative_to_cwd
from utils.text import truncate_text
from typing import Any, Callable
import asyncio
import random
import time

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08

GUTTER_CHAR = "│"

# Tool chatter is worth clipping; a diff is the thing you actually asked for,
# so it gets a far larger budget before we cut it.
MAX_BLOCK_TOKENS = 2400
MAX_DIFF_TOKENS = 4000

THINKING_WORDS = [
    "Thinking…",
    "Working…",
    "Fluctuating…",
    "Writing…",
    "Typing…",
    "Helping…",
]


def random_thinking_text() -> str:
    return random.choice(THINKING_WORDS)


class Gutter:
    """Hang a renderable off a single coloured column in the left gutter.

    Deliberately has no right border: wide content (syntax blocks, diffs) keeps
    the full terminal width, and a mouse selection grabs the body text without
    dragging a trailing border character onto every line.
    """

    def __init__(self, renderable: Any, style: str = "border") -> None:
        self.renderable = renderable
        self.style = style

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        bar = Segment(f"{GUTTER_CHAR} ", console.get_style(self.style))
        body_width = max(options.max_width - 2, 1)
        lines = console.render_lines(
            self.renderable,
            options.update(width=body_width),
            pad=False,
        )
        for line in lines:
            yield bar
            yield from line
            yield Segment("\n")


_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    return _console


class TUI:
    def __init__(self, config: Config, console: Console | None = None) -> None:
        self.console = console or get_console()
        self.config = config
        self.cwd = config.cwd
        self._assistant_stream_open = False
        self.tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self.tool_started_at: dict[str, float] = {}

        self._spinner_live: Live | None = None
        self._spinner_task: asyncio.Task | None = None
        self._spinner_render: Callable[[], Text] | None = None
        self._spinner_frame = 0
        self._thinking_label = ""

    # ---- transient spinner -------------------------------------------------

    def _spinner_char(self) -> str:
        return SPINNER_FRAMES[self._spinner_frame % len(SPINNER_FRAMES)]

    async def _animate_spinner(self) -> None:
        try:
            while True:
                await asyncio.sleep(SPINNER_INTERVAL)
                self._spinner_frame += 1
                if self._spinner_live is not None and self._spinner_render is not None:
                    self._spinner_live.update(self._spinner_render())
        except asyncio.CancelledError:
            pass

    def _start_spinner(self, render: Callable[[], Text]) -> None:
        """Show a transient animated line that vanishes when stopped.

        rich permits only one Live at a time, so thinking and running-tool
        lines share this single slot; starting one implicitly ends the other.
        """
        self._stop_spinner()
        self._spinner_frame = 0
        self._spinner_render = render
        self._spinner_live = Live(
            render(),
            console=self.console,
            refresh_per_second=1 / SPINNER_INTERVAL,
            transient=True,
        )
        self._spinner_live.start()
        self._spinner_task = asyncio.create_task(self._animate_spinner())

    def _stop_spinner(self) -> None:
        if self._spinner_task is not None:
            self._spinner_task.cancel()
            self._spinner_task = None
        if self._spinner_live is not None:
            self._spinner_live.stop()
            self._spinner_live = None
        self._spinner_render = None

    def _thinking_renderable(self) -> Text:
        return Text.assemble(
            (f"{self._spinner_char()} ", "muted"), (self._thinking_label, "muted")
        )

    def start_thinking(self, label: str | None = None) -> None:
        self._thinking_label = label if label is not None else random_thinking_text()
        self._start_spinner(self._thinking_renderable)

    def stop_thinking(self) -> None:
        self._stop_spinner()

    # ---- assistant text ----------------------------------------------------

    def begin_assistant(self) -> None:
        self._stop_spinner()
        self.console.print()
        self._assistant_stream_open = True

    def end_assistant(self) -> None:
        if self._assistant_stream_open:
            self.console.print()
        self._assistant_stream_open = False

    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="", markup=False)

    # ---- tool calls --------------------------------------------------------

    def _relativise(self, arguments: dict[str, Any]) -> dict[str, Any]:
        display_args = dict(arguments)
        for key in ("path", "cwd"):
            value = display_args.get(key)
            if isinstance(value, str) and self.cwd:
                display_args[key] = str(display_path_relative_to_cwd(value, self.cwd))
        return display_args

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="muted", justify="right", no_wrap=True)
        table.add_column(style="code", overflow="fold")
        for key, value in ordered_args(tool_name, args):
            table.add_row(key, summarise_value(key, value))
        return table

    def _tool_header(
        self,
        icon: str,
        icon_style: str,
        name: str,
        headline: str | None,
        status: Text,
    ) -> Table:
        left = Text.assemble((f"{icon} ", icon_style), (name, "tool"))
        if headline:
            left.append("  ")
            left.append(headline, style="subtitle")

        header = Table.grid(expand=True)
        header.add_column(overflow="ellipsis", no_wrap=True)
        header.add_column(justify="right", no_wrap=True)
        header.add_row(left, status)
        return header

    def tool_call_start(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        arguments: dict[str, Any],
    ) -> None:
        """Show a transient running line; the durable block lands on complete."""
        display_args = self._relativise(arguments)
        self.tool_args_by_call_id[call_id] = display_args
        self.tool_started_at[call_id] = time.monotonic()
        head = headline_of(display_args)

        def render() -> Text:
            line = Text.assemble((f"{self._spinner_char()} ", "muted"), (name, "tool"))
            if head:
                line.append("  ")
                line.append(head[1], style="muted")
            return line

        self.console.print()
        self._start_spinner(render)

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
        diff: str | None,
        exit_code: int | None,
    ) -> None:
        self._stop_spinner()

        border_style = f"tool.{tool_kind}" if tool_kind else "tool"
        status_style = "success" if success else "error"
        started_at = self.tool_started_at.pop(call_id, None)
        elapsed = (
            format_elapsed(time.monotonic() - started_at) if started_at is not None else None
        )
        display_args = self.tool_args_by_call_id.pop(call_id, {})
        args = display_args

        status = Text()
        if not success:
            status.append("failed", style=status_style)
        if elapsed:
            if status.plain:
                status.append(" · ", style="muted")
            status.append(elapsed, style="muted")

        head = headline_of(display_args)
        header = self._tool_header(
            "✓" if success else "✖",
            status_style,
            name,
            head[1] if head else None,
            status,
        )

        metadata = metadata or {}
        primary_path = None
        if isinstance(metadata.get("path"), str):
            primary_path = metadata["path"]

        blocks: list[Any] = []

        if not success:
            blocks.append(Text(error or "Tool failed", style="error"))
            if output.strip():
                blocks.append(
                    Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style="muted")
                )

        elif name == "read_file" and primary_path:
            result = extract_read_file_code(output)
            start_line, code = result if result else (1, output)

            shown_start = metadata.get("shown_start")
            shown_end = metadata.get("shown_end")
            total_lines = metadata.get("total_lines")
            if shown_start and shown_end and total_lines:
                blocks.append(
                    Text(f"lines {shown_start}–{shown_end} of {total_lines}", style="muted")
                )
            blocks.append(
                Syntax(
                    code,
                    guess_language(primary_path),
                    theme="nord",
                    line_numbers=True,
                    start_line=start_line,
                    word_wrap=False,
                )
            )

        elif name in {"write_file", "edit"} and success:
            blocks.append(Text(output.strip() or "Completed", style="muted"))
            if diff:
                blocks.append(
                    Syntax(
                        truncate_text(diff, self.config.model_name, MAX_DIFF_TOKENS),
                        "diff",
                        theme="nord",
                        word_wrap=True,
                    )
                )
        
        elif name == 'shell' and success:
            command = args.get('command')
            if isinstance(command, str) and command.strip():
                blocks.append(Text(f'$ {command.strip()}', style='muted'))
            
            if exit_code is not None:
                blocks.append(Text(
                    f'exit_code={exit_code}', style='muted'
                ))
            
            output_display = truncate_text(
                output, 
                self.config.model_name,
                MAX_BLOCK_TOKENS,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="nord",
                    word_wrap=True,
                    )
            )

        elif name == 'list_dir' and success:

            entries = metadata.get('entries')
            path = metadata.get('path')
            summary = []

            if isinstance(path, str):
                summary.append(path)

            if isinstance(entries, int):
                summary.append(f"{entries} entries")
            
            if summary:
                blocks.append(Text(' ┈ '.join(summary), style='muted'))
            
            output_display = truncate_text(
                output, 
                self.config.model_name, 
                MAX_BLOCK_TOKENS
            )

            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="nord",
                    word_wrap=True,
                    )
            )
        
        elif name == 'grep' and success:

            matches = metadata.get('matches')
            files_searched = metadata.get('files_searched')

            summary = []

            if isinstance(matches, int):
                summary.append(f"{matches} matches")
            if isinstance(files_searched, int):
                summary.append(f"searched {files_searched} files")
            
            if summary:
                blocks.append(Text(" ┈ ".join(summary), style='muted'))
            
            output_display = truncate_text(output, self.config.model_name, MAX_BLOCK_TOKENS)
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="nord",
                    word_wrap=True,
                    )
            )
        
        elif name == 'glob' and success:

            matches = metadata.get('matches')

            if isinstance(matches, int):
                blocks.append(Text(f"{matches} matches", style='muted'))
            
            output_display = truncate_text(output, self.config.model_name, MAX_BLOCK_TOKENS)
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="nord",
                    word_wrap=True,
                    )
            )

        elif name == 'web_search' and success:

            results = metadata.get('results')
            query = args.get('query')

            summary = []

            if isinstance(query, str):
                summary.append(
                    query
                )
            if isinstance(results, int):
                summary.append(
                    f'{results} results'
                )
            
            blocks.append(Text(" ┈ ".join(summary), style='muted'))
            
            output_display = truncate_text(output, self.config.model_name, MAX_BLOCK_TOKENS)
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="nord",
                    word_wrap=True,
                    )
            )
            
        elif output.strip():
            blocks.append(
                Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style="code")
            )

        if not blocks:
            blocks.append(Text("(no output)", style="muted"))
        if truncated:
            blocks.append(Text("Tool output was truncated", style="warning"))

        secondary = secondary_args(display_args, head[0] if head else None)
        if secondary:
            blocks.insert(0, self._render_args_table(name, secondary))

        self.console.print()
        self.console.print(header)
        self.console.print(Gutter(Group(*blocks), style=border_style))

    # ---- usage -------------------------------------------------------------

    def render_usage(self, usage: dict[str, Any] | None) -> None:
        """Print a dim one-line context/usage gauge after a turn completes."""
        if not usage:
            return

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        cached_tokens = usage.get("cached_tokens", 0) or 0
        context_window = self.config.model.context_window

        line = Text()
        line.append("context ", style="muted")
        line.append(f"{prompt_tokens:,}", style="subtitle")
        line.append(f" / {context_window:,}", style="muted")

        if context_window:
            line.append(f"  ({prompt_tokens / context_window * 100:.1f}%)", style="info")

        line.append("   ·   ", style="muted")
        line.append(f"{completion_tokens:,} out", style="muted")
        if cached_tokens:
            line.append("   ·   ", style="muted")
            line.append(f"{cached_tokens:,} cached", style="muted")

        self.console.print()
        self.console.print(line)