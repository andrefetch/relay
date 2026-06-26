from openai import AysncOpenAI
from typing import Any

class LLMClient:
    def __init__(self) -> None:
        self._client : AysncOpenAI | None = None

    def get_client(self) -> AysncOpenAI:
        if self._client is None:
            self._client = AysncOpenAI(
                    api_key="",
                    base_url="https://openrouter.ai/api/v1",
            )
        return self._client
    
    async def close(self) -> None:
        if self._client:
            await self.client.close()
            self._client = None

    async def chat_completion(self, messages: list[dict[str, Any]], stream: bool = True):
        if stream:
            self._stream_response()
        else:
            self.non_stream_response()
        
    async def _stream_response(self):
        pass

    async def _non_stream_response(self):
        pass