from collections.abc import Iterator
from pathlib import Path

import pytest

from paw.core.config import DataPaths
from paw.db import migrate
from paw.db.backup import BackupStore
from paw.db.database import Database


@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    paths = DataPaths(tmp_path / "paw")
    paths.create()
    return paths


@pytest.fixture
def database(paths: DataPaths) -> Iterator[Database]:
    database = Database(paths.database)
    migrate.upgrade(database, BackupStore(database, paths.backups))
    yield database
    database.close()


@pytest.fixture
def store(database: Database, paths: DataPaths) -> BackupStore:
    return BackupStore(database, paths.backups)
