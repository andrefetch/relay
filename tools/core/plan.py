import uuid
from typing import Any

from config.config import Config
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field

PENDING = 'pending'
COMPLETED = 'completed'


class PlanParams(BaseModel):

    action: str = Field(
        ...,
        description="Action: 'add', 'complete', 'list', 'clear'"
    )

    id: str | None = Field(
        None,
        description="A plan step ID (required for the 'complete' action)",
    )

    content: str | None = Field(
        None,
        description="The content for the 'add' action",
    )


class PlanTool(Tool):
    name = 'plan'
    description = (
        'Manage the plan (a.k.a. todo list) for the current session. Use this to '
        'track progress on complex, multi-step tasks. When the user asks you to '
        'create or update a todo / todos, use this tool. Actions: add, complete, '
        'list, clear.'
    )
    kind = ToolKind.MEMORY
    schema = PlanParams

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._steps: dict[str, str] = {}
        self._status: dict[str, str] = {}

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return False

    def reset(self) -> None:
        """Drop every tracked step so a new turn starts with a clean plan."""
        self._steps.clear()
        self._status.clear()

    def _snapshot(self) -> dict[str, Any]:
        steps = [
            {'id': step_id, 'content': content, 'status': self._status[step_id]}
            for step_id, content in self._steps.items()
        ]
        return {
            'steps': steps,
            'completed': sum(1 for step in steps if step['status'] == COMPLETED),
            'total': len(steps),
        }

    def _listing(self) -> str:
        if not self._steps:
            return "No plan steps."

        snapshot = self._snapshot()
        lines = [f"Plan ({snapshot['completed']}/{snapshot['total']} completed):"]

        for step in snapshot['steps']:
            marker = 'x' if step['status'] == COMPLETED else ' '
            lines.append(f"  [{marker}] [{step['id']}] {step['content']}")

        return "\n".join(lines)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:

        params = PlanParams(**invocation.params)

        try:
            action = params.action.lower()

            if action == 'add':
                if not params.content:
                    return ToolResult.error_result(
                        "Content is required for the 'add' action."
                    )

                step_id = str(uuid.uuid4())[:8]

                self._steps[step_id] = params.content
                self._status[step_id] = PENDING

                return ToolResult.success_result(
                    f"Added step [{step_id}]: {params.content}\n\n{self._listing()}",
                    metadata=self._snapshot(),
                )

            elif action == 'complete':
                if not params.id:
                    return ToolResult.error_result(
                        "An id is required for the 'complete' action."
                    )
                if params.id not in self._steps:
                    return ToolResult.error_result(
                        f"Plan step not found: {params.id}"
                    )

                self._status[params.id] = COMPLETED
                content = self._steps[params.id]

                return ToolResult.success_result(
                    f"Completed step [{params.id}]: {content}\n\n{self._listing()}",
                    metadata=self._snapshot(),
                )

            elif action == 'list':
                return ToolResult.success_result(
                    self._listing(),
                    metadata=self._snapshot(),
                )

            elif action == 'clear':
                count = len(self._steps)

                self._steps.clear()
                self._status.clear()

                return ToolResult.success_result(
                    f"Cleared {count} plan step(s).",
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
