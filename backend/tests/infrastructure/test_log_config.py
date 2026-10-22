"""Application logs reach stdout at the configured level and format."""

import io
import json
import logging

import pytest

from backend.core.runtime.correlation import bind_correlation_id, reset_correlation_id
from backend.infrastructure.log_config import (
    APPLICATION_LOGGERS,
    configure_logging,
    log_level,
)


@pytest.fixture(autouse=True)
def restore_loggers() -> object:
    saved = {
        name: (
            list(logging.getLogger(name).handlers),
            logging.getLogger(name).level,
            logging.getLogger(name).propagate,
        )
        for name in APPLICATION_LOGGERS
    }
    yield
    for name, (handlers, level, propagate) in saved.items():
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate


def _capture(monkeypatch: pytest.MonkeyPatch, environ: dict[str, str]) -> io.StringIO:
    stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", stream)
    configure_logging(environ)
    return stream


def test_info_logs_are_written_as_json_with_the_correlation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _capture(monkeypatch, {"LOG_LEVEL": "INFO"})
    token = bind_correlation_id("req-1")
    try:
        logging.getLogger("parsrag.requests").info("request_complete status=%s", 200)
    finally:
        reset_correlation_id(token)

    entry = json.loads(stream.getvalue())
    assert entry["level"] == "INFO"
    assert entry["logger"] == "parsrag.requests"
    assert entry["message"] == "request_complete status=200"
    assert entry["correlation_id"] == "req-1"


def test_development_logs_are_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _capture(monkeypatch, {"ENVIRONMENT": "development"})

    logging.getLogger("backend.main").warning("readiness failed")

    assert "WARNING backend.main: readiness failed" in stream.getvalue()


def test_level_filters_and_repeated_setup_does_not_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr("sys.stdout", stream)
    configure_logging({"LOG_LEVEL": "warning"})
    configure_logging({"LOG_LEVEL": "warning"})

    logging.getLogger("parsrag.operations").info("hidden")
    logging.getLogger("parsrag.operations").error("shown")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "shown"


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("DEBUG", logging.DEBUG),
        ("error", logging.ERROR),
        ("", logging.INFO),
        ("loud", logging.INFO),
    ],
)
def test_log_level_names(value: str, level: int) -> None:
    assert log_level({"LOG_LEVEL": value}) == level
