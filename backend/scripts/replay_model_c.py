"""Explicit chronological Model C replay for selected or all sites."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import SiteDailyActivity
from backend.app.db.session import SessionLocal
from backend.app.services.model_c_replay_service import ModelCReplayService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD replay cutoff")
    parser.add_argument("--site-id", action="append", default=[])
    parser.add_argument("--commit-every", type=int, default=250)
    args = parser.parse_args()
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").date()
    db = SessionLocal()
    replay = ModelCReplayService()
    try:
        query = db.query(SiteDailyActivity.site_id).filter(
            SiteDailyActivity.acq_date <= cutoff
        ).distinct().order_by(SiteDailyActivity.site_id)
        if args.site_id:
            query = query.filter(SiteDailyActivity.site_id.in_(args.site_id))
        site_ids = [row[0] for row in query.all()]
        replayed_days = 0
        for index, site_id in enumerate(site_ids, 1):
            result = replay.replay_site(db, site_id, cutoff=cutoff)
            replayed_days += int(result["replayed_days"])
            if index % args.commit_every == 0:
                db.commit()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(json.dumps({"cutoff": args.cutoff, "sites": len(site_ids), "replayed_days": replayed_days}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
