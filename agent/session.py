import uuid

from client.llm_client import LLMClient
from client.response import TokenUsage
from config.config import Config
from context.manager import ContextManager
from tools.registry import create_default_registery
from datetime import datetime

class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(
            config=config,
        )
        self.context_manager = ContextManager(config=config)
        self.tool_registery = create_default_registery(config)
        self.session_id = str(uuid.uuid4()) # Unique identifiers to resume sessions
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        # Usage from the most recent completion. prompt_tokens on the latest
        # call reflects the full context currently in the window, so this
        # doubles as the "context used" gauge.
        self.last_usage: TokenUsage | None = None

        # Usage summed across every completion in the current turn. The agent
        # loops once per tool round-trip, so this grows as the turn works.
        self.turn_usage = TokenUsage()

        self._turn_count = 0

    def reset_turn_usage(self) -> None:
        self.turn_usage = TokenUsage()
    
    def inc_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.now()

        return self._turn_count
