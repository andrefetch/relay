import uuid

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

class TodoParams(BaseModel):

    action: str = Field(
        ...,
        description="Action: 'add', 'complete, 'list', 'clear'"
    ),

    id: str | None = Field(
        None,
        description="A Todo ID (for completed Todo(s) )",
    ),

    content = str | None = Field(
        None,
        description='The content for Todo add'
    )


class TodoTool(Tool):
    name = 'todo'
    description = 'Manage a task list for the current session, use this to track progress on more complex and multi-step tasks that can get resourse intensive.'
    kind = ToolKind.MEMORY
    schema = TodoParams

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._todos: dict[str, str] = {}
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:

        params = TodoParams(**invocation.params)

        try:

            if params.action.lower() == 'add':
                if not params.content:
                    return ToolResult.error_result(
                        "Content is required for the 'add' action."
                    )
                
                todo_id = str(uuid.uuid4())[:8]

                self._todos[todo_id] = params.content 
                return ToolResult.success_result(
                    f"Added todo [{todo_id}] : {params.content}"
                )

            elif params.action.lower() == 'complete':
                if not params.content:
                    return ToolResult.error_result(
                        "Content is required for the 'complete' action."
                    )
                if params.id not in self._todos:
                    return ToolResult.error_result(
                        f"Todo not found: {params.id}"
                    )
                
                content = self._todos.pop(params.id)
                return ToolResult.success_result(
                    f"Completed todo [{params.id}]: {params.content}"
                )
            
            elif params.content == 'list':
                if not self._todos:
                    return ToolResult.success_result(
                        "No todos."
                    )
                
                lines = ['Todos:']

                for todo_id, content in self._todos.items():
                    lines.append(f" [{todo_id}] [{content}]")
                return ToolResult.success_result(
                    "\n".join(lines)
                )
            
            elif params.action == 'clear':

                count = len(self._todos)

                self._todos.clear()
                return ToolResult.success_result(
                    f"Cleared {count} todo(s)."
                )

            else:
                return ToolResult.error_result(
                    f"Unknown action: {params.action}"
                )
        
        except Exception as e:

            return ToolResult.error_result(
                f"Unknown error: {e}"
            )


       