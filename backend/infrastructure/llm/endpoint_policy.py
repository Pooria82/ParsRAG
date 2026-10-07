"""Network policy for user-configured model service endpoints."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def _resolved_addresses(
    hostname: str, port: int | None
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a model host to concrete IP addresses."""
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("The model API hostname could not be resolved.") from exc
        return {ipaddress.ip_address(record[4][0]) for record in records}
    return {literal}


def _is_forbidden_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Return whether an address is unsafe for a user-configured model service."""
    return (
        address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


def validate_model_api_url(value: str) -> str:
    """Validate and normalize an OpenAI-compatible local or remote API base URL."""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Model API URLs must be plain HTTP(S) URLs without credentials, query strings, or fragments."
        )

    addresses = _resolved_addresses(parsed.hostname, parsed.port)
    if not addresses or any(_is_forbidden_address(address) for address in addresses):
        raise ValueError("The model API URL resolves to a blocked network address.")
    if parsed.scheme == "http" and not all(
        address.is_private or address.is_loopback for address in addresses
    ):
        raise ValueError("Public model API endpoints must use HTTPS.")
    return normalized


def model_api_is_external(value: str) -> bool:
    """Distinguish a third-party API from loopback or private-network services."""
    hostname = urlparse(value).hostname
    if hostname is None:
        raise ValueError("The model API URL has no hostname.")
    return any(
        not (address.is_private or address.is_loopback)
        for address in _resolved_addresses(hostname, urlparse(value).port)
    )
