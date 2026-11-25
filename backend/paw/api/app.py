import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

from paw.api import memory, system
from paw.api.deps import Context
from paw.api.guard import RequestGuard, error_response
from paw.core.errors import PawError

logger = logging.getLogger("paw.api")


async def _paw_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, PawError)  # noqa: S101 - narrows the registered type
    return error_response(error.status, error.code, error.message, error.details)


async def _validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)  # noqa: S101
    # Location and message only; the rejected input may be private.
    fields = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in error.errors()]
    return error_response(422, "validation_error", "The request is not valid.", {"fields": fields})


async def _http_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)  # noqa: S101
    return error_response(error.status_code, "http_error", str(error.detail))


async def _database_error(_: Request, error: Exception) -> JSONResponse:
    logger.error("database_error", exc_info=error)
    return error_response(503, "database_unavailable", "The database is not available.")


async def _unexpected_error(_: Request, error: Exception) -> JSONResponse:
    logger.error("unexpected_error", exc_info=error)
    return error_response(500, "internal_error", "Something went wrong. See the PAW log.")


def create_app(context: Context, token: str) -> FastAPI:
    # No schema or docs routes at run time; types are generated offline from app.openapi().
    app = FastAPI(title="PAW", version="0.1.0", openapi_url=None)
    app.state.context = context
    app.include_router(memory.router)
    app.include_router(system.router)
    app.add_exception_handler(PawError, _paw_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(OperationalError, _database_error)
    app.add_exception_handler(Exception, _unexpected_error)
    app.add_middleware(RequestGuard, token=token)
    return app
