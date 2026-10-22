"""Send application logs to stdout at the level chosen in ``LOG_LEVEL``.

Nothing configured the ``backend`` and ``parsrag`` loggers before, so Python's
default WARNING level dropped every request and operation log. Production
(the default) writes one JSON object per line for log collectors; with
``ENVIRONMENT=development`` the lines are plain text.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime

from backend.core.runtime.correlation import current_correlation_id

# Loggers owned by ParsRAG; uvicorn keeps its own handlers.
APPLICATION_LOGGERS = ("backend", "parsrag")
_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Format a record as one JSON object with the active correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a single JSON line."""
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = current_correlation_id()
        if correlation_id:
            entry["correlation_id"] = correlation_id
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def log_level(environ: Mapping[str, str] = os.environ) -> int:
    """Return the level named by ``LOG_LEVEL``; INFO when unset or unknown."""
    name = environ.get("LOG_LEVEL", "INFO").strip().upper()
    if name not in _LEVELS:
        return logging.INFO
    return int(getattr(logging, name))


def configure_logging(environ: Mapping[str, str] = os.environ) -> None:
    """Attach one stdout handler to the application loggers.

    Calling it again replaces the handler instead of adding a second one.
    """
    handler = logging.StreamHandler(sys.stdout)
    if environ.get("ENVIRONMENT", "production").strip().lower() == "development":
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))
    else:
        handler.setFormatter(JsonFormatter())
    level = log_level(environ)
    for name in APPLICATION_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(level)
        logger.propagate = True
