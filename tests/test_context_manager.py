"""Tests for context/manager.py: message history building and serialization."""

from pathlib import Path
from unittest import mock

import pytest

from context.manager import ContextManager, EMPTY_TOOL_OUTPUT
from config.config import Config


@pytest.fixture
def manager(tmp_path):
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        cfg = Config(cwd=tmp_path)
    return ContextManager(config=cfg, user_memory=None)


def test_system_prompt_included(manager):
    messages = manager.get_messages()
    assert messages[0]["role"] == "system"
    assert manager._system_prompt in messages[0]["content"]


def test_add_user_message(manager):
    manager.add_user_message("hello")
    messages = manager.get_messages()
    user = [m for m in messages if m["role"] == "user"]
    assert user and user[0]["content"] == "hello"


def test_add_assistant_message_with_tool_calls(manager):
    manager.add_assistant_message(
        "thinking", tool_calls=[{"id": "1", "type": "function", "function": {}}]
    )
    messages = manager.get_messages()
    asst = [m for m in messages if m["role"] == "assistant"][-1]
    assert asst["tool_calls"]
    assert asst["content"] == "thinking"


def test_add_assistant_message_empty_content_still_serializes(manager):
    manager.add_assistant_message("")
    messages = manager.get_messages()
    asst = [m for m in messages if m["role"] == "assistant"][-1]
    # Empty content is omitted from serialization for assistant messages.
    assert "content" not in asst or asst["content"] == ""


def test_add_tool_result_empty_content_gets_placeholder(manager):
    manager.add_tool_result("call_1", "")
    messages = manager.get_messages()
    tool_msg = [m for m in messages if m["role"] == "tool"][-1]
    assert tool_msg["content"] == EMPTY_TOOL_OUTPUT
    assert tool_msg["tool_call_id"] == "call_1"


def test_add_tool_result_with_content(manager):
    manager.add_tool_result("call_2", "real output")
    messages = manager.get_messages()
    tool_msg = [m for m in messages if m["role"] == "tool"][-1]
    assert tool_msg["content"] == "real output"


def test_clear_removes_messages_but_keeps_system(manager):
    manager.add_user_message("x")
    manager.clear()
    messages = manager.get_messages()
    assert len(messages) == 1
    assert messages[0]["role"] == "system"


def test_order_of_messages(manager):
    manager.add_user_message("u")
    manager.add_assistant_message("a")
    manager.add_tool_result("c", "t")
    roles = [m["role"] for m in manager.get_messages()]
    assert roles == ["system", "user", "assistant", "tool"]
