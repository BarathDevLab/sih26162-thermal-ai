"""Container entrypoint: initialize tables, apply idempotent migrations, start API."""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend.app.db.models  # noqa: F401 - registers SQLAlchemy metadata
from backend.app.db.session import engine, init_db


def main() -> None:
    init_db()
    if engine.url.drivername.startswith("postgresql"):
        connection = engine.raw_connection()
        try:
            for migration in sorted((ROOT / "backend/migrations").glob("*.sql")):
                connection.execute(migration.read_text(encoding="utf-8"))
                connection.commit()
        finally:
            connection.close()
    os.execvp(
        "uvicorn",
        ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )


if __name__ == "__main__":
    main()
