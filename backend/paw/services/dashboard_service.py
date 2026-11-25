from sqlalchemy.orm import Session

from paw.models.enums import MemoryStatus, ProposalStatus
from paw.schemas.system import ActivityOut, DashboardOut
from paw.services.activity_service import ActivityService
from paw.services.memory_service import MemoryService
from paw.services.proposal_service import ProposalService


def build_dashboard(session: Session) -> DashboardOut:
    memories = MemoryService(session)
    proposals = ProposalService(session)
    counts = memories.counts()
    latest, _ = proposals.list_page(status=ProposalStatus.PENDING, limit=5)
    recent, _ = ActivityService(session).list_page(limit=10)
    return DashboardOut(
        confirmed_memories=counts.get(MemoryStatus.CONFIRMED, 0),
        archived_memories=counts.get(MemoryStatus.ARCHIVED, 0),
        pending_proposals=proposals.count_pending(),
        memories_by_category=memories.counts_by_category(),
        latest_proposals=[proposals.present(p) for p in latest],
        recent_activity=[ActivityOut.model_validate(e) for e in recent],
    )
