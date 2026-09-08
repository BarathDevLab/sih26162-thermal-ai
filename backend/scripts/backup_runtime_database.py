"""Create a recoverable in-database copy before an authoritative rebuild."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, text


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema",
        default=f"backup_runtime_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", args.schema):
        raise ValueError("Backup schema must be a lowercase SQL identifier.")
    if engine.dialect.name != "postgresql":
        raise RuntimeError("In-database backup is supported only for PostgreSQL.")

    inspector = inspect(engine)
    tables = sorted(
        table for table in inspector.get_table_names(schema="public")
        if table != "spatial_ref_sys"
    )
    quote = engine.dialect.identifier_preparer.quote
    counts = {}
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {quote(args.schema)}"))
        for table in tables:
            connection.execute(text(
                f"CREATE TABLE {quote(args.schema)}.{quote(table)} "
                f"AS TABLE public.{quote(table)}"
            ))
            counts[table] = int(connection.execute(text(
                f"SELECT count(*) FROM {quote(args.schema)}.{quote(table)}"
            )).scalar_one())

    print(json.dumps({"schema": args.schema, "tables": counts}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
