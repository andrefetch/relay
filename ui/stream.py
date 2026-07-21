from __future__ import annotations

from agent.agent import Agent
from agent.events import AgentEventType
from ui.renderer import TUI, random_thinking_text


def _tool_kind(agent: Agent, tool_name: str) -> str | None:
    tool = agent.session.tool_registry.get(tool_name)
    return tool.kind.value if tool else None


async def stream_turn(tui: TUI, agent: Agent, message: str) -> str | None:
    """Render one agent turn onto `tui`, returning the final assistant text.

    Shared by the one-shot CLI and the interactive REPL so both front-ends
    stay identical in what they show. Returns None if the turn errored.
    """
    final_response: str | None = None
    streaming = False
    failed = False
    label = random_thinking_text()

    try:
        async for event in agent.run(message):
            if event.type == AgentEventType.AGENT_START:
                tui.start_thinking(label)

            elif event.type == AgentEventType.USAGE:
                tui.update_turn_usage(event.data.get("usage"))

            elif event.type == AgentEventType.TEXT_DELTA:
                if not streaming:
                    tui.begin_assistant()
                    streaming = True
                tui.stream_assistant_delta(event.data.get("content", ""))

            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                if streaming:
                    tui.end_assistant()
                    streaming = False

            elif event.type == AgentEventType.TOOL_CALL_START:
                name = event.data.get("name", "unknown")
                tui.tool_call_start(
                    event.data.get("call_id", ""),
                    name,
                    _tool_kind(agent, name),
                    event.data.get("arguments", {}),
                )

            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                name = event.data.get("name", "unknown")
                tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    name,
                    _tool_kind(agent, name),
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("truncated", False),
                    event.data.get("diff"),
                    event.data.get("exit_code"),
                )
                tui.start_thinking(label)

            elif event.type == AgentEventType.AGENT_END:
                tui.stop_thinking()
                tui.render_usage(event.data.get("usage"))

            elif event.type == AgentEventType.AGENT_ERROR:
                tui.stop_thinking()
                tui.console.print(f"[error]{event.data.get('error')}[/error]")
                failed = True
                break
    finally:
        tui.stop_thinking()
        if streaming:
            tui.end_assistant()

    return None if failed else final_response
