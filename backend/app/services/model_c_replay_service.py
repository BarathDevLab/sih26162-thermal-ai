"""Chronological Model C replay and state persistence."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import SiteDailyActivity, SiteDailyInference, SiteModelC
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.model_c import ModelCEngine


MODEL_VERSION = os.environ.get("MODEL_STACK_VERSION", "2026-09-04-r1")


class ModelCReplayService:
    def __init__(
        self,
        model_c: Optional[ModelCEngine] = None,
        model_b: Optional[ModelBEngine] = None,
    ) -> None:
        self.model_c = model_c or ModelCEngine()
        self.model_b = model_b or ModelBEngine()

    def replay_site(
        self,
        db: Session,
        site_id: str,
        cutoff: Optional[date] = None,
    ) -> Dict[str, object]:
        latest_available = (
            db.query(SiteDailyActivity.acq_date)
            .filter(SiteDailyActivity.site_id == site_id)
            .order_by(SiteDailyActivity.acq_date.desc())
            .first()
        )
        query = db.query(SiteDailyActivity).filter(SiteDailyActivity.site_id == site_id)
        if cutoff is not None:
            query = query.filter(SiteDailyActivity.acq_date <= cutoff)
        activities = query.order_by(SiteDailyActivity.acq_date.asc()).all()
        if not activities:
            return {"site_id": site_id, "replayed_days": 0, "latest": None}

        history = []
        prev_ewma = 0.0
        prev_cusum = 0.0
        latest_result = None
        now = datetime.now(timezone.utc)
        active_dates = [activity.acq_date for activity in activities]

        for index, activity in enumerate(activities):
            current = {
                "site_id": site_id,
                "acq_date": activity.acq_date,
                "detections": activity.detections,
                "mean_frp": activity.mean_frp,
                "max_frp": activity.max_frp,
            }
            result = self.model_c.score(
                history,
                current,
                prev_ewma=prev_ewma,
                prev_cusum=prev_cusum,
            )
            b_result = self.model_b.predict(active_dates[: index + 1], as_of_date=activity.acq_date)
            row = db.query(SiteDailyInference).filter_by(
                site_id=site_id, acq_date=activity.acq_date
            ).one_or_none()
            if row is None:
                row = SiteDailyInference(site_id=site_id, acq_date=activity.acq_date)
                db.add(row)
            row.model_c_status = result["status"]
            row.c_score = result.get("c_score")
            row.c_raw = result.get("c_raw")
            row.group_scores = result.get("group_scores")
            row.evidence_99 = result.get("evidence_99", 0)
            row.drivers = result.get("drivers")
            row.raw_signals = result.get("raw_signals")
            row.model_c_version = MODEL_VERSION
            row.model_b_state = b_result["state"]
            row.computed_at = now

            raw_signals = result.get("raw_signals") or {}
            if result.get("history_ok") and raw_signals:
                prev_ewma = float(raw_signals["ewma_score"])
                prev_cusum = float(raw_signals["cusum_score"])
            history.append(current)
            latest_result = result

        materialize_latest = (
            cutoff is None
            or latest_available is None
            or cutoff >= latest_available[0]
        )
        if materialize_latest:
            latest = db.query(SiteModelC).filter_by(site_id=site_id).one_or_none()
            if latest is None:
                latest = SiteModelC(site_id=site_id)
                db.add(latest)
            latest.event_date = activities[-1].acq_date
            latest.operational_status = latest_result["status"]
            latest.c_score = latest_result.get("c_score")
            latest.c_raw = latest_result.get("c_raw")
            latest.group_scores = latest_result.get("group_scores")
            latest.evidence_99 = latest_result.get("evidence_99", 0)
            latest.drivers = latest_result.get("drivers")
            latest.history_counts = {
                "prior_active_days": max(0, len(activities) - 1),
                "data_through_date": str(activities[-1].acq_date),
            }
            latest.model_version = MODEL_VERSION
            latest.computed_at = now
        db.flush()
        return {
            "site_id": site_id,
            "replayed_days": len(activities),
            "latest": latest_result,
            "event_date": activities[-1].acq_date,
        }
