"""
Live Incremental Ingestion & Operational Rescoring Pipeline
Executes the incremental processing loop for incoming NASA FIRMS active fire hotspots:
1. Normalizes and deduplicates detections
2. Spatially resolves detections against physical sites (750m Haversine) and candidate accumulators
3. Upserts raw detections and updates today's site_daily_activity in PostgreSQL
4. For touched sites: recomputes Model B temporal state and Model C anomaly scores
5. Evaluates Unified Decision Engine and emits/escalates operational alerts
6. Enqueues uncertain/high-priority sites to background Prithvi worker queue
"""

import time
import uuid
import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Set, Tuple

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.app.db.models import (
    SourceSite,
    FirmsDetection,
    CandidateSource,
    SiteDailyActivity,
    SiteModelA,
    SiteModelB,
    SiteModelC,
    SiteDailyInference,
    Alert,
    IngestionRun
)
from backend.app.engines.source_resolver import SourceResolver
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.model_c import ModelCEngine
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.services.firms_ingestion import FirmsIngestionService
from backend.app.services.prithvi_queue import enqueue_site_for_prithvi

logger = logging.getLogger(__name__)


class LivePipelineService:
    def __init__(self):
        self.resolver = SourceResolver(eps_m=750.0, min_samples=3)
        self.ingestion_service = FirmsIngestionService(source_resolver=self.resolver)
        self.model_b_engine = ModelBEngine()
        self.model_c_engine = ModelCEngine()
        self.decision_engine = DecisionEngine()
        self._resolver_initialized = False

    def ensure_resolver_loaded(self, db: Session):
        """Loads all existing physical sites into the 750m BallTree if not already done."""
        if self._resolver_initialized and self.resolver.site_tree is not None:
            return

        t0 = time.time()
        sites = db.query(SourceSite.site_id, SourceSite.latitude, SourceSite.longitude).all()
        records = [
            {"site_id": s[0], "latitude": float(s[1]), "longitude": float(s[2])}
            for s in sites
        ]
        self.resolver.load_sites(records)
        self._resolver_initialized = True
        logger.info(f"SourceResolver spatial tree loaded with {len(records)} sites in {time.time()-t0:.2f}s.")

    def process_detections_batch(
        self,
        raw_records: List[Dict[str, Any]],
        db: Session,
        source_sensor: str = "VIIRS_NOAA20_NRT"
    ) -> Dict[str, Any]:
        """
        Processes an incoming batch of raw FIRMS hotspots.
        """
        run_id = f"RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        t_start = datetime.now(timezone.utc)
        logger.info(f"Starting live ingestion {run_id} with {len(raw_records)} detections.")

        ingestion_run = IngestionRun(
            run_id=run_id,
            source=source_sensor,
            started_at=t_start,
            records_read=len(raw_records),
            status="RUNNING"
        )
        db.add(ingestion_run)
        db.commit()

        if not raw_records:
            ingestion_run.status = "COMPLETED"
            ingestion_run.ended_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "EMPTY", "processed": 0, "alerts_generated": 0}

        try:
            self.ensure_resolver_loaded(db)

            # Query existing detection IDs to deduplicate against database
            # Sample recent 3-day detection IDs for fast in-memory check
            cutoff_date = date.today()
            recent_det_ids = set(
                r[0] for r in db.query(FirmsDetection.detection_id)
                .filter(FirmsDetection.acq_date >= cutoff_date)
                .all()
            )

            # Ingest, normalize, deduplicate, and spatially resolve
            ingest_result = self.ingestion_service.ingest_batch(
                raw_records=raw_records,
                source_sensor=source_sensor,
                existing_ids=recent_det_ids
            )

            resolved_dets = ingest_result["resolved_detections"]
            promoted_sites = ingest_result.get("promoted_sites", [])

            # 1. Persist Promoted Sites in PostgreSQL
            now_iso = datetime.now(timezone.utc)
            for ps in promoted_sites:
                new_site_id = ps["site_id"]
                new_site = SourceSite(
                    site_id=new_site_id,
                    latitude=float(ps["latitude"]),
                    longitude=float(ps["longitude"]),
                    status="ACTIVE",
                    created_at=now_iso
                )
                db.add(new_site)

                # Baseline Model A: Promoted sites start in review queue (UNKNOWN)
                db.add(SiteModelA(
                    site_id=new_site_id,
                    core_probability=0.50,
                    class_name="UNKNOWN",
                    decision="UNKNOWN",
                    prithvi_status="NOT_TRIGGERED",
                    model_version="2026-09-04-r1",
                    computed_at=now_iso
                ))

                # Baseline Model B: NEW
                db.add(SiteModelB(
                    site_id=new_site_id,
                    state="NEW",
                    confidence="HIGH",
                    reason="Promoted from candidate accumulator (3 detections within 750m)",
                    days_since_last=0,
                    active_days_windows={"30d": 1, "90d": 1, "180d": 1, "365d": 1},
                    model_version="2026-09-04-r1",
                    computed_at=now_iso
                ))

                # Baseline Model C: INSUFFICIENT_HISTORY
                db.add(SiteModelC(
                    site_id=new_site_id,
                    operational_status="INSUFFICIENT_HISTORY",
                    c_score=None,
                    c_raw=None,
                    model_version="2026-09-04-r1",
                    computed_at=now_iso
                ))
            db.commit()

            # 2. Persist Raw Hotspots to firms_detections
            db_detections = []
            for d in resolved_dets:
                acq_d = datetime.strptime(d["acq_date"][:10], "%Y-%m-%d").date() if isinstance(d["acq_date"], str) else d["acq_date"]
                raw_meta = d.get("raw_payload") or {}
                if not isinstance(raw_meta, dict):
                    raw_meta = {"raw": str(raw_meta)}
                raw_meta["resolution_status"] = d.get("resolution_status", "UNKNOWN")
                raw_meta["distance_to_site_m"] = d.get("distance_m")
                raw_meta["is_ambiguous"] = d.get("is_ambiguous", False)

                db_detections.append(FirmsDetection(
                    detection_id=d["detection_id"],
                    source_sensor=d.get("source_sensor", "VIIRS_NOAA20_NRT"),
                    satellite=d.get("satellite", "20"),
                    instrument=d.get("instrument", "VIIRS"),
                    latitude=d["latitude"],
                    longitude=d["longitude"],
                    bright_ti4=d.get("bright_ti4"),
                    bright_ti5=d.get("bright_ti5"),
                    frp=d.get("frp", 0.0) or 0.0,
                    scan=d.get("scan"),
                    track=d.get("track"),
                    acq_date=acq_d,
                    acq_time=d.get("acq_time", "0000"),
                    confidence=d.get("confidence"),
                    version=d.get("version"),
                    daynight=d.get("daynight") or "D",
                    source_site_id=d.get("site_id"),
                    raw_payload=raw_meta
                ))

            if db_detections:
                # Merge or insert new detections
                for det in db_detections:
                    db.merge(det)
                db.commit()

            # 3. Aggregate Daily Activity for Matched Detections
            matched_dets = [d for d in resolved_dets if d.get("site_id")]
            touched_site_ids: Set[str] = set(d["site_id"] for d in matched_dets)

            today = date.today()
            site_day_groups: Dict[Tuple[str, date], List[float]] = {}
            for d in matched_dets:
                sid = d["site_id"]
                acq_d = datetime.strptime(d["acq_date"][:10], "%Y-%m-%d").date() if isinstance(d["acq_date"], str) else d["acq_date"]
                frp_val = float(d.get("frp", 0.0) or 0.0)
                key = (sid, acq_d)
                site_day_groups.setdefault(key, []).append(frp_val)

            # Upsert into site_daily_activity
            for (sid, act_date), frp_list in site_day_groups.items():
                existing_act = (
                    db.query(SiteDailyActivity)
                    .filter(SiteDailyActivity.site_id == sid, SiteDailyActivity.acq_date == act_date)
                    .first()
                )
                if existing_act:
                    new_count = existing_act.detections + len(frp_list)
                    tot_frp = (existing_act.mean_frp * existing_act.detections) + sum(frp_list)
                    existing_act.detections = new_count
                    existing_act.mean_frp = round(tot_frp / new_count, 2)
                    existing_act.max_frp = round(max(existing_act.max_frp, max(frp_list)), 2)
                    existing_act.updated_at = datetime.now(timezone.utc)
                else:
                    db.add(SiteDailyActivity(
                        site_id=sid,
                        acq_date=act_date,
                        detections=len(frp_list),
                        mean_frp=round(float(np.mean(frp_list)), 2),
                        max_frp=round(float(np.max(frp_list)), 2),
                        updated_at=datetime.now(timezone.utc)
                    ))
            db.commit()

            # 4. Rescore Model B, Model C, and Decision Engine for Touched Sites
            alerts_generated = 0
            for sid in touched_site_ids:
                # Fetch all activity dates for site up to today
                all_acts = (
                    db.query(SiteDailyActivity)
                    .filter(SiteDailyActivity.site_id == sid, SiteDailyActivity.acq_date <= today)
                    .order_by(SiteDailyActivity.acq_date.asc())
                    .all()
                )
                if not all_acts:
                    continue

                active_dates = [a.acq_date for a in all_acts]

                # (a) Model B Recalculation
                b_res = self.model_b_engine.predict(active_dates=active_dates, as_of_date=today)
                b_stats = b_res.get("stats", {})
                mb_row = db.query(SiteModelB).filter(SiteModelB.site_id == sid).first()
                b_windows = {
                    "30d": b_stats.get("active_days_30", 0),
                    "90d": b_stats.get("active_days_90", 0),
                    "180d": b_stats.get("active_days_180", 0),
                    "365d": b_stats.get("active_days_365", 0),
                }
                if mb_row:
                    mb_row.state = b_res["state"]
                    mb_row.confidence = b_res["confidence"]
                    mb_row.reason = b_res["reason"]
                    mb_row.days_since_last = int(b_stats.get("days_since_last", 0))
                    mb_row.active_days_windows = b_windows
                    mb_row.computed_at = datetime.now(timezone.utc)
                else:
                    db.add(SiteModelB(
                        site_id=sid,
                        state=b_res["state"],
                        confidence=b_res["confidence"],
                        reason=b_res["reason"],
                        days_since_last=int(b_stats.get("days_since_last", 0)),
                        active_days_windows=b_windows,
                        model_version="2026-09-04-r1",
                        computed_at=datetime.now(timezone.utc)
                    ))

                # (b) Model C Recalculation (prior completed days vs today)
                prior_acts = [a for a in all_acts if a.acq_date < today]
                today_act = next((a for a in all_acts if a.acq_date == today), None)

                c_status = "INSUFFICIENT_HISTORY"
                c_score = None
                c_raw = None
                c_drivers = None

                if today_act:
                    prior_history = [
                        {
                            "site_id": a.site_id,
                            "acq_date": str(a.acq_date),
                            "detections": a.detections,
                            "mean_frp": a.mean_frp,
                            "max_frp": a.max_frp
                        }
                        for a in prior_acts
                    ]
                    current_day_dict = {
                        "site_id": today_act.site_id,
                        "acq_date": str(today_act.acq_date),
                        "detections": today_act.detections,
                        "mean_frp": today_act.mean_frp,
                        "max_frp": today_act.max_frp
                    }

                    c_res = self.model_c_engine.score(prior_history, current_day_dict)
                    c_status = c_res["status"]
                    c_score = c_res.get("c_score")
                    c_raw = c_res.get("c_raw")
                    c_drivers = c_res.get("drivers")

                    # Upsert into site_daily_inference
                    inf_row = (
                        db.query(SiteDailyInference)
                        .filter(SiteDailyInference.site_id == sid, SiteDailyInference.acq_date == today)
                        .first()
                    )
                    if inf_row:
                        inf_row.model_c_status = c_status
                        inf_row.c_score = c_score
                        inf_row.c_raw = c_raw
                        inf_row.drivers = c_drivers
                        inf_row.evidence_99 = c_res.get("evidence_99", 0)
                        inf_row.computed_at = datetime.now(timezone.utc)
                    else:
                        db.add(SiteDailyInference(
                            site_id=sid,
                            acq_date=today,
                            model_c_status=c_status,
                            c_score=c_score,
                            c_raw=c_raw,
                            drivers=c_drivers,
                            evidence_99=c_res.get("evidence_99", 0),
                            model_c_version="2026-09-04-r1",
                            model_b_state=b_res["state"],
                            computed_at=datetime.now(timezone.utc)
                        ))

                    # Update latest site_model_c
                    mc_row = db.query(SiteModelC).filter(SiteModelC.site_id == sid).first()
                    if mc_row:
                        mc_row.operational_status = c_status
                        mc_row.c_score = c_score
                        mc_row.c_raw = c_raw
                        mc_row.drivers = c_drivers
                        mc_row.evidence_99 = c_res.get("evidence_99", 0)
                        mc_row.event_date = today
                        mc_row.computed_at = datetime.now(timezone.utc)

                # (c) Decision Engine Evaluation & Alert Dispatch
                ma_row = db.query(SiteModelA).filter(SiteModelA.site_id == sid).first()
                a_class = ma_row.class_name if ma_row else "UNKNOWN"
                core_prob = float(ma_row.core_probability) if ma_row else 0.5

                existing_alert = (
                    db.query(Alert)
                    .filter(Alert.site_id == sid, Alert.status == "ACTIVE")
                    .order_by(Alert.created_at.desc())
                    .first()
                )
                existing_alert_dict = None
                if existing_alert:
                    existing_alert_dict = {
                        "alert_level": existing_alert.alert_level,
                        "alert_type": existing_alert.alert_type,
                        "created_at": existing_alert.created_at.isoformat() if existing_alert.created_at else None
                    }

                alert_dict = self.decision_engine.evaluate(
                    site_id=sid,
                    site_day=str(today),
                    model_a_result={"decision": a_class, "probability": core_prob},
                    model_b_result={"state": b_res["state"]},
                    model_c_result={"status": c_status, "c_score": c_score},
                    existing_alert=existing_alert_dict
                )

                if alert_dict and alert_dict.get("alert_level") not in ("NONE", "INFO"):
                    now_utc = datetime.now(timezone.utc)
                    fp = alert_dict.get("alert_fingerprint")
                    existing_fp_alert = db.query(Alert).filter(Alert.fingerprint == fp).first() if fp else None
                    if existing_fp_alert:
                        existing_fp_alert.alert_level = alert_dict["alert_level"]
                        existing_fp_alert.alert_type = alert_dict["alert_type"]
                        existing_fp_alert.headline = alert_dict["headline"]
                        existing_fp_alert.updated_at = now_utc
                    else:
                        new_alert = Alert(
                            alert_id=f"ALT_{uuid.uuid4().hex[:12]}",
                            site_id=sid,
                            site_day=today,
                            alert_type=alert_dict["alert_type"],
                            alert_level=alert_dict["alert_level"],
                            headline=alert_dict["headline"],
                            reason_codes=alert_dict.get("reason_codes"),
                            evidence_required=alert_dict.get("evidence_required", False),
                            fingerprint=fp or f"FP_{uuid.uuid4().hex[:12]}",
                            status="ACTIVE",
                            is_escalation=alert_dict.get("is_escalation", False),
                            created_at=now_utc,
                            updated_at=now_utc
                        )
                        db.add(new_alert)
                    alerts_generated += 1

                # (d) Enqueue for Prithvi Worker if uncertain or high alert
                if (0.405 <= core_prob < 0.885) or (alert_dict and alert_dict.get("alert_level") in ("HIGH", "CRITICAL")):
                    enqueue_site_for_prithvi(sid)

            db.commit()

            # Telemetry update
            ingestion_run.inserted = len(db_detections)
            ingestion_run.updated = len(touched_site_ids)
            ingestion_run.status = "COMPLETED"
            ingestion_run.ended_at = datetime.now(timezone.utc)
            db.commit()

            return {
                "run_id": run_id,
                "status": "COMPLETED",
                "processed_count": len(raw_records),
                "unique_count": ingest_result["unique_count"],
                "duplicate_count": ingest_result["duplicate_count"],
                "matched_count": ingest_result["matched_count"],
                "promoted_count": ingest_result["promoted_count"],
                "touched_sites_count": len(touched_site_ids),
                "alerts_generated": alerts_generated
            }
        except Exception as e:
            logger.error(f"Error executing live ingestion {run_id}: {e}", exc_info=True)
            db.rollback()
            ingestion_run.status = "FAILED"
            ingestion_run.error_summary = str(e)
            ingestion_run.ended_at = datetime.now(timezone.utc)
            db.commit()
            raise


