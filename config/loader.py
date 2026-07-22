from pathlib import Path
from config.config import Config
from platformdirs import user_config_dir
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import logging
from typing import Any

from utils.errors import ConfigError

logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.toml'
AGENT_MD_FILE = 'AGENTS.md'

def get_config_dir() -> Path:
    return Path(user_config_dir('relay'))

def get_data_dir() -> Path:
    return Path(user_config_dir('relay'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE

def _parse_toml(path: Path):
    try:
        with open(path, 'rb') as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}", config_file=str(path)) from e
    except (OSError, IOError) as e:
        raise ConfigError(f"Failed to read config file: {path}: {e}", config_file=str(path)) from e
    
def _get_project_config(cwd: Path) -> Path:

    current = cwd.resolve()
    agent_dir = current / '.relay'

    if agent_dir.is_dir():
        config_file = agent_dir / CONFIG_FILE
        if config_file.is_file():
            return config_file
    
    return None

def _get_agent_md(cwd: Path) -> str | None:

    current = cwd.resolve()

    search_dirs: list[Path] = []
    for directory in [current, *current.parents]:
        search_dirs.append(directory)
        if (directory / '.git').exists():
            break

    sections: list[str] = []
    for directory in reversed(search_dirs):
        agent_md_file = directory / AGENT_MD_FILE
        if not agent_md_file.is_file():
            continue
        try:
            content = agent_md_file.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            logger.warning(f"Failed to read {agent_md_file}", exc_info=True)
            continue
        if content.strip():
            sections.append(f"## From {agent_md_file}\n\n{content.strip()}")

    if not sections:
        return None

    return "\n\n".join(sections)

def _merge_dicts(
        base: dict[str, Any], 
        override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
        
    return result

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()

    system_path = get_system_config_path()

    config_dict: dict[str, Any] = {}

    if system_path.is_file():
        try:
            config_dict = _merge_dicts(config_dict, _parse_toml(system_path))
        except ConfigError:
            logger.exception(f"Invalid system config: {system_path}")
            raise

    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_config_dict = _parse_toml(project_path)
            config_dict = _merge_dicts(config_dict, project_config_dict)
        except ConfigError:
            logger.exception(f"Invalid project config: {project_path}")
            raise

    if "cwd" not in config_dict:
        config_dict["cwd"] = cwd

    if "developer_instructions" not in config_dict:
        agent_md_content = _get_agent_md(cwd)

        if agent_md_content:
            config_dict['developer_instructions'] = agent_md_content

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ConfigError(f"Invalid config: {e}") from e

    return config
