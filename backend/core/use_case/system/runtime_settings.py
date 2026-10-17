"""Use cases: read and change the settings that apply without a restart."""

from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.runtime_settings import (
    RUNTIME_SETTINGS,
    SETTINGS_BY_KEY,
    normalize_setting,
)
from backend.core.dto.input.runtime_settings import RuntimeSettingsUpdate
from backend.core.dto.output.runtime_settings import (
    RuntimeSettingItem,
    RuntimeSettingsResponse,
)
from backend.core.port.settings_store import RuntimeSettingsStore


class ReadRuntimeSettings:
    """Show every runtime setting with its ``.env`` value."""

    def __init__(self, store: RuntimeSettingsStore, upload_ceiling_bytes: int) -> None:
        """Bind the settings store and the HTTP request ceiling."""
        self._store = store
        self._ceiling = upload_ceiling_bytes

    def execute(self) -> RuntimeSettingsResponse:
        """Return the settings in display order."""
        values = self._store.values()
        env_values = self._store.env_values()
        overrides = self._store.overrides()
        automatic = self._store.automatic_values()
        return RuntimeSettingsResponse(
            settings=[
                RuntimeSettingItem(
                    key=spec.key,
                    group=spec.group,
                    kind=spec.kind,
                    value=values[spec.key],
                    env_value=env_values[spec.key],
                    overridden=spec.key in overrides,
                    minimum=spec.minimum,
                    maximum=spec.maximum,
                    automatic=spec.automatic,
                    automatic_value=automatic.get(spec.key) if spec.automatic else None,
                )
                for spec in RUNTIME_SETTINGS
            ],
            upload_ceiling_bytes=self._ceiling,
        )


class UpdateRuntimeSettings:
    """Validate and apply changes; each applies to the next request."""

    def __init__(self, store: RuntimeSettingsStore, upload_ceiling_bytes: int) -> None:
        """Bind the settings store and the HTTP request ceiling."""
        self._store = store
        self._ceiling = upload_ceiling_bytes

    def execute(self, update: RuntimeSettingsUpdate) -> RuntimeSettingsResponse:
        """Apply ``update`` and return the resulting settings.

        Raises:
            InvalidInputError: A name is unknown, a value is out of bounds, or
                the upload limits contradict each other or the server ceiling.
        """
        changes: dict[str, str | None] = {}
        for key, value in update.values.items():
            spec = SETTINGS_BY_KEY.get(key)
            if spec is None:
                raise InvalidInputError(
                    f"Unknown setting {key}.", code="invalid_setting"
                )
            if value is None:
                changes[key] = None
                continue
            try:
                changes[key] = normalize_setting(spec, value)
            except ValueError as exc:
                raise InvalidInputError(str(exc), code="invalid_setting") from exc
        self._check_upload_limits(changes)
        self._store.apply(changes)
        return ReadRuntimeSettings(self._store, self._ceiling).execute()

    def reset(self) -> RuntimeSettingsResponse:
        """Return every setting to its ``.env`` value."""
        self._store.apply(dict.fromkeys(self._store.overrides()))
        return ReadRuntimeSettings(self._store, self._ceiling).execute()

    def _check_upload_limits(self, changes: dict[str, str | None]) -> None:
        """A file must fit in a batch, and a batch in one HTTP request."""
        values = self._store.values()
        env_values = self._store.env_values()

        def after(key: str) -> int:
            if key in changes:
                change = changes[key]
                return int(change if change is not None else env_values[key])
            return int(values[key])

        file_bytes = after("PARSRAG_MAX_FILE_BYTES")
        batch_bytes = after("PARSRAG_MAX_BATCH_BYTES")
        if file_bytes > batch_bytes:
            raise InvalidInputError(
                "The file size limit cannot exceed the upload batch limit.",
                code="invalid_setting",
            )
        if batch_bytes > self._ceiling:
            raise InvalidInputError(
                "The upload batch limit exceeds what the server accepts per "
                "request; raise PARSRAG_MAX_REQUEST_BYTES in .env first.",
                code="upload_ceiling",
            )
