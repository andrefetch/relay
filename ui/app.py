from __future__ import annotations
import random
import time

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from rich.console import Group
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Static

from agent.agent import Agent
from agent.events import AgentEventType
from config.config import Config
from ui.format import (
    diff_stat,
    extract_read_code,
    format_elapsed,
    guess_language,
    headline as headline_of,
    ordered_args,
    secondary_args,
    summarise_value,
)
from ui.logo import RELAY_VERSION, gradient_logo, small_wordmark
from ui.theme import PALETTE, tool_colour
from utils.paths import display_path_relative_to_cwd
from utils.text import truncate_text
import time

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08

COLLAPSED_SYMBOL = "▸"
EXPANDED_SYMBOL = "▾"
INTERRUPTED_SYMBOL = "⊘"

LOGO_MIN_WIDTH = 29

# Tool chatter is worth clipping; a diff is the thing you actually asked for,
# so it gets a far larger budget before we cut it.
MAX_BLOCK_TOKENS = 240
MAX_DIFF_TOKENS = 4000

# Tools whose output is plain text worth showing verbatim under a count summary,
# rather than syntax-highlighted source or a diff.
TEXT_OUTPUT_TOOLS = frozenset(
    {
        "shell", 
        "list_dir", 
        "grep", 
        "glob",
        "search",
        "fetch",
    }

)


def _two_column(left: Text, right: Text) -> Table:
    """A grid that fills the width, so `right` truly sits on the right edge."""
    grid = Table.grid(expand=True)
    grid.add_column(overflow="ellipsis", no_wrap=True)
    grid.add_column(justify="right", no_wrap=True)
    grid.add_row(left, right)
    return grid


def _tilde(path: str) -> str:
    home = str(Path.home())
    return f"~{path[len(home):]}" if path.startswith(home) else path


class Footer(Static):
    """cwd on the left; keybind hint and version on the right."""

    def __init__(self, cwd: str) -> None:
        super().__init__()
        self._cwd = _tilde(cwd)

    def on_mount(self) -> None:
        right = Text("ctrl+t", style=PALETTE["slate"])
        right.append(" details   ", style=PALETTE["graphite"])
        right.append(f"v{RELAY_VERSION}", style=PALETTE["graphite"])
        self.update(_two_column(Text(self._cwd, style=PALETTE["graphite"]), right))


class PromptRule(Static):
    """A rule above the input, carrying the model and context usage inline.

    Deliberately not a filled box: relay sits directly on the terminal's own
    background rather than painting a panel over it.
    """

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model
        self._usage = ""

    def on_mount(self) -> None:
        self._draw()

    def on_resize(self) -> None:
        self._draw()

    def set_usage(self, prompt_tokens: int, context_window: int) -> None:
        if context_window:
            self._usage = f"{prompt_tokens / context_window * 100:.0f}% ctx"
        else:
            self._usage = f"{prompt_tokens:,} tok"
        self._draw()

    def _label(self) -> Text:
        label = Text(self._model, style=PALETTE["silver"])
        if self._usage:
            label.append("  ·  ", style=PALETTE["slate"])
            label.append(self._usage, style=PALETTE["accent"])
        return label

    def _draw(self) -> None:
        width = self.size.width
        if not width:
            return

        label = self._label()
        # ── label ──────────────────────────────────────────
        lead = 2
        gap = 2  # one space either side of the label
        trail = max(width - lead - gap - label.cell_len, 0)

        rule = Text("─" * lead, style=PALETTE["slate"])
        rule.append(" ")
        rule.append_text(label)
        rule.append(" ")
        rule.append("─" * trail, style=PALETTE["slate"])
        self.update(rule)


class Caret(Static):
    pass


class PromptRow(Horizontal):
    """`❯` plus the input, sitting on the bare terminal background."""


