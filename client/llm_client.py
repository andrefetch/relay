from openai import AsyncOpenAI
from typing import Any
from client.response import TextDelta, TokenUsage, StreamEvent, EventType

class LLMClient:
    def __init__(self) -> None:
        self._client : AsyncOpenAI | None = None

    def get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                    api_key="",
                    base_url="https://openrouter.ai/api/v1",
            )
        return self._client
    
    async def close(self) -> None:
        if self._client:
            await self.client.close()
            self._client = None

    async def chat_completion(self, messages: list[dict[str, Any]], stream: bool = True) -> str:

        client = self.get_client()

        kwargs = {
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "messages": messages,
            "stream": stream,
        }

        if stream:
            self._stream_response()
        else:
            await self._non_stream_response(client, kwargs)
        
    async def _stream_response(self):
        pass

    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: dict[str, Any]) -> StreamEvent:
        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0] # only interested in first index, first message
        message = choice.message
        text_delta = None

        if message.content:
            text_delta = TextDelta(content=message.content) 
        
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.prompt_token_details.cached_tokens
            )
        
        return StreamEvent(
            type=EventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )