"""Tests for prompts/system.py: system prompt assembly."""

from unittest import mock

import pytest

from config.config import Config
from prompts.system import (
    create_loop_breaker_prompt,
    get_compression_prompt,
    get_system_prompt,
)
from tools.base import Tool, ToolKind, ToolResult


@pytest.fixture
def config(tmp_path):
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        return Config(cwd=tmp_path)


def test_get_system_prompt_includes_core_sections(config):
    prompt = get_system_prompt(config)
    assert "# Identity" in prompt
    assert "# Security Guidelines" in prompt
    assert "# Operational Guidelines" in prompt
    assert "# AGENTS.md Specification" in prompt


def test_get_system_prompt_includes_environment(config):
    prompt = get_system_prompt(config)
    assert "Environment" in prompt
    assert str(config.cwd) in prompt


def test_get_system_prompt_includes_developer_instructions(config):
    config.developer_instructions = "Use black for formatting."
    prompt = get_system_prompt(config)
    assert "# Project Instructions" in prompt
    assert "Use black for formatting." in prompt


def test_get_system_prompt_includes_user_instructions(config):
    config.user_instructions = "Be terse."
    prompt = get_system_prompt(config)
    assert "# User Instructions" in prompt
    assert "Be terse." in prompt


def test_get_system_prompt_includes_user_memory(config):
    prompt = get_system_prompt(config, user_memory="User likes Go.")
    assert "# Remembered Context" in prompt
    assert "User likes Go." in prompt


def test_get_system_prompt_tool_guidelines_with_tools(config):
    from tools.base import Tool, ToolKind

    class _T(Tool):
        name = "thing"
        description = "does a thing"
        kind = ToolKind.READ
        schema = {}

        async def execute(self, invocation):
            return ToolResult.success_result("ok")

    prompt = get_system_prompt(config, tools=[_T(config)])
    assert "# Tool Usage Guidelines" in prompt
    assert "thing" in prompt


def test_get_compression_prompt_structure():
    prompt = get_compression_prompt()
    for section in [
        "ORIGINAL GOAL",
        "COMPLETED ACTIONS",
        "CURRENT STATE",
        "REMAINING TASKS",
        "NEXT STEP",
        "KEY CONTEXT",
    ]:
        assert section in prompt


def test_create_loop_breaker_prompt_includes_description():
    prompt = create_loop_breaker_prompt("repeating the same edit")
    assert "repeating the same edit" in prompt
    assert "Loop Detected" in prompt
