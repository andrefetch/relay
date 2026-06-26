from openai import AysncOpenAI

class LLMClient:
    def __init__(self) -> None:
        self._client : AysncOpenAI | None = None

    def get_client(self) -> AysncOpenAI:
        if self._client is None:
            self._client = AysncOpenAI(
                    api_key='',
                    base_url='',
                    )
        return self._client
    
    async def close(self) -> None:
        if self._client:
            await self.client.close()
            self._client = None

