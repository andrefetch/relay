from typing import Any

from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage
from context.manager import ContextManager
from prompts.system import get_compaction_prompt

class ChatCompactor:

    def __init__(self, client: LLMClient):
        self.client = client

    def _format_history(self, messages: list[dict[str, Any]]) -> str:

        output = [
            'Here is the conversation that needs to be continued. \n'
        ]

        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')

            if role == 'system':
                continue

            if role == 'tool':
                tool_id = message.get('tool_call_id', 'unknown')

                truncated = content[:2000] if len(content) > 2000 else content
                if len(content) > 2000:
                    truncated += '\n... [tool output truncated]'

                output.append(f'[Tool Result ({tool_id})]:\n{truncated}')

            elif role == 'assistant':

                tool_details = []

                if content:
                    truncated = content[:3000] if len(content) > 3000 else content
                    if len(content) > 3000:
                        truncated += '\n... [response truncated]'
                    output.append(f'Agent:\n{truncated}')

                if message.get('tool_calls'):
                    for tc in message['tool_calls']:
                        func = tc.get('function', {})
                        name = func.get('name', 'unknown')
                        args = func.get('arguments', "{}")

                        if len(args) > 500:
                            args = args[:500]
                        tool_details.append(f"  - {name}({args})")

                output.append('Agent called tools:\n' + '\n'.join(tool_details))

            else:
                truncated = content[:1500] if len(content) > 1500 else content
                if len(content) > 1500:
                    truncated += '\n... [message truncated]'
                output.append(f'User:\n{truncated}')

        return "\n\n---\n\n".join(output)


    async def compress(
            self, 
            context_manager: ContextManager
    ) -> tuple[str | None, TokenUsage | None]:

        messages = context_manager.get_messages()

        if len(messages) < 3:
            return None, None

        compression_messages = [
            {
                'role': 'system',
                'content': get_compaction_prompt()
            },
            {
                'role': 'user',
                'content': self._format_history(messages),
            }
        ]

        try:
            summary = ""
            usage = None

            async for event in self.client.chat_completion(
                compression_messages,
                stream=False
            ):
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
                    summary += event.text_delta.content

            if not summary or not usage:
                return None, None

            return summary, usage
        
        except Exception as e:
            print(f"Error: {e}")
            return None, None