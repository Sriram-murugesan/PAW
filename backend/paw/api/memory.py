from typing import Annotated, Literal

from fastapi import APIRouter, Query

from paw.api.deps import IMPORT, USER, Ctx, Cursor, Id, Limit
from paw.models.enums import MemoryCategory, MemoryStatus, ProposalStatus
from paw.schemas.common import Item, Page
from paw.schemas.memory import (
    ImportOut,
    MemoryCreate,
    MemoryDetail,
    MemoryExport,
    MemoryOut,
    MemoryUpdate,
    ProposalApprove,
    ProposalCreate,
    ProposalImport,
    ProposalOut,
    RevisionOut,
)
from paw.services.memory_service import MemoryService
from paw.services.proposal_service import ProposalService

router = APIRouter(prefix="/api/memory", tags=["memory"])

# Fixed paths are declared before /{memory_id}.


@router.get("/export")
def export_memories(ctx: Ctx, format: Literal["json", "markdown"] = "json") -> Item[MemoryExport]:
    with ctx.database.read() as session:
        return Item(data=MemoryService(session).export(as_markdown=format == "markdown"))


@router.get("/proposals")
def list_proposals(
    ctx: Ctx, status: ProposalStatus | None = None, limit: Limit = 50, cursor: Cursor = None
) -> Page[ProposalOut]:
    with ctx.database.read() as session:
        service = ProposalService(session)
        rows, following = service.list_page(status=status, limit=limit, cursor=cursor)
        return Page(data=[service.present(p) for p in rows], next_cursor=following)


@router.post("/proposals", status_code=201)
def submit_proposal(ctx: Ctx, body: ProposalCreate) -> Item[ProposalOut]:
    with ctx.database.write() as session:
        service = ProposalService(session)
        return Item(data=service.present(service.submit(body, USER)))


@router.post("/proposals/import", status_code=201)
def import_proposals(ctx: Ctx, body: ProposalImport) -> Item[ImportOut]:
    with ctx.database.write() as session:
        return Item(data=ProposalService(session).import_items(body.items, IMPORT))


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(ctx: Ctx, proposal_id: Id, body: ProposalApprove | None = None) -> Item[MemoryDetail]:
    with ctx.database.write() as session:
        memory = ProposalService(session).approve(str(proposal_id), body or ProposalApprove())
        return Item(data=MemoryService(session).detail(memory.id))


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(ctx: Ctx, proposal_id: Id) -> Item[ProposalOut]:
    with ctx.database.write() as session:
        service = ProposalService(session)
        return Item(data=service.present(service.reject(str(proposal_id))))


@router.get("")
def list_memories(
    ctx: Ctx,
    status: MemoryStatus | None = None,
    category: MemoryCategory | None = None,
    q: Annotated[str | None, Query(max_length=500)] = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[MemoryOut]:
    with ctx.database.read() as session:
        rows, following = MemoryService(session).list_page(
            status=status, category=category, q=q, limit=limit, cursor=cursor
        )
        return Page(data=[MemoryOut.model_validate(m) for m in rows], next_cursor=following)


@router.post("", status_code=201)
def create_memory(ctx: Ctx, body: MemoryCreate) -> Item[MemoryDetail]:
    with ctx.database.write() as session:
        service = MemoryService(session)
        return Item(data=service.detail(service.create(body).id))


@router.get("/{memory_id}")
def get_memory(ctx: Ctx, memory_id: Id) -> Item[MemoryDetail]:
    with ctx.database.read() as session:
        return Item(data=MemoryService(session).detail(str(memory_id)))


@router.put("/{memory_id}")
def update_memory(ctx: Ctx, memory_id: Id, body: MemoryUpdate) -> Item[MemoryDetail]:
    with ctx.database.write() as session:
        service = MemoryService(session)
        return Item(data=service.detail(service.update(str(memory_id), body).id))


@router.delete("/{memory_id}", status_code=204)
def delete_memory(ctx: Ctx, memory_id: Id) -> None:
    with ctx.database.write() as session:
        MemoryService(session).delete(str(memory_id))


@router.post("/{memory_id}/archive")
def archive_memory(ctx: Ctx, memory_id: Id) -> Item[MemoryDetail]:
    return _set_status(ctx, memory_id, MemoryStatus.ARCHIVED)


@router.post("/{memory_id}/unarchive")
def unarchive_memory(ctx: Ctx, memory_id: Id) -> Item[MemoryDetail]:
    return _set_status(ctx, memory_id, MemoryStatus.CONFIRMED)


@router.get("/{memory_id}/history")
def memory_history(ctx: Ctx, memory_id: Id) -> Page[RevisionOut]:
    with ctx.database.read() as session:
        rows = MemoryService(session).history(str(memory_id))
        return Page(data=[RevisionOut.model_validate(r) for r in rows])


def _set_status(ctx: Ctx, memory_id: Id, status: MemoryStatus) -> Item[MemoryDetail]:
    with ctx.database.write() as session:
        service = MemoryService(session)
        return Item(data=service.detail(service.set_status(str(memory_id), status).id))
