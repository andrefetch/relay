"""Tests for config/credentials.py: load/save/clear of stored credentials.

These tests isolate the credentials file by monkeypatching get_credentials_path,
so they never touch the real user config dir.
"""

import importlib

from config import credentials as credentials_mod


def _reload(monkeypatch, path):
    monkeypatch.setattr(credentials_mod, "get_credentials_path", lambda: path)
    return importlib.reload(credentials_mod)


def test_load_credentials_missing_returns_empty(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    assert creds.load_credentials() == {}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    creds.save_credentials("sk-abc", base_url="https://api.example.com")
    loaded = creds.load_credentials()
    assert loaded["api_key"] == "sk-abc"
    assert loaded["base_url"] == "https://api.example.com"


def test_save_credentials_escapes_special_chars(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    creds.save_credentials('key"with\\backslash')
    loaded = creds.load_credentials()
    assert loaded["api_key"] == 'key"with\\backslash'


def test_save_credentials_without_base_url(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    creds.save_credentials("sk-only")
    loaded = creds.load_credentials()
    assert "base_url" not in loaded


def test_clear_credentials_existing(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    creds.save_credentials("sk-abc")
    assert creds.clear_credentials() is True
    assert creds.load_credentials() == {}


def test_clear_credentials_missing(tmp_path, monkeypatch):
    creds = _reload(monkeypatch, tmp_path / "credentials.toml")
    assert creds.clear_credentials() is False


def test_toml_escape_escapes_backslash_and_quote():
    assert credentials_mod._toml_escape('a"b\\c') == 'a\\"b\\\\c'
