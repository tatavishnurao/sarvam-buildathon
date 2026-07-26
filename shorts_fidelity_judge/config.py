from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def load_repository_env(path: Path | None = None) -> bool:
    """Load a local environment file without overriding shell variables."""
    dotenv_path = path if path is not None else REPOSITORY_ROOT / ".env"
    if not dotenv_path.is_file():
        return False
    return bool(load_dotenv(dotenv_path=dotenv_path, override=False, verbose=False))
