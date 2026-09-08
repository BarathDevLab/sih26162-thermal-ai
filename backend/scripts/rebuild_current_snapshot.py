"""Rebuild current materializations only from already audited FIRMS windows."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.firms_client import DEFAULT_INDIA_BBOX, DEFAULT_PRIMARY_SOURCE
from backend.app.services.live_pipeline import run_global_daily_model_b_refresh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-through", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source", default=DEFAULT_PRIMARY_SOURCE)
    parser.add_argument("--bbox", default=DEFAULT_INDIA_BBOX)
    args = parser.parse_args()
    target = datetime.strptime(args.data_through, "%Y-%m-%d").date()
    start = datetime.strptime("2026-01-01", "%Y-%m-%d").date()
    orchestrator = BackfillOrchestrator()
    orchestrator._verify_required_bootstrap_files()
    db = SessionLocal()
    try:
        orchestrator._verify_database_bootstrap(db)
        orchestrator._verify_database_coverage(db, start, target, args.source, args.bbox)
        run_global_daily_model_b_refresh(db, target)
        unavailable = orchestrator._refresh_2026_stack(db, start, target, args.source)
        if unavailable:
            raise RuntimeError(f"Model A unavailable for {len(unavailable)} touched sites.")
        snapshot = orchestrator._publish_snapshot(db, target, args.source)
        db.commit()
        result = {"snapshot_id": snapshot.snapshot_id, "data_through_date": args.data_through}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
