import uuid

from client.llm_client import LLMClient
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
        self.tool_registery = create_default_registery()
        self.session_id = str(uuid.uuid4()) # Unique identifiers to resume sessions
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self._turn_count = 0
    
    def inc_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.now()

        return self._turn_count
