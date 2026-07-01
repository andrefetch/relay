from typing import Any
from agent.agent import Agent
from agent.events import AgentEventType
from ui.renderer import TUI, get_console
import asyncio
import click

console = get_console()

class CLI:
    def __init__(self):
        self.agent : Agent | None = None
        self.tui = TUI()

    async def run_single(self, message: str):
        async with Agent() as agent:
            self.agent = agent
            self._process_message(message)
    
    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                self.tui.stream_assistant_delta(content)

@click.command()
@click.argument("prompt", required=False)
def main(
    prompt: str | None,
):
    cli = CLI()
    messages = [{
        'role': 'user',
        'content': prompt
    }]
    if prompt:
        asyncio.run(cli.run_single(prompt))

main()