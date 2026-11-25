"""Backups use SQLite's online backup API: a file copy would miss data still in the WAL."""

import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from paw.core.clock import utcnow
from paw.core.config import PRIVATE_FILE
from paw.core.errors import BackupError, NotFoundError
from paw.db.base import new_id
from paw.db.database import Database

Reason = Literal["manual", "pre-migration", "pre-restore"]
_NAME = re.compile(r"^(\d{8}T\d{12}Z)_(manual|pre-migration|pre-restore)_[0-9a-f]{8}$")


@dataclass(frozen=True)
class Backup:
    id: str
    reason: str
    created_at: datetime
    size_bytes: int


class BackupStore:
    def __init__(self, database: Database, directory: Path) -> None:
        self.database = database
        self.directory = directory

    def create(self, reason: Reason = "manual") -> Backup:
        stamp = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        backup_id = f"{stamp}_{reason}_{new_id()[:8]}"
        target = self.directory / f"{backup_id}.db"
        partial = target.with_suffix(".partial")
        partial.touch(mode=PRIVATE_FILE)
        try:
            with self.database.raw() as source, closing(sqlite3.connect(partial)) as copy:
                source.backup(copy)
                copy.execute("PRAGMA journal_mode=DELETE")  # one self-contained file
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
        return self._describe(target)

    def list_all(self) -> list[Backup]:
        files = [f for f in self.directory.glob("*.db") if _NAME.match(f.stem) and self._is_plain(f)]
        return [self._describe(f) for f in sorted(files, reverse=True)]

    def path(self, backup_id: str) -> Path:
        target = self.directory / f"{backup_id}.db"
        if not _NAME.match(backup_id) or not self._is_plain(target):
            raise NotFoundError("Backup not found.")
        return target

    def verify(self, backup_id: str) -> str:
        """Return the backup's schema revision, or raise if it is damaged or not a PAW database."""
        try:
            with closing(sqlite3.connect(f"{self.path(backup_id).as_uri()}?mode=ro", uri=True)) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise BackupError("The backup is damaged.")
                if db.execute("PRAGMA foreign_key_check").fetchone():
                    raise BackupError("The backup has inconsistent records.")
                row = db.execute("SELECT version_num FROM alembic_version").fetchone()
        except sqlite3.DatabaseError as error:
            raise BackupError("The file is not a valid PAW backup.") from error
        if row is None:
            raise BackupError("The backup has no schema version.")
        return str(row[0])

    def copy_into_database(self, backup_id: str) -> None:
        """Replace the live content in one SQLite transaction, safe with other open processes."""
        with (
            closing(sqlite3.connect(f"{self.path(backup_id).as_uri()}?mode=ro", uri=True)) as source,
            self.database.raw() as live,
        ):
            source.backup(live)
            live.execute("PRAGMA journal_mode=WAL")

    @staticmethod
    def _is_plain(path: Path) -> bool:
        return path.is_file() and not path.is_symlink()

    @staticmethod
    def _describe(path: Path) -> Backup:
        match = _NAME.match(path.stem)
        if match is None:
            raise NotFoundError("Backup not found.")
        created = datetime.strptime(match[1], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
        return Backup(path.stem, match[2], created, path.stat().st_size)
