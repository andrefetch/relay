from typing import Any
from agent.agent import Agent
from agent.events import AgentEventType
from ui.renderer import TUI, get_console
import asyncio
import click
import sys

console = get_console()

class CLI:
    def __init__(self):
        self.agent : Agent | None = None
        self.tui = TUI()

    async def run_single(self, message: str) -> str | None:
        async with Agent() as agent:
            self.agent = agent
            return await self._process_message(message)
    
    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None
        
        assistant_streaming = False
        final_response: str | None = None

        async for event in self.agent.run(message):
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
            elif event.type == AgentEventType.AGENT_ERROR:
                console.print(f"[error]{event.data.get('error')}[/error]")
                return None
            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "unknown")
                tool_kind = None
                tool = self.agent.tool_registery.get(tool_name)
                if not tool:
                    tool_kind = None
                
                tool_kind = tool.kind.value
        
        return final_response

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
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)

main()