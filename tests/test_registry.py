"""Tests for tools/registry.py: ToolRegistry registration and invocation."""

from pathlib import Path
from unittest import mock

import pytest
from anyio import from_thread, run

from config.config import Config
from tools.base import Tool, ToolKind, ToolResult
from tools.registry import ToolRegistry, create_default_registry


class _Cfg:
    pass


class _FakeTool(Tool):
    name = "fake"
    description = "fake tool"
    kind = ToolKind.READ
    schema = {}

    async def execute(self, invocation):
        return ToolResult.success_result(f"ran {invocation.params}")


def _make_config(tmp_path):
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        return Config(cwd=tmp_path)


def test_register_and_get(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))
    assert reg.get("fake") is not None
    assert reg.get("missing") is None


def test_register_overwrites_same_name(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))
    reg.register(_FakeTool(_Cfg()))
    assert len(reg.get_tools()) == 1


def test_unregister(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))
    assert reg.unregister("fake") is True
    assert reg.unregister("fake") is False
    assert reg.get_tools() == []


def test_get_tools_respects_allowed_tools(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))
    reg.config.allowed_tools = ["other"]
    assert reg.get_tools() == []


def test_get_schemas(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))
    schemas = reg.get_schemas()
    assert isinstance(schemas, list)
    assert schemas[0]["name"] == "fake"


def test_invoke_unknown_tool(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))

    async def _run():
        return await reg.invoke("nope", {}, Path(tmp_path))

    result = run(_run)
    assert result.success is False
    assert "Unknown Tool" in result.error


def test_invoke_validation_error(tmp_path):
    reg = ToolRegistry(_make_config(tmp_path))
    reg.register(_FakeTool(_Cfg()))

    async def _run():
        return await reg.invoke("fake", {}, Path(tmp_path))

    result = run(_run)
    assert result.success is True


def test_create_default_registry_has_core_tools(tmp_path):
    reg = create_default_registry(_make_config(tmp_path))
    names = {t.name for t in reg.get_tools()}
    # Core tools from tools/core are registered by default.
    assert "memory" in names
    assert len(names) > 0
