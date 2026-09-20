"""Repair NOAA-20 observations duplicated across NRT and standard delivery.

The deterministic detection id intentionally includes the delivery source.  Older
deployments could therefore ingest the same physical observation twice when a
date rolled from VIIRS_NOAA20_NRT into VIIRS_NOAA20_SP.  This maintenance tool
removes only exact cross-delivery matches, restores invalid candidate promotions,
and rematerializes the affected A/B/C states in one transaction.

The command is read-only unless ``--apply`` is supplied.  Applying a repair also
requires a verified database backup path.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.models import StackSnapshot
from backend.app.db.session import SessionLocal
from backend.app.services.backfill_firms_2026 import BackfillOrchestrator
from backend.app.services.firms_client import DEFAULT_PRIMARY_SOURCE
from backend.app.services.live_pipeline import LivePipelineService
from backend.app.services.model_a_service import ModelAInputUnavailable


logger = logging.getLogger(__name__)
ADVISORY_LOCK_ID = 261622026


CREATE_DUPLICATE_TABLE = """
CREATE TEMP TABLE repair_noaa20_duplicates AS
SELECT DISTINCT ON (sp.detection_id)
       sp.detection_id AS duplicate_id,
       nrt.detection_id AS canonical_id,
       sp.source_site_id AS duplicate_site_id,
       nrt.source_site_id AS canonical_site_id,
       sp.acq_date
FROM firms_detections sp
JOIN firms_detections nrt
  ON nrt.source_sensor = 'VIIRS_NOAA20_NRT'
 AND nrt.satellite = sp.satellite
 AND round(nrt.latitude::numeric, 4) = round(sp.latitude::numeric, 4)
 AND round(nrt.longitude::numeric, 4) = round(sp.longitude::numeric, 4)
 AND nrt.acq_date = sp.acq_date
 AND lpad(nrt.acq_time, 4, '0') = lpad(sp.acq_time, 4, '0')
WHERE sp.source_sensor = 'VIIRS_NOAA20_SP'
  AND sp.ingested_at >= :since
