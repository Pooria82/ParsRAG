"""Release versions: ``MAJOR.MINOR.PATCH``, compared numerically."""

import re

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int] | None:
    """Read ``1.2.3`` or ``v1.2.3``; anything else (pre-releases too) is None."""
    match = _VERSION.match(value.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    """Whether ``candidate`` is a later release than ``current``."""
    newer, base = parse_version(candidate), parse_version(current)
    return newer is not None and base is not None and newer > base
