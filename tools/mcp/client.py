from enum import Enum
import os
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport

from config.config import MCPServerConfig

class MCPServerStatus(str, Enum):
    
    DISCONNECTED = 'disconnected'
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    ERROR = 'error'

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
        self._client = Client | None = None
    
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

        except Exception as e:
            self.status = MCPServerStatus.ERROR
            print(f"Error: {e}")