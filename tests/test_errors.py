"""Tests for utils/errors.py: AgentError and ConfigError."""

import pytest

from utils.errors import AgentError, ConfigError


def test_agent_error_basic_message():
    err = AgentError("boom")
    assert err.message == "boom"
    assert str(err) == "boom"


def test_agent_error_with_details():
    err = AgentError("boom", details={"code": 42})
    assert err.details == {"code": 42}
    assert "code=42" in str(err)


def test_agent_error_with_cause():
    cause = ValueError("root cause")
    err = AgentError("boom", cause=cause)
    assert err.cause is cause
    assert "root cause" in str(err)


def test_agent_error_to_dict():
    err = AgentError("boom", details={"k": "v"}, cause=RuntimeError("x"))
    d = err.to_dict()
    assert d["type"] == "AgentError"
    assert d["message"] == "boom"
    assert d["details"] == {"k": "v"}
    assert d["cause"] == "x"


def test_config_error_stores_config_fields():
    err = ConfigError("bad", config_key="model", config_file="config.toml")
    assert err.config_key == "model"
    assert err.config_file == "config.toml"
    assert err.details["config_key"] == "model"
    assert err.details["config_file"] == "config.toml"
    assert isinstance(err, AgentError)


def test_config_error_str_includes_details():
    err = ConfigError("bad", config_key="temperature")
    assert "temperature" in str(err)


def test_config_error_is_raiseable():
    with pytest.raises(ConfigError):
        raise ConfigError("nope")
