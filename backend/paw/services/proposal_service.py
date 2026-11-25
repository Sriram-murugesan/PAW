"""Proposals are the only route from extracted information to permanent memory."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from paw.core.clock import utcnow
from paw.core.errors import ConflictError, NotFoundError
from paw.models import Memory, MemorySource, Proposal
from paw.models.enums import MemoryStatus, ProposalOperation, ProposalStatus, SourceType
from paw.schemas.memory import (
    ImportItem,
    ImportOut,
    MemoryChanges,
    ProposalApprove,
    ProposalCreate,
    ProposalOut,
    SourceInput,
    SourceOut,
)
from paw.services.activity_service import ActivityService
from paw.services.memory_service import MemoryService, content_hash
from paw.services.paging import newest_first


class ProposalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.memories = MemoryService(session)
        self.activity = ActivityService(session)

    def get(self, proposal_id: str) -> Proposal:
        proposal = self.session.get(Proposal, proposal_id)
        if proposal is None:
            raise NotFoundError("Proposal not found.")
        return proposal

    def list_page(
        self, *, status: ProposalStatus | None = None, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[Proposal], str | None]:
        query = select(Proposal)
        if status:
            query = query.where(Proposal.status == status)
        return newest_first(self.session, query, Proposal.created_at, Proposal.id, limit, cursor)

    def count_pending(self) -> int:
        query = select(func.count()).where(Proposal.status == ProposalStatus.PENDING)
        return self.session.scalar(query) or 0

    def present(self, proposal: Proposal) -> ProposalOut:
        duplicates = []
        if proposal.content_hash and proposal.status == ProposalStatus.PENDING:
            found = self.memories.duplicates(proposal.content_hash)
            duplicates = [m for m in found if m != proposal.target_id]
        return ProposalOut(
            **{f: getattr(proposal, f) for f in ProposalOut.model_fields if hasattr(Proposal, f)},
            sources=[SourceOut.model_validate(s) for s in self._sources(proposal)],
            possible_duplicates=duplicates,
        )

    def submit(self, data: ProposalCreate, submitted_by: str) -> Proposal:
        if data.target_id:
            self.memories.get(data.target_id)
        content = data.payload.content
        proposal = Proposal(
            target_type=data.target_type,
            operation=data.operation,
            target_id=data.target_id,
            base_version=data.base_version,
            payload=data.payload.present(),
            content_hash=content_hash(content) if content else None,
            confidence=data.confidence,
            submitted_by=submitted_by,
        )
        self.session.add(proposal)
        self.session.flush()
        self.session.add(MemorySource(proposal_id=proposal.id, **data.source.model_dump()))
        self.activity.record("proposal.submitted", proposal.id, submitted_by=submitted_by)
        self.session.flush()
        return proposal

    def import_items(self, items: list[ImportItem], submitted_by: str) -> ImportOut:
        """Add each item as a pending proposal, skipping text already known or already proposed."""
        query = select(Proposal.content_hash).where(Proposal.status == ProposalStatus.PENDING)
        known = set(self.session.scalars(query))
        added = 0
        for item in items:
            digest = content_hash(item.content)
            if digest in known or self.memories.duplicates(digest):
                continue
            known.add(digest)
            proposal = ProposalCreate(
                payload=MemoryChanges(**item.model_dump()),
                confidence=0.5,
                source=SourceInput(source_type=SourceType.SEED),
            )
            self.submit(proposal, submitted_by)
            added += 1
        return ImportOut(added=added, skipped=len(items) - added)

    def approve(self, proposal_id: str, data: ProposalApprove) -> Memory:
        proposal = self._pending(proposal_id)
        edits = data.edits.present()
        if proposal.operation == ProposalOperation.ARCHIVE and edits:
            raise ConflictError("An archive proposal cannot be edited.")
        values = {**proposal.payload, **edits}
        if proposal.operation == ProposalOperation.CREATE:
            # The user has verified it, so it is fully confident from here on.
            memory = self.memories.add(
                {**values, "confidence": 1.0}, reason="proposal_approved", proposal_id=proposal.id
            )
        else:
            memory = self._apply_to_existing(proposal, values, data.current_version)
        for source in self._sources(proposal):
            self.session.add(
                MemorySource(
                    memory_id=memory.id,
                    source_type=source.source_type,
                    source_id=source.source_id,
                    reference_metadata={**source.reference_metadata, "proposal_id": proposal.id},
                )
            )
        # Recorded so that deleting the memory also finds the proposal holding its text.
        proposal.target_id = memory.id
        self._decide(proposal, ProposalStatus.APPROVED)
        return memory

    def reject(self, proposal_id: str) -> Proposal:
        proposal = self._pending(proposal_id)
        self._decide(proposal, ProposalStatus.REJECTED)
        return proposal

    def _apply_to_existing(
        self, proposal: Proposal, values: dict[str, object], seen_version: int | None
    ) -> Memory:
        memory = self.memories.get(str(proposal.target_id))
        if memory.status == MemoryStatus.ARCHIVED:
            raise ConflictError("The memory is archived.")
        self.memories.check_version(memory, proposal.base_version if seen_version is None else seen_version)
        if proposal.operation == ProposalOperation.ARCHIVE:
            values = {"status": MemoryStatus.ARCHIVED}
        return self.memories.change(memory, values, reason="proposal_approved", proposal_id=proposal.id)

    def _pending(self, proposal_id: str) -> Proposal:
        proposal = self.get(proposal_id)
        if proposal.status != ProposalStatus.PENDING:
            raise ConflictError(f"The proposal is already {proposal.status.lower()}.")
        return proposal

    def _decide(self, proposal: Proposal, status: ProposalStatus) -> None:
        proposal.status = status
        proposal.reviewed_at = utcnow()
        self.activity.record(f"proposal.{status.lower()}", proposal.id)
        self.session.flush()

    def _sources(self, proposal: Proposal) -> list[MemorySource]:
        query = select(MemorySource).where(MemorySource.proposal_id == proposal.id)
        return list(self.session.scalars(query))
