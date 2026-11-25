"""Print the API description, from which the interface's types are generated."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from paw.api.app import create_app
from paw.api.deps import Context
from paw.db.backup import BackupStore
from paw.db.database import Database

with TemporaryDirectory() as directory:
    database = Database(Path(directory) / "paw.db")
    app = create_app(Context(database, BackupStore(database, Path(directory))), "")
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    database.close()
