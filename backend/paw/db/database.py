"""Engine, transactions and the gate that keeps requests out during a restore."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session

from paw.core.config import PRIVATE_FILE
from paw.core.errors import UnavailableError

_WRITE = "paw_write"


def _on_connect(dbapi_connection: Any, _record: Any) -> None:
    dbapi_connection.isolation_level = None  # SQLAlchemy emits BEGIN; see _on_begin
    for pragma in (
        "journal_mode=WAL",
        "foreign_keys=ON",
        "busy_timeout=10000",
        "synchronous=NORMAL",
        "secure_delete=ON",
    ):
        dbapi_connection.execute(f"PRAGMA {pragma}")


def _on_begin(connection: Connection) -> None:
    # Taking the write lock up front avoids a failed upgrade from read to write mid-transaction.
    write = connection.get_execution_options().get(_WRITE, False)
    connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        # Create with private permissions before SQLite would create it with the default ones.
        path.touch(mode=PRIVATE_FILE, exist_ok=True)
        path.chmod(PRIVATE_FILE)
        # hide_parameters keeps user content out of exception text.
        self.engine: Engine = create_engine(f"sqlite:///{path}", hide_parameters=True)
        event.listen(self.engine, "connect", _on_connect)
        event.listen(self.engine, "begin", _on_begin)
        self.write_engine = self.engine.execution_options(**{_WRITE: True})
        self._gate = threading.Condition()
        self._active = 0
        self._closed_for_maintenance = False

    @contextmanager
    def _session(self, engine: Engine) -> Iterator[Session]:
        with self._gate:
            if self._closed_for_maintenance:
                raise UnavailableError("PAW is restoring a backup. Try again shortly.")
            self._active += 1
        try:
            with Session(engine, expire_on_commit=False) as session, session.begin():
                yield session
        finally:
            with self._gate:
                self._active -= 1
                self._gate.notify_all()

    @contextmanager
    def read(self) -> Iterator[Session]:
        with self._session(self.engine) as session:
            yield session

    @contextmanager
    def write(self) -> Iterator[Session]:
        with self._session(self.write_engine) as session:
            yield session

    @contextmanager
    def maintenance(self, timeout: float = 15) -> Iterator[None]:
        """Refuse new sessions, wait for current ones, and drop pooled connections."""
        with self._gate:
            if self._closed_for_maintenance:
                raise UnavailableError("Another maintenance operation is running.")
            self._closed_for_maintenance = True
            if not self._gate.wait_for(lambda: self._active == 0, timeout):
                self._closed_for_maintenance = False
                raise UnavailableError("The database is busy. Try again shortly.")
        try:
            self.engine.dispose()
            yield
        finally:
            with self._gate:
                self._closed_for_maintenance = False

    @contextmanager
    def raw(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            yield connection
        finally:
            connection.close()

    def close(self) -> None:
        self.engine.dispose()
