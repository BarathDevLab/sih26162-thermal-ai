"""Transactional 2026 FIRMS backfill using the same path as live ingestion."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.db.models import (
    FirmsBackfillWindow,
    FirmsDetection,
    SiteModelA,
    SiteModelB,
    SourceSite,
    StackSnapshot,
)
from backend.app.db.session import SessionLocal
from backend.app.services.firms_client import (
    DEFAULT_INDIA_BBOX,
    DEFAULT_PRIMARY_SOURCE,
    FirmsClient,
)
from backend.app.services.live_pipeline import LivePipelineService, run_global_daily_model_b_refresh
from backend.app.services.model_a_service import LAND_COVER_FEATURES, ModelAInputUnavailable
from backend.app.services.feature_validation import feature_validation_issue
from backend.app.services.stack_readiness import (
    PROJECT_ROOT, REQUIRED_FILES, _active_manifest_issue, _verify_declared_checksums,
)


logger = logging.getLogger(__name__)
DEFAULT_CACHE_DIR = str(PROJECT_ROOT / "data" / "cache" / "firms")
MODEL_STACK_VERSION = os.environ.get("MODEL_STACK_VERSION", "2026-09-04-r1")
FEATURE_VERSION = "1.0"
RESOLVER_VERSION = "incremental-member-radius-750m-min3-v1"
NOAA20_STANDARD_SOURCE = "VIIRS_NOAA20_SP"
NOAA20_SOURCE_FAMILY = (NOAA20_STANDARD_SOURCE, DEFAULT_PRIMARY_SOURCE)


class BackfillOrchestrator:
    """Fetch contiguous FIRMS windows and commit each through LivePipelineService."""

    def __init__(
        self,
        firms_client: Optional[FirmsClient] = None,
        source_resolver=None,
        ingestion_service=None,
        bootstrap_sites_path: Optional[str] = None,
        daily_activity_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        session_factory=SessionLocal,
        pipeline: Optional[LivePipelineService] = None,
    ) -> None:
        # Retain legacy constructor parameters while making the database authoritative.
        del source_resolver, ingestion_service, bootstrap_sites_path, daily_activity_path
        self.client = firms_client or FirmsClient()
        self.output_dir = output_dir or str(PROJECT_ROOT / "data" / "backfill_2026")
        self.session_factory = session_factory
        self.pipeline = pipeline or LivePipelineService()

    @staticmethod
    def generate_5day_windows(start_date_str: str, end_date_str: str) -> List[Tuple[str, int]]:
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        if start > end:
            raise ValueError(f"start_date {start_date_str} is after end_date {end_date_str}")
        windows: List[Tuple[str, int]] = []
        current = start
        while current <= end:
            span = min(5, (end - current).days + 1)
            windows.append((current.isoformat(), span))
            current += timedelta(days=span)
        return windows

    def run_backfill(
        self,
        start_date: str = "2026-01-01",
        end_date: Optional[str] = None,
        source: str = DEFAULT_PRIMARY_SOURCE,
        bbox: str = DEFAULT_INDIA_BBOX,
        dry_run: bool = False,
        update_db: bool = False,
    ) -> Dict[str, Any]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        target = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
        if start != date(2026, 1, 1):
            raise ValueError("The operational 2026 backfill must start at 2026-01-01.")
        if target > date.today():
            raise ValueError("Backfill end date cannot be in the future.")
        if update_db and dry_run:
            raise ValueError("--dry-run and --update-db are mutually exclusive.")
        if update_db:
            logger.info("Verifying packaged runtime artifacts and database prerequisites...")
            self._verify_required_bootstrap_files()
            logger.info("Runtime artifact verification passed.")

        if self.client.offline_mode:
            windows = [
                (source, window_start, day_span)
                for window_start, day_span in self.generate_5day_windows(
                    start.isoformat(), target.isoformat()
                )
            ]
        else:
            logger.info("Checking NASA FIRMS source availability through %s...", target)
            availability = self.client.check_availability("all")
            windows = self.build_available_source_windows(start, target, source, availability)
        logger.info("Planned %d audited FIRMS windows.", len(windows))

        totals = {"fetched": 0, "unique": 0, "inserted": 0, "revised": 0,
                  "promoted": 0, "alerts": 0}
        degraded_a: Dict[str, str] = {}
        completed_windows: List[Dict[str, Any]] = []

        db: Optional[Session] = self.session_factory() if update_db else None
        try:
            model_refresh_start = start
            if db is not None:
                self._verify_database_bootstrap(db)
                baseline = (
                    db.query(StackSnapshot)
                    .filter(StackSnapshot.status.in_(("CURRENT", "REBUILDING")))
                    .order_by(StackSnapshot.data_through_date.desc())
                    .first()
                )
                if baseline is not None:
                    model_refresh_start = max(
                        start, baseline.data_through_date + timedelta(days=1)
                    )
                    logger.info(
                        "Incremental A/C refresh will cover sites active from %s through %s.",
                        model_refresh_start,
                        target,
                    )
                else:
                    logger.info(
                        "No prior runtime snapshot found; full A/C materialization is required."
                    )
            for index, (window_source, window_start, day_span) in enumerate(windows, 1):
                window_start_date = datetime.strptime(window_start, "%Y-%m-%d").date()
                window_end = min(target, window_start_date + timedelta(days=day_span - 1))
                if db is not None:
                    completed = db.query(FirmsBackfillWindow).filter_by(
                        source_sensor=window_source,
                        bbox=bbox,
                        window_start=window_start_date,
                        window_end=window_end,
                        status="COMPLETED",
                    ).one_or_none()
                    if completed is not None:
                        logger.info(
                            "[%d/%d] Skipping audited %s window %s..%s.",
                            index, len(windows), window_source, window_start, window_end,
                        )
                        completed_windows.append({
                            "source": window_source,
                            "start": window_start,
                            "days": day_span,
                            "records": completed.records_fetched,
                            "status": "ALREADY_COMPLETED",
                        })
                        continue
                self._require_offline_cache(window_start, day_span, window_source, bbox, dry_run)
                logger.info("[%d/%d] Fetching %s for %s (%d days).",
                            index, len(windows), window_source, window_start, day_span)
                rows = self.client.fetch_area_detections(
                    source=window_source, bbox=bbox, day_range=day_span, date=window_start
                )
                self._validate_window_payload(rows, window_start_date, window_end)
                totals["fetched"] += len(rows)
                window_result: Dict[str, Any] = {"status": "FETCHED", "processed_count": len(rows)}
                if db is not None:
                    window_result = self.pipeline.process_detections_batch(
                        rows,
                        db,
                        source_sensor=window_source,
                        as_of_date=window_end,
                        refresh_models=False,
                    )
                    totals["unique"] += int(window_result.get("unique_count", 0))
                    totals["inserted"] += int(window_result.get("inserted_count", 0))
                    totals["revised"] += int(window_result.get("revised_count", 0))
                    totals["promoted"] += int(window_result.get("promoted_count", 0))
                    totals["alerts"] += int(window_result.get("alerts_generated", 0))
                    degraded_a.update(window_result.get("model_a_unavailable", {}))
                    self._record_completed_window(
                        db, window_source, bbox, window_start_date, window_end, rows,
                    )
                completed_windows.append({
                    "source": window_source, "start": window_start,
                    "days": day_span, "records": len(rows),
                    "status": window_result["status"],
                })

            snapshot_status = "DRY_RUN" if dry_run else "FETCH_ONLY"
            snapshot_id = None
            if db is not None:
                logger.info("Refreshing deterministic Model B through %s...", target)
                run_global_daily_model_b_refresh(db, target)
                logger.info("Refreshing Model A/C for sites changed since %s...", model_refresh_start)
                degraded_a = self._refresh_2026_stack(
                    db, model_refresh_start, target, source
                )
                logger.info("Verifying audited FIRMS date coverage through %s...", target)
                self._verify_database_coverage(db, start, target, source, bbox)
                if degraded_a:
                    raise RuntimeError(
                        f"Backfill processed data but Model A lacked authoritative inputs for {len(degraded_a)} "
                        "sites; CURRENT snapshot was not published."
                    )
                logger.info("Publishing atomic CURRENT A/B/C snapshot through %s...", target)
                snapshot = self._publish_snapshot(db, target, source)
                db.commit()
                snapshot_id = snapshot.snapshot_id
                snapshot_status = snapshot.status
                logger.info("Backfill snapshot published with status %s.", snapshot_status)
        except Exception:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

        return {
            "start_date": start.isoformat(), "end_date": target.isoformat(),
            "total_windows": len(windows), "completed_windows": completed_windows,
            "total_fetched": totals["fetched"], "total_unique": totals["unique"],
            "total_inserted": totals["inserted"], "total_revised": totals["revised"],
            "total_promoted": totals["promoted"], "alerts_generated": totals["alerts"],
            "snapshot_id": snapshot_id, "snapshot_status": snapshot_status, "dry_run": dry_run,
        }

    @classmethod
    def build_available_source_windows(
        cls,
        start: date,
        target: date,
        source: str,
        availability: List[Dict[str, Any]],
    ) -> List[Tuple[str, str, int]]:
        """Plan complete <=5-day windows without querying outside source availability."""
        allowed = NOAA20_SOURCE_FAMILY if source == DEFAULT_PRIMARY_SOURCE else (source,)
        ranges: Dict[str, Tuple[date, date]] = {}
        for row in availability:
            data_id = str(row.get("data_id", "")).strip()
            if data_id not in allowed:
                continue
            try:
                min_date = datetime.strptime(str(row["min_date"]), "%Y-%m-%d").date()
                max_date = datetime.strptime(str(row["max_date"]), "%Y-%m-%d").date()
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"FIRMS returned invalid availability metadata for {data_id}."
                ) from exc
            ranges[data_id] = (min_date, max_date)

        if not ranges:
            raise RuntimeError(
                f"FIRMS availability contains no usable range for {', '.join(allowed)}."
            )

        planned: List[Tuple[str, str, int]] = []
        cursor = start
        while cursor <= target:
            eligible = [
                candidate
                for candidate in allowed
                if candidate in ranges and ranges[candidate][0] <= cursor <= ranges[candidate][1]
            ]
            if not eligible:
                raise RuntimeError(
                    f"No authoritative {source} family data are available for {cursor}; "
                    "the backfill cannot be declared complete."
                )

            # Prefer NRT during an overlap; use SP only as the archive bridge.
            window_source = source if source in eligible else eligible[0]
            source_end = min(target, ranges[window_source][1])
            day_span = min(5, (source_end - cursor).days + 1)
            planned.append((window_source, cursor.isoformat(), day_span))
            cursor += timedelta(days=day_span)
        return planned

    @staticmethod
    def _verify_required_bootstrap_files() -> None:
        missing = [relative for relative in REQUIRED_FILES if not (PROJECT_ROOT / relative).is_file()]
        if missing:
            raise FileNotFoundError("Required runtime/bootstrap artifacts are missing: " + ", ".join(missing))
        mismatches = _verify_declared_checksums()
        if mismatches:
            raise RuntimeError("Runtime artifact checksum mismatch: " + ", ".join(mismatches))
        manifest_issue = _active_manifest_issue()
        if manifest_issue:
            raise RuntimeError(manifest_issue)
        issue = feature_validation_issue()
        if issue:
            raise RuntimeError(issue)

    @staticmethod
    def _verify_database_bootstrap(db: Session) -> None:
        if db.query(SourceSite.site_id).first() is None:
            raise RuntimeError("Database has no frozen source-site bootstrap.")
        if db.query(FirmsDetection.detection_id).filter(FirmsDetection.acq_date < date(2026, 1, 1)).first() is None:
            raise RuntimeError("Database has no authoritative assigned pre-2026 FIRMS history.")
        if db.query(SiteModelA.site_id).first() is None:
            raise RuntimeError("Database has no genuine Model A bootstrap states.")

    def _require_offline_cache(self, window_start: str, day_span: int, source: str,
                               bbox: str, dry_run: bool) -> None:
        if not self.client.offline_mode or dry_run:
            return
        if self.client._read_cache(source, bbox, day_span, window_start) is None:
            raise FileNotFoundError(
                f"Offline backfill cache is missing window {window_start} ({day_span} days)."
            )

    @staticmethod
    def _validate_window_payload(rows: List[Dict[str, Any]], start: date, end: date) -> None:
        required = {"latitude", "longitude", "acq_date", "acq_time"}
        for index, row in enumerate(rows):
            missing = required - set(row)
            if missing:
                raise ValueError(f"FIRMS row {index} is missing required fields: {sorted(missing)}")
            observed = datetime.strptime(str(row["acq_date"])[:10], "%Y-%m-%d").date()
            if not start <= observed <= end:
                raise ValueError(
                    f"FIRMS returned {observed} outside requested window {start}..{end}."
                )

    def _record_completed_window(
        self, db: Session, source: str, bbox: str, start: date, end: date,
        rows: List[Dict[str, Any]],
    ) -> None:
        row = db.query(FirmsBackfillWindow).filter_by(
            source_sensor=source, bbox=bbox, window_start=start, window_end=end
        ).one_or_none()
        if row is None:
            row = FirmsBackfillWindow(
                source_sensor=source, bbox=bbox, window_start=start, window_end=end
            )
            db.add(row)
        canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
        row.records_fetched = len(rows)
        row.payload_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        row.fetch_mode = "CACHE" if self.client.offline_mode else "API"
        row.status = "COMPLETED"
        row.completed_at = datetime.now(timezone.utc)
        db.commit()

    def _verify_database_coverage(
        self, db: Session, start: date, target: date, source: str, bbox: str
    ) -> None:
        allowed = NOAA20_SOURCE_FAMILY if source == DEFAULT_PRIMARY_SOURCE else (source,)
        rows = (
            db.query(FirmsBackfillWindow)
            .filter(
                FirmsBackfillWindow.source_sensor.in_(allowed),
                FirmsBackfillWindow.bbox == bbox,
                FirmsBackfillWindow.status == "COMPLETED",
                FirmsBackfillWindow.window_end >= start,
                FirmsBackfillWindow.window_start <= target,
            )
            .order_by(FirmsBackfillWindow.window_start, FirmsBackfillWindow.window_end)
            .all()
        )
        cursor = start
        while cursor <= target:
            covering = [row for row in rows if row.window_start <= cursor <= row.window_end]
            if not covering:
                raise RuntimeError(
                    f"FIRMS backfill date {cursor} is not covered by an audited completed "
                    f"{'/'.join(allowed)} window; CURRENT snapshot was not published."
                )
            cursor = max(row.window_end for row in covering) + timedelta(days=1)

    def _refresh_2026_stack(
        self, db: Session, refresh_start: date, target: date, source: str
    ) -> Dict[str, str]:
        """Materialize A/C only for sites changed since the last published cutoff."""
        accepted_sources = NOAA20_SOURCE_FAMILY if source == DEFAULT_PRIMARY_SOURCE else (source,)
        if refresh_start > target:
            logger.info("A/C stack is already materialized through %s.", target)
            return {}
        touched_sites = (
            db.query(FirmsDetection.source_site_id.label("site_id"))
            .filter(
                FirmsDetection.source_sensor.in_(accepted_sources),
                FirmsDetection.acq_date >= refresh_start,
                FirmsDetection.acq_date <= target,
                FirmsDetection.source_site_id.isnot(None),
            )
            .distinct()
            .subquery()
        )
        sites = (
            db.query(SourceSite)
            .join(touched_sites, SourceSite.site_id == touched_sites.c.site_id)
            .all()
        )
        site_ids = [site.site_id for site in sites]
        unavailable: Dict[str, str] = {}
        sites_by_id = {site.site_id: site for site in sites}
        missing_worldcover = {
            site.site_id: (site.latitude, site.longitude)
            for site in sites
            if any(
                feature not in (site.land_cover or {})
                for feature in LAND_COVER_FEATURES
            )
        }
        if missing_worldcover:
            logger.info(
                "Hydrating WorldCover for %d sites in tile batches",
                len(missing_worldcover),
            )
            fractions, worldcover_errors = (
                self.pipeline.model_a.worldcover.get_fractions_many(missing_worldcover)
            )
            for site_id, extracted in fractions.items():
                site = sites_by_id[site_id]
                site.land_cover = {**(site.land_cover or {}), **extracted}
            unavailable.update(worldcover_errors)
            db.commit()

        total_sites = len(site_ids)
        logger.info("Incremental Model A/C materialization includes %d sites.", total_sites)
        for index, site_id in enumerate(site_ids, start=1):
            a_result = None
            if site_id not in unavailable:
                try:
                    a_result = self.pipeline.model_a.score_site(
                        db, site_id, cutoff=target, source_sensor=source
                    )
                except ModelAInputUnavailable as exc:
                    unavailable[site_id] = str(exc)
            c_result = self.pipeline.model_c_replay.replay_site(db, site_id, cutoff=target)
            if a_result is not None:
                b_row = db.query(SiteModelB).filter_by(site_id=site_id).one()
                self.pipeline._evaluate_alert(
                    db,
                    site_id,
                    c_result.get("event_date") or target,
                    a_result,
                    {"state": b_row.state, "confidence": b_row.confidence},
                    c_result.get("latest") or {"status": "INSUFFICIENT_HISTORY"},
                )
            if index % 500 == 0:
                db.commit()
                logger.info("Materialized Model A/C for %d/%d sites", index, total_sites)
        db.commit()
        logger.info("Model A/C materialization complete for %d sites.", total_sites)
        return unavailable

    @staticmethod
    def _publish_snapshot(db: Session, target: date, source: str) -> StackSnapshot:
        for old in db.query(StackSnapshot).filter(
            StackSnapshot.status.in_(("CURRENT", "REBUILDING"))
        ).all():
            old.status = "SUPERSEDED"
        identity = f"{MODEL_STACK_VERSION}:{target.isoformat()}:{source}"
        snapshot_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        row = db.query(StackSnapshot).filter_by(snapshot_id=snapshot_id).one_or_none()
        if row is None:
            row = StackSnapshot(snapshot_id=snapshot_id)
            db.add(row)
        row.model_stack_version = MODEL_STACK_VERSION
        row.data_through_date = target
        row.primary_firms_source = source
        row.a_core_artifact_sha256 = _sha256(PROJECT_ROOT / "backend/models/MODEL_A_FINAL.joblib")
        row.c_artifact_sha256 = _sha256(PROJECT_ROOT / "backend/models/MODEL_C_V3_FROZEN.joblib")
        row.feature_version = FEATURE_VERSION
        row.resolver_version = RESOLVER_VERSION
        row.backfill_completed_at = datetime.now(timezone.utc)
        row.status = "CURRENT"
        db.flush()
        return row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="NASA FIRMS 2026 transactional backfill")
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--map-key", default=None)
    parser.add_argument("--source", default=DEFAULT_PRIMARY_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--update-db", action="store_true")
    args = parser.parse_args()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(
        "Starting FIRMS backfill: %s through %s (update_db=%s, offline=%s)",
        args.start_date,
        args.end_date or date.today().isoformat(),
        args.update_db,
        args.offline,
    )
    client = FirmsClient(map_key=args.map_key, offline_mode=args.offline, cache_dir=args.cache_dir)
    result = BackfillOrchestrator(firms_client=client).run_backfill(
        start_date=args.start_date, end_date=args.end_date,
        source=args.source, dry_run=args.dry_run, update_db=args.update_db,
    )
    print(json.dumps(result, indent=2, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
