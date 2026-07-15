from config.config import Config
from tools.base import Tool
from typing import Any
from pathlib import Path
from tools.base import ToolResult, ToolInvocation
from tools.core import ReadFileTool, get_all_core_tools
import logging

from tools.subagents.subagents import SubAgentTool, get_default_subagent_definitions


logger = logging.getLogger(__name__)

class ToolRegistry:

    def __init__(self, config: Config):
        self._tools: dict[str, Tool] = {}
        self.config = config
    
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
        
        return None
    
    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []

        for tool in self._tools.values():
            tools.append(tool)
        
        if self.config.allowed_tools:
            allowed_set = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed_set]

        return tools
    
    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self.get_tools()]
    
    async def invoke(
            self,
            name: str,
            params: dict[str, Any],
            cwd: Path | None
        ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult.error_result(
                f"Unknown Tool: {name}",
                metadata={
                    'tool_name': name
                },
            )
        
        validiation_errors = tool.validate_params(params)
        if validiation_errors:
            return ToolResult.error_result(
                f"Invalid paramaters: {'; '.join(validiation_errors)}",
                metadata={
                    'tool_name': name,
                    'validation_errors': validiation_errors
                }
            )
        invocation = ToolInvocation(
            params=params,
            cwd=cwd,
        )
        try:
            result = await tool.execute(invocation)
        except Exception as e:
            logger.exception(f"Tool {name} raised unexpected error")
            result = ToolResult.error_result(
                f"Internal error: {(str(e))}",
                metadata = {
                    "tool_name": name
                }
            )
        
        return result
        
def create_default_registery(config: Config) -> ToolRegistry:

    registery = ToolRegistry(config)
    
    for tool_class in get_all_core_tools():
        registery.register(tool_class(config))
    
    for subagent_def in get_default_subagent_definitions():
        registery.register(SubAgentTool(config, subagent_def))

    return registery