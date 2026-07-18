from enum import Enum
import os
from pathlib import Path
from typing import Any
from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport
from dataclasses import dataclass, field

from config.config import MCPServerConfig

class MCPServerStatus(str, Enum):
    
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ERROR = 'error'

@dataclass
class MCPToolInfo:

    name: str
    description: str
    input_schema: dict[str, Any] = field(
        default_factory=dict
    )
    server_name: str = ""

class MCPClient:
    def __init__(
            self,
            name: str,
            config: MCPServerConfig,
            cwd: Path
    ) -> None:
        
        self.name = name
        self.config = config
        self.cwd = cwd
        self.status = MCPServerStatus.DISCONNECTED
        self._client: Client | None = None

        self._tools: dict[str, MCPToolInfo] = dict()
    
    def _create_transport(self) -> StdioTransport | SSETransport:

        if self.config.command:
            env = os.environ.copy()
            env.update(self.config.env)
            return StdioTransport(
                command = self.config.command,
                args = list(self.config.args),
                env = env,
                cwd = str(self.config.cwd or self.cwd)
            )
        else:
            return SSETransport(url=self.config.url)

    async def connect(self) -> None:

        if self.status == MCPServerStatus.CONNECTED:
            return
        
        self.status = MCPServerStatus.CONNECTING

        try:
            self._client = Client(
                transport=self._create_transport()
            )

            await self._client.__aenter__()

            tools = self._client.list_tools()
            for tool in tools:
                self._tools[tool.name] = MCPToolInfo(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=self.name
                )
            
            self.status = MCPServerStatus.CONNECTED

        except Exception as e:
            self.status = MCPServerStatus.ERROR
            self._tools.clear()
    
    async def disconnect(self) -> None:

        if self._client:
            await self._client.__aexit__(
                None,
                None,
                None,
            )

            self._client = None
        
        self._tools.clear()
        self.status = MCPServerStatus.DISCONNECTED