from pathlib import Path
from typing import Any, Tuple
import re

# Shown beside the tool name instead of on its own row; first match wins.
HEADLINE_KEYS = ("path", "command", "pattern", "url", "query")

# Summarised as a line/byte count rather than dumped verbatim.
BULKY_KEYS = frozenset({"content", "old_string", "new_string"})

# Argument display order per tool; anything unlisted follows, sorted.
ARG_ORDER = {
    "read_file": ["path", "offset", "limit"],
    "write_file": ["path", "create_directories", "content"],
    "edit": ["path", "replace_all", "old_string", "new_string"],
    "shell": ['command', 'timeout', 'cwd'],
    "list_dir": ['path', 'inclide_hidden'],
}

_EXTENSION_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".css": "css",
    ".html": "html",
    ".xml": "xml",
    ".sql": "sql",
}

HEADLINE_MAX_WIDTH = 64


def format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s"


def guess_language(path: str | None) -> str:
    if not path:
        return "text"
    return _EXTENSION_LANGUAGES.get(Path(path).suffix.lower(), "text")


def ordered_args(tool_name: str, args: dict[str, Any]) -> list[Tuple[str, Any]]:
    preferred = ARG_ORDER.get(tool_name, [])
    ordered: list[Tuple[str, Any]] = []
    seen: set[str] = set()

    for key in preferred:
        if key in args:
            ordered.append((key, args[key]))
            seen.add(key)

    # sorted() so a dict ordering change can't reshuffle the display
    ordered.extend((key, args[key]) for key in sorted(args.keys() - seen))
    return ordered


def summarise_value(key: str, value: Any) -> str:
    """Collapse bulky string args to a line/byte count."""
    if isinstance(value, str) and key in BULKY_KEYS:
        line_count = len(value.splitlines())
        byte_count = len(value.encode("utf-8", errors="replace"))
        return f"{line_count} lines ┈ {byte_count} bytes"
    
    if isinstance(value, bool):
        value = str(value)
        
    return str(value)


def headline(args: dict[str, Any]) -> tuple[str, str] | None:
    """The one argument worth showing beside the tool name, as (key, text)."""
    for key in HEADLINE_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            first_line = value.strip().splitlines()[0]
            if len(first_line) > HEADLINE_MAX_WIDTH:
                first_line = f"{first_line[:HEADLINE_MAX_WIDTH - 1]}…"
            return key, first_line
    return None


def secondary_args(args: dict[str, Any], headline_key: str | None) -> dict[str, Any]:
    """Args worth showing under the header, minus the one already shown inline."""
    return {
        key: value
        for key, value in args.items()
        if key != headline_key and not (key == "cwd" and value == ".")
    }


def extract_read_file_code(text: str) -> tuple[int, str] | None:
    """Strip the `N|` line-number gutter from read_file output.

    Returns (start_line, code) or None if the text isn't in that shape.
    """
    body = text
    header_match = re.match(
        r"^Showing lines (\d+)-(\d+) of (\d+)[^\n]*\n\n", text, re.IGNORECASE
    )
    if header_match:
        body = text[header_match.end():]

    code_lines: list[str] = []
    start_line: int | None = None

    for line in body.splitlines():
        match = re.match(r"^\s*(\d+)\|(.*)$", line)
        if not match:
            return None
        if start_line is None:
            start_line = int(match.group(1))
        code_lines.append(match.group(2))

    if start_line is None:
        return None

    return start_line, "\n".join(code_lines)


def diff_stat(diff: str) -> str:
    """`+12 -4` summary for a unified diff, ignoring the ---/+++ file headers."""
    added = removed = 0
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"+{added} -{removed}"
