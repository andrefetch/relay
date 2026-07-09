from pathlib import Path


def resolve_path(base: str | Path, path: str | Path) -> Path:
    base_path = Path(base).resolve()
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (base_path / candidate).resolve()
    try:
        resolved.relative_to(base_path)
    except ValueError as exc:
        raise ValueError(f"Path is outside the working directory: {path}") from exc
    return resolved

def display_path_relative_to_cwd(path: str, cwd: Path | None) -> str:
    try:
        p = Path(path)
    except Exception:
        return path
    
    if cwd:
        try:
            return str(p.relative_to(cwd))
        except ValueError:
            pass
    
    return str(p)

def is_binary_file(path: str | Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except (OSError, IOError):
        return False
    
def ensure_parent_dir(path: str | Path) -> Path:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    return path