def run_global_daily_model_b_refresh(db: Session, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Daily maintenance task to decay Model B temporal states for sites with no activity today.
    A site active 31 days ago was PERSISTENT or INTERMITTENT, but today slips to DORMANT.
    """
    ref_date = as_of_date or date.today()
    logger.info(f"Running global daily Model B decay refresh for {ref_date}...")

    # Query all sites where state is not already DORMANT
    active_b_rows = (
        db.query(SiteModelB)
        .filter(SiteModelB.state.in_(["PERSISTENT", "INTERMITTENT", "REACTIVATED", "NEW"]))
        .all()
    )

    decayed_to_dormant = 0
    now_utc = datetime.now(timezone.utc)

    for mb in active_b_rows:
        # Check days since last
        if mb.days_since_last is not None:
            mb.days_since_last += 1
            if mb.days_since_last > 30 and mb.state in ("PERSISTENT", "INTERMITTENT", "REACTIVATED", "NEW"):
                mb.state = "DORMANT"
                mb.reason = f"Observation gap reached {mb.days_since_last}d (>30d decay threshold)"
                mb.computed_at = now_utc
                decayed_to_dormant += 1

    db.commit()
    logger.info(f"Global daily Model B refresh complete: {decayed_to_dormant} sites transitioned to DORMANT.")
    return {
        "status": "COMPLETED",
        "as_of_date": str(ref_date),
        "sites_evaluated": len(active_b_rows),
        "decayed_to_dormant": decayed_to_dormant
    }


# Global singleton instance
_live_pipeline: Optional[LivePipelineService] = None

def get_live_pipeline_service() -> LivePipelineService:
    global _live_pipeline
    if _live_pipeline is None:
        _live_pipeline = LivePipelineService()
    return _live_pipeline
