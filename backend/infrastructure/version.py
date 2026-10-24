"""The running version, read from the ``VERSION`` file at the project root."""

from functools import cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@cache
def app_version() -> str:
    """Return the version every other file is generated from."""
    return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
