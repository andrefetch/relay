from openai import AsyncOpenAI
from typing import Any

class LLMClient:
    def __init__(self) -> None:
        self._client : AsyncOpenAI | None = None

    def get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                    api_key="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",
                    base_url="https://openrouter.ai/api/v1",
            )
        return self._client
    
    async def close(self) -> None:
        if self._client:
            await self.client.close()
            self._client = None

    async def chat_completion(self, messages: list[dict[str, Any]], stream: bool = True):

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

    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: dict[str, Any]):
        response = await client.chat.completions.create(**kwargs)
        print(response)