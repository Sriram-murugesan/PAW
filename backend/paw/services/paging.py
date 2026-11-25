"""Keyset paging, so that rows added while paging neither repeat nor disappear."""

import base64
import binascii
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute, Session

from paw.core.errors import InvalidRequestError


def _encode(when: datetime, row_id: str) -> str:
    return base64.urlsafe_b64encode(f"{when.isoformat()}|{row_id}".encode()).decode()


def _decode(cursor: str) -> tuple[datetime, str]:
    try:
        when, _, row_id = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        parsed = datetime.fromisoformat(when)
    except (ValueError, binascii.Error) as error:
        raise InvalidRequestError("Invalid cursor.") from error
    if parsed.tzinfo is None or not row_id:
        raise InvalidRequestError("Invalid cursor.")
    return parsed, row_id


def newest_first[T](
    session: Session,
    query: Select[T],
    when: InstrumentedAttribute[datetime],
    row_id: InstrumentedAttribute[str],
    limit: int,
    cursor: str | None,
) -> tuple[list[T], str | None]:
    if cursor:
        at, last = _decode(cursor)
        query = query.where(or_(when < at, and_(when == at, row_id < last)))
    rows: list[Any] = list(session.scalars(query.order_by(when.desc(), row_id.desc()).limit(limit + 1)))
    if len(rows) <= limit:
        return rows, None
    rows = rows[:limit]
    return rows, _encode(getattr(rows[-1], when.key), getattr(rows[-1], row_id.key))
