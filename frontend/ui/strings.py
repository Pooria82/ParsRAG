"""Backward-compatible UI strings and message templates.

Delegates to frontend.ui.i18n for full bilingual support (fa / en).
"""

from frontend.ui.i18n import (
    LANG_FA,
    MODE_LABEL_HYBRID,
    MODE_LABEL_LLM_ONLY,
    MODE_LABEL_STRICT,
    MODE_OPTIONS,
    get_settings_labels,
    get_welcome_markdown,
)
from frontend.ui.i18n import (
    format_file_limit_exceeded as i18n_format_file_limit_exceeded,
)
from frontend.ui.i18n import (
    format_ingest_error as i18n_format_ingest_error,
)
from frontend.ui.i18n import (
    format_ingest_progress as i18n_format_ingest_progress,
)
from frontend.ui.i18n import (
    format_ingest_success as i18n_format_ingest_success,
)
from frontend.ui.i18n import (
    format_language_switched as i18n_format_language_switched,
)
from frontend.ui.i18n import (
    format_query_error as i18n_format_query_error,
)
from frontend.ui.i18n import (
    format_settings_updated as i18n_format_settings_updated,
)

WELCOME_MARKDOWN: str = get_welcome_markdown(LANG_FA)
SETTINGS_MODE_LABEL: str = get_settings_labels(LANG_FA)["mode_label"]
SETTINGS_MODE_DESC: str = get_settings_labels(LANG_FA)["mode_desc"]

MODE_OPTION_HYBRID: str = MODE_LABEL_HYBRID[LANG_FA]
MODE_OPTION_STRICT: str = MODE_LABEL_STRICT[LANG_FA]
MODE_OPTION_LLM_ONLY: str = MODE_LABEL_LLM_ONLY[LANG_FA]
AVAILABLE_MODE_OPTIONS: list[str] = MODE_OPTIONS[LANG_FA]


def format_settings_updated(
    raw_mode: str,
    normalized_mode: str,
    top_k: int | None = None,
    lang: str = LANG_FA,
    dynamic_depth: bool = True,
    threshold: float = 0.80,
) -> str:
    """Formats settings update confirmation."""
    return i18n_format_settings_updated(
        lang=lang,
        raw_mode=raw_mode,
        normalized_mode=normalized_mode,
        dynamic_depth=dynamic_depth,
        top_k=top_k,
        threshold=threshold,
    )


def format_file_limit_exceeded(
    current_count: int, new_count: int, max_limit: int, lang: str = LANG_FA
) -> str:
    """Formats file limit exceeded error."""
    return i18n_format_file_limit_exceeded(
        lang=lang,
        current_count=current_count,
        new_count=new_count,
        max_limit=max_limit,
    )


def format_ingest_progress(count: int, lang: str = LANG_FA) -> str:
    """Formats ingestion progress notice."""
    return i18n_format_ingest_progress(lang=lang, count=count)


def format_ingest_success(
    backend_message: str, active_files: list[str], lang: str = LANG_FA
) -> str:
    """Formats ingestion success summary."""
    return i18n_format_ingest_success(
        lang=lang, backend_message=backend_message, active_files=active_files
    )


def format_ingest_error(error_detail: str, lang: str = LANG_FA) -> str:
    """Formats ingestion error alert."""
    return i18n_format_ingest_error(lang=lang, error_detail=error_detail)


def format_query_error(error_detail: str, lang: str = LANG_FA) -> str:
    """Formats query error alert."""
    return i18n_format_query_error(lang=lang, error_detail=error_detail)


def format_language_switched(lang: str) -> str:
    """Formats language switch notice."""
    return i18n_format_language_switched(lang)
