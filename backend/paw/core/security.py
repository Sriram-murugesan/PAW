"""Checks applied to every request before routing."""

import secrets
from collections.abc import Iterable

MIN_TOKEN_LENGTH = 32
MAX_BODY_BYTES = 1_048_576
_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def token_matches(expected: str, authorization: str | None) -> bool:
    scheme, _, supplied = (authorization or "").partition(" ")
    # compare_digest rejects non-ASCII str, so compare bytes.
    return scheme.lower() == "bearer" and secrets.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    )


def host_allowed(host: str | None) -> bool:
    """Reject foreign Host headers, which is how DNS rebinding reaches a local server."""
    return (host or "").partition(":")[0] in _ALLOWED_HOSTS


def first_header(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str | None:
    return next((v.decode("latin-1") for k, v in headers if k.lower() == name), None)
