import os
from pathlib import Path

from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

from utils.paths import is_binary_file, resolve_path

class WebSearchParams(BaseModel):

    qurey: str = Field(
        ...,
        description='Search query'
    )

    max_results: int = Field(
        10,
        ge=1,
        le=50,
        description='Maximum results to return (default: 10)'
    )

class WebSearchTool(Tool):
    name = 'web_search'
    description = 'Search the web for information. Returns the search results that contains titles, URL(s) and snippets.'
    kind = ToolKind.NETWORK
    schema = WebSearchParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebSearchParams(**invocation.params)

       