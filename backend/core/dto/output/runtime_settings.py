"""Outbound DTOs describing the runtime settings shown in the app."""

from pydantic import BaseModel

from backend.core.domain.runtime_settings import SettingGroup, SettingKind


class RuntimeSettingItem(BaseModel):
    """One setting with its active value and the ``.env`` value it overrides.

    Values are environment strings: "1"/"0" for switches, bytes for sizes,
    and "" for "automatic".
    """

    key: str
    group: SettingGroup
    kind: SettingKind
    value: str
    env_value: str
    overridden: bool
    minimum: float | None = None
    maximum: float | None = None
    automatic: bool = False


class RuntimeSettingsResponse(BaseModel):
    """Every runtime setting, plus the request size the server can accept."""

    settings: list[RuntimeSettingItem]
    upload_ceiling_bytes: int
