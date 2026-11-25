from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from paw.models import ActivityEvent
from paw.services.paging import newest_first


class ActivityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, event_type: str, entity_id: str | None = None, **metadata: Any) -> None:
        """Pass ids, states and counts only; see ActivityEvent."""
        self.session.add(ActivityEvent(event_type=event_type, entity_id=entity_id, event_metadata=metadata))

    def list_page(self, limit: int = 50, cursor: str | None = None) -> tuple[list[ActivityEvent], str | None]:
        return newest_first(
            self.session, select(ActivityEvent), ActivityEvent.occurred_at, ActivityEvent.id, limit, cursor
        )
