import hashlib
import unicodedata
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from paw.core.clock import utcnow
from paw.core.errors import ConflictError, NotFoundError, VersionConflictError
from paw.models import Memory, MemoryRevision, MemorySource, Proposal
from paw.models.enums import MemoryCategory, MemoryStatus, SourceType
from paw.schemas.memory import (
    ExportMemory,
    MemoryCreate,
    MemoryDetail,
    MemoryExport,
    MemoryOut,
    MemoryUpdate,
    RevisionOut,
    SourceOut,
)
from paw.services.activity_service import ActivityService
from paw.services.paging import newest_first

SNAPSHOT_FIELDS = ("category", "title", "content", "confidence", "status", "shareable")


def content_hash(text: str) -> str:
    """Same text apart from case, spacing and Unicode form gives the same hash."""
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MemoryService:
    """Every change goes through `_save`, so none can skip its revision."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.activity = ActivityService(session)

    def get(self, memory_id: str) -> Memory:
        memory = self.session.get(Memory, memory_id)
        if memory is None:
            raise NotFoundError("Memory not found.")
        return memory

    def detail(self, memory_id: str) -> MemoryDetail:
        memory = self.get(memory_id)
        return MemoryDetail(**MemoryOut.model_validate(memory).model_dump(), sources=self.sources(memory_id))

    def sources(self, memory_id: str) -> list[SourceOut]:
        query = (
            select(MemorySource)
            .where(MemorySource.memory_id == memory_id)
            .order_by(MemorySource.created_at, MemorySource.id)
        )
        return [SourceOut.model_validate(s) for s in self.session.scalars(query)]

    def list_page(
        self,
        *,
        status: MemoryStatus | None = None,
        category: MemoryCategory | None = None,
        q: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Memory], str | None]:
        query: Select[Memory] = select(Memory)
        if status:
            query = query.where(Memory.status == status)
        if category:
            query = query.where(Memory.category == category)
        if q:
            pattern = f"%{escape_like(q)}%"
            query = query.where(
                or_(Memory.title.ilike(pattern, escape="\\"), Memory.content.ilike(pattern, escape="\\"))
            )
        return newest_first(self.session, query, Memory.updated_at, Memory.id, limit, cursor)

    def history(self, memory_id: str) -> list[MemoryRevision]:
        self.get(memory_id)
        query = (
            select(MemoryRevision)
            .where(MemoryRevision.memory_id == memory_id)
            .order_by(MemoryRevision.version.desc())
        )
        return list(self.session.scalars(query))

    def create(self, data: MemoryCreate) -> Memory:
        memory = self.add(data.model_dump(), reason="created")
        self.session.add(MemorySource(memory_id=memory.id, source_type=SourceType.MANUAL))
        return memory

    def add(self, values: dict[str, Any], *, reason: str, proposal_id: str | None = None) -> Memory:
        memory = Memory(**values, content_hash=content_hash(values["content"]), version=1)
        self.session.add(memory)
        self._save(memory, reason, proposal_id)
        return memory

    def update(self, memory_id: str, data: MemoryUpdate) -> Memory:
        memory = self.get(memory_id)
        self.check_version(memory, data.version)
        return self.change(memory, data.model_dump(exclude={"version"}), reason="edited")

    def set_status(self, memory_id: str, status: MemoryStatus) -> Memory:
        memory = self.get(memory_id)
        if memory.status == status:
            raise ConflictError(f"The memory is already {status.lower()}.")
        reason = "archived" if status == MemoryStatus.ARCHIVED else "unarchived"
        return self.change(memory, {"status": status}, reason=reason)

    def change(
        self, memory: Memory, values: dict[str, Any], *, reason: str, proposal_id: str | None = None
    ) -> Memory:
        changed = {k: v for k, v in values.items() if getattr(memory, k) != v}
        if not changed:
            return memory
        for key, value in changed.items():
            setattr(memory, key, value)
        memory.content_hash = content_hash(memory.content)
        memory.version += 1
        self._save(memory, reason, proposal_id)
        return memory

    def delete(self, memory_id: str) -> None:
        """Remove the memory and every copy of its text: revisions, sources and proposals."""
        memory = self.get(memory_id)
        self.session.delete(memory)
        self.session.flush()  # cascades to revisions, which reference proposals
        self.session.execute(delete(Proposal).where(Proposal.target_id == memory_id))
        self.activity.record("memory.deleted", memory_id)

    def check_version(self, memory: Memory, version: int | None) -> None:
        if memory.version != version:
            raise VersionConflictError(
                "The memory changed since it was read.",
                {
                    "expected_version": version,
                    "current": MemoryOut.model_validate(memory).model_dump(mode="json"),
                },
            )

    def duplicates(self, digest: str) -> list[str]:
        query = select(Memory.id).where(
            Memory.content_hash == digest, Memory.status == MemoryStatus.CONFIRMED
        )
        return list(self.session.scalars(query))

    def counts(self) -> dict[str, int]:
        rows = self.session.execute(select(Memory.status, func.count()).group_by(Memory.status))
        return {status: count for status, count in rows}

    def counts_by_category(self) -> dict[MemoryCategory, int]:
        rows = self.session.execute(
            select(Memory.category, func.count())
            .where(Memory.status == MemoryStatus.CONFIRMED)
            .group_by(Memory.category)
        )
        return {MemoryCategory(category): count for category, count in rows}

    def export(self, as_markdown: bool) -> MemoryExport:
        memories = list(self.session.scalars(select(Memory).order_by(Memory.category, Memory.title)))
        if as_markdown:
            return MemoryExport(
                format="markdown",
                exported_at=utcnow(),
                count=len(memories),
                markdown=self._markdown(memories),
            )
        full = [
            ExportMemory(
                **self.detail(m.id).model_dump(),
                history=[RevisionOut.model_validate(r) for r in self.history(m.id)],
            )
            for m in memories
        ]
        return MemoryExport(format="json", exported_at=utcnow(), count=len(full), memories=full)

    @staticmethod
    def _markdown(memories: Iterable[Memory]) -> str:
        lines = ["# PAW memories", ""]
        category = ""
        for memory in memories:
            if memory.category != category:
                category = memory.category
                lines += [f"## {category.replace('_', ' ').capitalize()}", ""]
            lines += [f"### {memory.title}", "", memory.content, ""]
            lines += [f"_{memory.status}, updated {memory.updated_at:%Y-%m-%d}_", ""]
        return "\n".join(lines)

    def _save(self, memory: Memory, reason: str, proposal_id: str | None) -> None:
        self.session.flush()
        self.session.add(
            MemoryRevision(
                memory_id=memory.id,
                version=memory.version,
                snapshot={field: getattr(memory, field) for field in SNAPSHOT_FIELDS},
                change_reason=reason,
                proposal_id=proposal_id,
            )
        )
        self.activity.record(f"memory.{reason}", memory.id, version=memory.version)
        self.session.flush()
