from openai import AysncOpenAI
from typing import Any

class LLMClient:
    def __init__(self) -> None:
        self._client : AysncOpenAI | None = None

    def get_client(self) -> AysncOpenAI:
        if self._client is None:
            self._client = AysncOpenAI(
                    api_key="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",
                    base_url="https://openrouter.ai/api/v1",
            )
        return self._client
    
    async def close(self) -> None:
        if self._client:
            await self.client.close()
            self._client = None

    async def chat_completion(self, messages: list[dict[str, Any]]):