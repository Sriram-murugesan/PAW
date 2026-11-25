"""Domain errors. The API layer turns these into responses; other adapters can do likewise."""

from typing import Any


class PawError(Exception):
    code = "error"
    status = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(PawError):
    code = "not_found"
    status = 404


class ConflictError(PawError):
    code = "conflict"
    status = 409


class VersionConflictError(ConflictError):
    code = "version_conflict"


class InvalidRequestError(PawError):
    code = "invalid_request"
    status = 422


class UnavailableError(PawError):
    code = "unavailable"
    status = 503


class SchemaError(PawError):
    code = "schema_error"


class BackupError(PawError):
    code = "backup_invalid"
    status = 409
