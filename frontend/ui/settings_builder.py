"""Builder for Chainlit interactive chat settings."""

import chainlit as cl
from chainlit.input_widget import InputWidget, RadioGroup

from frontend.config import FrontendConfig
from frontend.ui.strings import (
    AVAILABLE_MODE_OPTIONS,
    MODE_OPTION_HYBRID,
    SETTINGS_MODE_DESC,
    SETTINGS_MODE_LABEL,
)


class SettingsBuilder:
    """Constructs and configures Chainlit ChatSettings widgets.

    Encapsulates widget creation so settings components can be modified
    or extended independently of application hooks.
    """

    def __init__(self, config: FrontendConfig | None = None) -> None:
        """Initializes the builder with frontend configuration.

        Args:
            config: Optional frontend configuration instance.
        """
        self.config = config or FrontendConfig()

    def build(self) -> cl.ChatSettings:
        """Builds the ChatSettings component with the Mode selection widget.

        Retrieval and multi-chunk aggregation depth is dynamically determined
        and optimized by the backend per query.

        Returns:
            cl.ChatSettings: Configured settings drawer for Chainlit.
        """
        mode_widget = RadioGroup(
            id="mode",
            label=SETTINGS_MODE_LABEL,
            values=AVAILABLE_MODE_OPTIONS,
            initial_value=MODE_OPTION_HYBRID,
            description=SETTINGS_MODE_DESC,
        )

        inputs: list[InputWidget] = [mode_widget]
        return cl.ChatSettings(inputs)
