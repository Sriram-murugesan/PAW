from paw.core.errors import BackupError, PawError
from paw.db import migrate
from paw.db.backup import Backup, BackupStore
from paw.db.database import Database
from paw.services.activity_service import ActivityService


class BackupService:
    def __init__(self, database: Database, store: BackupStore) -> None:
        self.database = database
        self.store = store

    def list_all(self) -> list[Backup]:
        return self.store.list_all()

    def create(self) -> Backup:
        backup = self.store.create("manual")
        with self.database.write() as session:
            ActivityService(session).record("backup.created", size_bytes=backup.size_bytes)
        return backup

    def restore(self, backup_id: str) -> Backup:
        """Replace the database. Returns the safety backup taken just before."""
        if not migrate.is_known_revision(self.store.verify(backup_id)):
            raise BackupError("The backup was created by a newer version of PAW.")
        with self.database.maintenance():
            safety = self.store.create("pre-restore")
            try:
                self.store.copy_into_database(backup_id)
                if migrate.current_revision(self.database) != migrate.head_revision():
                    migrate.run(self.database, "head")
            except Exception as error:
                self.store.copy_into_database(safety.id)
                if isinstance(error, PawError):
                    raise
                raise BackupError("Restore failed. Your data was put back as it was.") from error
            finally:
                self.database.engine.dispose()
        with self.database.write() as session:
            ActivityService(session).record("backup.restored")
        return safety
