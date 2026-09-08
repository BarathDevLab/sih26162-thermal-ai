"""Leakage-safe historical system snapshot reconstruction."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.db.models import (
    SiteDailyActivity,
    SiteDailyInference,
    SiteModelAHistory,
    SourceSite,
)
from backend.app.db.session import get_db
from backend.app.engines.model_b import ModelBEngine
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.schemas.sites import SiteCompactProperties, SiteGeoJSONFeature, SiteGeoJSONGeometry


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/replay", response_model=ReplaySnapshotResponse)
def get_replay_snapshot(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    bbox: str = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    try:
        cutoff = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    latest_activity = (
        db.query(
            SiteDailyActivity.site_id.label("site_id"),
            func.max(SiteDailyActivity.acq_date).label("latest_seen"),
        )
        .filter(SiteDailyActivity.acq_date <= cutoff)
        .group_by(SiteDailyActivity.site_id)
        .subquery()
    )
    query = (
        db.query(SourceSite, latest_activity.c.latest_seen)
        .join(latest_activity, latest_activity.c.site_id == SourceSite.site_id)
    )
    if bbox:
        try:
            parts = [float(value.strip()) for value in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox must contain four values")
            min_lon, min_lat, max_lon, max_lat = parts
            query = query.filter(
                SourceSite.longitude.between(min_lon, max_lon),
                SourceSite.latitude.between(min_lat, max_lat),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid bbox: {exc}")

    rows = query.order_by(SourceSite.site_id).limit(limit).all()
    features: List[SiteGeoJSONFeature] = []
    alert_count = 0
    model_b = ModelBEngine()
    decision_engine = DecisionEngine()

    for site, latest_seen in rows:
        a_history = (
            db.query(SiteModelAHistory)
            .filter(
                SiteModelAHistory.site_id == site.site_id,
                SiteModelAHistory.feature_as_of_detection_date <= cutoff,
                or_(
                    SiteModelAHistory.imagery_acquisition_date.is_(None),
                    SiteModelAHistory.imagery_acquisition_date <= cutoff,
                ),
            )
            .order_by(
                SiteModelAHistory.feature_as_of_detection_date.desc(),
                SiteModelAHistory.computed_at.desc(),
            )
            .first()
        )
        c_history = (
            db.query(SiteDailyInference)
            .filter(
                SiteDailyInference.site_id == site.site_id,
                SiteDailyInference.acq_date <= cutoff,
            )
            .order_by(SiteDailyInference.acq_date.desc())
            .first()
        )
        active_dates = [
            value[0]
            for value in db.query(SiteDailyActivity.acq_date)
            .filter(
                SiteDailyActivity.site_id == site.site_id,
                SiteDailyActivity.acq_date <= cutoff,
            )
            .order_by(SiteDailyActivity.acq_date)
            .all()
        ]
        b_result = model_b.predict(active_dates, as_of_date=cutoff) if active_dates else None
        if c_history is None:
            c_status = "UNAVAILABLE"
            c_score = None
        elif (cutoff - c_history.acq_date).days > 30:
            c_status = "NO_RECENT_EVENT"
            c_score = None
        else:
            c_status = c_history.model_c_status
            c_score = c_history.c_score

        replay_alert = None
        if (
            a_history is not None
            and b_result is not None
            and c_status not in ("NO_RECENT_EVENT", "UNAVAILABLE")
        ):
            candidate = decision_engine.evaluate(
                site_id=site.site_id,
                site_day=cutoff.isoformat(),
                model_a_result={"decision": a_history.decision},
                model_b_result=b_result,
                model_c_result={"status": c_status, "c_score": c_score},
            )
            if candidate["alert_level"] not in ("NONE", "INFO"):
                replay_alert = candidate
                alert_count += 1
        features.append(SiteGeoJSONFeature(
            geometry=SiteGeoJSONGeometry(coordinates=[site.longitude, site.latitude]),
            properties=SiteCompactProperties(
                site_id=site.site_id,
                a_class=a_history.class_name if a_history else "UNAVAILABLE",
                a_prob=a_history.core_probability if a_history else None,
                b_state=b_result["state"] if b_result else "UNAVAILABLE",
                c_status=c_status,
                c_score=c_score,
                alert_severity=replay_alert["alert_level"] if replay_alert else None,
                alert_type=replay_alert["alert_type"] if replay_alert else None,
                latest_seen=str(latest_seen),
            ),
        ))

    return ReplaySnapshotResponse(
        as_of_date=date,
        active_sites_count=len(features),
        alerts_count=alert_count,
        features=features,
    )
