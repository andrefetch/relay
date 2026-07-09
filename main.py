from typing import Any
from pathlib import Path
from agent.agent import Agent
from agent.events import AgentEventType
from config.config import Config
from config.loader import load_config
from ui.renderer import TUI, get_console
import asyncio
import click
import sys

console = get_console()

class CLI:
    def __init__(self, config: Config):
        self.agent: Agent | None = None
        self.config = config
        self.tui = TUI(config)

    async def run_single(self, message: str) -> str | None:
        async with Agent(self.config) as agent:
            self.agent = agent
            return await self._process_message(message)
    
    async def run_interactive(self) -> str | None:
        async with Agent(self.config) as agent:
            self.agent = agent
            self.tui.welcome(
                self.config.model_name,
            )

            while True:
                try:
                    user_input = (await self.tui.prompt()).strip()
                    if not user_input:
                        continue
                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break
            
            console.print("\n[dim]Exiting.[/dim]")
    
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
                    )
        finally:
            self.tui.stop_thinking()

        return final_response

@click.command()
@click.argument("prompt", required=False)
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
def main(
    prompt: str | None,
    cwd: Path | None,
):
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

    cli = CLI(config)

    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())

if __name__ == "__main__": # better than just main() ngl
    main()