from __future__ import annotations

import asyncio
import signal

from pathlib import Path

from platformdirs import user_config_dir
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import FileHistory
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

WELCOME_TITLE = "Welcome to relay!"
WELCOME_HINT = "Send /help for help information."

# Panel is borders + padding + logo + gap + the widest welcome line. Below
# this the logo is dropped rather than letting the panel wrap.
BANNER_MIN_WIDTH = 2 + 2 + LOGO_WIDTH + 2 + len(WELCOME_HINT)

PROMPT_STYLE = Style.from_dict(
    {
        "prompt": f"{hex_colour('accent')} bold",
        "frame": hex_colour("slate"),
        # The bottom edge rides in the toolbar slot, which defaults to
        # reverse video; noreverse makes it read as a plain border.
        "bottom-toolbar": f"noreverse {hex_colour('slate')}",
        "bottom-toolbar.text": f"noreverse {hex_colour('slate')}",
    }
)

COMMANDS = {
    "/help": "Show this help",
    "/clear": "Clear the screen and start a fresh conversation",
    "/exit": "Quit relay",
}


def _tilde(path: str) -> str:
    home = str(Path.home())
    return f"~{path[len(home):]}" if path.startswith(home) else path


def _history_path() -> Path:
    path = Path(user_config_dir("relay")) / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Repl:
    """Interactive prompt loop.

    Deliberately line-oriented: everything the agent does is printed into the
    terminal's own scrollback, so output stays scrollable, selectable and
    pipe-able rather than living inside a full-screen canvas.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.console = get_console()
        self.tui = TUI(config, self.console)
        self.session: PromptSession[str] = PromptSession(
            history=FileHistory(str(_history_path())),
            style=PROMPT_STYLE,
            key_bindings=build_key_bindings(self.tui),
        )

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
        welcome.add_row(Text(WELCOME_HINT, style="muted"))

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
                "/help for commands · ctrl+o expands tool output · "
                "ctrl+c interrupts · ctrl+d quits",
                style="border",
            )
        )

    def _help(self) -> None:
        self.console.print()
        for name, description in COMMANDS.items():
            self.console.print(
                Text.assemble((f"  {name:<8}", "info"), (description, "muted"))
            )

    def _clear(self, agent: Agent) -> None:
        self.console.clear()
        agent.session.context_manager.clear()
        self._reset_plan(agent)
        self._banner(agent)

    def _reset_plan(self, agent: Agent) -> None:
        # A new prompt starts a fresh plan, so stale todos never linger next
        # to unrelated work.
        tool = agent.session.tool_registery.get("plan")
        if tool is not None and hasattr(tool, "reset"):
            tool.reset()

    def _handle_command(self, command: str, agent: Agent) -> bool:
        """Run a slash command. Returns False when the REPL should exit."""
        if command in {"/exit", "/quit"}:
            return False
        if command == "/help":
            self._help()
        elif command == "/clear":
            self._clear(agent)
        else:
            self.console.print(
                f"[warning]Unknown command: {command}[/warning] — try /help"
            )
        return True

    async def _run_turn(self, agent: Agent, message: str) -> None:
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(stream_turn(self.tui, agent, message))

        # While a turn is running nothing is reading stdin, so route ctrl+c to
        # cancelling the turn instead of tearing down the process.
        try:
            loop.add_signal_handler(signal.SIGINT, task.cancel)
        except NotImplementedError:
            pass

        try:
            await task
        except asyncio.CancelledError:
            self.tui.stop_thinking()
            self.console.print("\n[warning]Interrupted[/warning]")
        except Exception as exc:
            self.tui.stop_thinking()
            self.console.print(f"[error]{type(exc).__name__}: {exc}[/error]")
        finally:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except NotImplementedError:
                pass

    def _prompt_fragments(self) -> StyleAndTextTuples:
        """Everything above and including the input line.

        Rebuilt on every repaint, so ctrl+o can fold the last tool call's
        details in and out without any of it touching scrollback. The top
        edge lives here too: prompt_toolkit owns it and redraws it in place.

        No rprompt right edge — prompt_toolkit pins rprompt to the first
        line of a multi-line prompt, which is not the input line.
        """
        top = "╭" + "─" * (self.console.width - 2) + "╮\n"
        return [
            *self.tui.expansion_fragments(),
            ("class:frame", top),
            ("class:frame", "│ "),
            ("class:prompt", "❯ "),
        ]

    def _bottom_fragments(self) -> StyleAndTextTuples:
        # Drawn by prompt_toolkit below the input so the box is closed the
        # whole time you are typing, not only once the line is submitted.
        return [("class:frame", "╰" + "─" * (self.console.width - 2) + "╯")]

    async def _read_input(self) -> str:
        self.console.print()
        try:
            return await self.session.prompt_async(
                self._prompt_fragments,
                bottom_toolbar=self._bottom_fragments,
            )
        finally:
            # Fold the details away so they never freeze into scrollback.
            self.tui.expanded = False
            # The toolbar edge is erased once the prompt is done, so the
            # submitted line needs its own bottom to stay boxed in the
            # transcript.
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

                if message.startswith("/"):
                    if not self._handle_command(message, agent):
                        break
                    continue

                self._reset_plan(agent)
                await self._run_turn(agent, message)
