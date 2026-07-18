"""Tests for utils/text.py: token counting and truncation helpers."""

import pytest

from utils.text import (
    count_tokens,
    estimate_tokens,
    get_tokenizer,
    truncate_text,
)


def test_get_tokenizer_known_model():
    enc = get_tokenizer("gpt-4o")
    assert enc is not None


def test_get_tokenizer_unknown_model_falls_back_to_cl100k():
    enc = get_tokenizer("definitely-not-a-real-model")
    assert enc is not None
    # cl100k_base is the fallback encoding.
    assert enc.name == "cl100k_base"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 1),          # estimate_tokens floors at 1
        ("abcd", 1),      # 4 chars -> 1 token
        ("abcde", 1),     # 5 chars -> 1.25 -> floors to 1
        ("a" * 40, 10),   # 40 chars -> 10 tokens
    ],
)
def test_estimate_tokens(text, expected):
    assert estimate_tokens(text) == expected


def test_count_tokens_empty_string():
    # With a real tokenizer, empty input encodes to zero tokens.
    assert count_tokens("") == 0


def test_count_tokens_deterministic():
    text = "The quick brown fox jumps over the lazy dog"
    assert count_tokens(text) == count_tokens(text)


def test_count_tokens_longer_than_short():
    assert count_tokens("hello world") < count_tokens("hello world " * 50)


def test_truncate_text_noop_when_within_budget():
    text = "short text"
    assert truncate_text(text, "gpt-4o", max_tokens=1000) == text


def test_truncate_text_returns_suffix_when_target_zero():
    long_text = "x" * 1000
    result = truncate_text(long_text, "gpt-4o", max_tokens=2, suffix="TRUNC")
    assert result == "TRUNC"


def test_truncate_text_by_lines_preserves_line_structure():
    text = "\n".join(f"line {i}" for i in range(50))
    result = truncate_text(text, "gpt-4o", max_tokens=10, preserve_lines=True)
    assert result.endswith("...[truncated]")
    # The truncation suffix is appended after a newline.
    assert "\n...[truncated]" in result or result == "...[truncated]"
    assert result.startswith("line 0")


def test_truncate_text_by_chars():
    text = "abcdefghij" * 20
    result = truncate_text(text, "gpt-4o", max_tokens=5, preserve_lines=False)
    # With a tiny budget the suffix alone may exceed the limit; the code
    # returns the stripped suffix rather than raising.
    assert result.endswith("...[truncated]")
    assert "abcdefghij" in result or result == "...[truncated]"


def test_truncate_text_result_under_max_tokens():
    text = "word " * 500
    result = truncate_text(text, "gpt-4o", max_tokens=20)
    assert count_tokens(result, "gpt-4o") <= 20
