"""One version, written in ``VERSION``, and every copy in step with it."""

import json
import re
import tomllib
from pathlib import Path

from backend.infrastructure.version import PROJECT_ROOT, app_version
from backend.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_every_copy_of_the_version_matches_the_version_file() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert PROJECT_ROOT == ROOT
    assert app_version() == version
    assert app.version == version
    assert (
        tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        == version
    )
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    assert (
        package["version"]
        == lock["version"]
        == lock["packages"][""]["version"]
        == version
    )
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(rf"^version: {re.escape(version)}$", citation, re.MULTILINE)


def test_no_source_file_hardcodes_the_version() -> None:
    version = app_version()
    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" in path.parts:
            continue
        assert f'"{version}"' not in path.read_text(encoding="utf-8"), path


def test_every_release_has_notes_in_both_languages() -> None:
    notes = ROOT / "release-notes"
    version = app_version()
    for language in ("fa", "en"):
        text = (notes / f"{version}.{language}.md").read_text(encoding="utf-8")
        assert text.strip()
