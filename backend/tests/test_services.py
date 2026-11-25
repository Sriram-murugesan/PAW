import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from paw.core.errors import ConflictError, NotFoundError, VersionConflictError
from paw.db.database import Database
from paw.models import ActivityEvent, Memory, MemoryRevision, MemorySource, Proposal
from paw.models.enums import MemoryStatus, ProposalStatus
from paw.schemas.memory import ImportItem, MemoryCreate, MemoryUpdate, ProposalApprove, ProposalCreate
from paw.schemas.system import ProfileUpdate, Settings
from paw.services.memory_service import MemoryService, content_hash
from paw.services.profile_service import ProfileService
from paw.services.proposal_service import ProposalService
from paw.services.settings_service import SettingsService

MARK = "zebra-canary"


def make(**kw: object) -> MemoryCreate:
    return MemoryCreate(**{"category": "technical_skill", "title": "T", "content": MARK, **kw})


def new_proposal(**kw: object) -> ProposalCreate:
    base = {
        "payload": {"category": "achievement", "title": "P", "content": MARK},
        "source": {"source_type": "conversation", "source_id": "c1"},
    }
    return ProposalCreate.model_validate({**base, **kw})


def change(memory: Memory, operation: str = "UPDATE", **payload: str) -> ProposalCreate:
    return new_proposal(
        operation=operation, target_id=memory.id, base_version=memory.version, payload=payload
    )


def test_create_records_revision_and_source(database: Database) -> None:
    with database.write() as s:
        m = MemoryService(s).create(make())
        assert (m.status, m.version, m.confidence) == ("CONFIRMED", 1, 1.0)
        assert [r.change_reason for r in MemoryService(s).history(m.id)] == ["created"]
        assert [x.source_type for x in MemoryService(s).sources(m.id)] == ["manual"]


