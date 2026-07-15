import json
import uuid
from typing import Any

from config.config import Config
from config.loader import get_data_dir
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field


class MemoryParams(BaseModel):

    action: str = Field(
        ...,
        description="Action: 'set', 'get', 'delete', 'list', 'clear'"
    )

    key: str | None = Field(
        None,
        description="Memory key: required for set, get, delete.",
    )

    value: str | None = Field(
        None,
        description="Value to store (required for set)",
    )


class MemoryTool(Tool):
    name = 'memory'
    description = 'Store and retrieve persistent memory, use this tool to remember user information and preferences, for example: important context, user-specific details.'
    kind = ToolKind.MEMORY
    schema = MemoryParams

    def _load_memory(self) -> dict:

        data_dir = get_data_dir()

        data_dir.mkdir(
            parents=True, 
            exist_ok=True
        )

        path = data_dir / 'user_memory.json'

        if not path.exists():
            return {
                'entries': {}
            }
        
        try:
            content = path.read_text(
                encoding='utf-8'
            )
            return json.loads(content)
        except Exception:
            return {
                "entries": {}
            }
    
    def _save_memory(self, memory: dict) -> None:

        data_dir = get_data_dir()

        data_dir.mkdir(
            parents=True, 
            exist_ok=True
        )

        path = data_dir / 'user_memory.json'

        path.write_text(json.dumps(
            memory, 
            indent=2, 
            ensure_ascii=False
            )
        )

    async def execute(self, invocation: ToolInvocation):
        
        params = MemoryParams(**invocation.params)

        try:
            if params.action.lower() == "set":
                if not params.key or not params.value:
                    return ToolResult.error_result(
                        "Key and value are required for set action."
                    )
                memory = self._load_memory()
                memory['entries'][params.key] = params.value
                self._save_memory(memory)

                return ToolResult.success_result(
                    f"Set memory: {params.key}"
                )
            
            elif params.action.lower() == "get":
                if not params.key:
                    return ToolResult.error_result(
                        "Key required for: 'get' action"
                    )
                
                memory = self._load_memory()
                if params.key not in memory:
                    return ToolResult.success_result(
                        f"Memory not found: {params.key}"
                    )
                return ToolResult.success_result(
                        f"Memory found: {params.key}: {memory['entries'][params.key]}"
                    )
            
            elif params.action == "delete":
                if not params.key:
                    return ToolResult.error_result(
                        "Key required for: 'delete' action"
                    )
                memory = self._load_memory()
                if params.key not in memory.get('entries', {}):
                    return ToolResult.success_result(
                        f"Memory not found: {params.key}"
                    )
                
                del memory['entries'][params.key]
                self._save_memory(memory)

                return ToolResult.success_result(
                    f"Deleted memory: {params.key}"
                )
            
            elif params.action == "list":

                memory = self._load_memory()
                entries = memory.get('entries', {})

                if not entries:
                    return ToolResult.success_result(
                        "No memory has been stored."
                    )
                
                lines = [f"Stored memories:"]
                for key, value in sorted(entries.items()):
                    lines.append(f" {key}: {value}")
                
                return ToolResult.success_result(
                    "\n".join(lines)
                )
            
            elif params.action == "clear":

                memory = self._load_memory()
                count = len(memory.get('entries', {}))
                self._save_memory(memory)
                return ToolResult.success_result(f"Cleared {count} entries")

            else:

                return ToolResult.error_result(
                    f"Unknown action: {params.action}"
                )
            
        except Exception as e:
            return ToolResult.error_result(
                f"Something went wrong: {e}"
            )