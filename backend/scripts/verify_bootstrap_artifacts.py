"""CLI preflight for authoritative runtime artifacts and checksums."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.stack_readiness import run_stack_preflight
from backend.app.services.feature_validation import (
    feature_validation_issue,
    validate_feature_builder_snapshot,
)


def main() -> int:
    if feature_validation_issue() is not None:
        try:
            validate_feature_builder_snapshot()
        except (FileNotFoundError, ValueError) as exc:
            print(f"Feature validation failed: {exc}", file=sys.stderr)
    db = SessionLocal()
    try:
        report = run_stack_preflight(db)
    finally:
        db.close()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.can_start_live else 2


if __name__ == "__main__":
    raise SystemExit(main())
