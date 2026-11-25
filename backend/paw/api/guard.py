"""Authentication and request limits, applied before routing so that no route can omit them."""

import logging
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from paw.core.logging import log_event
from paw.core.security import MAX_BODY_BYTES, first_header, host_allowed, token_matches

logger = logging.getLogger("paw.api")
PUBLIC_PATHS = {"/health"}


def error_response(status: int, code: str, message: str, details: object = None) -> JSONResponse:
    error = {"code": code, "message": message, "details": details or {}}
    return JSONResponse({"error": error}, status_code=status)


class RequestGuard:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            return  # no WebSocket routes exist
        started = time.monotonic()
        status = 0

        async def tracked_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        refusal = self._refusal(scope)
        if refusal:
            await refusal(scope, receive, tracked_send)
        else:
            await self.app(scope, receive, tracked_send)
        # The path has ids only; the query string may hold search text and is left out.
        log_event(
            logger,
            "request",
            method=scope["method"],
            path=scope["path"] if not refusal else "",
            status=status,
            ms=round((time.monotonic() - started) * 1000),
        )

    def _refusal(self, scope: Scope) -> JSONResponse | None:
        headers = scope["headers"]
        if not host_allowed(first_header(headers, b"host")):
            return error_response(403, "forbidden_host", "Host not allowed.")
        # The desktop proxy never sends Origin, so its presence means a web page is calling.
        if first_header(headers, b"origin") is not None:
            return error_response(403, "forbidden_origin", "Browser requests are not allowed.")
        if scope["path"] not in PUBLIC_PATHS and not token_matches(
            self.token, first_header(headers, b"authorization")
        ):
            return error_response(401, "unauthorized", "Missing or invalid token.")
        if first_header(headers, b"transfer-encoding") is not None:
            return error_response(411, "length_required", "Content-Length is required.")
        length = first_header(headers, b"content-length") or "0"
        if not length.isdecimal() or int(length) > MAX_BODY_BYTES:
            return error_response(413, "too_large", "Request body is too large.")
        return None
