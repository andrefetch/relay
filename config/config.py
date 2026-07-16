from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, model_validator

from config.credentials import load_credentials

class ModelConfig(BaseModel):

    name: str = ''
    
    temperature: float = Field(
        default=1, 
        ge=0.0, 
        le=2.0
    ) # clarity of the model

    context_window: int = 256_000

class ShellEnvironmentConfig(BaseModel):
    ignore_default_excludes: bool = False # for filtering keys, secrets
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*KEY*", "*TOKEN*", "*SECRET*"]
    )
    set_vars: dict[str, str] = Field(default_factory=dict)

class MCPServerConfig(BaseModel):

    enabled: bool = True
    startup_timeout: float = 10

    # standard input transport
    command: str | None = None

    args: list[str] = Field(
        default_factory=list
    )

    env: dict[str, str] = Field(
        default_factory=dict
    )

    cwd: Path | None = None

    # Http/ sse transports
    url: str | None = None

    @model_validator(
        mode='after'
    )
    def validate_transport(self) -> MCPServerConfig:
        has_command = self.command is not None
        has_url = self.url is not None

        if not has_command and not has_url:
            raise ValueError(
                "MCP Servers must have either 'command' (stdio) or 'url' (http/sse)"
            )
        
        if has_command and has_url:
            raise ValueError(
                "MCP Severs can't have both command and url"
            )


class Config(BaseModel):

    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    shell_environment: ShellEnvironmentConfig = Field(
        default_factory=ShellEnvironmentConfig
    )

    allowed_tools: list[str] | None = Field(
        None,
        description='If set, only these tools would be avaliable to the agent or subagents.'
    )

    max_turns: int = 100
    mcp_servers: dict[str, MCPServerConfig] = Field(
        default_factory=dict
    )
    max_tool_output_tokens: int = 50_000

    developer_instructions: str | None = None
    user_instructions: str | None = None
    debug: bool = False

    @property
    def api_key(self) -> str | None:
        # Env var wins (handy for CI / one-off overrides); otherwise fall
        # back to whatever `relay login` saved.
        return os.environ.get("API_KEY") or load_credentials().get("api_key")

    @property
    def base_url(self) -> str | None:
        return os.environ.get("BASE_URL") or load_credentials().get("base_url")
    
    @property
    def model_name(self) -> str:
        return self.model.name
    
    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    @property
    def temperature(self) -> float:
        return self.model.temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self.model.temperature = value
    
    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.api_key:
            errors.append("No API key was found. Solution: run `relay login` (or set the API_KEY environment variable)")
        
        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")
        
        return errors
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(
            mode='json'
        )
