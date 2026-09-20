"""Rebuild current materializations only from already audited FIRMS windows."""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.firms_client import DEFAULT_INDIA_BBOX, DEFAULT_PRIMARY_SOURCE
from backend.app.services.live_pipeline import run_global_daily_model_b_refresh


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-through", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source", default=DEFAULT_PRIMARY_SOURCE)
    parser.add_argument("--bbox", default=DEFAULT_INDIA_BBOX)
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Materialize only source sites missing Model A or Model C state.",
    )
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
        if args.missing_only:
            from backend.app.db.models import SiteModelA, SiteModelC, SourceSite
            missing_a = {
                row[0]
                for row in db.query(SourceSite.site_id)
                .outerjoin(SiteModelA, SiteModelA.site_id == SourceSite.site_id)
                .filter(SiteModelA.site_id.is_(None))
            }
            missing_c = {
                row[0]
                for row in db.query(SourceSite.site_id)
                .outerjoin(SiteModelC, SiteModelC.site_id == SourceSite.site_id)
                .filter(SiteModelC.site_id.is_(None))
            }
            missing = missing_a | missing_c
            logging.info("Materializing %d sites with missing A/C state.", len(missing))
            unavailable = orchestrator._refresh_2026_stack(
                db,
                target + timedelta(days=1),
                target,
                args.source,
                additional_site_ids=missing,
            )
        else:
            unavailable = orchestrator._refresh_2026_stack(db, start, target, args.source)
        if unavailable:
            raise RuntimeError(f"Model A unavailable for {len(unavailable)} touched sites.")
        orchestrator._verify_model_materialization(db)
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
