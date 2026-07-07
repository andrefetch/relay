from __future__ import annotations
import json
from pathlib import Path
from typing import AsyncGenerator
from config.config import Config
from context.manager import ContextManager
from agent.events import AgentEvent, AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType, ToolCall, ToolResultMessage
from tools.registry import create_default_registery

class Agent:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(
            config=config,
        )
        self.context_manager = ContextManager(config=config)
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
        tool_calls: list[ToolCall] = []
        
        async for event in self.client.chat_completion(
            self.context_manager.get_messages(), 
            tools=tool_schemas if tool_schemas else None, 
            stream=True
        ):
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    content = event.text_delta.content
                    response_text += content
                yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                if event.tool_call:
                    tool_calls.append(event.tool_call)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occured.")
        
        self.context_manager.add_assistant_message(
            response_text or None,
            [
                {
                    'id': tc.call_id,
                    'type': 'function',
                    'function': {
                        'name': tc.name,
                        'arguments': json.dumps(tc.arguments),
                    },
                }
                for tc in tool_calls
            ]
            if tool_calls
            else None
        )
    
        if response_text:
            yield AgentEvent.text_complete(response_text)
        
        tool_call_results: list[ToolResultMessage] = []

        for tool_call in tool_calls:
            yield AgentEvent.tool_call_start(
                tool_call.call_id,
                tool_call.name,
                tool_call.arguments
            )

            result = await self.tool_registery.invoke(
                tool_call.name,
                tool_call.arguments,
                Path.cwd(),
            )

            yield AgentEvent.tool_call_complete(
                tool_call.call_id,
                tool_call.name,
                result,
            )

            tool_call_results.append(
                ToolResultMessage(
                    tool_call_id=tool_call.call_id,
                    content=result.to_model_output(),
                    is_error=not result.success
                )
            )

        for tool_result in tool_call_results:
            self.context_manager.add_tool_result(
                tool_result.tool_call_id,
                tool_result.content,
            )
    
    async def __aenter__(self) -> Agent:
        return self
    
    async def __aexit__(
            self, 
            exc_type, 
            exc_val, 
            exc_tb
            ) -> None:

        if self.client:
            await self.client.close()
            self.client = None