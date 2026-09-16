"""Builder for Chainlit interactive chat settings."""

import chainlit as cl
from chainlit.input_widget import RadioGroup, Slider

from frontend.config import FrontendConfig
from frontend.ui.strings import (
    AVAILABLE_MODE_OPTIONS,
    MODE_OPTION_HYBRID,
    SETTINGS_MODE_DESC,
    SETTINGS_MODE_LABEL,
    SETTINGS_TOP_K_DESC,
    SETTINGS_TOP_K_LABEL,
)


class SettingsBuilder:
    """Constructs and configures Chainlit ChatSettings widgets.

    Encapsulates widget creation so settings components can be modified
    or extended independently of application hooks.
    """

    def __init__(self, config: FrontendConfig | None = None) -> None:
        """Initializes the builder with frontend configuration.

        Args:
            config: Optional configuration instance.
        """
        self.config = config or FrontendConfig()

    def build(self) -> cl.ChatSettings:
        """Builds the ChatSettings component with Mode and Top-K widgets.

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

        top_k_widget = Slider(
            id="top_k",
            label=SETTINGS_TOP_K_LABEL,
            min=self.config.min_top_k,
            max=self.config.max_top_k,
            step=self.config.step_top_k,
            initial=self.config.default_top_k,
            description=SETTINGS_TOP_K_DESC,
        )

        return cl.ChatSettings([mode_widget, top_k_widget])
