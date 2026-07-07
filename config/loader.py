from pathlib import Path
from config.config import Config
from platformdirs import user_config_dir
from tomli import TOMLDecodeError

CONFIG_FILE = 'config.toml'

def get_config_dir() -> Path:
    return Path(user_config_dir('relay'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE

def _parse_toml(path: Path):
    try:
        pass
    except TOMLDecodeError as e:
        print(e)

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()

    system_path = get_system_config_path()

    if system_path.is_file():
