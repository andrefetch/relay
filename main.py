from client.llm_client import LLMClient
import asyncio

async def main():

    client = LLMClient()
    messages = [{
        'role': 'user',
        'content': 'what is up'
    }]
    await client.chat_completion(messages, False)
    print('done')

asyncio.run(main())