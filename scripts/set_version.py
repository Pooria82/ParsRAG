"""Write the version in ``VERSION`` to every file that repeats it.

Usage: ``python scripts/set_version.py 1.2.0`` (or without an argument to
copy the current ``VERSION`` everywhere). The backend and the frontend build
read ``VERSION`` directly; these files keep a copy for their own tools.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _replace(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"{path.name}: version line not found")
    path.write_text(updated, encoding="utf-8", newline="\n")


def set_version(version: str, released: date | None = None) -> None:
    """Write ``version`` to ``VERSION`` and the files that copy it."""
    if not _SEMVER.match(version):
        raise SystemExit(f"{version!r} is not MAJOR.MINOR.PATCH")
    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8", newline="\n")
    _replace(ROOT / "pyproject.toml", r'^version = "[^"]+"$', f'version = "{version}"')
    _replace(ROOT / "CITATION.cff", r"^version: .+$", f"version: {version}")
    if released:
        _replace(
            ROOT / "CITATION.cff",
            r"^date-released: .+$",
            f"date-released: '{released.isoformat()}'",
        )
    # package.json keeps its hand formatting: only its own "version" changes.
    _replace(
        ROOT / "frontend/package.json",
        r'^  "version": "[^"]+",$',
        f'  "version": "{version}",',
    )
    lock_path = ROOT / "frontend/package-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["version"] = version
    lock["packages"][""]["version"] = version
    lock_path.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    target = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    )
    set_version(target)
    print(f"Version {target}")
