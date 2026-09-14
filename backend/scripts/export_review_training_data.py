"""Export verified analyst adjudications as a versioned Model A research dataset.

This command never retrains or replaces the frozen production model. It exports
only latest, consensus-verified, high-confidence binary determinations that
captured the exact 33-feature snapshot reviewed by analysts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import SiteReview, SourceSite
from backend.app.db.session import SessionLocal


FEATURE_CONFIG = ROOT / "backend/config/model_a_features.json"
DEFAULT_OUTPUT_DIR = ROOT / "data/exports"


def export_verified_reviews(output_path: Path) -> int:
    config = json.loads(FEATURE_CONFIG.read_text(encoding="utf-8"))
    feature_names = list(config["ordered_features"])
    db = SessionLocal()
    try:
        rows = (
            db.query(SiteReview, SourceSite)
            .join(SourceSite, SiteReview.site_id == SourceSite.site_id)
            .order_by(
                SiteReview.site_id,
                SiteReview.reviewed_at.desc(),
                SiteReview.review_id.desc(),
            )
            .all()
        )
    finally:
        db.close()

    latest_by_site = {}
    seen_sites = set()
    for review, site in rows:
        if review.site_id in seen_sites:
            continue
        seen_sites.add(review.site_id)
        if not (
            review.training_eligible
            and review.consensus_status == "VERIFIED"
            and review.determination in {"INDUSTRIAL", "NONINDUSTRIAL"}
        ):
            continue
        features = review.feature_snapshot
        if not isinstance(features, dict) or set(feature_names).difference(features):
            continue
        latest_by_site[review.site_id] = {
            "site_id": review.site_id,
            "country": review.country,
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
            "review_label": review.determination,
            "review_confidence": review.confidence,
            "review_id": review.review_id,
            "reviewed_at": review.reviewed_at,
            "reviewed_by": review.reviewed_by,
            "evidence_refs": json.dumps(review.evidence_refs or [], sort_keys=True),
            "reason_codes": json.dumps(review.reason_codes or [], sort_keys=True),
            "model_a_original_class": review.model_a_class,
            "model_a_original_probability": review.model_a_probability,
            "model_a_original_decision": review.model_a_decision,
            "model_stack_version": review.model_stack_version,
            "feature_version": review.feature_version,
            **{name: features.get(name) for name in feature_names},
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_columns = [
        "site_id", "country", "latitude", "longitude", "review_label",
        "review_confidence", "review_id", "reviewed_at", "reviewed_by",
        "evidence_refs", "reason_codes", "model_a_original_class",
        "model_a_original_probability", "model_a_original_decision",
        "model_stack_version", "feature_version",
    ]
    frame = pd.DataFrame(latest_by_site.values(), columns=[*metadata_columns, *feature_names])
    if output_path.suffix.lower() == ".csv":
        frame.to_csv(output_path, index=False)
    else:
        frame.to_parquet(output_path, index=False)
    return len(frame)


def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"reviewed_model_a_training_{timestamp}.parquet",
    )
    args = parser.parse_args()
    count = export_verified_reviews(args.output.resolve())
    print(f"Exported {count} verified reviewed sites to {args.output.resolve()}")


if __name__ == "__main__":
    main()
