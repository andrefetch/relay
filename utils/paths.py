from pathlib import Path

def resolve_path(base: str | Path, path: str | Path):
    path = Path(path)
    
    if path.is_absolute:
        return path.absolute()
    
    return Path(base).resolve() / path

def is_binary_file(path: str | Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return f"\x00" in chunk
    except (OSError, IOError):
        return False