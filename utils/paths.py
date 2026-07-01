from pathlib import Path

def resolve_path(base: str | Path, path: str | Path):
    path = Path(path)
    
    if path.is_absolute:
        return path.absolute()
    
    return Path(base).resolve() / path