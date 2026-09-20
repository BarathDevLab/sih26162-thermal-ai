"""Transactional live FIRMS processing for the source-centric A+B+C stack."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timezone
from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Alert,
    CandidateSource,
    CandidateSourceDetection,
    FirmsDetection,
    IngestionRun,
    SiteDailyActivity,
    SiteModelA,
    SiteModelB,
    SiteModelBHistory,
    SiteModelC,
    SourceSite,
)
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.source_resolver import SourceResolver
from backend.app.services.firms_client import NOAA20_SOURCE_FAMILY
from backend.app.services.firms_ingestion import FirmsIngestionService, normalize_acq_time
from backend.app.services.model_a_service import ModelAInputUnavailable, ModelAService
from backend.app.services.model_c_replay_service import ModelCReplayService
from backend.app.services.prithvi_queue import enqueue_site_for_prithvi
from backend.app.services.stack_readiness import get_shared_model_a, get_shared_model_c


logger = logging.getLogger(__name__)
MODEL_VERSION = os.environ.get("MODEL_STACK_VERSION", "2026-09-04-r1")
PRIMARY_SENSOR = os.environ.get("FIRMS_PRIMARY_SOURCE", "VIIRS_NOAA20_NRT")


class LivePipelineService:
    def __init__(self) -> None:
        self.resolver = SourceResolver()
        self.ingestion = FirmsIngestionService(self.resolver)
        self.model_b = ModelBEngine()
        self.model_c_replay = ModelCReplayService(
            model_c=get_shared_model_c(), model_b=self.model_b
        )
        self.decision = DecisionEngine()
        self._model_a: Optional[ModelAService] = None
        self._resolver_initialized = False

    @property
    def model_a(self) -> ModelAService:
        if self._model_a is None:
            self._model_a = ModelAService(engine=get_shared_model_a())
        return self._model_a

    def ensure_resolver_loaded(self, db: Session) -> None:
        if self._resolver_initialized:
            return
        members = (
            db.query(
                FirmsDetection.detection_id,
                FirmsDetection.source_site_id,
                FirmsDetection.latitude,
                FirmsDetection.longitude,
            )
            .filter(FirmsDetection.source_site_id.isnot(None))
            .all()
        )
        self.resolver.load_members(
            [
                {
                    "detection_id": row[0],
                    "site_id": row[1],
                    "latitude": row[2],
                    "longitude": row[3],
                }
                for row in members
            ]
        )
        candidates = db.query(CandidateSource).filter_by(status="ACCUMULATING").all()
        candidate_payloads = []
        for candidate in candidates:
            candidate_members = (
                db.query(CandidateSourceDetection)
                .filter_by(candidate_id=candidate.candidate_id)
                .all()
            )
            candidate_payloads.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "latitude": candidate.latitude,
                    "longitude": candidate.longitude,
                    "detection_count": candidate.detection_count,
                    "detections": [
                        {
                            "detection_id": member.detection_id,
                            "latitude": member.latitude,
                            "longitude": member.longitude,
                        }
                        for member in candidate_members
                    ],
                }
            )
        self.resolver.load_candidates(candidate_payloads)
        self._resolver_initialized = True
        logger.info(
            "Resolver loaded with %d member points and %d persistent candidates.",
            len(members),
            len(candidates),
        )

    def process_detections_batch(
        self,
        raw_records: List[Dict[str, Any]],
        db: Session,
        source_sensor: str = PRIMARY_SENSOR,
        as_of_date: Optional[date] = None,
        refresh_models: bool = True,
    ) -> Dict[str, Any]:
        run = IngestionRun(
            run_id=f"RUN_{uuid.uuid4().hex}",
            source=source_sensor,
            started_at=datetime.now(timezone.utc),
            records_read=len(raw_records),
            status="RUNNING",
        )
        db.add(run)
        db.commit()
        if not raw_records:
            run.status = "COMPLETED"
            run.ended_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "EMPTY", "processed_count": 0, "alerts_generated": 0}

        try:
            self.ensure_resolver_loaded(db)
            normalized = self._normalize_unique(raw_records, source_sensor)
            existing = {
                row.detection_id: row
                for row in db.query(FirmsDetection)
                .filter(FirmsDetection.detection_id.in_(normalized))
                .all()
            }
            family_existing = self._existing_family_observations(
                db, normalized, source_sensor
            )
            touched_days: Set[Tuple[str, date]] = set()
            promoted_sites: List[str] = []
            inserted = 0
            revised = 0
            unchanged = 0
            cross_source_duplicates = 0

            self.resolver.begin_batch()
            for detection_id, payload in normalized.items():
                row = existing.get(detection_id)
                family_row = family_existing.get(self._physical_observation_key(payload))
                if (
                    row is None
                    and family_row is not None
                    and family_row.detection_id != detection_id
                ):
                    unchanged += 1
                    cross_source_duplicates += 1
                    continue
                if row is not None and not self._changed(row, payload):
                    unchanged += 1
                    continue

                resolution = self._resolve(payload, row)
                promoted_site_id = None
                if resolution["status"] == "PROMOTED":
                    # The referenced source row must exist before the detection FK is flushed.
                    promoted_site_id = self._persist_promotion(db, resolution)
                    promoted_sites.append(promoted_site_id)
                if row is None:
                    row = FirmsDetection(detection_id=detection_id)
                    db.add(row)
                    inserted += 1
                else:
                    if row.source_site_id:
                        touched_days.add((row.source_site_id, row.acq_date))
                    revised += 1
                self._apply_detection(row, payload, resolution)
                db.flush()

                if resolution["status"] in ("NEW_CANDIDATE", "CANDIDATE_ACCUMULATED"):
                    self._persist_candidate(db, resolution["candidate_id"], row)
                elif resolution["status"] == "PROMOTED":
                    site_id = promoted_site_id
                    for member in resolution.get("member_detections", []):
                        member_id = member.get("detection_id")
                        member_row = db.query(FirmsDetection).filter_by(detection_id=member_id).one_or_none()
                        if member_row:
                            member_row.source_site_id = site_id
                            member_row.resolution_status = "PROMOTED_MEMBER"
                            touched_days.add((site_id, member_row.acq_date))
                            self._persist_promoted_member(
                                db, resolution["candidate_id"], member_row
                            )

                if row.source_site_id:
                    touched_days.add((row.source_site_id, row.acq_date))

            self.resolver.end_batch()
            db.flush()
            touched_sites = {site_id for site_id, _ in touched_days}
            for site_id, activity_date in sorted(touched_days):
                self._rebuild_daily_activity(db, site_id, activity_date)
            for site_id in touched_sites:
                self._update_latest_seen(db, site_id)

            if not refresh_models:
                run.inserted = inserted
                run.updated = revised
                run.failed = 0
                run.status = "COMPLETED"
                run.ended_at = datetime.now(timezone.utc)
                db.commit()
                return {
                    "run_id": run.run_id,
                    "status": run.status,
                    "processed_count": len(raw_records),
                    "unique_count": len(normalized),
                    "inserted_count": inserted,
                    "revised_count": revised,
                    "unchanged_count": unchanged,
                    "cross_source_duplicate_count": cross_source_duplicates,
                    "promoted_count": len(promoted_sites),
                    "promoted_site_ids": sorted(set(promoted_sites)),
                    "touched_sites_count": len(touched_sites),
                    "touched_site_ids": sorted(touched_sites),
                    "alerts_generated": 0,
                    "model_a_unavailable": {},
                    "models_deferred": True,
                }

            model_a_errors: Dict[str, str] = {}
            model_a_results: Dict[str, Dict[str, Any]] = {}
            for site_id in touched_sites:
                try:
                    model_a_results[site_id] = self.model_a.score_site(db, site_id)
                except ModelAInputUnavailable as exc:
                    model_a_errors[site_id] = str(exc)

            temporal_cutoff = as_of_date or date.today()
            b_results = {
                site_id: self._refresh_model_b_site(db, site_id, temporal_cutoff)
                for site_id in touched_sites
            }
            c_results = {
                site_id: self.model_c_replay.replay_site(db, site_id, cutoff=temporal_cutoff)
                for site_id in touched_sites
            }

            alerts_generated = 0
            for site_id in touched_sites:
                a_result = model_a_results.get(site_id)
                if a_result is None:
                    continue
                c_latest = c_results[site_id].get("latest") or {"status": "INSUFFICIENT_HISTORY"}
                site_day = c_results[site_id].get("event_date") or temporal_cutoff
                alerts_generated += self._evaluate_alert(
                    db, site_id, site_day, a_result, b_results[site_id], c_latest
                )
                if a_result.get("should_queue_prithvi"):
                    enqueue_site_for_prithvi(site_id)

            run.inserted = inserted
            run.updated = revised
            run.failed = len(model_a_errors)
            run.status = "COMPLETED" if not model_a_errors else "COMPLETED_DEGRADED"
            run.ended_at = datetime.now(timezone.utc)
            db.commit()
            return {
                "run_id": run.run_id,
                "status": run.status,
                "processed_count": len(raw_records),
                "unique_count": len(normalized),
                "inserted_count": inserted,
                "revised_count": revised,
                "unchanged_count": unchanged,
                "cross_source_duplicate_count": cross_source_duplicates,
                "promoted_count": len(promoted_sites),
                "promoted_site_ids": sorted(set(promoted_sites)),
                "touched_sites_count": len(touched_sites),
                "alerts_generated": alerts_generated,
                "model_a_unavailable": model_a_errors,
            }
        except Exception as exc:
            db.rollback()
            # Resolution mutates an in-memory spatial/candidate index. Discard it
            # after a failed transaction so the next batch reloads committed DB state.
            self.resolver = SourceResolver()
            self.ingestion.resolver = self.resolver
            self._resolver_initialized = False
            persisted_run = db.query(IngestionRun).filter_by(run_id=run.run_id).one_or_none()
            if persisted_run:
                persisted_run.status = "FAILED"
                persisted_run.failed = 1
                persisted_run.error_summary = str(exc)
                persisted_run.ended_at = datetime.now(timezone.utc)
                db.commit()
            raise

    def _normalize_unique(self, raw_records: List[Dict[str, Any]], source_sensor: str) -> Dict[str, dict]:
        normalized: Dict[str, dict] = {}
        for raw in raw_records:
            payload = self.ingestion.normalize_record(raw, source_sensor=source_sensor)
            normalized[payload["detection_id"]] = payload
        return normalized

    @staticmethod
    def _physical_observation_key(payload: Any) -> Tuple[str, str, str, str, str]:
        observed_date = payload.acq_date if isinstance(payload, FirmsDetection) else payload["acq_date"]
        date_text = observed_date.isoformat() if isinstance(observed_date, date) else str(observed_date)[:10]
        value = lambda name: getattr(payload, name) if isinstance(payload, FirmsDetection) else payload[name]
        return (
            str(value("satellite")).strip(),
            f"{round(float(value('latitude')), 4):.4f}",
            f"{round(float(value('longitude')), 4):.4f}",
            date_text,
            normalize_acq_time(value("acq_time")),
        )

    def _existing_family_observations(
        self,
        db: Session,
        normalized: Dict[str, dict],
        source_sensor: str,
    ) -> Dict[Tuple[str, str, str, str, str], FirmsDetection]:
        if source_sensor not in NOAA20_SOURCE_FAMILY or not normalized:
            return {}
        observed_dates = {
            datetime.strptime(str(payload["acq_date"])[:10], "%Y-%m-%d").date()
            for payload in normalized.values()
        }
        rows = (
            db.query(FirmsDetection)
            .filter(
                FirmsDetection.source_sensor.in_(NOAA20_SOURCE_FAMILY),
                FirmsDetection.acq_date.in_(observed_dates),
            )
            .all()
        )
        result: Dict[Tuple[str, str, str, str, str], FirmsDetection] = {}
        # Prefer the operational NRT record if legacy data already contain both.
        for row in sorted(rows, key=lambda item: item.source_sensor != PRIMARY_SENSOR):
            result.setdefault(self._physical_observation_key(row), row)
        return result

    def _resolve(self, payload: dict, existing: Optional[FirmsDetection]) -> dict:
        if existing is not None and existing.latitude == payload["latitude"] and existing.longitude == payload["longitude"]:
            return {
                "status": existing.resolution_status or ("MATCHED" if existing.source_site_id else "UNRESOLVED"),
                "site_id": existing.source_site_id,
                "distance_m": existing.assignment_distance_m,
                "is_ambiguous": existing.is_ambiguous,
                "candidate_site_ids": existing.candidate_site_ids or [],
            }
        return self.resolver.resolve_detection(
            payload["latitude"],
            payload["longitude"],
            payload["detection_id"],
            payload,
        )

    @staticmethod
    def _changed(row: FirmsDetection, payload: dict) -> bool:
        fields = (
            "source_sensor", "satellite", "instrument", "latitude", "longitude",
            "acq_date", "acq_time", "frp", "bright_ti4", "bright_ti5", "scan",
            "track", "confidence", "daynight", "version",
        )
        for field in fields:
            incoming = payload.get(field)
            if field == "acq_date" and isinstance(incoming, str):
                incoming = datetime.strptime(incoming[:10], "%Y-%m-%d").date()
            if getattr(row, field) != incoming:
                return True
        return False

    @staticmethod
    def _apply_detection(row: FirmsDetection, payload: dict, resolution: dict) -> None:
        for field in (
            "source_sensor", "satellite", "instrument", "latitude", "longitude",
            "acq_date", "acq_time", "frp", "bright_ti4", "bright_ti5", "scan",
            "track", "confidence", "daynight", "version", "raw_payload",
        ):
            value = payload.get(field)
            if field == "acq_date" and isinstance(value, str):
                value = datetime.strptime(value[:10], "%Y-%m-%d").date()
            setattr(row, field, value)
        row.source_site_id = resolution.get("site_id")
        row.resolution_status = resolution.get("status")
        row.is_ambiguous = bool(resolution.get("is_ambiguous", False))
        row.candidate_site_ids = resolution.get("candidate_site_ids") or None
        row.assignment_distance_m = resolution.get("distance_m")
        row.ingested_at = datetime.now(timezone.utc)

    def _persist_candidate(self, db: Session, candidate_id: str, detection: FirmsDetection) -> None:
        state = self.resolver.candidates[candidate_id]
        candidate = db.query(CandidateSource).filter_by(candidate_id=candidate_id).one_or_none()
        if candidate is None:
            candidate = CandidateSource(candidate_id=candidate_id, first_seen=datetime.now(timezone.utc))
            db.add(candidate)
        candidate.latitude = state["latitude"]
        candidate.longitude = state["longitude"]
        candidate.detection_count = state["detection_count"]
        candidate.last_seen = datetime.now(timezone.utc)
        candidate.status = "ACCUMULATING"
        member = db.query(CandidateSourceDetection).filter_by(
            candidate_id=candidate_id, detection_id=detection.detection_id
        ).one_or_none()
        if member is None:
            db.add(CandidateSourceDetection(
                candidate_id=candidate_id,
                detection_id=detection.detection_id,
                latitude=detection.latitude,
                longitude=detection.longitude,
                observed_at=datetime.combine(detection.acq_date, datetime.min.time(), tzinfo=timezone.utc),
            ))

    @staticmethod
    def _persist_promoted_member(
        db: Session, candidate_id: str, detection: FirmsDetection
    ) -> None:
        member = db.query(CandidateSourceDetection).filter_by(
            candidate_id=candidate_id, detection_id=detection.detection_id
        ).one_or_none()
        if member is None:
            db.add(CandidateSourceDetection(
                candidate_id=candidate_id,
                detection_id=detection.detection_id,
                latitude=detection.latitude,
                longitude=detection.longitude,
                observed_at=datetime.combine(
                    detection.acq_date, datetime.min.time(), tzinfo=timezone.utc
                ),
            ))

    @staticmethod
    def _persist_promotion(db: Session, resolution: dict) -> str:
        site_id = resolution["site_id"]
        if db.query(SourceSite).filter_by(site_id=site_id).one_or_none() is None:
            db.add(SourceSite(
                site_id=site_id,
                latitude=resolution["latitude"],
                longitude=resolution["longitude"],
                status="PROMOTED",
                promoted_at=datetime.now(timezone.utc),
            ))
            db.flush()
        candidate = db.query(CandidateSource).filter_by(
            candidate_id=resolution["candidate_id"]
        ).one_or_none()
        if candidate:
            candidate.status = "PROMOTED"
            candidate.promoted_site_id = site_id
            candidate.detection_count = int(
                resolution.get("total_detections")
                or len(resolution.get("member_detections") or [])
            )
            candidate.latitude = resolution["latitude"]
            candidate.longitude = resolution["longitude"]
            candidate.last_seen = datetime.now(timezone.utc)
        return site_id

    @staticmethod
    def _rebuild_daily_activity(db: Session, site_id: str, activity_date: date) -> None:
        rows = db.query(FirmsDetection).filter_by(
            source_site_id=site_id, acq_date=activity_date
        ).all()
        activity = db.query(SiteDailyActivity).filter_by(
            site_id=site_id, acq_date=activity_date
        ).one_or_none()
        if not rows:
            if activity:
                db.delete(activity)
            return
        frps = [float(row.frp or 0.0) for row in rows]
        if activity is None:
            activity = SiteDailyActivity(site_id=site_id, acq_date=activity_date)
            db.add(activity)
        activity.detections = len(rows)
        activity.mean_frp = sum(frps) / len(frps)
        activity.max_frp = max(frps)
        activity.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _update_latest_seen(db: Session, site_id: str) -> None:
        latest = (
            db.query(FirmsDetection.acq_date)
            .filter(FirmsDetection.source_site_id == site_id)
            .order_by(FirmsDetection.acq_date.desc())
            .first()
        )
        site = db.query(SourceSite).filter_by(site_id=site_id).one()
        site.latest_seen = latest[0] if latest else None

    def _refresh_model_b_site(self, db: Session, site_id: str, as_of_date: date) -> dict:
        active_dates = [
            row[0]
            for row in db.query(SiteDailyActivity.acq_date)
            .filter(SiteDailyActivity.site_id == site_id, SiteDailyActivity.acq_date <= as_of_date)
            .order_by(SiteDailyActivity.acq_date)
            .all()
        ]
        result = self.model_b.predict(active_dates, as_of_date=as_of_date)
        stats = result.get("stats", {})
        windows = {key: stats.get(f"active_days_{key}", 0) for key in ("30", "90", "180", "365")}
        row = db.query(SiteModelB).filter_by(site_id=site_id).one_or_none()
        latest_history_date = (
            db.query(SiteModelBHistory.as_of_date)
            .filter(SiteModelBHistory.site_id == site_id)
            .order_by(SiteModelBHistory.as_of_date.desc())
            .first()
        )
        materialize_latest = latest_history_date is None or as_of_date >= latest_history_date[0]
        computed_at = datetime.now(timezone.utc)
        if materialize_latest:
            if row is None:
                row = SiteModelB(site_id=site_id)
                db.add(row)
            row.state = result["state"]
            row.confidence = result["confidence"]
            row.reason = result["reason"]
            row.days_since_last = stats.get("days_since_last")
            row.active_days_windows = windows
            row.model_version = MODEL_VERSION
            row.computed_at = computed_at
        history = db.query(SiteModelBHistory).filter_by(
            site_id=site_id, as_of_date=as_of_date
        ).one_or_none()
        if history is None:
            history = SiteModelBHistory(site_id=site_id, as_of_date=as_of_date)
            db.add(history)
        history.state = result["state"]
        history.confidence = result["confidence"]
        history.reason = result["reason"]
        history.days_since_last = stats.get("days_since_last")
        history.active_days_windows = windows
        history.model_version = MODEL_VERSION
        history.computed_at = computed_at
        return result

    def _evaluate_alert(self, db, site_id, site_day, a_result, b_result, c_result) -> int:
        existing = (
            db.query(Alert)
            .filter(Alert.site_id == site_id, Alert.site_day == site_day, Alert.status == "ACTIVE")
            .order_by(Alert.created_at.desc())
            .first()
        )
        existing_payload = None
        if existing:
            existing_payload = {
                "alert_level": existing.alert_level,
                "alert_type": existing.alert_type,
                "created_at": existing.created_at.isoformat(),
            }
        alert = self.decision.evaluate(
            site_id=site_id,
            site_day=site_day.isoformat(),
            model_a_result={"decision": a_result["decision"]},
            model_b_result=b_result,
            model_c_result=c_result,
            existing_alert=existing_payload,
        )
        if alert["alert_level"] in ("NONE", "INFO"):
            return 0
        # DecisionEngine returns the existing alert payload when a same-day
        # evaluation would not escalate it. Nothing needs to be rewritten.
        fingerprint = alert.get("alert_fingerprint")
        if not fingerprint:
            return 0
        row = db.query(Alert).filter_by(fingerprint=fingerprint).one_or_none()
        if row is None:
            row = Alert(
                alert_id=f"ALT_{uuid.uuid4().hex}",
                site_id=site_id,
                site_day=site_day,
                fingerprint=fingerprint,
                status="ACTIVE",
            )
            db.add(row)
        row.alert_type = alert["alert_type"]
        row.alert_level = alert["alert_level"]
        row.headline = alert["headline"]
        row.reason_codes = alert["reason_codes"]
        row.evidence_required = alert["evidence_required"]
        row.is_escalation = alert["is_escalation"]
        row.updated_at = datetime.now(timezone.utc)
        return 1


def run_global_daily_model_b_refresh(
    db: Session,
    as_of_date: Optional[date] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Recompute every site with bulk I/O and the frozen deterministic engine."""
    def report_progress(processed: int, total: int, percent: int, detail: str) -> None:
        if progress_callback is not None:
            progress_callback({
                "processed_sites": processed,
                "total_sites": total,
                "progress_percent": max(0, min(100, percent)),
                "detail": detail,
            })

    service = get_live_pipeline_service()
    ref_date = as_of_date or date.today()
    site_ids = [row[0] for row in db.query(SourceSite.site_id).all()]
    report_progress(
        0,
        len(site_ids),
        0,
        f"Loading temporal histories for {len(site_ids)} sites through {ref_date}.",
    )
    history_count = (
        db.query(SiteModelBHistory.site_id)
        .filter(SiteModelBHistory.as_of_date == ref_date)
        .count()
    )
    current_count = db.query(SiteModelB.site_id).count()
    if history_count == len(site_ids) and current_count == len(site_ids):
        logger.info(
            "Daily Model B is already materialized for all %d sites through %s.",
            len(site_ids),
            ref_date,
        )
        report_progress(
            len(site_ids),
            len(site_ids),
            100,
            f"Model B was already current for all {len(site_ids)} sites.",
        )
        return {
            "status": "ALREADY_COMPLETED",
            "as_of_date": ref_date.isoformat(),
            "sites_evaluated": len(site_ids),
        }

    logger.info(
        "Loading Model B activity histories for %d sites through %s...",
        len(site_ids),
        ref_date,
    )
    active_dates: DefaultDict[str, List[date]] = defaultdict(list)
    for site_id, active_date in (
        db.query(SiteDailyActivity.site_id, SiteDailyActivity.acq_date)
        .filter(SiteDailyActivity.acq_date <= ref_date)
        .order_by(SiteDailyActivity.site_id, SiteDailyActivity.acq_date)
        .yield_per(10_000)
    ):
        active_dates[site_id].append(active_date)

    missing_activity = [site_id for site_id in site_ids if not active_dates.get(site_id)]
    if missing_activity:
        raise ValueError(
            "Model B cannot refresh sites without activity on or before the cutoff: "
            + ", ".join(missing_activity[:10])
        )

    current_ids = {row[0] for row in db.query(SiteModelB.site_id).all()}
    history_ids = {
        row[0]
        for row in db.query(SiteModelBHistory.site_id)
        .filter(SiteModelBHistory.as_of_date == ref_date)
        .all()
    }
    latest_history_dates = dict(
        db.query(SiteModelBHistory.site_id, func.max(SiteModelBHistory.as_of_date))
        .group_by(SiteModelBHistory.site_id)
        .all()
    )
    logger.info("Model B histories loaded; starting batched deterministic evaluation.")
    report_progress(
        0,
        len(site_ids),
        10,
        f"Temporal histories loaded; evaluating {len(site_ids)} deterministic site states.",
    )

    batch_size = 5_000
    for offset in range(0, len(site_ids), batch_size):
        current_inserts = []
        current_updates = []
        history_inserts = []
        history_updates = []
        computed_at = datetime.now(timezone.utc)
        batch = site_ids[offset:offset + batch_size]
        for site_id in batch:
            result = service.model_b.predict(active_dates[site_id], as_of_date=ref_date)
            stats = result.get("stats", {})
            values = {
                "state": result["state"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "days_since_last": stats.get("days_since_last"),
                "active_days_windows": {
                    key: stats.get(f"active_days_{key}", 0)
                    for key in ("30", "90", "180", "365")
                },
                "model_version": MODEL_VERSION,
                "computed_at": computed_at,
            }
            latest_history = latest_history_dates.get(site_id)
            if latest_history is None or ref_date >= latest_history:
                current_values = {"site_id": site_id, **values}
                if site_id in current_ids:
                    current_updates.append(current_values)
                else:
                    current_inserts.append(current_values)
            history_values = {"site_id": site_id, "as_of_date": ref_date, **values}
            if site_id in history_ids:
                history_updates.append(history_values)
            else:
                history_inserts.append(history_values)

        if current_updates:
            db.bulk_update_mappings(SiteModelB, current_updates)
        if current_inserts:
            db.bulk_insert_mappings(SiteModelB, current_inserts)
        if history_updates:
            db.bulk_update_mappings(SiteModelBHistory, history_updates)
        if history_inserts:
            db.bulk_insert_mappings(SiteModelBHistory, history_inserts)
        db.commit()
        logger.info(
            "Materialized daily Model B for %d/%d sites",
            min(offset + len(batch), len(site_ids)),
            len(site_ids),
        )
        processed = min(offset + len(batch), len(site_ids))
        report_progress(
            processed,
            len(site_ids),
            10 + round(90 * processed / max(1, len(site_ids))),
            f"Materialized Model B for {processed}/{len(site_ids)} sites.",
        )
    return {
        "status": "COMPLETED",
        "as_of_date": ref_date.isoformat(),
        "sites_evaluated": len(site_ids),
    }


_live_pipeline: Optional[LivePipelineService] = None


def get_live_pipeline_service() -> LivePipelineService:
    global _live_pipeline
    if _live_pipeline is None:
        _live_pipeline = LivePipelineService()
    return _live_pipeline
