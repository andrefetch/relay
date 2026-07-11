from pathlib import Path
from agent.agent import Agent
from agent.events import AgentEventType
from config.config import Config
from config.loader import load_config
from config.credentials import (
    clear_credentials,
    get_credentials_path,
    load_credentials,
    save_credentials,
)
from config.oauth import OAuthError, login_with_oauth
from ui.app import RelayApp
from ui.renderer import TUI, get_console
import asyncio
import click
import sys

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

async def confirm_tool(tool_name: str, arguments: dict) -> bool:
    console.print(f"[warning]The agent wants to run [bold]{tool_name}[/bold] with arguments:[/warning]")
    for key, value in arguments.items():
        console.print(f"  {key}: {value}")
    answer = await asyncio.to_thread(click.prompt, "Allow this tool? [y/N]", default="N", show_default=False)
    return answer.strip().lower() in {"y", "yes"}

console = get_console()

class CLI:
    """One-shot (`relay "prompt"`) driver.

    Stays line-oriented so the output can be piped and redirected; the
    interactive front-end is the full-screen RelayApp.
    """

    def __init__(self, config: Config):
        self.agent: Agent | None = None
        self.config = config
        self.tui = TUI(config)

    async def run_single(self, message: str) -> str | None:
        async with Agent(self.config, confirmation_handler=confirm_tool) as agent:
            self.agent = agent
            return await self._process_message(message)

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool = self.agent.session.tool_registery.get(tool_name)
        if not tool:
            return None
        return tool.kind.value
    
    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None
        
        assistant_streaming = False
        final_response: str | None = None
        thinking = False

        try:
            async for event in self.agent.run(message):
                if event.type == AgentEventType.AGENT_START:
                    self.tui.start_thinking()
                    thinking = True
                    continue

                if thinking:
                    self.tui.stop_thinking()
                    thinking = False

                if event.type == AgentEventType.TEXT_DELTA:
                    content = event.data.get("content", "")
                    if not assistant_streaming:
                        self.tui.begin_assistant()
                        assistant_streaming = True
                    self.tui.stream_assistant_delta(content)
                elif event.type == AgentEventType.TEXT_COMPLETE:
                    final_response = event.data.get("content")
                    if assistant_streaming:
                        self.tui.end_assistant()
                        assistant_streaming = False
                elif event.type == AgentEventType.AGENT_END:
                    self.tui.render_usage(event.data.get('usage'))
                elif event.type == AgentEventType.AGENT_ERROR:
                    console.print(f"[error]{event.data.get('error')}[/error]")
                    return None
                elif event.type == AgentEventType.TOOL_CALL_START:
                    tool_name = event.data.get("name", "unknown")
                    tool_kind = self._get_tool_kind(tool_name)
                    self.tui.tool_call_start(
                        event.data.get('call_id', ''),
                        tool_name,
                        tool_kind,
                        event.data.get('arguments', {}),
                    )
                elif event.type  == AgentEventType.TOOL_CALL_COMPLETE:
                    tool_name = event.data.get('name', 'unknown')
                    tool_kind = self._get_tool_kind(tool_name)
                    self.tui.tool_call_complete(
                        event.data.get('call_id', ''),
                        tool_name,
                        tool_kind,
                        event.data.get('success', False),
                        event.data.get('output', ""),
                        event.data.get('error'),
                        event.data.get('metadata'),
                        event.data.get('truncated', False),
                        event.data.get('diff'),
                        event.data.get('exit_code'),
                    )
        finally:
            self.tui.stop_thinking()

        return final_response

class DefaultGroup(click.Group):
    """Group that falls back to the `run` command for unknown tokens.

    Keeps the original ergonomics working: `relay "prompt"` and `relay`
    (no args) still hit the agent, while `relay login` / `relay logout`
    are dispatched as real subcommands.
    """

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # First token isn't a known subcommand, treat the whole thing
            # as a prompt for `run`.
            return "run", self.get_command(ctx, "run"), args


@click.group(cls=DefaultGroup, invoke_without_command=True)
@click.option(
    '--cwd',
    '-c',
    type=click.Path(
        exists=True,
        file_okay=False,
        path_type=Path,
    ),
    help='Current Working Directory'
)
@click.pass_context
def main(ctx: click.Context, cwd: Path | None):
    ctx.obj = {"cwd": cwd}
    # Bare `relay` with no subcommand launches the interactive TUI.
    if ctx.invoked_subcommand is None:
        ctx.invoke(run, prompt=None)


@main.command()
@click.argument("prompt", required=False)
@click.pass_context
def run(ctx: click.Context, prompt: str | None):
    """Run a one-shot prompt, or launch the TUI when no prompt is given."""
    cwd = ctx.obj.get("cwd") if ctx.obj else None

    try:
        config = load_config(cwd=cwd)
    except Exception as e:
        console.print(f"[error]Config Error: {e}[/error]")
        sys.exit(1)

    errors = config.validate()

    if errors:
        for error in errors:
            console.print(f'[error]Config Error: {error}[/error]')

        sys.exit(1)

    if prompt:
        result = asyncio.run(CLI(config).run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        RelayApp(config).run()


@main.command()
@click.option(
    "--base-url",
    default=None,
    help=f"API base URL to save (default: {DEFAULT_BASE_URL})",
)
@click.option(
    "--paste",
    is_flag=True,
    help="Paste an API key manually instead of authorizing in the browser.",
)
def login(base_url: str | None, paste: bool):
    """Log in to OpenRouter via your browser (or --paste an API key)."""
    if load_credentials().get("api_key"):
        if not click.confirm("You're already logged in. Overwrite the saved key?", default=False):
            console.print("[warning]Login cancelled.[/warning]")
            return

    resolved_base_url = base_url or DEFAULT_BASE_URL

    if paste:
        api_key = click.prompt("Paste your OpenRouter API key", hide_input=True).strip()
        if not api_key:
            console.print("[error]No key entered, nothing saved.[/error]")
            sys.exit(1)
    else:
        console.print("Opening your browser to authorize relay with OpenRouter...")
        try:
            api_key = login_with_oauth(resolved_base_url)
        except OAuthError as e:
            console.print(f"[error]Login failed:[/error] {e}")
            console.print("[warning]You can retry, or run `relay login --paste` to enter a key manually.[/warning]")
            sys.exit(1)

    path = save_credentials(api_key, resolved_base_url)
    console.print(f"[success]Logged in.[/success] Key saved to {path}")
    console.print("[warning]The API_KEY environment variable, if set, still takes precedence.[/warning]")


@main.command()
def logout():
    """Remove the saved OpenRouter API key."""
    if clear_credentials():
        console.print(f"[success]Logged out.[/success] Removed {get_credentials_path()}")
    else:
        console.print("[warning]No saved credentials to remove.[/warning]")


if __name__ == "__main__": # better than just main() ngl
    main()