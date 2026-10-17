"""Port for runtime settings that override ``.env`` without a restart."""

from typing import Protocol


class RuntimeSettingsStore(Protocol):
    """Active values, their ``.env`` origin, and persisted overrides."""

    def values(self) -> dict[str, str]:
        """Return the value in effect for every runtime setting."""
        ...

    def env_values(self) -> dict[str, str]:
        """Return the value each setting had from ``.env`` at startup."""
        ...

    def overrides(self) -> dict[str, str]:
        """Return the settings changed in the app."""
        ...

    def apply(self, changes: dict[str, str | None]) -> None:
        """Activate and persist changes; None returns a setting to ``.env``."""
        ...
