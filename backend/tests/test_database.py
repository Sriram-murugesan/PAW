import multiprocessing
import stat
import time
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from paw.core.config import DataPaths
from paw.core.errors import BackupError, NotFoundError, SchemaError, UnavailableError
from paw.db import migrate
from paw.db.backup import BackupStore
from paw.db.base import Base
from paw.db.database import Database
from paw.models import Memory, MemoryRevision, Proposal
from paw.schemas.memory import MemoryCreate
from paw.services.backup_service import BackupService
from paw.services.memory_service import MemoryService

NEW = MemoryCreate(category="general_preference", title="Style", content="Concept first")


def add(database: Database, title: str = "Style") -> str:
    with database.write() as s:
        return MemoryService(s).create(NEW.model_copy(update={"title": title})).id


def count(database: Database) -> int:
    with database.read() as s:
        return s.scalar(select(func.count()).select_from(Memory)) or 0


def test_connection_pragmas(database: Database) -> None:
    with database.read() as s:
        assert s.scalar(text("PRAGMA journal_mode")) == "wal"
        assert s.scalar(text("PRAGMA foreign_keys")) == 1
        assert s.scalar(text("PRAGMA busy_timeout")) == 10000


def test_data_is_private(database: Database, paths: DataPaths, store: BackupStore) -> None:
    add(database)
    backup = store.path(store.create().id)
    for d in (paths.root, paths.database.parent, paths.backups, paths.logs):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700
    for f in (paths.database, backup, *paths.database.parent.glob("paw.db-*")):
        assert stat.S_IMODE(f.stat().st_mode) == 0o600, f


def test_migration_matches_models(database: Database) -> None:
    with database.engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []


def test_migration_down_and_up(database: Database) -> None:
    migrate.run(database, "base", down=True)
    assert set(inspect(database.engine).get_table_names()) <= {"alembic_version"}
    migrate.run(database, "head")
    add(database)
    assert count(database) == 1


def test_refuses_newer_database(database: Database, store: BackupStore) -> None:
    with database.write() as s:
        s.execute(text("UPDATE alembic_version SET version_num='9999'"))
    with pytest.raises(SchemaError):
        migrate.upgrade(database, store)


def test_write_rolls_back_on_error(database: Database) -> None:
    with pytest.raises(RuntimeError), database.write() as s:
        MemoryService(s).create(NEW)
        raise RuntimeError
    assert count(database) == 0


def _write_many(path: Path, n: int) -> None:
    database = Database(path)
    for i in range(n):
        # Reading before writing fails with "database is locked" unless the lock is taken first.
        with database.write() as session:
            service = MemoryService(session)
            service.list_page(limit=5)
            time.sleep(0.002)
            service.create(NEW.model_copy(update={"title": f"m{i}"}))
    database.close()


def test_processes_write_concurrently(database: Database) -> None:
    ctx = multiprocessing.get_context("spawn")
    workers = [ctx.Process(target=_write_many, args=(database.path, 40)) for _ in range(3)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(60)
    assert [w.exitcode for w in workers] == [0, 0, 0]
    assert count(database) == 120


def proposal(**kw: object) -> Proposal:
    values = {
        "target_type": "MEMORY",
        "operation": "CREATE",
        "payload": {"a": 1},
        "confidence": 0.5,
        "submitted_by": "t",
    }
    return Proposal(**{**values, **kw})


def test_cannot_insert_decided_proposal(database: Database) -> None:
    with pytest.raises(IntegrityError, match="must be pending"), database.write() as s:
        s.add(proposal(status="APPROVED"))


@pytest.mark.parametrize(
    "sql", ["UPDATE proposals SET payload='{}'", "UPDATE proposals SET submitted_by='user'"]
)
def test_proposal_content_is_immutable(database: Database, sql: str) -> None:
    with database.write() as s:
        s.add(proposal())
    with pytest.raises(IntegrityError, match="immutable"), database.write() as s:
        s.execute(text(sql))


def test_proposal_is_decided_once(database: Database) -> None:
    with database.write() as s:
        s.add(proposal())
    with database.write() as s:
        s.execute(text("UPDATE proposals SET status='REJECTED'"))
    with pytest.raises(IntegrityError, match="already reviewed"), database.write() as s:
        s.execute(text("UPDATE proposals SET status='APPROVED'"))


def test_revisions_are_append_only(database: Database) -> None:
    add(database)
    with pytest.raises(IntegrityError, match="append-only"), database.write() as s:
        s.execute(text("UPDATE memory_revisions SET version=9"))


def test_backup_and_restore(database: Database, store: BackupStore) -> None:
    service = BackupService(database, store)
    add(database, "kept")
    backup = service.create()
    add(database, "later")
    safety = service.restore(backup.id)
    with database.read() as s:
        assert [m.title for m in s.scalars(select(Memory))] == ["kept"]
        assert s.scalar(text("PRAGMA journal_mode")) == "wal"
        assert s.scalar(select(func.count()).select_from(MemoryRevision)) == 1
    service.restore(safety.id)
    assert count(database) == 2


def test_restore_rejects_backup_without_schema(database: Database, store: BackupStore) -> None:
    add(database)
    migrate.run(database, "base", down=True)
    with database.write() as s:
        s.execute(text("INSERT INTO alembic_version VALUES ('0001')"))
        s.execute(text("DELETE FROM alembic_version"))
    empty = store.create()
    with pytest.raises(BackupError, match="no schema version"):
        BackupService(database, store).restore(empty.id)


def test_failed_restore_keeps_data(
    database: Database, store: BackupStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = BackupService(database, store)
    backup = service.create()
    add(database, "current")
    monkeypatch.setattr(migrate, "current_revision", lambda _: "old")
    monkeypatch.setattr(migrate, "run", lambda *_: 1 / 0)
    with pytest.raises(BackupError, match="put back"):
        service.restore(backup.id)
    assert count(database) == 1


def test_restore_rejects_bad_files(database: Database, store: BackupStore, tmp_path: Path) -> None:
    service = BackupService(database, store)
    good = store.create()
    store.path(good.id).write_bytes(b"not a database" * 100)
    with pytest.raises(BackupError):
        service.restore(good.id)
    newer = store.create()
    import sqlite3

    c = sqlite3.connect(store.path(newer.id))
    c.execute("UPDATE alembic_version SET version_num='9999'")
    c.commit()
    c.close()
    with pytest.raises(BackupError, match="newer"):
        service.restore(newer.id)
    for bad in ("../paw", "x", "../../etc/passwd", ""):
        with pytest.raises(NotFoundError):
            service.restore(bad)


def test_backup_symlink_is_ignored(store: BackupStore, tmp_path: Path) -> None:
    real = store.create()
    link = store.directory / f"{real.id[:-8]}00000000.db"
    link.symlink_to(store.path(real.id))
    assert [b.id for b in store.list_all()] == [real.id]
    with pytest.raises(NotFoundError):
        store.path(link.stem)


def test_maintenance_refuses_new_sessions(database: Database) -> None:
    with database.maintenance(), pytest.raises(UnavailableError), database.read():
        pass
    assert count(database) == 0


def test_maintenance_times_out_when_busy(database: Database) -> None:
    with database.read(), pytest.raises(UnavailableError), database.maintenance(timeout=0.05):
        pass
    assert count(database) == 0
