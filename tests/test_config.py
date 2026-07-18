"""Tests for config/config.py: Config model validation and properties."""

from pathlib import Path
from unittest import mock

import pytest

from config.config import Config, MCPServerConfig, ModelConfig, ShellEnvironmentConfig


def test_default_config_values():
    cfg = Config(cwd=Path("/tmp"))
    assert cfg.max_turns == 100
    assert cfg.max_tool_output_tokens == 50_000
    assert cfg.model.temperature == 1
    assert cfg.model.context_window == 256_000


def test_model_config_temperature_bounds():
    with pytest.raises(Exception):
        ModelConfig(temperature=3.0)
    with pytest.raises(Exception):
        ModelConfig(temperature=-1.0)


def test_model_config_temperature_valid():
    assert ModelConfig(temperature=0.5).temperature == 0.5


def test_shell_environment_default_excludes():
    env = ShellEnvironmentConfig()
    assert env.exclude_patterns == ["*KEY*", "*TOKEN*", "*SECRET*"]
    assert env.ignore_default_excludes is False


def test_mcp_server_requires_transport():
    with pytest.raises(ValueError, match="must have either"):
        MCPServerConfig()


def test_mcp_server_cannot_have_both():
    with pytest.raises(ValueError, match="can't have both"):
        MCPServerConfig(command="x", url="http://y")


def test_mcp_server_stdio_valid():
    srv = MCPServerConfig(command="node", args=["server.js"])
    assert srv.enabled is True
    assert srv.startup_timeout == 10


def test_mcp_server_http_valid():
    srv = MCPServerConfig(url="http://localhost:1234")
    assert srv.url == "http://localhost:1234"


def test_model_name_property_roundtrip():
    cfg = Config(cwd=Path("/tmp"))
    cfg.model_name = "gpt-4o-mini"
    assert cfg.model_name == "gpt-4o-mini"
    assert cfg.model.name == "gpt-4o-mini"


def test_temperature_property_roundtrip():
    cfg = Config(cwd=Path("/tmp"))
    cfg.temperature = 0.2
    assert cfg.temperature == 0.2
    assert cfg.model.temperature == 0.2


def test_validate_reports_missing_api_key(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={}):
        cfg = Config(cwd=Path("/tmp"))
        errors = cfg.validate()
    assert any("No API key" in e for e in errors)


def test_validate_reports_missing_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        with mock.patch.object(Path, "exists", return_value=False):
            cfg = Config(cwd=tmp_path / "nope")
            errors = cfg.validate()
    assert any("does not exist" in e for e in errors)


def test_validate_passes_with_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch(
        "config.config.load_credentials", return_value={"api_key": "sk-test"}
    ):
        cfg = Config(cwd=tmp_path)
        assert cfg.validate() == []


def test_api_key_env_wins_over_credentials(monkeypatch):
    monkeypatch.setenv("API_KEY", "env-key")
    with mock.patch(
        "config.config.load_credentials", return_value={"api_key": "file-key"}
    ):
        cfg = Config(cwd=Path("/tmp"))
        assert cfg.api_key == "env-key"


def test_to_dict_serializes_json_compatible():
    cfg = Config(cwd=Path("/tmp"))
    d = cfg.to_dict()
    assert d["max_turns"] == 100
    assert isinstance(d["cwd"], str)
