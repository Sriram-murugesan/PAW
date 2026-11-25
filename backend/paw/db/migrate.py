"""Only the backend migrates. Other processes compare revisions and refuse on a mismatch."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from paw.core.errors import SchemaError
from paw.db.backup import BackupStore
from paw.db.database import Database

MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS).replace("%", "%%"))
    return config


def head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise SchemaError("No migrations found.")
    return head


def is_known_revision(revision: str | None) -> bool:
    scripts = ScriptDirectory.from_config(alembic_config())
    return revision in {s.revision for s in scripts.walk_revisions()}


def current_revision(database: Database) -> str | None:
    with database.engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade(database: Database, backups: BackupStore) -> None:
    current = current_revision(database)
    if current == head_revision():
        return
    if current is not None:
        if not is_known_revision(current):
            raise SchemaError("This database was created by a newer version of PAW.")
        backups.create("pre-migration")
    run(database, "head")


def run(database: Database, revision: str, *, down: bool = False) -> None:
    config = alembic_config()
    with database.write_engine.connect() as connection, connection.begin():
        config.attributes["connection"] = connection
        (command.downgrade if down else command.upgrade)(config, revision)
