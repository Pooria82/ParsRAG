"""Model API requests are checked again at send time and never follow redirects."""

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from backend.infrastructure.llm.endpoint_policy import (
    GuardedTransport,
    guarded_http_client,
)


def _resolve_to(address: str) -> Any:
    return patch(
        "backend.infrastructure.llm.endpoint_policy.socket.getaddrinfo",
        return_value=[(None, None, None, None, (address, 443))],
    )


def test_a_host_that_now_resolves_to_cloud_metadata_is_refused() -> None:
    """DNS changed after the URL was validated: the request is not sent."""
    sent: list[httpx.Request] = []

    with (
        _resolve_to("169.254.169.254"),
        patch.object(httpx.HTTPTransport, "handle_request", side_effect=sent.append),
        httpx.Client(transport=GuardedTransport()) as client,
        pytest.raises(httpx.ConnectError, match="blocked network address"),
    ):
        client.get("https://models.example/v1/models")

    assert sent == []


def test_an_allowed_host_is_sent() -> None:
    response = httpx.Response(200, json={"data": []})
    with (
        _resolve_to("104.18.2.115"),
        patch.object(httpx.HTTPTransport, "handle_request", return_value=response),
        httpx.Client(transport=GuardedTransport()) as client,
    ):
        assert client.get("https://models.example/v1/models").status_code == 200


def test_the_model_client_does_not_follow_redirects() -> None:
    client = guarded_http_client(30.0)
    assert client.follow_redirects is False
    assert isinstance(client._transport, GuardedTransport)
    client.close()
