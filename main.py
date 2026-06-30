from typing import Any
from agent.agent import Agent
import asyncio
import click

class CLI:
    def __init__(self):
        self.agent : Agent | None = None

    async def run_single(self, message: str):
        async with Agent() as agent:
            self.agent = agent
            self._process_message(message)

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