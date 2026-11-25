from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from paw.models.enums import (
    MemoryCategory,
    MemoryStatus,
    ProposalOperation,
    ProposalStatus,
    ProposalTarget,
    SourceType,
)
from paw.schemas.common import Schema

Title = Annotated[str, Field(min_length=1, max_length=200)]
Content = Annotated[str, Field(min_length=1, max_length=20_000)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class SourceInput(Schema):
    source_type: SourceType
    source_id: Annotated[str, Field(max_length=200)] | None = None


class SourceOut(SourceInput):
    id: str
    reference_metadata: dict[str, Any]
    created_at: datetime


class MemoryCreate(Schema):
    category: MemoryCategory
    title: Title
    content: Content
    shareable: bool = True


class MemoryUpdate(MemoryCreate):
    version: int


class MemoryOut(Schema):
    id: str
    category: MemoryCategory
    title: str
    content: str
    confidence: float
    status: MemoryStatus
    shareable: bool
    version: int
    created_at: datetime
    updated_at: datetime


class MemoryDetail(MemoryOut):
    sources: list[SourceOut]


class RevisionOut(Schema):
    id: str
    version: int
    snapshot: dict[str, Any]
    change_reason: str
    proposal_id: str | None
    created_at: datetime


class MemoryChanges(Schema):
    """Fields a proposal may set. Sharing stays a user-only choice."""

    category: MemoryCategory | None = None
    title: Title | None = None
    content: Content | None = None

    def present(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class ProposalCreate(Schema):
    target_type: Literal[ProposalTarget.MEMORY] = ProposalTarget.MEMORY
    operation: ProposalOperation = ProposalOperation.CREATE
    target_id: str | None = None
    base_version: int | None = None
    payload: MemoryChanges = MemoryChanges()
    confidence: Confidence = 0.5
    source: SourceInput

    @model_validator(mode="after")
    def check_shape(self) -> "ProposalCreate":
        p = self.payload
        if self.operation == ProposalOperation.CREATE:
            if self.target_id or self.base_version:
                raise ValueError("CREATE takes no target_id or base_version")
            if not (p.category and p.title and p.content):
                raise ValueError("CREATE needs category, title and content")
        else:
            if not self.target_id or self.base_version is None:
                raise ValueError("UPDATE and ARCHIVE need target_id and base_version")
            if (self.operation == ProposalOperation.UPDATE) != bool(p.present()):
                raise ValueError("UPDATE needs changes and ARCHIVE takes none")
        return self


class ImportItem(Schema):
    category: MemoryCategory
    title: Title
    content: Content


class ProposalImport(Schema):
    items: Annotated[list[ImportItem], Field(min_length=1, max_length=500)]


class ImportOut(Schema):
    added: int
    skipped: int


class ProposalApprove(Schema):
    """`edits` corrects the proposal. `current_version` confirms the user saw a newer memory."""

    edits: MemoryChanges = MemoryChanges()
    current_version: int | None = None


class ProposalOut(Schema):
    id: str
    target_type: ProposalTarget
    operation: ProposalOperation
    target_id: str | None
    base_version: int | None
    payload: dict[str, Any]
    confidence: float
    status: ProposalStatus
    submitted_by: str
    created_at: datetime
    reviewed_at: datetime | None
    sources: list[SourceOut]
    possible_duplicates: list[str]


class ExportMemory(MemoryOut):
    sources: list[SourceOut]
    history: list[RevisionOut]


class MemoryExport(Schema):
    format: Literal["json", "markdown"]
    exported_at: datetime
    count: int
    memories: list[ExportMemory] | None = None
    markdown: str | None = None
