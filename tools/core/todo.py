import uuid
from typing import Any

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

PENDING = 'pending'
COMPLETED = 'completed'


class TodoParams(BaseModel):

    action: str = Field(
        ...,
        description="Action: 'add', 'complete', 'list', 'clear'"
    )

    id: str | None = Field(
        None,
        description="A Todo ID (required for the 'complete' action)",
    )

    content: str | None = Field(
        None,
        description="The content for the 'add' action",
    )


class TodoTool(Tool):
    name = 'todo'
    description = 'Manage a task list for the current session, use this to track progress on more complex and multi-step tasks that can get resourse intensive.'
    kind = ToolKind.MEMORY
    schema = TodoParams

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._todos: dict[str, str] = {}
        self._status: dict[str, str] = {}

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return False

    def _snapshot(self) -> dict[str, Any]:
        todos = [
            {'id': todo_id, 'content': content, 'status': self._status[todo_id]}
            for todo_id, content in self._todos.items()
        ]
        return {
            'todos': todos,
            'completed': sum(1 for todo in todos if todo['status'] == COMPLETED),
            'total': len(todos),
        }

    def _listing(self) -> str:
        if not self._todos:
            return "No todos."

        snapshot = self._snapshot()
        lines = [f"Todos ({snapshot['completed']}/{snapshot['total']} completed):"]

        for todo in snapshot['todos']:
            marker = 'x' if todo['status'] == COMPLETED else ' '
            lines.append(f"  [{marker}] [{todo['id']}] {todo['content']}")

        return "\n".join(lines)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:

        params = TodoParams(**invocation.params)

        try:
            action = params.action.lower()

            if action == 'add':
                if not params.content:
                    return ToolResult.error_result(
                        "Content is required for the 'add' action."
                    )

                todo_id = str(uuid.uuid4())[:8]

                self._todos[todo_id] = params.content
                self._status[todo_id] = PENDING

                return ToolResult.success_result(
                    f"Added todo [{todo_id}]: {params.content}\n\n{self._listing()}",
                    metadata=self._snapshot(),
                )

            elif action == 'complete':
                if not params.id:
                    return ToolResult.error_result(
                        "An id is required for the 'complete' action."
                    )
                if params.id not in self._todos:
                    return ToolResult.error_result(
                        f"Todo not found: {params.id}"
                    )

                self._status[params.id] = COMPLETED
                content = self._todos[params.id]

                return ToolResult.success_result(
                    f"Completed todo [{params.id}]: {content}\n\n{self._listing()}",
                    metadata=self._snapshot(),
                )

            elif action == 'list':
                return ToolResult.success_result(
                    self._listing(),
                    metadata=self._snapshot(),
                )

            elif action == 'clear':
                count = len(self._todos)

                self._todos.clear()
                self._status.clear()

                return ToolResult.success_result(
                    f"Cleared {count} todo(s).",
                    metadata=self._snapshot(),
                )

            else:
                return ToolResult.error_result(
                    f"Unknown action: {params.action}"
                )

        except Exception as e:

            return ToolResult.error_result(
                f"Unknown error: {e}"
            )
