from pathlib import Path
from config.config import Config
from platformdirs import user_config_dir
import tomli
import logging
from typing import Any

from utils.errors import ConfigError

logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.toml'
AGENT_MD_FILE = 'AGENT.MD'

def get_config_dir() -> Path:
    return Path(user_config_dir('relay'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE

def _parse_toml(path: Path):
    try:
        with open(path, 'rb') as f:
            return tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ConfigError("Invalid TOML in {path}: {e}", config_file=str(path)) from e
    except (OSError, IOError) as e:
        raise ConfigError("Failed to read config file: {path}: {e}", config_file=str(path)) from e
    
def _get_project_config(cwd: Path) -> Path:

    current = cwd.resolve()
    agent_dir = current / '.relay'

    if agent_dir.is_dir():
        config_file = agent_dir / CONFIG_FILE
        if config_file.is_file():
            return config_file
    
    return None

def _get_agent_md(cwd: Path) -> Path:

    current = cwd.resolve()
    
    if current.is_dir():
        agent_md_file = current / AGENT_MD_FILE
        if agent_md_file.is_file():
            content = agent_md_file.read_bytes(encoding='utf-8')
            return content
    
    return None

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
            _parse_toml(system_path)
        except ConfigError:
            logger.warning(f"Skipping invalid system config: {system_path}") 
    
    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_config_dict = _parse_toml(project_path)
            config_dict = _merge_dicts(config_dict, project_config_dict)
        except:
            logger.warning(f"Skipping invalid system config: {system_path}") 
        
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
