"""Locations of PAW's own data. Project repositories never live here."""

import os
from dataclasses import dataclass
from pathlib import Path

PRIVATE_DIR = 0o700
PRIVATE_FILE = 0o600


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @classmethod
    def default(cls) -> "DataPaths":
        xdg = os.environ.get("XDG_DATA_HOME", "")
        # The XDG specification says relative values must be ignored.
        base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "share"
        return cls(base / "paw")

    @property
    def database(self) -> Path:
        return self.root / "database" / "paw.db"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def lock(self) -> Path:
        return self.root / "backend.lock"

    def create(self) -> None:
        for path in (self.root, self.database.parent, self.backups, self.logs):
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(PRIVATE_DIR)
