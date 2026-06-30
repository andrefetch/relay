from client.llm_client import LLMClient
import asyncio

async def main():

    client = LLMClient()
    messages = [{
        'role': 'user',
        'content': 'what is up'
    }]
    async for event in client.chat_completion(messages, True):
        print(event)
    print("done!")

asyncio.run(main())