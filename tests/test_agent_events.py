"""Tests for agent/events.py: AgentEvent factory methods."""

import pytest

from agent.events import AgentEvent, AgentEventType
from client.response import TokenUsage
from tools.base import FileDiff, ToolKind, ToolResult


def test_agent_start():
    ev = AgentEvent.agent_start("go")
    assert ev.type == AgentEventType.AGENT_START
    assert ev.data["message"] == "go"


def test_agent_end_with_usage():
    usage = TokenUsage(total_tokens=5)
    ev = AgentEvent.agent_end(response="done", usage=usage)
    assert ev.type == AgentEventType.AGENT_END
    assert ev.data["response"] == "done"
    assert ev.data["usage"]["total_tokens"] == 5


def test_agent_end_without_usage():
    ev = AgentEvent.agent_end()
    assert ev.data["usage"] is None
    assert ev.data["response"] is None


def test_usage_event():
    usage = TokenUsage(prompt_tokens=1)
    ev = AgentEvent.usage(usage)
    assert ev.type == AgentEventType.USAGE
    assert ev.data["usage"]["prompt_tokens"] == 1


def test_agent_error_event():
    ev = AgentEvent.agent_error("boom", details={"code": 1})
    assert ev.type == AgentEventType.AGENT_ERROR
    assert ev.data["error"] == "boom"
    assert ev.data["details"] == {"code": 1}


def test_text_delta_event():
    ev = AgentEvent.text_delta("hi")
    assert ev.type == AgentEventType.TEXT_DELTA
    assert ev.data["content"] == "hi"


def test_text_complete_event():
    ev = AgentEvent.text_complete("final")
    assert ev.type == AgentEventType.TEXT_COMPLETE
    assert ev.data["content"] == "final"


def test_tool_call_start_event():
    ev = AgentEvent.tool_call_start("c1", "read", {"path": "x"})
    assert ev.data["call_id"] == "c1"
    assert ev.data["name"] == "read"
    assert ev.data["arguments"] == {"path": "x"}


def test_tool_call_complete_event_with_diff():
    from pathlib import Path

    result = ToolResult.success_result(
        "ok",
        diff=FileDiff(path=Path("a"), old_content="x\n", new_content="y\n"),
        exit_code=0,
    )
    ev = AgentEvent.tool_call_complete("c1", "edit", result)
    assert ev.data["success"] is True
    assert ev.data["output"] == "ok"
    assert ev.data["exit_code"] == 0
    assert "a" in ev.data["diff"]


def test_tool_call_complete_event_error():
    result = ToolResult.error_result("nope")
    ev = AgentEvent.tool_call_complete("c1", "read", result)
    assert ev.data["success"] is False
    assert ev.data["error"] == "nope"
    assert ev.data["diff"] is None
