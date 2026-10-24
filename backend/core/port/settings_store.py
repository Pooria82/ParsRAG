"""Port for runtime settings that override ``.env`` without a restart."""

from collections.abc import Callable
from typing import Protocol


class RuntimeSettingsStore(Protocol):
    """Active values, their ``.env`` origin, and persisted overrides."""

    def values(self) -> dict[str, str]:
        """Return the value in effect for every runtime setting."""
        ...

    def env_values(self) -> dict[str, str]:
        """Return the value each setting had from ``.env`` at startup."""
        ...

    def automatic_values(self) -> dict[str, str]:
        """Return what each automatic setting resolves to right now."""
        ...

    def overrides(self) -> dict[str, str]:
        """Return the settings changed in the app."""
        ...

    def apply(
        self,
        changes: dict[str, str | None],
        validate: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        """Validate, persist, then activate changes as one step.

        None returns a setting to ``.env``. ``validate`` receives the values
        that would be in effect and may raise to reject the whole change.
        """
        ...
