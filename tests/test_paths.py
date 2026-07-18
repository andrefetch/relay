"""Tests for utils/paths.py: path resolution, display, binary detection, mkdir."""

from pathlib import Path

import pytest

from utils.paths import (
    display_path_relative_to_cwd,
    ensure_parent_dir,
    is_binary_file,
    resolve_path,
)


def test_resolve_path_relative_to_base():
    base = Path("/tmp/relay_test_base")
    resolved = resolve_path(base, "sub/file.txt")
    assert resolved == (base / "sub/file.txt").resolve()


def test_resolve_path_absolute_inside_base():
    base = Path("/tmp/relay_test_base")
    abs_path = Path("/tmp/relay_test_base/sub/file.txt")
    resolved = resolve_path(base, abs_path)
    assert resolved == abs_path.resolve()


def test_resolve_path_absolute_outside_base_rejected():
    base = Path("/tmp/relay_test_base")
    with pytest.raises(ValueError, match="outside the working directory"):
        resolve_path(base, "/etc/hosts")


def test_resolve_path_rejects_traversal(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    with pytest.raises(ValueError, match="outside the working directory"):
        resolve_path(base, "../escape.txt")


def test_resolve_path_rejects_absolute_outside(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    with pytest.raises(ValueError, match="outside the working directory"):
        resolve_path(base, "/etc/passwd")


def test_resolve_path_accepts_nested_path(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    resolved = resolve_path(base, "a/b/c.txt")
    assert resolved == (base / "a/b/c.txt").resolve()


def test_display_path_relative_to_cwd(tmp_path):
    cwd = tmp_path / "cwd"
    target = cwd / "src" / "main.py"
    assert display_path_relative_to_cwd(str(target), cwd) == str(Path("src/main.py"))


def test_display_path_outside_cwd_returns_absolute(tmp_path):
    cwd = tmp_path / "cwd"
    outside = tmp_path / "other" / "x.py"
    result = display_path_relative_to_cwd(str(outside), cwd)
    assert result == str(outside)


def test_display_path_no_cwd_returns_absolute(tmp_path):
    target = tmp_path / "x.py"
    assert display_path_relative_to_cwd(str(target), None) == str(target)


def test_display_path_invalid_path_returns_original():
    assert display_path_relative_to_cwd("not a real : path", Path("/tmp")) == "not a real : path"


def test_is_binary_file_text(tmp_path):
    f = tmp_path / "text.txt"
    f.write_text("hello world")
    assert is_binary_file(f) is False


def test_is_binary_file_binary(tmp_path):
    f = tmp_path / "bin.bin"
    f.write_bytes(b"\x00\x01\x02\x03")
    assert is_binary_file(f) is True


def test_is_binary_file_missing(tmp_path):
    f = tmp_path / "missing.txt"
    # Missing file should not raise; defaults to False.
    assert is_binary_file(f) is False


def test_ensure_parent_dir_creates_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c.txt"
    result = ensure_parent_dir(target)
    assert result.parent.is_dir()
    assert result == target
