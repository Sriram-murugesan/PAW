from datetime import datetime
from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from paw.core.clock import utcnow
from paw.db.base import Base, IdMixin


class ActivityEvent(IdMixin, Base):
    """Holds ids and counts, never content, so deleting a memory leaves none of it behind."""

    __tablename__ = "activity_events"

    event_type: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", default=dict)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
