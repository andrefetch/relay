import json
import uuid

from client.llm_client import LLMClient
from client.response import TokenUsage
from config.config import Config
from config.loader import get_data_dir
from context.manager import ContextManager
from tools.discovery import ToolDiscoveryManager
from tools.registry import create_default_registry
from datetime import datetime

class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(
            config=config,
        )
        self.context_manager = ContextManager(
            config=config, 
            user_memory=self._load_memory()
        )
        self.tool_registry = create_default_registry(config)
        self.discovery_manager = ToolDiscoveryManager(
            self.config,
            self.tool_registry
        )
        self.session_id = str(uuid.uuid4()) # Unique identifiers to resume sessions
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        self.last_usage: TokenUsage | None = None

        self.turn_usage = TokenUsage()

        self.discovery_manager.discover()

        self._turn_count = 0
    
    def _load_memory(self) -> str | None:

        data_dir = get_data_dir()

        data_dir.mkdir(
            parents=True, 
            exist_ok=True
        )

        path = data_dir / 'user_memory.json'

        if not path.exists():
            return None
        
        try:
            content = path.read_text(
                encoding='utf-8'
            )
            data = json.loads(content)
            entries = data.get('entries')
            if not entries:
                return None
            
            lines = ["User preferences and notes:"]
            for key, value in entries.items():
                lines.append(f"- {key}: {value}")
            
            return "\n".join(lines)
        except Exception:
            return None

    def reset_turn_usage(self) -> None:
        self.turn_usage = TokenUsage()
    
    def inc_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.now()

        return self._turn_count
