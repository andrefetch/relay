from prompt_toolkit.formatted_text import ANSI, StyleAndTextTuples, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.text import Text
from rich.segment import Segment
from rich.table import Table
from rich.live import Live
from rich.syntax import Syntax

from config.config import Config
from ui.format import (
    diff_glimpse,
    diff_stat,
    extract_read_code,
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
from collections import deque
from io import StringIO
from typing import Any, Callable
import asyncio
import random
import time

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08

GUTTER_CHAR = "│"

MAX_BLOCK_TOKENS = 2400
MAX_DIFF_TOKENS = 4000

MAX_REMEMBERED_TOOLS = 20
MAX_EXPANSION_LINES = 24

EXPAND_KEY = "c-o"


def build_key_bindings(tui: "TUI") -> KeyBindings:
    """Prompt keybindings owned by the TUI.

    ctrl+o toggles the last tool call's details. The expansion is rendered
    as part of the prompt (see `TUI.expansion_fragments`) rather than
    printed, so prompt_toolkit repaints it in place and toggling it off
    genuinely removes it — nothing reaches scrollback, and the pending
    input is never submitted.
    """
    bindings = KeyBindings()

    @bindings.add(EXPAND_KEY)
    def _(event) -> None:
        tui.toggle_expansion()
        event.app.invalidate()

    return bindings

# One mark for every tool: the kind is already carried by the colour, and a
# steady glyph keeps a column of calls reading as one list.
TOOL_ICON = "◇"

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

        # Tool detail blocks are hidden when printed; ctrl+o re-renders the
        # most recent call's details into the prompt from this buffer.
        self.collapsed = True
        self.expanded = False
        self._recent_tools: deque[tuple[Table, list[Any], list[Any], str]] = deque(
            maxlen=MAX_REMEMBERED_TOOLS
        )

        self._spinner_live: Live | None = None
        self._spinner_task: asyncio.Task | None = None
        self._spinner_render: Callable[[], Any] | None = None
        self._spinner_frame = 0
        self._thinking_label = ""


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

    def _start_spinner(self, render: Callable[[], Any]) -> None:
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

    def _live_group(self, line: Text) -> Any:
        """A live line, with the expanded tool details above it if toggled.

        The spinner's Live region is the only thing we own while a turn is
        running, so ctrl+o folds the details in here — same as the prompt
        does between turns. A leading blank keeps the line off the heels of
        whatever printed last.
        """
        expansion = self.expansion_renderable()
        if expansion is not None:
            return Group(Text(""), expansion, line)
        return Group(Text(""), line)

    def _thinking_renderable(self) -> Any:
        line = Text.assemble(
            (f"{self._spinner_char()} ", "tool"), (self._thinking_label, "highlight")
        )
        return self._live_group(line)

    def start_thinking(self, label: str | None = None) -> None:
        self._thinking_label = label if label is not None else random_thinking_text()
        self._start_spinner(self._thinking_renderable)

    def stop_thinking(self) -> None:
        self._stop_spinner()


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


    def _relativise(self, arguments: dict[str, Any]) -> dict[str, Any]:
        display_args = dict(arguments)
        for key in ("path", "cwd"):
            value = display_args.get(key)
            if isinstance(value, str) and self.cwd:
                display_args[key] = str(display_path_relative_to_cwd(value, self.cwd))
        return display_args

    def _render_todos(self, metadata: dict[str, Any]) -> Table | Text:
        todos = metadata.get("todos") or []
        if not todos:
            return Text("No todos.", style="muted")

        checklist = Table.grid(padding=(0, 1))
        checklist.add_column(no_wrap=True)
        checklist.add_column(overflow="fold")
        checklist.add_column(style="muted", no_wrap=True, justify="right")

        markers = {
            "completed": ("✔", "success", "muted strike"),
            "in_progress": ("▶", "info", "highlight"),
            "pending": ("☐", "muted", "code"),
        }

        for todo in todos:
            marker, marker_style, content_style = markers.get(
                str(todo.get("status")), markers["pending"]
            )
            checklist.add_row(
                Text(marker, style=marker_style),
                Text(str(todo.get("content", "")), style=content_style),
                Text(str(todo.get("id", ""))),
            )
        return checklist

    def _render_memory(self, metadata: dict[str, Any]) -> Table | Text:
        entries = metadata.get("entries") or []
        if not entries:
            return Text("No memory stored.", style="muted")

        active_key = metadata.get("active_key")

        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True)
        table.add_column(style="info", no_wrap=True)
        table.add_column(overflow="fold")

        for entry in entries:
            key = str(entry.get("key", ""))
            is_active = active_key is not None and key == active_key
            marker_style = "highlight" if is_active else "tool.memory"
            value_style = "highlight" if is_active else "code"
            table.add_row(
                Text("●", style=marker_style),
                Text(key),
                Text(str(entry.get("value", "")), style=value_style),
            )
        return table

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

    def _print_tool(self, header: Table, blocks: list[Any], border_style: str) -> None:
        self.console.print()
        self.console.print(header)
        if blocks:
            self.console.print(Gutter(Group(*blocks), style=border_style))

    def toggle_details(self) -> None:
        self.collapsed = not self.collapsed
        state = "collapsed" if self.collapsed else "expanded"
        self.console.print(Text(f"Tool output is now {state}.", style="muted"))

    def show_recent_tool(self, back: int = 1) -> None:
        """Replay a recent tool call with its detail blocks: 1 = most recent."""
        if not self._recent_tools or back < 1 or back > len(self._recent_tools):
            self.console.print(Text("Nothing to expand.", style="muted"))
            return
        header, summary, details, border_style = self._recent_tools[-back]
        self._print_tool(header, summary + details, border_style)

    def toggle_expansion(self) -> None:
        self.expanded = not self.expanded

    def expansion_renderable(self, back: int = 1) -> Any | None:
        """The withheld details of a recent tool call, or None.

        Header and summary are already on screen from when the call ran, so
        only the hidden part belongs here.
        """
        if not self.expanded or not self._recent_tools:
            return None
        if back < 1 or back > len(self._recent_tools):
            return None

        _header, _summary, details, border_style = self._recent_tools[-back]
        if not details:
            return None
        return Gutter(Group(*details), style=border_style)

    def expansion_fragments(self, back: int = 1) -> StyleAndTextTuples:
        """`expansion_renderable` as prompt_toolkit fragments.

        Rich paints to an ANSI buffer which prompt_toolkit re-parses, so the
        block keeps its styling while living in the prompt rather than in
        scrollback.
        """
        renderable = self.expansion_renderable(back)
        if renderable is None:
            return []

        buffer = StringIO()
        console = Console(
            theme=AGENT_THEME,
            file=buffer,
            force_terminal=True,
            width=self.console.width,
            highlight=False,
        )
        console.print(renderable)

        lines = buffer.getvalue().rstrip("\n").split("\n")
        if len(lines) > MAX_EXPANSION_LINES:
            hidden = len(lines) - MAX_EXPANSION_LINES
            lines = lines[:MAX_EXPANSION_LINES] + [f"… {hidden} more lines"]
        return to_formatted_text(ANSI("\n".join(lines) + "\n"))

    def tool_call_start(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        arguments: dict[str, Any],
    ) -> None:
        display_args = self._relativise(arguments)
        self.tool_args_by_call_id[call_id] = display_args
        self.tool_started_at[call_id] = time.monotonic()
        head = headline_of(display_args)

        def render() -> Any:
            line = Text.assemble(
                (f"{self._spinner_char()} ", "tool"), (name, "highlight")
            )
            if head:
                line.append("  ")
                line.append(head[1], style="subtitle")
            return self._live_group(line)

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
        started_at = self.tool_started_at.pop(call_id, None)
        elapsed = (
            format_elapsed(time.monotonic() - started_at) if started_at is not None else None
        )
        display_args = self.tool_args_by_call_id.pop(call_id, {})
        args = display_args

        metadata = metadata or {}
        primary_path = None
        if isinstance(metadata.get("path"), str):
            primary_path = metadata["path"]

        # summary is always printed; details only when expanded (or replayed
        # via /expand). Failures ignore the collapse switch entirely.
        summary: list[Any] = []
        details: list[Any] = []

        def output_block(style_name: str = "text") -> Syntax:
            return Syntax(
                truncate_text(output, self.config.model_name, MAX_BLOCK_TOKENS),
                style_name,
                theme="nord",
                word_wrap=True,
            )

        def joined(parts: list[Any]) -> Text | None:
            parts = [str(part) for part in parts if part is not None]
            return Text(" ┈ ".join(parts), style="muted") if parts else None

        if not success:
            summary.append(Text(error or "Tool failed", style="error"))
            if output.strip():
                details.append(
                    Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style="muted")
                )

        elif name == "read" and primary_path:
            result = extract_read_code(output)
            start_line, code = result if result else (1, output)

            shown_start = metadata.get("shown_start")
            shown_end = metadata.get("shown_end")
            total_lines = metadata.get("total_lines")
            if shown_start and shown_end and total_lines:
                summary.append(
                    Text(f"lines {shown_start}–{shown_end} of {total_lines}", style="muted")
                )
            else:
                summary.append(Text(f"{len(code.splitlines())} lines", style="muted"))
            details.append(
                Syntax(
                    code,
                    guess_language(primary_path),
                    theme="nord",
                    line_numbers=True,
                    start_line=start_line,
                    word_wrap=False,
                )
            )

        elif name in {"write", "edit"}:
            parts: list[Any] = [output.strip() or "Completed"]
            if diff:
                parts.append(diff_stat(diff))
            summary.append(joined(parts))
            if diff:
                # A peek at what actually landed, so a collapsed edit still
                # says something about the change and not just its size.
                glimpse = diff_glimpse(diff)
                if glimpse:
                    summary.append(
                        Syntax(
                            glimpse,
                            guess_language(primary_path or args.get("path")),
                            theme="nord",
                            word_wrap=False,
                            background_color="default",
                        )
                    )
                details.append(
                    Syntax(
                        truncate_text(diff, self.config.model_name, MAX_DIFF_TOKENS),
                        "diff",
                        theme="nord",
                        word_wrap=True,
                    )
                )

        elif name == "shell":
            line = joined(
                [
                    f"exit {exit_code}" if exit_code is not None else None,
                    f"{len(output.splitlines())} lines",
                ]
            )
            summary.append(line)
            command = args.get("command")
            if isinstance(command, str) and command.strip():
                details.append(Text(f"$ {command.strip()}", style="muted"))
            details.append(output_block())

        elif name == "list_dir":
            summary.append(
                joined(
                    [
                        metadata.get("path") if isinstance(metadata.get("path"), str) else None,
                        f"{metadata['entries']} entries"
                        if isinstance(metadata.get("entries"), int)
                        else None,
                    ]
                )
            )
            details.append(output_block())

        elif name == "grep":
            summary.append(
                joined(
                    [
                        f"{metadata['matches']} matches"
                        if isinstance(metadata.get("matches"), int)
                        else None,
                        f"searched {metadata['files_searched']} files"
                        if isinstance(metadata.get("files_searched"), int)
                        else None,
                    ]
                )
            )
            details.append(output_block())

        elif name == "glob":
            if isinstance(metadata.get("matches"), int):
                summary.append(Text(f"{metadata['matches']} matches", style="muted"))
            details.append(output_block())

        elif name == "search":
            summary.append(
                joined(
                    [
                        args.get("query") if isinstance(args.get("query"), str) else None,
                        f"{metadata['results']} results"
                        if isinstance(metadata.get("results"), int)
                        else None,
                    ]
                )
            )
            details.append(output_block())

        elif name == "fetch":
            summary.append(
                joined(
                    [
                        metadata.get("status_code")
                        if isinstance(metadata.get("status_code"), int)
                        else None,
                        f"{metadata['content_length']} bytes"
                        if isinstance(metadata.get("content_length"), int)
                        else None,
                        args.get("url") if isinstance(args.get("url"), str) else None,
                    ]
                )
            )
            details.append(output_block())

        elif name == "plan":
            completed = metadata.get("completed")
            total = metadata.get("total")
            if isinstance(completed, int) and isinstance(total, int) and total:
                summary.append(Text(f"{completed}/{total} completed", style="muted"))
            # The plan is the point: keep the checklist visible even collapsed.
            summary.append(self._render_todos(metadata))

        elif name == "memory":
            summary.append(
                joined(
                    [
                        metadata.get("action") if isinstance(metadata.get("action"), str) else None,
                        f"{metadata['count']} stored"
                        if isinstance(metadata.get("count"), int)
                        else None,
                    ]
                )
            )
            summary.append(self._render_memory(metadata))

        elif output.strip():
            first_line = output.strip().splitlines()[0]
            summary.append(Text(first_line, style="muted"))
            details.append(
                Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style="code")
            )

        summary = [block for block in summary if block is not None]
        if not summary and not details:
            summary.append(Text("(no output)", style="muted"))
        if truncated:
            summary.append(Text("Tool output was truncated", style="warning"))

        head = headline_of(display_args)
        secondary = secondary_args(display_args, head[0] if head else None)
        if secondary and name not in {"plan", "memory"}:
            details.insert(0, self._render_args_table(name, secondary))

        collapsed = self.collapsed and success
        hidden = collapsed and bool(details)

        status = Text()
        status.append("✓" if success else "✖ failed", style="success" if success else "error")
        if elapsed:
            status.append(" ")
            status.append(elapsed, style="muted")
        if hidden:
            hidden_lines = len((diff or output).splitlines())
            status.append(" · ", style="dim")
            status.append(f"+{hidden_lines} lines", style="dim")

        header = self._tool_header(
            TOOL_ICON,
            border_style,
            name,
            head[1] if head else None,
            status,
        )

        self._recent_tools.append((header, summary, details, border_style))
        self._print_tool(header, summary if collapsed else summary + details, border_style)


    def render_usage(self, usage: dict[str, Any] | None) -> None:
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