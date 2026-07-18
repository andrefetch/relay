"""Tests for ui/format.py: display helpers used by the terminal UI."""

import pytest

from ui.format import (
    diff_glimpse,
    diff_stat,
    extract_read_code,
    format_elapsed,
    guess_language,
    headline,
    ordered_args,
    secondary_args,
    summarise_value,
)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0.25, "250ms"),
        (0.9, "900ms"),
        (5.0, "5.0s"),
        (59.0, "59.0s"),
        (60.0, "1m00s"),
        (125.0, "2m05s"),
    ],
)
def test_format_elapsed(seconds, expected):
    assert format_elapsed(seconds) == expected


@pytest.mark.parametrize(
    "path,lang",
    [
        (None, "text"),
        ("", "text"),
        ("main.py", "python"),
        ("app.js", "javascript"),
        ("style.CSS", "css"),
        ("notes.md", "markdown"),
        ("data.unknown", "text"),
    ],
)
def test_guess_language(path, lang):
    assert guess_language(path) == lang


def test_ordered_args_uses_preferred_order():
    args = {"limit": 10, "path": "a.txt", "offset": 0}
    ordered = ordered_args("read", args)
    keys = [k for k, _ in ordered]
    assert keys == ["path", "offset", "limit"]


def test_ordered_args_appends_unknown_sorted():
    args = {"zzz": 1, "path": "x", "aaa": 2}
    ordered = ordered_args("read", args)
    keys = [k for k, _ in ordered]
    assert keys[:1] == ["path"]
    assert keys[1:] == ["aaa", "zzz"]


def test_summarise_value_bulky_keys_shows_lines_and_bytes():
    out = summarise_value("content", "line1\nline2\nline3")
    assert "lines" in out
    assert "bytes" in out


def test_summarise_value_bool_returns_string():
    assert summarise_value("x", True) == "True"


def test_summarise_value_plain():
    assert summarise_value("path", "/tmp/x") == "/tmp/x"


def test_headline_picks_first_matching_key():
    args = {"command": "ls -la", "path": "a"}
    # HEADLINE_KEYS checks "path" before "command".
    assert headline(args) == ("path", "a")


def test_headline_falls_through_to_command():
    args = {"command": "ls -la"}
    assert headline(args) == ("command", "ls -la")


def test_headline_truncates_long_value():
    args = {"command": "x" * 200}
    key, value = headline(args)
    assert key == "command"
    assert len(value) <= 64
    assert value.endswith("…")


def test_headline_returns_none_when_no_match():
    assert headline({"offset": 1, "limit": 2}) is None


def test_secondary_args_excludes_headline_and_dot_cwd():
    args = {"path": "a", "cwd": ".", "limit": 5}
    result = secondary_args(args, "path")
    assert "path" not in result
    assert "cwd" not in result
    assert result == {"limit": 5}


def test_extract_read_code_parses_body():
    text = "Showing lines 1-3 of 3\n\n1|hello\n2|world\n3|end"
    start, code = extract_read_code(text)
    assert start == 1
    assert code == "hello\nworld\nend"


def test_extract_read_code_without_header():
    text = "10|alpha\n11|beta"
    start, code = extract_read_code(text)
    assert start == 10
    assert code == "alpha\nbeta"


def test_extract_read_code_invalid_returns_none():
    assert extract_read_code("not a code block") is None


def test_diff_glimpse_returns_added_lines():
    diff = "@@ -1,2 +1,3 @@\n-old\n+added1\n+added2\n context"
    glimpse = diff_glimpse(diff, max_lines=2)
    assert "added1" in glimpse
    assert "added2" in glimpse


def test_diff_glimpse_falls_back_to_removed():
    diff = "@@ -1,2 +1,1 @@\n-removed\n context"
    glimpse = diff_glimpse(diff)
    assert "removed" in glimpse


def test_diff_glimpse_empty_for_no_changes():
    assert diff_glimpse(" context only\n more context") == ""


def test_diff_stat_counts_changes():
    diff = "@@ -1,1 +1,2 @@\n-old\n+new1\n+new2\n"
    assert diff_stat(diff) == "+2 -1"
