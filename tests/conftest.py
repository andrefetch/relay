"""pytest configuration and shared fixtures for the Relay test suite."""

import sys
from pathlib import Path

import pytest

# Ensure the repository root is importable so that `import config`,
# `import utils`, etc. work regardless of pytest's rootdir.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def make_config():
    """Return a factory that builds a minimal valid Config for unit tests.

    Keeps the API key requirement out of pure unit tests by setting cwd to a
    real directory and bypassing credential lookup via monkeypatching.
    """
    from config.config import Config

    def _factory(cwd=REPO_ROOT, **kwargs):
        cfg = Config(cwd=Path(cwd), **kwargs)
        return cfg

    return _factory
