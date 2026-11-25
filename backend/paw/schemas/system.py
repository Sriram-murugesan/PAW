from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from paw.models.enums import MemoryCategory
from paw.schemas.common import Schema
from paw.schemas.memory import ProposalOut


class ProfileUpdate(Schema):
    display_name: Annotated[str, Field(max_length=200)]
    # Sections chosen by the user; nothing about them is fixed in code.
    profile_data: dict[Annotated[str, Field(min_length=1, max_length=64)], str | list[str]]
    version: int

    @field_validator("profile_data")
    @classmethod
    def limit_size(cls, value: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
        size = sum(len(v) if isinstance(v, str) else sum(map(len, v)) for v in value.values())
        if len(value) > 50 or size > 50_000:
            raise ValueError("profile is too large")
        return value


class ProfileOut(Schema):
    display_name: str
    profile_data: dict[str, Any]
    version: int
    updated_at: datetime | None


class Settings(Schema):
    theme: Literal["dark", "light", "system"] = "dark"


class ActivityOut(Schema):
    id: str
    event_type: str
    project_id: str | None
    entity_id: str | None
    event_metadata: dict[str, Any]
    occurred_at: datetime


class BackupOut(Schema):
    id: str
    reason: str
    created_at: datetime
    size_bytes: int


class RestoreOut(Schema):
    restored: str
    safety_backup: str


class DashboardOut(Schema):
    confirmed_memories: int
    archived_memories: int
    pending_proposals: int
    memories_by_category: dict[MemoryCategory, int]
    latest_proposals: list[ProposalOut]
    recent_activity: list[ActivityOut]