class ToolHeader(Static, can_focus=True):
    """The always-visible row. Click or press enter to toggle the body."""

    BINDINGS = [Binding("enter", "toggle", "Toggle tool output", show=False)]

    class Toggle(Message):
        def __init__(self, header: ToolHeader) -> None:
            super().__init__()
            self.header = header

    def on_click(self) -> None:
        self.post_message(self.Toggle(self))

    def action_toggle(self) -> None:
        self.post_message(self.Toggle(self))


class ToolBody(Vertical):
    """Holds the expanded output; the left border is the gutter."""


class ToolCall(Vertical):
    """One tool invocation: a collapsed header row over an expandable body.

    Starts in a `running` state and is mutated in place when the call
    completes, rather than printing a second block.
    """

    def __init__(
        self,
        name: str,
        tool_kind: str | None,
        args: dict[str, Any],
        cwd: Path | None = None,
    ) -> None:
        super().__init__()
        self.tool_name = name
        self.tool_kind = tool_kind
        self.args = args
        self.cwd = cwd
        self.started_at = time.monotonic()
        self.collapsed = True
        self.done = False

        self._frame = 0
        self._timer = None
        self._failed = False
        self._interrupted = False
        self._has_body = False
        self._status = Text("running", style=PALETTE["graphite"])
        self._header = ToolHeader()
        self._body = ToolBody()

    def compose(self) -> ComposeResult:
        yield self._header
        yield self._body

    def on_mount(self) -> None:
        self._body.display = False
        self._body.styles.border_left = ("solid", tool_colour(self.tool_kind))
        self._timer = self.set_interval(SPINNER_INTERVAL, self._tick)
        self._render_header()

    def _tick(self) -> None:
        self._frame += 1
        self._render_header()

    def _symbol(self) -> tuple[str, str]:
        if not self.done:
            frame = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]
            return frame, PALETTE["graphite"]
        if self._interrupted:
            return INTERRUPTED_SYMBOL, PALETTE["sand"]
        if self._failed:
            return "✖", PALETTE["red"]
        if not self._has_body:
            # Nothing to expand, so don't imply there is.
            return "·", PALETTE["graphite"]
        return COLLAPSED_SYMBOL if self.collapsed else EXPANDED_SYMBOL, PALETTE["teal"]

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def interrupt(self) -> None:
        """The turn ended without a completion event for this call.

        Without this the spinner timer runs forever and the row lies about
        still being in flight.
        """
        if self.done:
            return
        self._stop_timer()
        self.done = True
        self._interrupted = True
        self._status = Text("interrupted", style=PALETTE["sand"])
        self._render_header()

    def _render_header(self) -> None:
        symbol, symbol_colour = self._symbol()
        left = Text.assemble(
            (f"{symbol} ", symbol_colour),
            (self.tool_name, f"bold {tool_colour(self.tool_kind)}"),
        )
        head = headline_of(self.args)
        if head:
            left.append("  ")
            left.append(head[1], style=PALETTE["silver"])

        self._header.update(_two_column(left, self._status))

    def toggle(self) -> None:
        if not self.done or not self._has_body:
            return
        self.collapsed = not self.collapsed
        self._body.display = not self.collapsed
        self._render_header()

    async def complete(
        self,
        success: bool,
        output: str,
        error: str | None,
        metadata: dict[str, Any] | None,
        truncated: bool,
        diff: str | None,
        model_name: str,
        exit_code: int | None = None,
    ) -> None:
        self._stop_timer()
        self.done = True
        self._failed = not success

        elapsed = format_elapsed(time.monotonic() - self.started_at)
        self._status = Text()
        if not success:
            self._status.append("failed", style=f"bold {PALETTE['red']}")
            self._status.append(" · ", style=PALETTE["graphite"])
        else:
            if diff:
                # So a collapsed edit still says how big it was.
                self._status.append(diff_stat(diff), style=PALETTE["silver"])
                self._status.append(" · ", style=PALETTE["graphite"])
            self._status.append("✓ ", style=PALETTE["teal"])
        self._status.append(elapsed, style=PALETTE["graphite"])

        blocks = self._build_blocks(
            success, output, error, metadata, truncated, diff, model_name, exit_code
        )
        self._has_body = bool(blocks)
        if blocks:
            await self._body.mount_all([Static(block) for block in blocks])

        # A write is the change you asked for and a failure is the thing you
        # need to see; everything else stays folded away.
        if self._has_body and (not success or self.tool_kind == "write"):
            self.collapsed = False
            self._body.display = True

        self._render_header()

    def _result_summary(
        self, metadata: dict[str, Any], head: tuple[str, str] | None
    ) -> list[str]:
        """Counts worth stating up front, so a collapsed row still tells you something."""
        summary: list[str] = []

        # The path is only worth repeating when it wasn't the headline — for a
        # bare `list_dir` or `grep` the tool resolved it and the header shows nothing.
        path = metadata.get("path")
        if not head and isinstance(path, str):
            summary.append(display_path_relative_to_cwd(path, self.cwd))

        entries = metadata.get("entries")
        if isinstance(entries, int):
            summary.append(f"{entries} entries")

        matches = metadata.get("matches")
        if isinstance(matches, int):
            summary.append(f"{matches} matches")

        files_searched = metadata.get("files_searched")
        if isinstance(files_searched, int):
            summary.append(f"searched {files_searched} files")

        results = metadata.get("results")
        if isinstance(results, int):
            summary.append(f"{results} results")

        status_code = metadata.get("status_code")
        if isinstance(status_code, int):
            summary.append(f"HTTP {status_code}")

        content_length = metadata.get("content_length")
        if isinstance(content_length, int):
            summary.append(f"{content_length} bytes")

        return summary

    def _build_blocks(
        self,
        success: bool,
        output: str,
        error: str | None,
        metadata: dict[str, Any] | None,
        truncated: bool,
        diff: str | None,
        model_name: str,
        exit_code: int | None = None,
    ) -> list[Any]:
        head = headline_of(self.args)
        metadata = metadata or {}
        primary_path = None
        if isinstance(metadata.get("path"), str):
            primary_path = metadata["path"]

        blocks: list[Any] = []

        secondary = secondary_args(self.args, head[0] if head else None)
        if secondary:
            grid = Table.grid(padding=(0, 1))
            grid.add_column(style=PALETTE["graphite"], justify="right", no_wrap=True)
            grid.add_column(style=PALETTE["silver"], overflow="fold")
            for key, value in ordered_args(self.tool_name, secondary):
                grid.add_row(key, summarise_value(key, value))
            blocks.append(grid)

        if not success:
            blocks.append(Text(error or "Tool failed", style=f"bold {PALETTE['red']}"))
            if output.strip():
                blocks.append(
                    Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style=PALETTE["graphite"])
                )

        elif self.tool_name == "read" and primary_path:
            result = extract_read_code(output)
            start_line, code = result if result else (1, output)
            shown_start = metadata.get("shown_start")
            shown_end = metadata.get("shown_end")
            total_lines = metadata.get("total_lines")
            if shown_start and shown_end and total_lines:
                blocks.append(
                    Text(
                        f"lines {shown_start}–{shown_end} of {total_lines}",
                        style=PALETTE["graphite"],
                    )
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

        elif self.tool_name in {"write_file", "edit"}:
            blocks.append(Text(output.strip() or "Completed", style=PALETTE["graphite"]))
            if diff:
                blocks.append(
                    Syntax(
                        truncate_text(diff, model_name, MAX_DIFF_TOKENS),
                        "diff",
                        theme="nord",
                        word_wrap=True,
                    )
                )

        elif self.tool_name in TEXT_OUTPUT_TOOLS:
            summary = self._result_summary(metadata, head)
            if summary:
                blocks.append(Text(" ┈ ".join(summary), style=PALETTE["graphite"]))
            if self.tool_name == "shell" and exit_code:
                blocks.append(Text(f"exit code {exit_code}", style=PALETTE["sand"]))
            if output.strip():
                blocks.append(
                    Syntax(
                        truncate_text(output, model_name, MAX_BLOCK_TOKENS),
                        "text",
                        theme="nord",
                        word_wrap=True,
                    )
                )

        elif output.strip():
            blocks.append(Text(truncate_text(output, "", MAX_BLOCK_TOKENS), style=PALETTE["silver"]))

        if truncated:
            blocks.append(Text("Tool output was truncated", style=PALETTE["sand"]))

        return blocks


class UserMessage(Static):
    pass


class AssistantMessage(Static):
    """Accumulates streamed deltas."""

    def __init__(self) -> None:
        super().__init__()
        self._buffer = ""

    def append(self, content: str) -> None:
        self._buffer += content
        self.update(Text(self._buffer, style=PALETTE["silver"]))


class Splash(Static):
    """Centred butterfly for the empty transcript; removed on the first message."""

    def __init__(self, cwd: str, model: str) -> None:
        super().__init__()
        self._rows = [
            ("cwd", _tilde(cwd)),
            ("model", model),
            ("commands", "/exit"),
        ]

    def on_mount(self) -> None:
        self._draw()

    def on_resize(self) -> None:
        self._draw()

    def _caption(self, width: int) -> Text:
        """Label/value rows, indented as one block so the labels stay in a column.

        Centring is done by hand: rich's `justify="center"` re-centres each line
        on its own width, which would rag the label column.
        """
        label_width = max(len(label) for label, _ in self._rows)
        gutter = label_width + 2
        cells = [(label, Text(value, no_wrap=True)) for label, value in self._rows]
        for _, value in cells:
            value.truncate(max(width - gutter, 8), overflow="ellipsis")

        block_width = gutter + max(value.cell_len for _, value in cells)
        indent = " " * max((width - block_width) // 2, 0)

        caption = Text(no_wrap=True)
        for index, (label, value) in enumerate(cells):
            caption.append(indent + label.ljust(label_width) + "  ", style=PALETTE["slate"])
            value.stylize_before(PALETTE["graphite"])
            caption.append_text(value)
            if index != len(cells) - 1:
                caption.append("\n")
        return caption

    def _draw(self) -> None:
        width = self.size.width
        if not width:
            return

        # The butterfly is 27 cells wide; below that it would wrap and shear.
        if width < LOGO_MIN_WIDTH:
            mark = Text("relay", style=f"bold {PALETTE['bright']}", justify="center")
        else:
            mark = Group(gradient_logo(justify="center"), Text(), small_wordmark(justify="center"))

        self.update(Group(mark, Text(), self._caption(width)))


def _compact_tokens(count: int) -> str:
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}k"
    return f"{count / 1_000_000:.1f}M"


def _elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s"


class Thinking(Static):
    """Status line pinned below the transcript for the length of a turn.

    Carries the spinner, a live elapsed clock, and the tokens burned so far.
    """

    def __init__(self) -> None:
        super().__init__()
        self._frame = 0
        self._timer = None
        self._started_at = time.monotonic()
        self._tokens = 0

    def on_mount(self) -> None:
        self._timer = self.set_interval(SPINNER_INTERVAL, self._tick)
        self._tick()

    def set_tokens(self, completion_tokens: int) -> None:
        self._tokens = completion_tokens
        self._tick()

    def _tick(self) -> None:
        self._frame += 1
        frame = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]

        line = Text(f"{frame} Thinking… ", style=PALETTE["graphite"])
        line.append(_elapsed(time.monotonic() - self._started_at), style=PALETTE["graphite"])
        if self._tokens:
            line.append(" · ", style=PALETTE["slate"])
            line.append(f"{_compact_tokens(self._tokens)} tokens", style=PALETTE["graphite"])
        self.update(line)

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()


