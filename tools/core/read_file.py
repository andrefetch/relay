from pydantic import BaseModel, Field
from tools.base import Tool, ToolKind, ToolInvocation, ToolResult

class ReadFileParams(BaseModel):

    path: str = Field(
        ...,
        description='Path to the file to read (relative to the working dir or abs path)'
    )

    offset: int = Field(
        1, 
        ge=1, 
        description='The line number to start reading from, does not use 0 as base index starts from 1. else -> defaults to 1')

    limit: int | None = Field(
        None,
        description='Maximum number of lines to read, without specification it will read the whole file'
    )

class ReadFileTool(Tool):
    name = 'read_file'
    description = (
        "Read the contents of a file from the filesystem and return it as text with line numbers prefixed "
        "(e.g. '1: import os'). If 'offset' exceeds the file's line count, returns an empty result. "
        "Fails if the file does not exist, is a directory, or cannot be read (e.g. binary/permission errors)."
        "Cannot read binary files (images, executables, etc.)"
    )
    kind = ToolKind.READ

    schema = ReadFileParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ReadFileParams(**invocation.params)