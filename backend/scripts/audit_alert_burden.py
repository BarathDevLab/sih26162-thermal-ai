"""Audit operational alert volume and claims after publishing a current stack."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import Alert, SiteModelA, StackSnapshot
from backend.app.db.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit current-stack alert burden")
    parser.add_argument(
        "--output",
        default="data/backfill_2026/alert_burden_audit.json",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        snapshot = (
            db.query(StackSnapshot)
            .filter_by(status="CURRENT")
            .order_by(StackSnapshot.data_through_date.desc())
            .first()
        )
        if snapshot is None:
            raise RuntimeError("A CURRENT stack snapshot is required before alert-burden audit.")

        start = date(2026, 1, 1)
        target = snapshot.data_through_date
        alerts = db.query(Alert).filter(
            Alert.site_day >= start,
            Alert.site_day <= target,
        ).all()
        by_type = Counter(row.alert_type for row in alerts)
        by_level = Counter(row.alert_level for row in alerts)
        by_day = Counter(row.site_day.isoformat() for row in alerts)
        daily_counts = sorted(by_day.values())
        high_critical = sum(
            count for level, count in by_level.items() if level in {"HIGH", "CRITICAL"}
        )

        industrial_claim_violations = (
            db.query(func.count(Alert.alert_id))
            .join(SiteModelA, SiteModelA.site_id == Alert.site_id)
            .filter(
                Alert.site_day >= start,
                Alert.site_day <= target,
                Alert.alert_type.in_((
                    "CRITICAL_INDUSTRIAL_ANOMALY",
                    "HIGH_INDUSTRIAL_ANOMALY",
                    "INDUSTRIAL_REACTIVATION_ANOMALY",
                    "INDUSTRIAL_ELEVATION",
                    "NORMAL_INDUSTRIAL_OPERATION",
                )),
                SiteModelA.class_name != "INDUSTRIAL",
            )
            .scalar()
        )

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_id": snapshot.snapshot_id,
            "model_stack_version": snapshot.model_stack_version,
            "period": {"start": start.isoformat(), "end": target.isoformat()},
            "total_alerts": len(alerts),
            "distinct_sites": len({row.site_id for row in alerts}),
            "high_or_critical": high_critical,
            "evidence_required": sum(bool(row.evidence_required) for row in alerts),
            "by_level": dict(sorted(by_level.items())),
            "by_type": dict(sorted(by_type.items())),
            "daily_burden": {
                "days_with_alerts": len(daily_counts),
                "mean": statistics.fmean(daily_counts) if daily_counts else 0.0,
                "median": statistics.median(daily_counts) if daily_counts else 0.0,
                "maximum": max(daily_counts, default=0),
            },
            "claims_checks": {
                "industrial_alert_on_nonindustrial_or_unknown_site": int(
                    industrial_claim_violations or 0
                ),
                "passed": not industrial_claim_violations,
            },
        }
    finally:
        db.close()

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
