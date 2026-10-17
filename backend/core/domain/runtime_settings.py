"""Settings an operator can change while the service runs.

Each setting is the environment variable of the same name. ``.env`` (or
Compose) gives the starting value; Settings in the app can override it
without a restart, and an override can be reset back to the ``.env`` value.
Settings that need a restart or that guard the trust boundary (ports,
allowed hosts and origins, Qdrant, memory limits, the embedding model) stay
in ``.env`` only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

SettingKind = Literal["int", "float", "bool", "text", "bytes"]
SettingGroup = Literal["model", "retrieval", "documents", "performance"]

MEBIBYTE = 1024 * 1024
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class SettingSpec:
    """One runtime setting: where it is shown, its type, and its bounds.

    ``default`` applies when neither ``.env`` nor the app sets a value; an
    empty default with ``automatic`` means the service decides (for example
    adaptive retrieval depth).
    """

    key: str
    group: SettingGroup
    kind: SettingKind
    default: str
    minimum: float | None = None
    maximum: float | None = None
    automatic: bool = False
    pattern: str | None = None


RUNTIME_SETTINGS: tuple[SettingSpec, ...] = (
    # Model
    SettingSpec("OLLAMA_CONTEXT_LENGTH", "model", "int", "8192", 2048, 131072),
    SettingSpec("OLLAMA_THINK", "model", "bool", "0"),
    SettingSpec("MODEL_CONTEXT_WINDOW", "model", "int", "32768", 2048, 1048576),
    SettingSpec("MODEL_API_MAX_RETRIES", "model", "int", "4", 0, 8),
    SettingSpec("LLM_REQUEST_TIMEOUT_SECONDS", "model", "int", "120", 10, 600),
    SettingSpec("CONDENSE_TIMEOUT_SECONDS", "model", "int", "30", 5, 120),
    # Retrieval
    SettingSpec("STRICT_RAG_THRESHOLD", "retrieval", "float", "0.75", 0.0, 1.0),
    SettingSpec("STRICT_RAG_TOP_K", "retrieval", "int", "", 1, 50, automatic=True),
    SettingSpec("HYBRID_RETRIEVE_TOP_K", "retrieval", "int", "25", 1, 50),
    SettingSpec("HYBRID_RERANK_TOP_K", "retrieval", "int", "", 1, 50, automatic=True),
    SettingSpec("KEYWORD_SEARCH", "retrieval", "bool", "1"),
    # Documents and OCR
    SettingSpec("PARSRAG_MAX_FILES_PER_SESSION", "documents", "int", "10", 1, 50),
    SettingSpec(
        "PARSRAG_MAX_FILE_BYTES",
        "documents",
        "bytes",
        str(100 * MEBIBYTE),
        MEBIBYTE,
        1024 * MEBIBYTE,
    ),
    SettingSpec(
        "PARSRAG_MAX_BATCH_BYTES",
        "documents",
        "bytes",
        str(500 * MEBIBYTE),
        MEBIBYTE,
        2048 * MEBIBYTE,
    ),
    SettingSpec("OCR_ENABLED", "documents", "bool", "0"),
    SettingSpec(
        "OCR_LANGUAGES",
        "documents",
        "text",
        "fas+eng",
        pattern=r"[a-z_]{3,20}(\+[a-z_]{3,20}){0,7}",
    ),
    SettingSpec("OCR_DPI", "documents", "int", "200", 150, 600),
    SettingSpec("OCR_ORIENTATION", "documents", "bool", "1"),
    SettingSpec("OCR_MAX_PAGES", "documents", "int", "30", 1, 200),
    SettingSpec("OCR_MAX_IMAGES", "documents", "int", "200", 1, 1000),
    SettingSpec("OCR_TIMEOUT_SECONDS", "documents", "int", "45", 1, 300),
    SettingSpec("OCR_MIN_IMAGE_PIXELS", "documents", "int", "10000", 1, 1_000_000),
    SettingSpec("SOURCE_IMAGE_PREVIEWS", "documents", "bool", "1"),
    # Performance
    SettingSpec("OCR_WORKERS", "performance", "int", "", 1, 16, automatic=True),
    SettingSpec("EMBED_BATCH_SIZE", "performance", "int", "", 1, 128, automatic=True),
    SettingSpec("PARSRAG_CPU_THREADS", "performance", "int", "", 1, 64, automatic=True),
    SettingSpec("QDRANT_UPSERT_BATCH_SIZE", "performance", "int", "64", 1, 512),
)
SETTINGS_BY_KEY = {spec.key: spec for spec in RUNTIME_SETTINGS}

SettingValue = bool | int | float | str | None


def normalize_setting(spec: SettingSpec, value: SettingValue) -> str:
    """Return the environment string for ``value``; "" means automatic.

    Raises:
        ValueError: The value has the wrong type or lies outside the bounds.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if spec.automatic:
            return ""
        raise ValueError(f"{spec.key} needs a value.")
    if spec.kind == "bool":
        return _boolean(spec, value)
    if spec.kind == "text":
        text = str(value).strip().lower()
        if spec.pattern and not re.fullmatch(spec.pattern, text):
            raise ValueError(f"{spec.key} has an invalid format.")
        return text
    number = _number(spec, value)
    if spec.minimum is not None and number < spec.minimum:
        raise ValueError(f"{spec.key} must be at least {spec.minimum:g}.")
    if spec.maximum is not None and number > spec.maximum:
        raise ValueError(f"{spec.key} must be at most {spec.maximum:g}.")
    return f"{number:g}" if spec.kind == "float" else str(int(number))


def _boolean(spec: SettingSpec, value: SettingValue) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).strip().lower()
    if text in _TRUE:
        return "1"
    if text in _FALSE:
        return "0"
    raise ValueError(f"{spec.key} must be on or off.")


def _number(spec: SettingSpec, value: SettingValue) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{spec.key} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{spec.key} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{spec.key} must be a number.")
    if spec.kind != "float" and not number.is_integer():
        raise ValueError(f"{spec.key} must be a whole number.")
    return number
