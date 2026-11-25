"""Structured logs holding events, ids and counts. Never log bodies, query strings or tokens."""

import json
import logging
import os
import sys
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from paw.core.config import PRIVATE_FILE

_FIELDS = "paw_fields"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            **getattr(record, _FIELDS, {}),
        }
        if record.exc_info and record.exc_info[0]:
            # Type and location only: exception messages can contain user content.
            entry["exception"] = record.exc_info[0].__name__
            frames = []
            tb = record.exc_info[2]
            while tb:
                frames.append(f"{Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}")
                tb = tb.tb_next
            entry["trace"] = frames[-8:]
        return json.dumps(entry)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, event, extra={_FIELDS: fields})


def _private_opener(path: str, flags: int) -> int:
    return os.open(path, flags, PRIVATE_FILE)


class _PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self) -> Any:
        opener: Callable[[str, int], int] = _private_opener
        return open(self.baseFilename, self.mode, encoding="utf-8", opener=opener)


def configure_logging(directory: Path) -> None:
    handlers: list[logging.Handler] = [
        _PrivateRotatingFileHandler(directory / "paw.log", maxBytes=1_000_000, backupCount=3),
        logging.StreamHandler(sys.stderr),  # stdout carries the startup handshake
    ]
    for handler in handlers:
        handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
