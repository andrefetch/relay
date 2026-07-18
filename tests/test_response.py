"""Tests for client/response.py: usage math and tool-call argument parsing."""

import pytest

from client.response import (
    StreamEvent,
    StreamEventType,
    TextDelta,
    TokenUsage,
    ToolResultMessage,
    parse_tool_call_arguments,
)


def test_token_usage_add():
    a = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3, cached_tokens=4)
    b = TokenUsage(prompt_tokens=5, completion_tokens=6, total_tokens=11, cached_tokens=1)
    c = a + b
    assert c.prompt_tokens == 6
    assert c.completion_tokens == 8
    assert c.total_tokens == 14
    assert c.cached_tokens == 5


import pytest


def test_parse_tool_call_arguments_valid_json():
    assert parse_tool_call_arguments('{"a": 1}') == {"a": 1}


def test_parse_tool_call_arguments_empty():
    assert parse_tool_call_arguments("") == {}


def test_parse_tool_call_arguments_invalid_json_returns_raw():
    result = parse_tool_call_arguments("not json {")
    assert result == {"raw_arguments": "not json {"}


def test_tool_result_message_to_openai_message():
    msg = ToolResultMessage(tool_call_id="call_1", content="ok")
    assert msg.to_openai_message() == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "ok",
    }


def test_stream_event_dataclass_fields():
    ev = StreamEvent(type=StreamEventType.TEXT_DELTA, text_delta=TextDelta("hi"))
    assert ev.type == StreamEventType.TEXT_DELTA
    assert str(ev.text_delta) == "hi"


def test_stream_event_type_values():
    assert StreamEventType.TEXT_DELTA.value == "text_delta"
    assert StreamEventType.TOOL_CALL_COMPLETE.value == "tool_call_complete"
