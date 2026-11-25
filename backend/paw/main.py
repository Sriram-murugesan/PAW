"""Backend process. The desktop app starts it, writes a token to stdin, and closes stdin to stop it.

Handshake: one token line in, one JSON line out. Nothing else is written to stdout.
"""

import argparse
import fcntl
import json
import logging
import os
import socket
import sys
import threading
from pathlib import Path
from typing import IO

import uvicorn

from paw.api.app import create_app
from paw.api.deps import Context
from paw.core.config import DataPaths
from paw.core.errors import PawError
from paw.core.logging import configure_logging, log_event
from paw.core.security import MIN_TOKEN_LENGTH
from paw.db import migrate
from paw.db.backup import BackupStore
from paw.db.database import Database

logger = logging.getLogger("paw.main")

EXIT_ALREADY_RUNNING = 3
EXIT_BAD_TOKEN = 4
EXIT_DATABASE = 5


def _emit(**event: object) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


class _Server(uvicorn.Server):
    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets)
        if sockets and not self.should_exit:
            _emit(event="ready", port=sockets[0].getsockname()[1], pid=os.getpid())


def _stop_at_eof(server: uvicorn.Server) -> None:
    """The desktop holds the other end of stdin, so EOF means it exited, even if it crashed."""
    while os.read(sys.stdin.fileno(), 4096):
        pass
    log_event(logger, "desktop_disconnected")
    server.should_exit = True


def _lock(path: Path) -> IO[str] | None:
    handle = path.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def serve(paths: DataPaths) -> int:
    os.umask(0o077)
    token = sys.stdin.buffer.readline(1024).decode("utf-8", "replace").strip()
    if len(token) < MIN_TOKEN_LENGTH:
        _emit(event="error", code="bad_token")
        return EXIT_BAD_TOKEN
    paths.create()
    configure_logging(paths.logs)
    lock = _lock(paths.lock)
    if lock is None:
        _emit(event="error", code="already_running")
        return EXIT_ALREADY_RUNNING
    with lock:
        database = Database(paths.database)
        try:
            backups = BackupStore(database, paths.backups)
            try:
                migrate.upgrade(database, backups)
            except Exception as error:
                logger.exception("migration_failed")
                code = error.code if isinstance(error, PawError) else "migration_failed"
                _emit(event="error", code=code)
                return EXIT_DATABASE
            _run(create_app(Context(database, backups), token))
        finally:
            database.close()
    return 0


def _run(app: object) -> None:
    config = uvicorn.Config(
        app,  # type: ignore[arg-type]
        log_config=None,
        access_log=False,
        server_header=False,
        timeout_graceful_shutdown=5,
    )
    server = _Server(config)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        threading.Thread(target=_stop_at_eof, args=(server,), daemon=True).start()
        server.run(sockets=[sock])
    log_event(logger, "stopped")


def main() -> None:
    parser = argparse.ArgumentParser(prog="paw-backend")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="run the local API for the desktop app")
    parser.parse_args()
    sys.exit(serve(DataPaths.default()))


if __name__ == "__main__":
    main()
