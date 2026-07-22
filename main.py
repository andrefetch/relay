from pathlib import Path
from agent.agent import Agent
from config.config import Config
from config.loader import load_config
from config.credentials import (
    clear_credentials,
    get_credentials_path,
    load_credentials,
    save_credentials,
)
from config.oauth import OAuthError, login_with_oauth
from ui.renderer import TUI, get_console
from ui.repl import Repl
from ui.stream import stream_turn
import asyncio
import click
import sys

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

console = get_console()

async def run_once(config: Config, message: str) -> str | None:
    tui = TUI(config)
    async with Agent(config, confirmation_callback=tui.confirm_tool) as agent:
        tui.render_approval_mode()
        return await stream_turn(tui, agent, message)


class DefaultGroup(click.Group):

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
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
        result = asyncio.run(run_once(config, prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(Repl(config).run())


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