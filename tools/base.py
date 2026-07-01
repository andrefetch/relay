from __future__ import annotations
import abc
from pathlib import Path
from pydantic import BaseModel
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class ToolType(str, Enum):
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolInvocation:
    params: dict[str, Any]
    cwd: Path

class Tool(abc.ABC):
    name: str = "base_tool"
    description: str = "Base tool"
    type: ToolType = ToolType.READ

    def __init__(self) -> None:
        pass
    
    @property
    def schema(self) -> dict[str, Any] | type['BaseModel']:
        raise NotImplementedError("Error: Tool must defined a schema property or an attribute.")

    @abc.abstractclassmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult