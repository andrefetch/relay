"""Persistent credential storage for `relay login`.

Keeps the API key out of config.toml (secrets don't belong in a file you
might commit or share) and out of the shell profile. Lives beside the
system config in the user config dir, locked to 0600.
"""
import os
from pathlib import Path

from platformdirs import user_config_dir

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

CREDENTIALS_FILE = "credentials.toml"


def get_credentials_path() -> Path:
    return Path(user_config_dir("relay")) / CREDENTIALS_FILE


def load_credentials() -> dict[str, str]:
    """Return stored credentials, or an empty dict if none are saved."""
    path = get_credentials_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        # A corrupt or unreadable credentials file shouldn't crash startup;
        # treat it as "not logged in" so the env-var path can still work.
        return {}


def _toml_escape(value: str) -> str:
    # Enough to safely round-trip a basic TOML string. API keys are ASCII
    # tokens, but be defensive against quotes/backslashes anyway.
    return value.replace("\\", "\\\\").replace('"', '\\"')


def save_credentials(api_key: str, base_url: str | None = None) -> Path:
    """Write credentials to disk with owner-only permissions."""
    path = get_credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# relay credentials, written by `relay login`. Do not commit.\n"]
    lines.append(f'api_key = "{_toml_escape(api_key)}"\n')
    if base_url:
        lines.append(f'base_url = "{_toml_escape(base_url)}"\n')

    # Create with 0600 up front so the key is never briefly world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.chmod(path, 0o600)
    return path


def clear_credentials() -> bool:
    """Delete stored credentials. Returns True if a file was removed."""
    path = get_credentials_path()
    if path.is_file():
        path.unlink()
        return True
    return False
