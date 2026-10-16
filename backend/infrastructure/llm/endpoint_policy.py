"""Network policy for user-configured model service endpoints."""

from __future__ import annotations

import ipaddress
import os
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


# Ollama hosts accepted without configuration: loopback for native runs, the
# Compose service, and the Docker host (Docker Desktop, or ``host-gateway`` on
# Linux), so an Ollama already installed on the machine can be used.
DEFAULT_OLLAMA_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "ollama", "host.docker.internal"}
)


class OllamaURLNotAllowedError(ValueError):
    """An Ollama URL points outside the allowed hosts or carries extra parts."""


def allowed_ollama_hosts() -> frozenset[str]:
    """Return the default Ollama hosts plus the operator's additions.

    ``OLLAMA_ALLOWED_HOSTS`` adds comma-separated host names or addresses;
    ``OLLAMA_INTERNAL_HOST`` (one host) is still read for compatibility.
    """
    configured = ",".join(
        (os.getenv("OLLAMA_INTERNAL_HOST", ""), os.getenv("OLLAMA_ALLOWED_HOSTS", ""))
    )
    extra = {host.strip().strip("[]").lower() for host in configured.split(",")}
    return DEFAULT_OLLAMA_HOSTS | {host for host in extra if host}


def is_allowed_ollama_url(value: str) -> bool:
    """Whether ``value`` is a plain ``http://host[:port]`` URL on an allowed host."""
    parsed = urlparse(value.strip())
    try:
        parsed.port  # noqa: B018 - raises ValueError for an invalid port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname is not None
        and parsed.hostname.lower() in allowed_ollama_hosts()
        and parsed.username is None
        and parsed.password is None
        and parsed.params == ""
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path in {"", "/"}
    )


def require_allowed_ollama_url(value: str) -> None:
    """Reject Ollama URLs that are not allowed.

    Raises:
        OllamaURLNotAllowedError: The URL is not ``http://`` on an allowed host,
            or it has credentials, a path, a query, or a fragment.
    """
    if not is_allowed_ollama_url(value):
        raise OllamaURLNotAllowedError(
            "Ollama must use http:// on localhost, ollama, host.docker.internal, "
            "or a host listed in OLLAMA_ALLOWED_HOSTS, without credentials, path, "
            "or query."
        )
