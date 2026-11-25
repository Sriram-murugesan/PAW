from alembic import context
from sqlalchemy import Connection, create_engine

import paw.models  # noqa: F401 - registers tables
from paw.db.base import Base


def migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


supplied = context.config.attributes.get("connection")
if supplied is not None:
    migrate(supplied)
else:
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Run migrations through paw.db.migrate.")
    with create_engine(url).begin() as dev_connection:
        migrate(dev_connection)
