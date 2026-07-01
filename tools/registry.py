from tools.base import Tool
from typing import Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        
        return False
    
    def get(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
    
    def get_tools(self) -> list[Tool]:
        tools: list[Tool]

        for tool in self._tools.values():
            tools.append(tool)
        
        return tools
    
    def get_schema(self) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self.get_tools()]
    
    async def invoke(self, name: str, params: dict[str, Any], cwd: Path | None):