import uuid
from typing import Any

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

PENDING = 'pending'
IN_PROGRESS = 'in_progress'
COMPLETED = 'completed'


class TodoParams(BaseModel):

    action: str = Field(
        ...,
        description="Action: 'add', 'start', 'complete', 'list', 'clear'"
    )

    id: str | None = Field(
        None,
        description="A Todo ID (required for the 'start' and 'complete' actions)",
    )

    content: str | None = Field(
        None,
        description="The content for the 'add' action",
    )


class TodoTool(Tool):
    name = 'todo'
    description = (
        'Manage a task list for the current session, use this to track progress on more '
        'complex and multi-step tasks that can get resourse intensive. Mark a todo as '
        "'start' when you begin working on it and 'complete' when it is done; only one "
        'todo can be in progress at a time.'
    )
    kind = ToolKind.MEMORY
    schema = TodoParams

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._todos: dict[str, str] = {}
        self._status: dict[str, str] = {}

    def is_mutating(self, params: dict[str, Any]) -> bool:
        # The list lives in memory for one session and touches nothing on disk,
        # so a confirmation prompt on every add would be pure noise.
        return False

    def _snapshot(self) -> dict[str, Any]:
        """Current list, shaped for the TUI checklist."""
        todos = [
            {'id': todo_id, 'content': content, 'status': self._status[todo_id]}
            for todo_id, content in self._todos.items()
        ]
        return {
            'todos': todos,
            'completed': sum(1 for todo in todos if todo['status'] == COMPLETED),
            'in_progress': sum(1 for todo in todos if todo['status'] == IN_PROGRESS),
            'total': len(todos),
        }

    def _listing(self) -> str:
        """The same list as text, for the model."""
        if not self._todos:
            return "No todos."

        markers = {COMPLETED: 'x', IN_PROGRESS: '~', PENDING: ' '}
        snapshot = self._snapshot()
        lines = [f"Todos ({snapshot['completed']}/{snapshot['total']} completed):"]

        for todo in snapshot['todos']:
            marker = markers[todo['status']]
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

            elif action == 'start':
                if not params.id:
                    return ToolResult.error_result(
                        "An id is required for the 'start' action."
                    )
                if params.id not in self._todos:
                    return ToolResult.error_result(
                        f"Todo not found: {params.id}"
                    )

                # One task in flight at a time: whatever was running goes back to
                # pending rather than leaving two rows both claiming to be active.
                for todo_id, status in self._status.items():
                    if status == IN_PROGRESS:
                        self._status[todo_id] = PENDING

                self._status[params.id] = IN_PROGRESS
                content = self._todos[params.id]

                return ToolResult.success_result(
                    f"Started todo [{params.id}]: {content}\n\n{self._listing()}",
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