def test_update_needs_current_version(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        m = service.create(make())
        update = MemoryUpdate(**make(title="New").model_dump(), version=1)
        assert service.update(m.id, update).version == 2
        with pytest.raises(VersionConflictError) as e:
            service.update(m.id, update)
        assert e.value.details["current"]["title"] == "New"
        assert [r.snapshot["title"] for r in service.history(m.id)] == ["New", "T"]


def test_unchanged_update_adds_no_revision(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        m = service.create(make())
        service.update(m.id, MemoryUpdate(**make().model_dump(), version=1))
        assert m.version == 1 and len(service.history(m.id)) == 1


def test_archive_and_unarchive(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        m = service.create(make())
        service.set_status(m.id, MemoryStatus.ARCHIVED)
        with pytest.raises(ConflictError):
            service.set_status(m.id, MemoryStatus.ARCHIVED)
        service.set_status(m.id, MemoryStatus.CONFIRMED)
        assert m.version == 3


def test_delete_leaves_no_copy_of_the_text(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        created = p.approve(p.submit(new_proposal(), "agent").id, ProposalApprove())
        p.submit(change(created, content=f"{MARK} two"), "agent")
        MemoryService(s).delete(created.id)
    with database.read() as s:
        for model in (Memory, MemoryRevision, MemorySource, Proposal):
            assert s.scalar(select(func.count()).select_from(model)) == 0, model
        assert MARK not in str([e.event_metadata for e in s.scalars(select(ActivityEvent))])
    with database.write() as s, pytest.raises(NotFoundError):
        MemoryService(s).get(created.id)
    with database.raw() as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert MARK.encode() not in database.path.read_bytes()


def test_list_filters_and_escapes(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        service.create(make(title="100% done"))
        service.create(make(title="100 done", category="achievement"))
        assert [m.title for m in service.list_page(q="100%")[0]] == ["100% done"]
        assert service.list_page(q="_")[0] == []
        assert [m.title for m in service.list_page(category="achievement")[0]] == ["100 done"]
        assert service.list_page(status=MemoryStatus.ARCHIVED)[0] == []


def test_paging_visits_each_row_once(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        ids = {service.create(make(title=str(i))).id for i in range(7)}
        seen: list[str] = []
        cursor = None
        while True:
            rows, cursor = service.list_page(limit=3, cursor=cursor)
            seen += [m.id for m in rows]
            if not cursor:
                break
        assert len(seen) == 7 and set(seen) == ids


def test_proposal_changes_nothing_until_approved(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        proposal = p.submit(new_proposal(), "agent")
        assert MemoryService(s).list_page()[0] == []
        m = p.approve(proposal.id, ProposalApprove())
        assert (m.status, m.confidence, m.content) == ("CONFIRMED", 1.0, MARK)
        source = MemoryService(s).sources(m.id)[0]
        assert (source.source_type, source.source_id) == ("conversation", "c1")
        assert source.reference_metadata == {"proposal_id": proposal.id}
        assert MemoryService(s).history(m.id)[0].proposal_id == proposal.id


def test_approve_with_edits_keeps_original_proposal(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        proposal = p.submit(new_proposal(), "agent")
        m = p.approve(proposal.id, ProposalApprove.model_validate({"edits": {"title": "Fixed"}}))
        assert m.title == "Fixed" and proposal.payload["title"] == "P"


def test_reject_creates_nothing_and_is_final(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        proposal = p.submit(new_proposal(), "agent")
        p.reject(proposal.id)
        assert proposal.status == ProposalStatus.REJECTED and proposal.reviewed_at
        assert MemoryService(s).list_page()[0] == []
        for act in (lambda: p.approve(proposal.id, ProposalApprove()), lambda: p.reject(proposal.id)):
            with pytest.raises(ConflictError):
                act()


def test_stale_proposal_never_overwrites(database: Database) -> None:
    with database.write() as s:
        p, service = ProposalService(s), MemoryService(s)
        m = service.create(make())
        proposal = p.submit(change(m, content="from agent"), "agent")
        service.update(m.id, MemoryUpdate(**make(content="from user").model_dump(), version=1))
        with pytest.raises(VersionConflictError):
            p.approve(proposal.id, ProposalApprove())
        assert m.content == "from user" and proposal.status == "PENDING"
        p.approve(proposal.id, ProposalApprove(current_version=2))
        assert m.content == "from agent"
        assert service.history(m.id)[1].snapshot["content"] == "from user"


def test_archive_proposal(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        m = MemoryService(s).create(make())
        first, second = p.submit(change(m, "ARCHIVE"), "a"), p.submit(change(m, title="X"), "a")
        p.approve(first.id, ProposalApprove())
        assert m.status == "ARCHIVED"
        with pytest.raises(ConflictError, match="archived"):
            p.approve(second.id, ProposalApprove(current_version=2))


def test_duplicates_are_flagged_not_blocked(database: Database) -> None:
    with database.write() as s:
        p = ProposalService(s)
        m = MemoryService(s).create(make(content="Prefers  FastAPI"))
        payload = {"category": "achievement", "title": "x", "content": "prefers fastapi"}
        proposal = p.submit(new_proposal(payload=payload), "agent")
        assert p.present(proposal).possible_duplicates == [m.id]
        p.approve(proposal.id, ProposalApprove())


def test_content_hash_normalizes() -> None:
    assert content_hash(" \uff21 b\n") == content_hash("a  B")
    assert content_hash("a") != content_hash("b")


@pytest.mark.parametrize(
    "bad",
    [
        {"payload": {"title": "only"}},
        {"operation": "UPDATE"},
        {"operation": "ARCHIVE", "target_id": "x", "base_version": 1},
        {"operation": "UPDATE", "target_id": "x", "base_version": 1, "payload": {}},
        {"target_type": "PROJECT"},
        {"payload": {"category": "nope", "title": "a", "content": "b"}},
        {"payload": {"category": "achievement", "title": "a", "content": "b", "shareable": True}},
        {"confidence": 2},
    ],
)
def test_invalid_proposals(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        new_proposal(**bad)


def test_proposal_for_missing_memory(database: Database) -> None:
    with database.write() as s, pytest.raises(NotFoundError):
        ProposalService(s).submit(
            new_proposal(operation="ARCHIVE", target_id="x", base_version=1, payload={}), "a"
        )


def test_profile(database: Database) -> None:
    with database.write() as s:
        service = ProfileService(s)
        assert service.get().version == 0
        data = ProfileUpdate(display_name="A", profile_data={"Interests": ["RAG"]}, version=0)
        assert service.update(data).version == 1
        with pytest.raises(VersionConflictError):
            service.update(data)
    with database.read() as s:
        assert ProfileService(s).get().profile_data == {"Interests": ["RAG"]}


def test_settings(database: Database) -> None:
    with database.write() as s:
        assert SettingsService(s).get().theme == "dark"
        SettingsService(s).update(Settings(theme="light"))
        SettingsService(s).update(Settings(theme="system"))
        assert SettingsService(s).get().theme == "system"


def test_export(database: Database) -> None:
    with database.write() as s:
        service = MemoryService(s)
        service.create(make())
        full = service.export(as_markdown=False)
        assert full.memories and full.memories[0].history and full.memories[0].sources
        assert MARK in (service.export(as_markdown=True).markdown or "")


def test_import_adds_pending_proposals_once(database: Database) -> None:
    items = [
        ImportItem(category="career_goal", title="Goal", content="AI engineer"),
        ImportItem(category="career_goal", title="Same", content="ai  ENGINEER"),
        ImportItem(category="achievement", title="Known", content=MARK),
    ]
    with database.write() as s:
        MemoryService(s).create(make())
        p = ProposalService(s)
        assert p.import_items(items, "file import").model_dump() == {"added": 1, "skipped": 2}
        assert p.import_items(items, "file import").added == 0
        (proposal,), _ = p.list_page()
        assert (proposal.status, proposal.submitted_by) == ("PENDING", "file import")
        assert p.present(proposal).sources[0].source_type == "seed"
        assert len(MemoryService(s).list_page()[0]) == 1
