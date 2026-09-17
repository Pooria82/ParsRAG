from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.security import validate_model_api_url
from backend.main import app


def test_untrusted_browser_origin_cannot_change_model_configuration() -> None:
    """A browser from an untrusted origin cannot mutate application state."""
    response = TestClient(app).put(
        "/models/configuration",
        headers={"Origin": "https://attacker.example"},
        json={
            "provider": "ollama",
            "model_name": "gemma3:12b",
            "base_url": "http://localhost:11434",
        },
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "url",
    [
        "ftp://models.example/v1",
        "https://user:secret@models.example/v1",
        "https://models.example/v1?key=secret",
        "https://models.example/v1#fragment",
    ],
)
def test_model_api_url_rejects_ambiguous_urls(url: str) -> None:
    """Configured endpoints cannot hide credentials or redirect parameters."""
    with pytest.raises(ValueError, match="plain HTTP"):
        validate_model_api_url(url)


@patch("backend.core.security._resolved_addresses")
def test_public_model_api_requires_https(mock_resolve: MagicMock) -> None:
    """Public model traffic must be encrypted while private HTTP remains valid."""
    from ipaddress import ip_address

    mock_resolve.return_value = {ip_address("8.8.8.8")}
    with pytest.raises(ValueError, match="must use HTTPS"):
        validate_model_api_url("http://models.example/v1")

    mock_resolve.return_value = {ip_address("10.20.30.40")}
    assert validate_model_api_url("http://models.internal:8000/v1") == (
        "http://models.internal:8000/v1"
    )


@patch("backend.core.security._resolved_addresses")
def test_model_api_rejects_link_local_targets(mock_resolve: MagicMock) -> None:
    """Link-local endpoints cannot be used to probe instance metadata services."""
    from ipaddress import ip_address

    mock_resolve.return_value = {ip_address("169.254.169.254")}
    with pytest.raises(ValueError, match="blocked network address"):
        validate_model_api_url("http://metadata.internal")
