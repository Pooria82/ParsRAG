"""Inbound DTO for changing runtime settings from the app."""

from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt


class RuntimeSettingsUpdate(BaseModel):
    """New values by setting name; null returns a setting to its ``.env`` value.

    An empty string means "decide automatically" for settings that allow it.
    """

    values: dict[str, StrictBool | StrictInt | StrictFloat | str | None] = Field(
        ..., max_length=64
    )
