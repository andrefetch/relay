from client.response import TokenUsage
from config.config import Config
from prompts.system import get_system_prompt
from dataclasses import dataclass, field
from tools.base import Tool
from utils.text import count_tokens
from typing import Any

EMPTY_TOOL_OUTPUT = "(no output)"

@dataclass
class MessageItem:
    role: str
    content: str
    token_count: int | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
           "role": self.role 
        }

        if self.tool_call_id:
            result['tool_call_id'] = self.tool_call_id
        
        if self.tool_calls:
            result['tool_calls'] = self.tool_calls

        if self.role == 'tool':
            result['content'] = self.content or EMPTY_TOOL_OUTPUT
        elif self.content:
            result['content'] = self.content

        return result

class ContextManager:

    PRUNE_PROTECT_TOKENS = 40_000
    PRUNE_MINIMUM_TOKENS = 20_000

    def __init__(
            self,
            config: Config,
            user_memory: str | None,
            tools: list[Tool] | None = None,
            ) -> None:
        self._system_prompt = get_system_prompt(config, user_memory, tools)
        self.config = config
        self._model_name = self.config.model_name
        self._messages: list[MessageItem] = []
        self._latest_usage = TokenUsage()
        self._total_usage = TokenUsage()
    
    def add_user_message(self, content):
        item = MessageItem(
            role = 'user', 
            content = content,
            token_count=count_tokens(content, self._model_name)
        )

        self._messages.append(item)
    
    def add_assistant_message(
            self, 
            content: str, 
            tool_calls: list[dict[str, Any]] | None = None,
            ) -> None:
        item = MessageItem(
            role = 'assistant', 
            content = content or "",
            token_count=count_tokens(
                content or "",
                self._model_name
            ),
            tool_calls=tool_calls or []
        )

        self._messages.append(item)
    
    def clear(self) -> None:
        self._messages.clear()

    def get_messages(self) -> list[dict[str, Any]]:
        messages = []

        if self._system_prompt:
            messages.append(
                {
                'role': 'system',
                'content': self._system_prompt
                }
            )
        
        for item in self._messages:
            messages.append(item.to_dict())
        
        return messages
    
    def add_tool_result(
            self, 
            tool_call_id: str, 
            content: str
            ) -> None:
        item = MessageItem(
            role='tool',
            content=content,
            tool_call_id=tool_call_id,
            token_count=count_tokens(content, self._model_name)
        )

        self._messages.append(item)

    def set_latest_usage(self, usage: TokenUsage):
        self._latest_usage = usage

    def add_usage(self, usage: TokenUsage):
        self._total_usage += usage

    def needs_compression(self) -> bool:

        context_lim = self.config.model.context_window
        current_tokens = self._latest_usage.total_tokens

        return current_tokens > (context_lim * 0.8)

    def replace_with_summary(self, summary: str) -> None:

        self._messages = []

        continuation_content = f"""# Context Restoration (Previous Session Compacted)

        The previous conversation was compacted due to context length limits. Below is a detailed summary of the work done so far. 

        **CRITICAL: Actions listed under "COMPLETED ACTIONS" are already done. DO NOT repeat them.**

        ---

        {summary}

        ---

        Resume work from where we left off. Focus ONLY on the remaining tasks."""

        summary_item = MessageItem(
            role="user",
            content=continuation_content,
            token_count=count_tokens(continuation_content, self._model_name),
        )
        self._messages.append(summary_item)

        ack_content = """I've reviewed the context from the previous session. I understand:
- The original goal and what was requested
- Which actions are ALREADY COMPLETED (I will NOT repeat these)
- The current state of the project
- What still needs to be done

I'll continue with the REMAINING tasks only, starting from where we left off."""
        ack_item = MessageItem(
            role="assistant",
            content=ack_content,
            token_count=count_tokens(ack_content, self._model_name),
        )
        self._messages.append(ack_item)

        continue_content = (
            "Continue with the REMAINING work only. Do NOT repeat any completed actions. "
            "Proceed with the next step as described in the context above."
        )

        continue_item = MessageItem(
            role="user",
            content=continue_content,
            token_count=count_tokens(continue_content, self._model_name),
        )
        self._messages.append(continue_item)

    def prune_tool_outputs(self) -> int:

        user_message_count = sum(1 for message in self._messages if message.role == 'user')

        if user_message_count < 2:
            return 0

        total_tokens = 0
        for message in self._messages:
            if message.role == 'tool' and message.tool_call_id:

                tokens = message.token_count or count_tokens(message.content, self._model_name)
                total_tokens += tokens

