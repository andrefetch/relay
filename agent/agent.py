from __future__ import annotations
from typing import AsyncGenerator
from context.manager import ContextManager
from agent.events import AgentEvent, AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType
from tools.registry import create_default_registery

class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.context_manager = ContextManager()
        self.tool_registery = create_default_registery()
    
    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self.context_manager.add_user_message(message)

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
        
        yield AgentEvent.agent_end()
    
    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:

        response_text = ""

        tool_schemas = self.tool_registery.get_schemas()
        
        async for event in self.client.chat_completion(
            self.context_manager.get_messages(), 
            tools=tool_schemas if tool_schemas else None, 
            stream=True
        ):
            print(event)
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    content = event.text_delta.content
                    response_text += content
                yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occured.")
        
        self.context_manager.add_assistant_message(
            response_text or None,
        )
    
        if response_text:
            yield AgentEvent.text_complete(response_text)
    
    async def __aenter__(self) -> Agent:
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:

        if self.client:
            await self.client.close()
            self.client = None