ORDER BY sp.detection_id, nrt.ingested_at, nrt.detection_id
"""


def _scalar(db, statement: str, **params: Any) -> int:
    return int(db.execute(text(statement), params).scalar() or 0)


def _prepare_audit_tables(db, since: datetime) -> None:
    db.execute(text(CREATE_DUPLICATE_TABLE), {"since": since})
    db.execute(text(
        "CREATE UNIQUE INDEX ON repair_noaa20_duplicates (duplicate_id)"
    ))
    db.execute(text("""
        CREATE TEMP TABLE repair_affected_site_days AS
        SELECT DISTINCT duplicate_site_id AS site_id, acq_date
        FROM repair_noaa20_duplicates
        WHERE duplicate_site_id IS NOT NULL
    """))
    db.execute(text("""
        CREATE TEMP TABLE repair_affected_candidates AS
        SELECT DISTINCT csd.candidate_id
        FROM candidate_source_detections csd
        JOIN repair_noaa20_duplicates d ON d.duplicate_id = csd.detection_id
    """))
    db.execute(text("""
        CREATE TEMP TABLE repair_affected_promotions AS
        SELECT DISTINCT c.candidate_id, c.promoted_site_id AS site_id
        FROM candidate_sources c
        JOIN repair_affected_candidates a ON a.candidate_id = c.candidate_id
        WHERE c.status = 'PROMOTED' AND c.promoted_site_id IS NOT NULL
    """))
    db.execute(text("""
        CREATE TEMP TABLE repair_invalid_promotions AS
        SELECT p.candidate_id, p.site_id
        FROM repair_affected_promotions p
        LEFT JOIN firms_detections fd ON fd.source_site_id = p.site_id
        LEFT JOIN repair_noaa20_duplicates d ON d.duplicate_id = fd.detection_id
        GROUP BY p.candidate_id, p.site_id
        HAVING count(fd.detection_id) FILTER (WHERE d.duplicate_id IS NULL) < 3
    """))
    db.execute(text("""
        CREATE TEMP TABLE repair_affected_sites AS
        SELECT DISTINCT duplicate_site_id AS site_id
        FROM repair_noaa20_duplicates WHERE duplicate_site_id IS NOT NULL
        UNION
        SELECT site_id FROM repair_invalid_promotions
    """))


def _audit(db) -> Dict[str, int]:
    return {
        "duplicate_rows": _scalar(db, "SELECT count(*) FROM repair_noaa20_duplicates"),
        "affected_sites": _scalar(db, "SELECT count(*) FROM repair_affected_sites"),
        "affected_candidates": _scalar(db, "SELECT count(*) FROM repair_affected_candidates"),
        "affected_promotions": _scalar(db, "SELECT count(*) FROM repair_affected_promotions"),
        "invalid_promotions": _scalar(db, "SELECT count(*) FROM repair_invalid_promotions"),
        "protected_reviews": _scalar(db, """
            SELECT count(*) FROM site_reviews r
            JOIN repair_invalid_promotions p ON p.site_id = r.site_id
        """),
        "protected_reference_labels": _scalar(db, """
            SELECT count(*) FROM site_reference_labels r
            JOIN repair_invalid_promotions p ON p.site_id = r.site_id
        """),
    }


def _apply_relational_repair(db, since: datetime) -> List[str]:
    # Remove alert decisions produced by the bad rows. Human-reviewed alerts are
    # protected by the precondition check in main.
    db.execute(text("""
        DELETE FROM alerts a
        USING repair_affected_sites s
        WHERE a.site_id = s.site_id AND a.created_at >= :since
    """), {"since": since})
    db.execute(text("""
        DELETE FROM site_model_a_history h
        USING repair_affected_sites s
        WHERE h.site_id = s.site_id AND h.computed_at >= :since
    """), {"since": since})

    db.execute(text("""
        DELETE FROM candidate_source_detections csd
        USING repair_noaa20_duplicates d
        WHERE csd.detection_id = d.duplicate_id
    """))
    db.execute(text("""
        DELETE FROM firms_detections fd
        USING repair_noaa20_duplicates d
        WHERE fd.detection_id = d.duplicate_id
    """))

    # A promotion that now has fewer than the frozen min_samples=3 is undone.
    # Its surviving observations go back into the original candidate pool.
    db.execute(text("""
        INSERT INTO candidate_source_detections
            (candidate_id, detection_id, latitude, longitude, observed_at)
        SELECT p.candidate_id, fd.detection_id, fd.latitude, fd.longitude,
               fd.acq_date::timestamp AT TIME ZONE 'UTC'
        FROM repair_invalid_promotions p
        JOIN firms_detections fd ON fd.source_site_id = p.site_id
        ON CONFLICT (candidate_id, detection_id) DO NOTHING
    """))
    db.execute(text("""
        UPDATE firms_detections fd
        SET source_site_id = NULL,
            resolution_status = 'CANDIDATE_ACCUMULATED',
            is_ambiguous = false,
            candidate_site_ids = NULL,
            assignment_distance_m = NULL
        FROM repair_invalid_promotions p
        WHERE fd.source_site_id = p.site_id
    """))

    # Delete materializations for invalid transient sites before deleting the
    # source-site row. Reviews/reference labels are forbidden by precondition.
    for table_name in (
        "imagery_cache",
        "site_daily_inference",
        "site_model_c",
        "site_model_b_history",
        "site_model_b",
        "site_model_a_features",
        "site_model_a_history",
        "site_model_a",
        "site_daily_activity",
        "alerts",
    ):
        db.execute(text(f"""
            DELETE FROM {table_name} row
            USING repair_invalid_promotions p
            WHERE row.site_id = p.site_id
        """))

    db.execute(text("""
        UPDATE candidate_sources c
        SET status = 'ACCUMULATING', promoted_site_id = NULL
        FROM repair_invalid_promotions p
        WHERE c.candidate_id = p.candidate_id
    """))
    db.execute(text("""
        DELETE FROM source_sites s
        USING repair_invalid_promotions p
        WHERE s.site_id = p.site_id
    """))

    # Promotions that remain physically valid keep their site. Restore a
    # three-member promotion audit trail if the removed duplicate was one of
    # the original promotion members.
    db.execute(text("""
        WITH ranked AS (
            SELECT p.candidate_id, fd.detection_id, fd.latitude, fd.longitude,
                   fd.acq_date::timestamp AT TIME ZONE 'UTC' AS observed_at,
                   row_number() OVER (
                       PARTITION BY p.candidate_id
                       ORDER BY fd.acq_date, fd.acq_time, fd.ingested_at, fd.detection_id
                   ) AS member_rank
            FROM repair_affected_promotions p
            LEFT JOIN repair_invalid_promotions bad
                   ON bad.candidate_id = p.candidate_id
            JOIN firms_detections fd ON fd.source_site_id = p.site_id
            WHERE bad.candidate_id IS NULL
        )
        INSERT INTO candidate_source_detections
            (candidate_id, detection_id, latitude, longitude, observed_at)
        SELECT candidate_id, detection_id, latitude, longitude, observed_at
        FROM ranked WHERE member_rank <= 3
        ON CONFLICT (candidate_id, detection_id) DO NOTHING
    """))

    # Recompute all affected candidate counts and centroids from surviving
    # membership, then remove empty accumulating candidates.
    db.execute(text("""
        WITH stats AS (
            SELECT csd.candidate_id, count(*) AS member_count,
                   avg(csd.latitude) AS latitude, avg(csd.longitude) AS longitude
            FROM candidate_source_detections csd
            JOIN repair_affected_candidates a ON a.candidate_id = csd.candidate_id
            GROUP BY csd.candidate_id
        )
        UPDATE candidate_sources c
        SET detection_count = stats.member_count,
            latitude = stats.latitude,
            longitude = stats.longitude
        FROM stats WHERE c.candidate_id = stats.candidate_id
    """))
    db.execute(text("""
        WITH times AS (
            SELECT csd.candidate_id,
                   min(csd.observed_at) AS first_seen,
                   max(csd.observed_at) AS last_seen
            FROM candidate_source_detections csd
            JOIN repair_affected_candidates a ON a.candidate_id = csd.candidate_id
            GROUP BY csd.candidate_id
        )
        UPDATE candidate_sources c
        SET first_seen = times.first_seen, last_seen = times.last_seen
        FROM times WHERE c.candidate_id = times.candidate_id
    """))
    db.execute(text("""
        UPDATE source_sites s
        SET latitude = c.latitude,
            longitude = c.longitude,
            land_cover = NULL,
            feature_version = NULL
        FROM repair_affected_promotions p
        JOIN candidate_sources c ON c.candidate_id = p.candidate_id
        LEFT JOIN repair_invalid_promotions bad
               ON bad.candidate_id = p.candidate_id
        WHERE s.site_id = p.site_id AND bad.candidate_id IS NULL
    """))
    db.execute(text("""
        DELETE FROM candidate_sources c
        USING repair_affected_candidates a
        WHERE c.candidate_id = a.candidate_id
          AND c.status = 'ACCUMULATING'
          AND NOT EXISTS (
              SELECT 1 FROM candidate_source_detections csd
              WHERE csd.candidate_id = c.candidate_id
          )
    """))

    # Rebuild only site-days touched by removed observations.
    db.execute(text("""
        DELETE FROM site_daily_activity a
        USING repair_affected_site_days d
        WHERE a.site_id = d.site_id AND a.acq_date = d.acq_date
    """))
    db.execute(text("""
        INSERT INTO site_daily_activity
            (site_id, acq_date, detections, mean_frp, max_frp, updated_at)
        SELECT fd.source_site_id, fd.acq_date, count(*), avg(fd.frp), max(fd.frp), now()
        FROM firms_detections fd
        JOIN repair_affected_site_days d
          ON d.site_id = fd.source_site_id AND d.acq_date = fd.acq_date
        JOIN source_sites s ON s.site_id = fd.source_site_id
        GROUP BY fd.source_site_id, fd.acq_date
    """))
    db.execute(text("""
        DELETE FROM site_daily_inference i
        USING repair_affected_site_days d
        WHERE i.site_id = d.site_id AND i.acq_date = d.acq_date
          AND NOT EXISTS (
              SELECT 1 FROM site_daily_activity a
              WHERE a.site_id = i.site_id AND a.acq_date = i.acq_date
          )
    """))
    db.execute(text("""
        UPDATE source_sites s
        SET latest_seen = latest.acq_date
        FROM (
            SELECT fd.source_site_id AS site_id, max(fd.acq_date) AS acq_date
            FROM firms_detections fd
            JOIN repair_affected_sites a ON a.site_id = fd.source_site_id
            GROUP BY fd.source_site_id
        ) latest
        WHERE s.site_id = latest.site_id
    """))

    return [
        row[0]
        for row in db.execute(text("""
            SELECT a.site_id FROM repair_affected_sites a
            JOIN source_sites s ON s.site_id = a.site_id
            ORDER BY a.site_id
        """))
    ]


def _refresh_models(db, site_ids: List[str], target: date) -> None:
    pipeline = LivePipelineService()
    unavailable: Dict[str, str] = {}
    total = len(site_ids)
    for index, site_id in enumerate(site_ids, start=1):
        try:
            a_result = pipeline.model_a.score_site(
                db, site_id, cutoff=target, source_sensor=DEFAULT_PRIMARY_SOURCE
            )
        except ModelAInputUnavailable as exc:
            unavailable[site_id] = str(exc)
            a_result = None
        b_result = pipeline._refresh_model_b_site(db, site_id, target)
        c_result = pipeline.model_c_replay.replay_site(db, site_id, cutoff=target)
        if a_result is not None:
            pipeline._evaluate_alert(
                db,
                site_id,
                c_result.get("event_date") or target,
                a_result,
                b_result,
                c_result.get("latest") or {"status": "INSUFFICIENT_HISTORY"},
            )
        if index % 100 == 0 or index == total:
            logger.info("Rematerialized corrected A/B/C state for %d/%d sites", index, total)
    if unavailable:
        examples = "; ".join(f"{key}: {value}" for key, value in list(unavailable.items())[:5])
        raise RuntimeError(
            f"Model A inputs are unavailable for {len(unavailable)} repaired sites: {examples}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        required=True,
        help="UTC ingestion timestamp at which the suspect standard-delivery run began.",
    )
    parser.add_argument("--target-date", required=True, help="Published operational cutoff date.")
    parser.add_argument("--apply", action="store_true", help="Apply the audited repair.")
    parser.add_argument("--backup", help="Verified pre-repair pg_dump path (required with --apply).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    target = date.fromisoformat(args.target_date)
    if args.apply:
        if not args.backup:
            raise SystemExit("--backup is required with --apply")
        backup = Path(args.backup).resolve()
        if not backup.is_file() or backup.stat().st_size == 0:
            raise SystemExit(f"Verified backup does not exist or is empty: {backup}")

    db = SessionLocal()
    acquired = False
    try:
        if db.get_bind().dialect.name != "postgresql":
            raise RuntimeError("This repair is PostgreSQL-only.")
        if args.apply:
            db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})
            acquired = True
            db.execute(text("""
                LOCK TABLE firms_detections, candidate_sources,
                           candidate_source_detections, source_sites
                IN SHARE ROW EXCLUSIVE MODE
            """))

        _prepare_audit_tables(db, since)
        audit = _audit(db)
        for key, value in audit.items():
            logger.info("%s=%d", key, value)
        if audit["protected_reviews"] or audit["protected_reference_labels"]:
            raise RuntimeError(
                "Repair stopped: an invalid transient site has protected human/reference data."
            )
        if not args.apply:
            db.rollback()
            logger.info("Dry audit complete; no database rows were changed.")
            return
        if audit["duplicate_rows"] == 0:
            raise RuntimeError("No matching duplicate rows were found; refusing an empty repair.")

        for snapshot in db.query(StackSnapshot).filter_by(status="CURRENT").all():
            snapshot.status = "REBUILDING"
        db.flush()
        affected_site_ids = _apply_relational_repair(db, since)
        db.expire_all()
        _refresh_models(db, affected_site_ids, target)

        # Coverage was not removed: the standard-delivery windows remain audited,
        # and only their duplicate physical observations were discarded.
        orchestrator = BackfillOrchestrator()
        orchestrator._verify_database_coverage(
            db, date(2026, 1, 1), target, DEFAULT_PRIMARY_SOURCE, "67,6,98,38"
        )
        snapshot = orchestrator._publish_snapshot(db, target, DEFAULT_PRIMARY_SOURCE)
        db.commit()
        logger.info(
            "Repair complete: removed %d duplicates, demoted %d invalid sites, "
            "refreshed %d surviving sites, snapshot=%s.",
            audit["duplicate_rows"],
            audit["invalid_promotions"],
            len(affected_site_ids),
            snapshot.snapshot_id,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        if acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})
            except Exception:
                logger.exception("Could not release repair advisory lock")
        db.close()


if __name__ == "__main__":
    main()
