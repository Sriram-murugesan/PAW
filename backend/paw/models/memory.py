from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from paw.db.base import Base, CreatedMixin, IdMixin, TimestampMixin
from paw.models.enums import (
    MemoryCategory,
    MemoryStatus,
    ProposalOperation,
    ProposalStatus,
    ProposalTarget,
    SourceType,
)


def one_of(column: str, values: type[StrEnum]) -> CheckConstraint:
    allowed = ", ".join(f"'{v.value}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=column)


class Memory(IdMixin, TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (
        one_of("category", MemoryCategory),
        one_of("status", MemoryStatus),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("ix_memories_status_updated_at", "status", "updated_at"),
    )

    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(16), default=MemoryStatus.CONFIRMED)
    shareable: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)


class Proposal(IdMixin, CreatedMixin, Base):
    __tablename__ = "proposals"
    __table_args__ = (
        one_of("target_type", ProposalTarget),
        one_of("operation", ProposalOperation),
        one_of("status", ProposalStatus),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("ix_proposals_status_created_at", "status", "created_at"),
    )

    target_type: Mapped[str] = mapped_column(String(16))
    operation: Mapped[str] = mapped_column(String(16))
    # Not a foreign key: the target table depends on target_type.
    target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    base_version: Mapped[int | None]
    payload: Mapped[dict[str, Any]]
    content_hash: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default=ProposalStatus.PENDING)
    submitted_by: Mapped[str] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None]


class MemoryRevision(IdMixin, CreatedMixin, Base):
    __tablename__ = "memory_revisions"
    __table_args__ = (UniqueConstraint("memory_id", "version"),)

    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    version: Mapped[int]
    snapshot: Mapped[dict[str, Any]]
    change_reason: Mapped[str] = mapped_column(String(32))
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"))


class MemorySource(IdMixin, CreatedMixin, Base):
    __tablename__ = "memory_sources"
    __table_args__ = (
        one_of("source_type", SourceType),
        CheckConstraint("(memory_id IS NULL) <> (proposal_id IS NULL)", name="one_owner"),
    )

    memory_id: Mapped[str | None] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    proposal_id: Mapped[str | None] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str | None] = mapped_column(String(200))
    reference_metadata: Mapped[dict[str, Any]] = mapped_column(default=dict)
