import math
import asyncio
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError
from typing import Any, AsyncGenerator
from client.response import TextDelta, TokenUsage, StreamEvent, StreamEventType, ToolCallDelta, ToolCall, parse_tool_call_arguments


class LLMClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._max_retries: int = 3

    def get_client(self) -> AsyncOpenAI:
        if self._client is None:
            # TODO: wire up to your own config system instead of hardcoding
            self._client = AsyncOpenAI(
                api_key="",
                base_url="https://openrouter.ai/api/v1",
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    def _build_tools(
            self,
            tools: list[dict[str, Any]]
    ):
        return [
            {
                'type': 'function',
                'function': {
                    'name': tool['name'],
                    'description': tool.get('description', ""),
                    'parameters': tool.get('parameters', {
                        'type': 'object',
                        'properties': {}
                    })
                },
            }
            for tool in tools
        ]

    async def chat_completion(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
            stream: bool = True
    ) -> AsyncGenerator[StreamEvent, None]:

        client = self.get_client()

        kwargs = {
            "model": "cohere/north-mini-code:free",
            "messages": messages,
            "stream": stream,
        }

        if tools:
            kwargs['tools'] = self._build_tools(tools)
            kwargs['tool_choice'] = 'auto'

        for attempt in range(self._max_retries + 1):
            try:
                if stream:
                    async for event in self._stream_response(client, kwargs):
                        yield event
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
                return
            except RateLimitError as e:
                if attempt < self._max_retries:
                    wait_time = math.pow(2, attempt)
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Rate limit exceeded: {e}",
                    )
                    return
            except APIConnectionError as e:
                if attempt < self._max_retries:
                    wait_time = math.pow(2, attempt)
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection Error exceeded: {e}",
                    )
                    return
            # No retries here, solely because there's no point in retrying if there is a hardstuck API Error
            except APIError as e:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=f"API Error: {e}",
                )
                return

    async def _stream_response(self, client: AsyncOpenAI, kwargs: dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
        response = await client.chat.completions.create(**kwargs)

        finish_reason: str | None = None
        usage: TokenUsage | None = None
        tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(delta.content),
                )

            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    index = tool_call_delta.index

                    if index not in tool_calls:
                        tool_calls[index] = {
                            'id': tool_call_delta.id or "",
                            'name': '',
                            'arguments': '',
                        }

                    # NOTE: this used to be nested inside "if index not in tool_calls",
                    # which meant argument fragments after the first chunk for a given
                    # index were silently dropped. Now runs on every chunk.
                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            tool_calls[index]['name'] = tool_call_delta.function.name
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_START,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[index]['id'],
                                    name=tool_call_delta.function.name,
                                )
                            )

                        if tool_call_delta.function.arguments:
                            tool_calls[index]['arguments'] += tool_call_delta.function.arguments
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[index]['id'],
                                    name=tool_calls[index]['name'],
                                    arguments_delta=tool_call_delta.function.arguments,
                                )
                            )

        for index, toolcall in tool_calls.items():
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    call_id=toolcall['id'],
                    name=toolcall['name'],
                    arguments=parse_tool_call_arguments(toolcall['arguments']),
                )
            )

        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: dict[str, Any]) -> StreamEvent:
        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]  # only interested in first index, first message
        message = choice.message

        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for toolcall in message.tool_calls:
                tool_calls.append(ToolCall(
                    call_id=toolcall.id,
                    name=toolcall.function.name,
                    arguments=parse_tool_call_arguments(
                        toolcall.function.arguments
                    )
                ))

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )