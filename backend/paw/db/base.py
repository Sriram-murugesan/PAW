import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Dialect, MetaData, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from paw.core.clock import utcnow

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """Fixed-width ISO-8601 UTC text, so that text order is time order."""

    impl = String(27)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime")
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy reads this attribute as is
        datetime: UtcDateTime,
        dict[str, Any]: JSON,
    }


def new_id() -> str:
    return str(uuid.uuid4())


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TimestampMixin(CreatedMixin):
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
