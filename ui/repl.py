from __future__ import annotations

import asyncio
import signal

from contextlib import contextmanager
from pathlib import Path

from platformdirs import user_config_dir
from prompt_toolkit import PromptSession
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import to_filter
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent.agent import Agent
from config.config import Config
from ui.logo import LOGO_WIDTH, RELAY_VERSION, logo
from ui.renderer import TUI, build_key_bindings, get_console
from ui.stream import stream_turn
from ui.theme import hex_colour

HISTORY_FILE = "history"

PROMPT_MARK = "❯"

PROMPT_WIDTH = len("│ ") + len(PROMPT_MARK) + len(" ")

WELCOME_TITLE = "Welcome to relay!"

BANNER_MIN_WIDTH = 2 + 2 + LOGO_WIDTH + 2 + len(WELCOME_TITLE)

PROMPT_STYLE = Style.from_dict(
    {
        "prompt": f"{hex_colour('accent')} bold",
        "frame": hex_colour("slate"),
        "bottom-toolbar": f"noreverse {hex_colour('slate')}",
        "bottom-toolbar.text": f"noreverse {hex_colour('slate')}",
    }
)


def _soft_wrap(text: str, width: int) -> str:

    if width < 1:
        return text

    chars = list(text)
    line_start = 0
    last_space = -1
    i = 0

    while i < len(chars):
        if chars[i] == " ":
            last_space = i
        if i - line_start + 1 > width and last_space > line_start:
            chars[last_space] = "\n"
            line_start = last_space + 1
            last_space = -1
            i = line_start
            continue
        i += 1

    return "".join(chars)


def _tilde(path: str) -> str:
    home = str(Path.home())
    return f"~{path[len(home):]}" if path.startswith(home) else path


def _history_path() -> Path:
    path = Path(user_config_dir("relay")) / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Repl:


    def __init__(self, config: Config) -> None:
        self.config = config
        self.console = get_console()
        self.tui = TUI(config, self.console)
        self.session: PromptSession[str] = PromptSession(
            history=FileHistory(str(_history_path())),
            style=PROMPT_STYLE,
            key_bindings=build_key_bindings(self.tui),
        )
        self._reflowing = False
        self.session.default_buffer.on_text_changed += self._reflow

        window = self.session.app.layout.current_window
        window.dont_extend_height = to_filter(True)

    def _reflow(self, buffer: Buffer) -> None:

        if self._reflowing:
            return
        width = self.console.width - PROMPT_WIDTH
        if width < 16:
            return

        wrapped = _soft_wrap(buffer.text.replace("\n", " "), width)
        if wrapped == buffer.text:
            return

        self._reflowing = True
        try:
            buffer.document = Document(wrapped, buffer.cursor_position)
        finally:
            self._reflowing = False

    def _box_bottom(self) -> None:
        self.console.print(Text("╰" + "─" * (self.console.width - 2) + "╯", style="border"))

    def _facts(self, agent: Agent | None) -> list[tuple[str, str]]:
        rows = [
            ("Directory", _tilde(str(self.config.cwd))),
            ("Session", agent.session.session_id if agent else ""),
            ("Model", self.config.model_name),
            ("Version", RELAY_VERSION),
        ]
        return [(label, value) for label, value in rows if value]

    def _banner(self, agent: Agent | None = None) -> None:
        welcome = Table.grid(padding=(0, 0))
        welcome.add_row(Text(WELCOME_TITLE, style="highlight"))

        head = Table.grid(padding=(0, 2))
        head.add_column(vertical="middle")
        head.add_column(vertical="middle")
        head.add_row(logo(), welcome)

        facts = Table.grid(padding=(0, 1))
        facts.add_column(style="muted")
        facts.add_column(style="subtitle")
        for label, value in self._facts(agent):
            facts.add_row(f"{label}:", value)

        self.console.print()
        if self.console.width >= BANNER_MIN_WIDTH:
            body = Table.grid(padding=(0, 0))
            body.add_row(head)
            body.add_row(Text())
            body.add_row(facts)
            self.console.print(
                Panel(body, box=ROUNDED, border_style="border", padding=(0, 1), expand=False)
            )
        else:
            self.console.print(Text("relay", style="highlight"))
            self.console.print(facts)
        self.console.print()
        self.console.print(
            Text(
                "ctrl+o expands tool output · ctrl+c interrupts · ctrl+d quits",
                style="border",
            )
        )

    def _reset_plan(self, agent: Agent) -> None:
        tool = agent.session.tool_registry.get("plan")
        if tool is not None and hasattr(tool, "reset"):
            tool.reset()

    @contextmanager
    def _turn_keys(self, task: asyncio.Task):

        try:
            device = create_input()
        except Exception:
            loop = asyncio.get_running_loop()
            try:
                loop.add_signal_handler(signal.SIGINT, task.cancel)
            except (NotImplementedError, RuntimeError):
                pass
            try:
                yield
            finally:
                try:
                    loop.remove_signal_handler(signal.SIGINT)
                except (NotImplementedError, RuntimeError):
                    pass
            return

        def on_keys() -> None:
            for key_press in device.read_keys():
                if key_press.key == Keys.ControlO:
                    self.tui.toggle_expansion()
                elif key_press.key == Keys.ControlC:
                    task.cancel()

        with device.raw_mode(), device.attach(on_keys):
            yield

    async def _run_turn(self, agent: Agent, message: str) -> None:
        task = asyncio.create_task(stream_turn(self.tui, agent, message))

        try:
            with self._turn_keys(task):
                await task
        except asyncio.CancelledError:
            self.tui.stop_thinking()
            self.console.print("\n[warning]Interrupted[/warning]")
        except Exception as exc:
            self.tui.stop_thinking()
            self.console.print(f"[error]{type(exc).__name__}: {exc}[/error]")

    def _prompt_fragments(self) -> StyleAndTextTuples:

        top = "╭" + "─" * (self.console.width - 2) + "╮\n"
        return [
            *self.tui.expansion_fragments(),
            ("class:frame", top),
            ("class:frame", "│ "),
            ("class:prompt", f"{PROMPT_MARK} "),
        ]

    def _continuation_fragments(
        self, width: int, _line_number: int, _wrap_count: int
    ) -> StyleAndTextTuples:
        return [("class:frame", "│"), ("", " " * (width - 1))]

    def _bottom_fragments(self) -> StyleAndTextTuples:
        return [("class:frame", "╰" + "─" * (self.console.width - 2) + "╯")]

    async def _read_input(self) -> str:
        self.console.print()
        try:
            message = await self.session.prompt_async(
                self._prompt_fragments,
                bottom_toolbar=self._bottom_fragments,
                prompt_continuation=self._continuation_fragments,
            )
            return message.replace("\n", " ")
        finally:
            self.tui.expanded = False
            self._box_bottom()

    async def run(self) -> None:
        async with Agent(self.config) as agent:
            self._banner(agent)
            while True:
                try:
                    message = await self._read_input()
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    break

                message = message.strip()
                if not message:
                    continue

                self._reset_plan(agent)
                await self._run_turn(agent, message)
