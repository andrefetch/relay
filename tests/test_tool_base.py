"""Tests for tools/base.py: ToolResult, FileDiff, validation, schema serialization."""

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from tools.base import (
    FileDiff,
    Tool,
    ToolInvocation,
    ToolKind,
    ToolResult,
)


class _Cfg:
    """Minimal stand-in for a Config object passed to Tool.__init__."""


def test_tool_result_success_factory():
    r = ToolResult.success_result("done", exit_code=0)
    assert r.success is True
    assert r.output == "done"
    assert r.error is None
    assert r.exit_code == 0


def test_tool_result_error_factory():
    r = ToolResult.error_result("bad", metadata={"k": 1})
    assert r.success is False
    assert r.error == "bad"
    assert r.metadata == {"k": 1}


def test_to_model_output_success_and_error():
    assert ToolResult.success_result("ok").to_model_output() == "ok"
    r = ToolResult.error_result("oops", output="partial")
    assert "Error: oops" in r.to_model_output()
    assert "partial" in r.to_model_output()


def test_file_diff_create_diff_modification():
    diff = FileDiff(path=Path("a.txt"), old_content="a\n", new_content="b\n")
    text = diff.create_diff()
    assert "a.txt" in text
    assert "-a" in text
    assert "+b" in text
    assert text.startswith("---") or text.startswith("+++") or "diff" not in text


def test_file_diff_create_diff_new_file():
    diff = FileDiff(
        path=Path("new.txt"), old_content="", new_content="x\n", is_new_file=True
    )
    text = diff.create_diff()
    assert "/dev/null" in text


def test_file_diff_create_diff_deletion():
    diff = FileDiff(
        path=Path("gone.txt"), old_content="y\n", new_content="", is_deletion=True
    )
    text = diff.create_diff()
    assert "/dev/null" in text


class _SampleParams(BaseModel):
    name: str = Field(..., description="the name")
    count: int = Field(1, description="how many")


class _SampleTool(Tool):
    name = "sample"
    description = "a sample tool"
    kind = ToolKind.READ
    schema = _SampleParams

    async def execute(self, invocation):
        return ToolResult.success_result("ok")


def _make_tool():
    return _SampleTool(_Cfg())


def test_validate_params_valid():
    tool = _make_tool()
    assert tool.validate_params({"name": "x", "count": 2}) == []


def test_validate_params_invalid():
    tool = _make_tool()
    errors = tool.validate_params({"count": "not-an-int"})
    assert errors  # missing required name + wrong type
    assert any("name" in e for e in errors)


def test_to_openai_schema_pydantic():
    tool = _make_tool()
    schema = tool.to_openai_schema()
    assert schema["name"] == "sample"
    assert schema["description"] == "a sample tool"
    assert "name" in schema["parameters"]["properties"]
    assert "name" in schema["parameters"]["required"]


def test_to_openai_schema_dict_schema():
    class _DictTool(Tool):
        name = "dicttool"
        description = "d"
        kind = ToolKind.READ
        schema = {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }

        async def execute(self, invocation):
            return ToolResult.success_result("ok")

    tool = _DictTool(_Cfg())
    schema = tool.to_openai_schema()
    assert schema["parameters"]["properties"]["q"]["type"] == "string"


def test_is_mutating():
    tool = _make_tool()
    assert tool.is_mutating({}) is False  # READ is not mutating
    tool.kind = ToolKind.WRITE
    assert tool.is_mutating({}) is True
    tool.kind = ToolKind.SHELL
    assert tool.is_mutating({}) is True


def test_toolinvocation_dataclass():
    inv = ToolInvocation(params={"a": 1}, cwd=Path("/tmp"))
    assert inv.params == {"a": 1}