class RelayApp(App):
    CSS = f"""
    /* No painted background: relay sits on the terminal's own colours. */
    Screen {{
        background: transparent;
        align-horizontal: center;
    }}

    /* Everything the user reads lives in one centred column. */
    #column {{
        width: 100%;
        max-width: 96;
        height: 1fr;
        padding: 0 1;
    }}

    Footer {{
        dock: bottom;
        height: 1;
        width: 100%;
        padding: 0 2;
    }}

    #transcript {{
        height: 1fr;
        scrollbar-size-vertical: 1;
        scrollbar-background: transparent;
        scrollbar-color: {PALETTE['slate']};
    }}

    Splash {{
        height: 1fr;
        content-align: center middle;
    }}

    PromptRule {{
        height: 1;
        margin-top: 1;
    }}

    PromptRow {{
        height: 1;
        margin-bottom: 1;
    }}

    Caret {{
        width: 2;
        color: {PALETTE['slate']};
    }}
    PromptRow:focus-within Caret {{
        color: {PALETTE['accent']};
        text-style: bold;
    }}

    #prompt {{
        height: 1;
        width: 1fr;
        border: none;
        padding: 0;
        background: transparent;
    }}
    #prompt:focus {{
        border: none;
    }}

    UserMessage {{
        color: {PALETTE['bright']};
        text-style: bold;
        margin: 1 0 0 0;
    }}

    AssistantMessage {{
        height: auto;
        margin: 1 0 0 0;
    }}

    ToolCall {{
        height: auto;
        margin: 1 0 0 0;
    }}

    ToolHeader {{
        height: 1;
    }}
    ToolHeader:focus {{
        background: $boost;
    }}

    ToolBody {{
        height: auto;
        padding-left: 1;
        margin-top: 1;
    }}

    Thinking {{
        height: 1;
        margin: 1 0 0 0;
    }}
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+t", "toggle_all", "Toggle tool details"),
    ]

    RANDOM_WELCOME = [
        'Ask relay…',
        'Relay, describe this codebase…',
        'Ask relay about refactoring…',
        'Relay, is this thing on…',
        'Ask relay about /help…',
        'Contribute to relay: github.com/andrefetch/relay…',
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._stack = AsyncExitStack()
        self.agent: Agent | None = None
        self._tools: dict[str, ToolCall] = {}
        self._thinking: Thinking | None = None
        self._busy = False

    async def _confirm_tool(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        # Approvals aren't built yet. This can't just be `None`: the agent reads
        # a missing handler as a denial, so mutating tools would never run.
        return True

    def compose(self) -> ComposeResult:
        with Vertical(id="column"):
            yield VerticalScroll(
                Splash(str(self.config.cwd), self.config.model_name),
                id="transcript",
            )
            yield PromptRule(self.config.model_name)
            with PromptRow():
                yield Caret("❯")
                yield Input(placeholder=random.choice(self.RANDOM_WELCOME), id="prompt")
        yield Footer(str(self.config.cwd))

    @property
    def transcript(self) -> VerticalScroll:
        return self.query_one("#transcript", VerticalScroll)

    @property
    def prompt_rule(self) -> PromptRule:
        return self.query_one(PromptRule)

    async def on_mount(self) -> None:
        self.agent = await self._stack.enter_async_context(
            Agent(self.config, confirmation_handler=self._confirm_tool)
        )
        self.query_one("#prompt", Input).focus()

    async def on_unmount(self) -> None:
        await self._stack.aclose()

    async def _append(self, widget: Widget) -> None:
        # The thinking line stays pinned at the foot of the transcript for the
        # whole turn, so new content has to slot in above it.
        if self._thinking is not None and self._thinking.is_mounted:
            await self.transcript.mount(widget, before=self._thinking)
        else:
            await self.transcript.mount(widget)
        self.transcript.scroll_end(animate=False)

    @on(ToolHeader.Toggle)
    def _toggle_tool(self, event: ToolHeader.Toggle) -> None:
        event.stop()
        tool = event.header.parent
        if isinstance(tool, ToolCall):
            tool.toggle()
            if not tool.collapsed:
                tool.scroll_visible(animate=False)

    def action_toggle_all(self) -> None:
        """Fold or unfold every tool call at once, like opencode's /details."""
        tools = [tool for tool in self.query(ToolCall) if tool.done and tool._has_body]
        if not tools:
            return
        # If anything is open, fold everything; otherwise open everything.
        target_collapsed = any(not tool.collapsed for tool in tools)
        for tool in tools:
            if tool.collapsed != target_collapsed:
                tool.toggle()

    @on(Input.Submitted, "#prompt")
    async def _submit(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message or self._busy:
            return

        if message in {"/exit", "/quit"}:
            self.exit()
            return

        event.input.value = ""

        # The logo owns the empty state only; once there's a conversation it goes.
        for splash in self.query(Splash):
            await splash.remove()

        await self._append(UserMessage(Text(f"❯ {message}", style=PALETTE["bright"])))
        self._run_turn(message)

    @work(exclusive=True)
    async def _run_turn(self, message: str) -> None:
        assert self.agent is not None
        self._busy = True
        prompt_input = self.query_one("#prompt", Input)
        prompt_input.disabled = True

        thinking = Thinking()
        await self._append(thinking)
        self._thinking = thinking
        assistant: AssistantMessage | None = None

        try:
            async for event in self.agent.run(message):
                if event.type == AgentEventType.USAGE:
                    usage = event.data.get("usage") or {}
                    thinking.set_tokens(usage.get("completion_tokens", 0) or 0)

                elif event.type == AgentEventType.TEXT_DELTA:
                    if assistant is None:
                        assistant = AssistantMessage()
                        await self._append(assistant)
                    assistant.append(event.data.get("content", ""))
                    self.transcript.scroll_end(animate=False)

                elif event.type == AgentEventType.TEXT_COMPLETE:
                    assistant = None

                elif event.type == AgentEventType.TOOL_CALL_START:
                    await self._tool_start(event.data)

                elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                    await self._tool_complete(event.data)

                elif event.type == AgentEventType.AGENT_END:
                    self._update_usage(event.data.get("usage"))

                elif event.type == AgentEventType.AGENT_ERROR:
                    await self._append(
                        Static(Text(str(event.data.get("error")), style=f"bold {PALETTE['red']}"))
                    )
                    break
        except Exception as exc:  # surface rather than kill the app
            await self._append(Static(Text(f"{type(exc).__name__}: {exc}", style=f"bold {PALETTE['red']}")))
        finally:
            self._thinking = None
            if thinking.is_mounted:
                await thinking.remove()
            # Any call still open never got a completion event: stop its
            # spinner rather than leaving a timer running for the session.
            for pending in self._tools.values():
                pending.interrupt()
            self._tools.clear()
            self._busy = False
            prompt_input.disabled = False
            prompt_input.focus()

    def _tool_kind(self, tool_name: str) -> str | None:
        assert self.agent is not None
        tool = self.agent.session.tool_registery.get(tool_name)
        return tool.kind.value if tool else None

    def _relativise(self, arguments: dict[str, Any]) -> dict[str, Any]:
        display_args = dict(arguments)
        for key in ("path", "cwd"):
            value = display_args.get(key)
            if isinstance(value, str) and self.config.cwd:
                display_args[key] = str(display_path_relative_to_cwd(value, self.config.cwd))
        return display_args

    async def _tool_start(self, data: dict[str, Any]) -> None:
        call_id = data.get("call_id", "")
        name = data.get("name", "unknown")
        widget = ToolCall(
            name,
            self._tool_kind(name),
            self._relativise(data.get("arguments", {})),
            self.config.cwd,
        )
        self._tools[call_id] = widget
        await self._append(widget)

    async def _tool_complete(self, data: dict[str, Any]) -> None:
        widget = self._tools.pop(data.get("call_id", ""), None)
        if widget is None:
            return
        await widget.complete(
            data.get("success", False),
            data.get("output", ""),
            data.get("error"),
            data.get("metadata"),
            data.get("truncated", False),
            data.get("diff"),
            self.config.model_name,
            data.get("exit_code"),
        )
        self.transcript.scroll_end(animate=False)

    def _update_usage(self, usage: dict[str, Any] | None) -> None:
        if not usage:
            return
        self.prompt_rule.set_usage(
            usage.get("prompt_tokens", 0) or 0,
            self.config.model.context_window,
        )
