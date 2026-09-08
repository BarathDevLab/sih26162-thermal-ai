"""Explicit, provenance-bearing Model A snapshot rebuild."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import SourceSite
from backend.app.db.session import SessionLocal
from backend.app.services.model_a_service import ModelAInputUnavailable, ModelAService
from backend.app.services.stack_readiness import get_shared_model_a


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD detection cutoff")
    parser.add_argument("--site-id", action="append", default=[])
    parser.add_argument("--commit-every", type=int, default=500)
    args = parser.parse_args()
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").date()
    service = ModelAService(engine=get_shared_model_a())
    db = SessionLocal()
    scored = 0
    unavailable = {}
    try:
        query = db.query(SourceSite.site_id).order_by(SourceSite.site_id)
        if args.site_id:
            query = query.filter(SourceSite.site_id.in_(args.site_id))
        site_ids = [row[0] for row in query.all()]
        for site_id in site_ids:
            try:
                service.score_site(db, site_id, cutoff=cutoff)
                scored += 1
            except ModelAInputUnavailable as exc:
                unavailable[site_id] = str(exc)
            if (scored + len(unavailable)) % args.commit_every == 0:
                db.commit()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(json.dumps({"cutoff": args.cutoff, "scored": scored, "unavailable": unavailable}, indent=2))
    return 0 if not unavailable else 2


if __name__ == "__main__":
    raise SystemExit(main())
