"""Runtime settings kept in the process environment and a JSON file.

Most adapters read their settings from the environment for each request, so
an override takes effect by updating ``os.environ``. Clients built once (the
model connection, the embedding model) are refreshed by ``on_change``.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from threading import RLock

from backend.core.domain.runtime_settings import (
    RUNTIME_SETTINGS,
    SETTINGS_BY_KEY,
    normalize_setting,
)

logger = logging.getLogger(__name__)


def runtime_settings_path() -> Path:
    """Where overrides are kept: ``PARSRAG_SETTINGS_PATH``, else next to the model settings."""
    explicit = os.getenv("PARSRAG_SETTINGS_PATH", "").strip()
    if explicit:
        return Path(explicit)
    model_settings = Path(
        os.getenv("PARSRAG_CONFIG_PATH", "data/model-configuration.json")
    )
    return model_settings.with_name("runtime-settings.json")


class EnvironmentSettingsStore:
    """``RuntimeSettingsStore`` adapter over ``os.environ`` and a JSON file."""

    def __init__(
        self,
        path: Path,
        on_change: Callable[[set[str]], None] | None = None,
    ) -> None:
        """Remember the ``.env`` values, then activate saved overrides."""
        self._path = path
        self._on_change = on_change
        self._lock = RLock()
        self._env = {spec.key: _valid_or_default(spec.key) for spec in RUNTIME_SETTINGS}
        self._raw_env = {
            spec.key: os.environ[spec.key]
            for spec in RUNTIME_SETTINGS
            if spec.key in os.environ
        }
        self._overrides: dict[str, str] = {}
        for key, value in self._load().items():
            self._overrides[key] = value
            os.environ[key] = value

    def values(self) -> dict[str, str]:
        """Return the value in effect for every runtime setting."""
        with self._lock:
            return {
                key: self._overrides.get(key, env) for key, env in self._env.items()
            }

    def env_values(self) -> dict[str, str]:
        """Return the value each setting had from ``.env`` at startup."""
        return dict(self._env)

    def overrides(self) -> dict[str, str]:
        """Return the settings changed in the app."""
        with self._lock:
            return dict(self._overrides)

    def apply(self, changes: dict[str, str | None]) -> None:
        """Activate and persist changes; None returns a setting to ``.env``."""
        with self._lock:
            for key, value in changes.items():
                if value is None:
                    self._overrides.pop(key, None)
                    self._restore(key)
                else:
                    self._overrides[key] = value
                    os.environ[key] = value
            self._save()
        if self._on_change is not None and changes:
            self._on_change(set(changes))

    def _restore(self, key: str) -> None:
        """Put back exactly what ``.env`` provided, or remove the variable."""
        if key in self._raw_env:
            os.environ[key] = self._raw_env[key]
        else:
            os.environ.pop(key, None)

    def _load(self) -> dict[str, str]:
        """Read saved overrides, ignoring unknown names and invalid values."""
        if not self._path.is_file():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("Ignoring unreadable runtime settings at %s", self._path)
            return {}
        if not isinstance(payload, dict):
            return {}
        overrides: dict[str, str] = {}
        for key, value in payload.items():
            spec = SETTINGS_BY_KEY.get(key)
            if spec is None or not isinstance(value, str):
                continue
            try:
                overrides[key] = normalize_setting(spec, value)
            except ValueError:
                logger.warning("Ignoring invalid saved setting %s", key)
        return overrides

    def _save(self) -> None:
        """Write overrides atomically; an empty set removes the file."""
        if not self._overrides:
            self._path.unlink(missing_ok=True)
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._overrides, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, self._path)


def _valid_or_default(key: str) -> str:
    """The ``.env`` value when valid, else the built-in default."""
    spec = SETTINGS_BY_KEY[key]
    raw = os.environ.get(key)
    if raw is None:
        return spec.default
    try:
        return normalize_setting(spec, raw)
    except ValueError:
        return spec.default
