"""Builder for Chainlit interactive chat settings drawer.

Exposes all operational parameters loaded initially from .env and enables
full in-app customization across language, modes, thresholds, and memory.
"""

from typing import cast

import chainlit as cl
from chainlit.input_widget import InputWidget, Select, Slider, Switch, TextInput

from frontend.config import FrontendConfig
from frontend.ui.i18n import (
    LANG_FA,
    MODE_LABEL_HYBRID,
    MODE_LABEL_LLM_ONLY,
    MODE_LABEL_STRICT,
    get_mode_options,
    get_settings_labels,
    normalize_language,
)


class SettingsBuilder:
    """Constructs and configures Chainlit ChatSettings widgets with .env defaults."""

    def __init__(self, config: FrontendConfig | None = None) -> None:
        """Initializes the builder with frontend configuration.

        Args:
            config: Optional frontend configuration instance.
        """
        self.config = config or FrontendConfig()

    def build(self, lang: str = LANG_FA) -> cl.ChatSettings:
        """Builds comprehensive ChatSettings drawer in the active language.

        Initial values are sourced from FrontendConfig (.env), and can be
        customized dynamically during user sessions.

        Args:
            lang: Active language code ('fa' or 'en').

        Returns:
            cl.ChatSettings: Configured settings drawer for Chainlit.
        """
        norm_lang = normalize_language(lang)
        labels = get_settings_labels(norm_lang)

        # 1. Language Selection
        lang_values = ["فارسی (Persian)", "English"]
        lang_initial = "فارسی (Persian)" if norm_lang == LANG_FA else "English"
        language_widget = Select(
            id="language",
            label=labels["language_label"],
            values=lang_values,
            initial_value=lang_initial,
            description=labels["language_desc"],
        )

        # 2. RAG Execution Mode
        mode_options = get_mode_options(norm_lang)
        default_mode_key = self.config.default_mode.lower()
        if "strict" in default_mode_key:
            initial_mode = MODE_LABEL_STRICT[norm_lang]
        elif "llm" in default_mode_key:
            initial_mode = MODE_LABEL_LLM_ONLY[norm_lang]
        else:
            initial_mode = MODE_LABEL_HYBRID[norm_lang]

        mode_widget = Select(
            id="mode",
            label=labels["mode_label"],
            values=mode_options,
            initial_value=initial_mode,
            description=labels["mode_desc"],
        )

        # 3. Strict RAG Similarity Threshold
        threshold_widget = Slider(
            id="strict_rag_threshold",
            label=labels["threshold_label"],
            min=0.50,
            max=0.95,
            step=0.05,
            initial=float(self.config.strict_rag_threshold),
            description=labels["threshold_desc"],
        )

        # 4. Dynamic Depth Optimization Switch
        dynamic_depth_widget = Switch(
            id="dynamic_depth",
            label=labels["dynamic_depth_label"],
            initial=self.config.dynamic_retrieval_depth,
            description=labels["dynamic_depth_desc"],
        )

        # 5. Manual Retrieval Depth (Top-K)
        manual_top_k_widget = Slider(
            id="manual_top_k",
            label=labels["manual_top_k_label"],
            min=float(self.config.min_top_k),
            max=float(self.config.max_top_k),
            step=float(self.config.step_top_k),
            initial=float(self.config.default_top_k),
            description=labels["manual_top_k_desc"],
        )

        # 6. Conversational Memory Window Turns
        history_widget = Slider(
            id="max_history_turns",
            label=labels["history_window_label"],
            min=2.0,
            max=20.0,
            step=2.0,
            initial=float(self.config.max_chat_history_turns),
            description=labels["history_window_desc"],
        )

        # 7. Backend API URL
        backend_url_widget = TextInput(
            id="backend_url",
            label=labels["backend_url_label"],
            initial=self.config.backend_url,
            description=labels["backend_url_desc"],
        )

        inputs: list[InputWidget] = [
            cast(InputWidget, language_widget),
            cast(InputWidget, mode_widget),
            cast(InputWidget, threshold_widget),
            cast(InputWidget, dynamic_depth_widget),
            cast(InputWidget, manual_top_k_widget),
            cast(InputWidget, history_widget),
            cast(InputWidget, backend_url_widget),
        ]

        return cl.ChatSettings(inputs)
