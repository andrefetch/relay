"""Tests for config/loader.py: merge logic and config discovery helpers."""

from pathlib import Path
from unittest import mock

import pytest

from config.loader import _merge_dicts, _get_project_config, load_config


def test_merge_dicts_simple_override():
    base = {"a": 1, "b": 2}
    override = {"b": 3, "c": 4}
    assert _merge_dicts(base, override) == {"a": 1, "b": 3, "c": 4}


def test_merge_dicts_nested_merge():
    base = {"model": {"name": "x", "temperature": 1}, "max_turns": 50}
    override = {"model": {"temperature": 0.5}}
    merged = _merge_dicts(base, override)
    assert merged["model"] == {"name": "x", "temperature": 0.5}
    assert merged["max_turns"] == 50


def test_merge_dicts_non_dict_override_replaces():
    base = {"model": {"name": "x"}}
    override = {"model": 5}
    assert _merge_dicts(base, override) == {"model": 5}


def test_merge_dicts_does_not_mutate_base():
    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    _merge_dicts(base, override)
    assert base == {"a": {"b": 1}}


def test_get_project_config_returns_none_without_relay_dir(tmp_path):
    assert _get_project_config(tmp_path) is None


def test_get_project_config_finds_config(tmp_path):
    relay_dir = tmp_path / ".relay"
    relay_dir.mkdir()
    (relay_dir / "config.toml").write_text('model = "x"')
    found = _get_project_config(tmp_path)
    assert found == relay_dir / "config.toml"


def test_get_project_config_relay_dir_without_config(tmp_path):
    relay_dir = tmp_path / ".relay"
    relay_dir.mkdir()
    assert _get_project_config(tmp_path) is None


def test_load_config_defaults_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        cfg = load_config(tmp_path)
    assert cfg.cwd == tmp_path


def test_load_config_merges_project_config(tmp_path, monkeypatch):
    relay_dir = tmp_path / ".relay"
    relay_dir.mkdir()
    (relay_dir / "config.toml").write_text('max_turns = 7\n')
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        cfg = load_config(tmp_path)
    assert cfg.max_turns == 7


def test_load_config_reads_agent_md(tmp_path, monkeypatch):
    (tmp_path / "AGENTS.md").write_text("# Project rules\nBe nice.\n")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        cfg = load_config(tmp_path)
    assert cfg.developer_instructions is not None
    assert "Be nice." in cfg.developer_instructions


def test_load_config_invalid_toml_raises(tmp_path, monkeypatch):
    relay_dir = tmp_path / ".relay"
    relay_dir.mkdir()
    (relay_dir / "config.toml").write_text("this is == not valid toml [[[")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    with mock.patch("config.config.load_credentials", return_value={"api_key": "k"}):
        with pytest.raises(Exception):
            load_config(tmp_path)
