"""Security helpers for browser origins and model service endpoints."""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
import time
import uuid
from collections.abc import Iterable
from contextlib import suppress
from contextvars import ContextVar
from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SENSITIVE_READ_PREFIXES = ("/models",)
logger = logging.getLogger("parsrag.requests")
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str | None:
    """Expose the active request ID to downstream adapters and operation logs."""
    return _correlation_id.get()


def configured_browser_origins() -> list[str]:
    """Return explicitly trusted cross-origin development origins."""
    configured = os.getenv(
        "PARSRAG_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [
        origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()
    ]


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


def _same_origin(origin: str, host: str) -> bool:
    """Return whether an Origin header targets the current HTTP host."""
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


class TrustedOriginMiddleware:
    """Reject browser requests from origins outside the local application boundary."""

    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]) -> None:
        """Initialize the middleware with normalized trusted origins."""
        self.app = app
        self.allowed_origins = {origin.rstrip("/") for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate browser origins before forwarding an HTTP request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", ""))
        protects_request = method not in _SAFE_METHODS or path.startswith(
            _SENSITIVE_READ_PREFIXES
        )
        trusted = origin is None or (
            origin.rstrip("/") in self.allowed_origins
            or _same_origin(origin, headers.get("host", ""))
        )
        if protects_request and not trusted:
            response = b'{"detail":"Browser origin is not trusted."}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(response)).encode("ascii")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": response})
            return
        await self.app(scope, receive, send)


class ContentLengthLimitMiddleware:
    """Reject oversized bodies even when clients omit Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        """Initialize the middleware with an inclusive byte limit."""
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject oversized HTTP requests before multipart parsing starts."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._declared_too_large(scope):
            await self._reject(send)
            return

        received = 0
        rejected = False

        async def receive_limited() -> Message:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    raise _RequestBodyTooLarge
            return message

        async def send_unless_rejected(message: Message) -> None:
            if not rejected:
                await send(message)

        with suppress(_RequestBodyTooLarge):
            await self.app(scope, receive_limited, send_unless_rejected)
        if rejected:
            await self._reject(send)

    def _declared_too_large(self, scope: Scope) -> bool:
        """Reject an invalid or oversized declared request length early."""
        value = Headers(scope=scope).get("content-length")
        try:
            return value is not None and int(value) > self.max_bytes
        except ValueError:
            return True

    @staticmethod
    async def _reject(send: Send) -> None:
        """Return the same bounded-body error for both transfer styles."""
        response = b'{"detail":"Request body exceeds the configured limit."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": response})


class _RequestBodyTooLarge(Exception):
    """Stop downstream parsing after an undeclared body crosses the limit."""


class RequestContextMiddleware:
    """Attach a correlation ID and log request metadata without user content."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Record method, path, status, duration, and a generated request ID."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        token = _correlation_id.set(correlation_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            logger.info(
                "request_complete correlation_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                correlation_id,
                scope.get("method"),
                scope.get("path"),
                status_code,
                (time.perf_counter() - started) * 1000,
            )
            _correlation_id.reset(token)
