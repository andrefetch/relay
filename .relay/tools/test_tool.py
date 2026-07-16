from pydantic import BaseModel, Field
from tools.base import Tool, ToolInvocation, ToolResult, ToolKind

class TestToolParams(BaseModel):
    message: str = Field(..., description="The message to echo back")


class TestTool(Tool):
    name = "test_tool"
    description = (
        "A test tool that echoes back the input message. "
        "This tool is discovered from .relay/tool/test_tool.py"
    )
    kind = ToolKind.READ
    schema = TestToolParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = TestToolParams(**invocation.params)
        message = params.message

        output = f"Test tool received: {message}\n"
        output += "Tool was discovered from: .relay/tool/test_tool.py"

        return ToolResult.success_result(output)