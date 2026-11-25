from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request

from paw.db.backup import BackupStore
from paw.db.database import Database

# The desktop app is the only holder of the token, so requests come from the user.
USER = "user"
IMPORT = "file import"


@dataclass(frozen=True)
class Context:
    database: Database
    backups: BackupStore


def get_context(request: Request) -> Context:
    context: Context = request.app.state.context
    return context


Ctx = Annotated[Context, Depends(get_context)]
Limit = Annotated[int, Query(ge=1, le=200)]
Cursor = Annotated[str | None, Query(max_length=200)]
Id = UUID
