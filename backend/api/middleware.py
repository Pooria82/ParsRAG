"""ASGI middleware enforcing the local HTTP trust boundary."""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Iterable
from contextlib import suppress
from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.core.runtime.correlation import bind_correlation_id, reset_correlation_id

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SENSITIVE_READ_PREFIXES = ("/models",)
_LOOPBACK_HOSTS = "localhost,127.0.0.1,::1"
logger = logging.getLogger("parsrag.requests")


def configured_hosts() -> list[str]:
    """Return the Host header names this server answers to.

    Only loopback names are accepted by default, so a public domain that a
    malicious page rebinds to 127.0.0.1 cannot reach the API. Deployments
    that serve other machines list their names in ``PARSRAG_ALLOWED_HOSTS``;
    ``*`` disables the check.
    """
    configured = os.getenv("PARSRAG_ALLOWED_HOSTS", "").strip() or _LOOPBACK_HOSTS
    return [
        host.strip().lower().strip("[]").rstrip(".")
        for host in configured.split(",")
        if host.strip()
    ]


def request_hostname(host_header: str) -> str:
    """Return the lower-case host name of a Host header without its port."""
    value = host_header.strip().lower()
    if value.startswith("["):
        return value[1 : value.find("]")] if "]" in value else ""
    if value.count(":") == 1:
        value = value.split(":", 1)[0]
    return value.rstrip(".")


class TrustedHostMiddleware:
    """Reject requests addressed to host names outside the configured set.

    This closes DNS rebinding: a page on ``attacker.example`` that rebinds
    its name to 127.0.0.1 is same-origin with itself, so origin checks pass,
    but its requests still carry ``Host: attacker.example``.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: Iterable[str]) -> None:
        """Initialize the middleware with normalized host names."""
        self.app = app
        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.allow_any = "*" in self.allowed_hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward requests whose Host header names this server."""
        if scope["type"] != "http" or self.allow_any:
            await self.app(scope, receive, send)
            return
        hostname = request_hostname(Headers(scope=scope).get("host", ""))
        if hostname in self.allowed_hosts:
            await self.app(scope, receive, send)
            return
        logger.warning("untrusted_host_rejected path=%s", scope.get("path"))
        response = b'{"detail":"Host is not trusted.","code":"untrusted_host"}'
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": response})


def configured_browser_origins() -> list[str]:
    """Return explicitly trusted cross-origin development origins."""
    configured = os.getenv(
        "PARSRAG_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [
        origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()
    ]


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
        token = bind_correlation_id(correlation_id)
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
            reset_correlation_id(token)
