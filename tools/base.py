from __future__ import annotations
import abc
from pathlib import Path
from pydantic import BaseModel, ValidationError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class ToolClass(str, Enum):
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
    type: ToolClass = ToolClass.READ

    def __init__(self) -> None:
        pass
    
    @property
    def schema(self) -> dict[str, Any] | type['BaseModel']:
        raise NotImplementedError("Error: Tool must defined a schema property or an attribute.")

    @abc.abstractclassmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        pass

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.schema
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    ".".join(str(x) for x in error.get("loc", []))
                    msg = error.get('msg', 'Validation Error')
                    errors.append(f"Paramater: '{field}': {msg}")
                
                return errors
            except Exception as e:
                return [str(e)]