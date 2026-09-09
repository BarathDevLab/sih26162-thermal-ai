"""Bulk, leakage-safe historical replay reconstruction."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    SiteDailyActivity,
    SiteDailyInference,
    SiteModelAHistory,
    SourceSite,
)
from backend.app.engines.decision_engine import DecisionEngine
from backend.app.engines.model_b import ModelBEngine
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.schemas.sites import (
    SiteCompactProperties,
    SiteGeoJSONFeature,
    SiteGeoJSONGeometry,
)


def parse_bbox(bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if bbox is None:
        return None
    parts = [float(value.strip()) for value in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must contain four values")
    min_lon, min_lat, max_lon, max_lat = parts
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("bbox minimums must not exceed maximums")
    return min_lon, min_lat, max_lon, max_lat


def build_replay_snapshot(
    db: Session,
    cutoff,
    bbox: Optional[str] = None,
    limit: int = 5000,
) -> ReplaySnapshotResponse:
    """Build one historical viewport using a bounded number of bulk queries."""
    bounds = parse_bbox(bbox)
    latest_activity = (
        db.query(
            SiteDailyActivity.site_id.label("site_id"),
            func.max(SiteDailyActivity.acq_date).label("latest_seen"),
        )
        .filter(SiteDailyActivity.acq_date <= cutoff)
        .group_by(SiteDailyActivity.site_id)
        .subquery()
    )
    site_query = (
        db.query(SourceSite, latest_activity.c.latest_seen)
        .join(latest_activity, latest_activity.c.site_id == SourceSite.site_id)
    )
    if bounds:
        min_lon, min_lat, max_lon, max_lat = bounds
        site_query = site_query.filter(
            SourceSite.longitude.between(min_lon, max_lon),
            SourceSite.latitude.between(min_lat, max_lat),
        )

    total_count = site_query.order_by(None).count()
    rows = (
        site_query.order_by(latest_activity.c.latest_seen.desc(), SourceSite.site_id)
        .limit(limit)
        .all()
    )
    if not rows:
        return ReplaySnapshotResponse(
            as_of_date=cutoff.isoformat(),
            active_sites_count=total_count,
            returned_sites_count=0,
            truncated=False,
            alerts_count=0,
            features=[],
        )

    site_ids = [site.site_id for site, _ in rows]
    a_by_site = _latest_model_a(db, site_ids, cutoff)
    c_by_site = _latest_model_c(db, site_ids, cutoff)
    dates_by_site = _activity_dates(db, site_ids, cutoff)

    model_b = ModelBEngine()
    decision_engine = DecisionEngine()
    decision_time = datetime.combine(cutoff, time.min, tzinfo=timezone.utc)
    features: List[SiteGeoJSONFeature] = []
    alert_count = 0

    for site, latest_seen in rows:
        a_history = a_by_site.get(site.site_id)
        c_history = c_by_site.get(site.site_id)
        active_dates = dates_by_site.get(site.site_id, [])
        b_result = model_b.predict(active_dates, as_of_date=cutoff) if active_dates else None

        if c_history is None:
            c_status = "UNAVAILABLE"
            c_score = None
        elif (cutoff - c_history["acq_date"]).days > 30:
            c_status = "NO_RECENT_EVENT"
            c_score = None
        else:
            c_status = c_history["model_c_status"]
            c_score = c_history["c_score"]

        replay_alert = None
        if (
            a_history is not None
            and b_result is not None
            and c_status not in ("NO_RECENT_EVENT", "UNAVAILABLE")
        ):
            candidate = decision_engine.evaluate(
                site_id=site.site_id,
                site_day=cutoff.isoformat(),
                model_a_result={"decision": a_history["decision"]},
                model_b_result=b_result,
                model_c_result={"status": c_status, "c_score": c_score},
                as_of_time=decision_time,
            )
            if candidate["alert_level"] not in ("NONE", "INFO"):
                replay_alert = candidate
                alert_count += 1

        features.append(SiteGeoJSONFeature(
            geometry=SiteGeoJSONGeometry(
                coordinates=[float(site.longitude), float(site.latitude)]
            ),
            properties=SiteCompactProperties(
                site_id=site.site_id,
                a_class=a_history["class_name"] if a_history else "UNAVAILABLE",
                a_prob=a_history["core_probability"] if a_history else None,
                b_state=b_result["state"] if b_result else "UNAVAILABLE",
                c_status=c_status,
                c_score=c_score,
                alert_severity=replay_alert["alert_level"] if replay_alert else None,
                alert_type=replay_alert["alert_type"] if replay_alert else None,
                latest_seen=latest_seen.isoformat() if latest_seen else None,
            ),
        ))

    return ReplaySnapshotResponse(
        as_of_date=cutoff.isoformat(),
        active_sites_count=total_count,
        returned_sites_count=len(features),
        truncated=total_count > len(features),
        alerts_count=alert_count,
        features=features,
    )


def _latest_model_a(db: Session, site_ids: List[str], cutoff) -> Dict[str, dict]:
    ranked = select(
        SiteModelAHistory.site_id.label("site_id"),
        SiteModelAHistory.class_name.label("class_name"),
        SiteModelAHistory.decision.label("decision"),
        SiteModelAHistory.core_probability.label("core_probability"),
        func.row_number().over(
            partition_by=SiteModelAHistory.site_id,
            order_by=(
                SiteModelAHistory.feature_as_of_detection_date.desc(),
                SiteModelAHistory.computed_at.desc(),
                SiteModelAHistory.inference_id.desc(),
            ),
        ).label("row_rank"),
    ).where(
        SiteModelAHistory.site_id.in_(site_ids),
        SiteModelAHistory.feature_as_of_detection_date <= cutoff,
        or_(
            SiteModelAHistory.imagery_acquisition_date.is_(None),
            SiteModelAHistory.imagery_acquisition_date <= cutoff,
        ),
    ).subquery()
    result = db.execute(select(ranked).where(ranked.c.row_rank == 1)).mappings()
    return {row["site_id"]: dict(row) for row in result}


def _latest_model_c(db: Session, site_ids: List[str], cutoff) -> Dict[str, dict]:
    ranked = select(
        SiteDailyInference.site_id.label("site_id"),
        SiteDailyInference.acq_date.label("acq_date"),
        SiteDailyInference.model_c_status.label("model_c_status"),
        SiteDailyInference.c_score.label("c_score"),
        func.row_number().over(
            partition_by=SiteDailyInference.site_id,
            order_by=SiteDailyInference.acq_date.desc(),
        ).label("row_rank"),
    ).where(
        SiteDailyInference.site_id.in_(site_ids),
        SiteDailyInference.acq_date <= cutoff,
    ).subquery()
    result = db.execute(select(ranked).where(ranked.c.row_rank == 1)).mappings()
    return {row["site_id"]: dict(row) for row in result}


def _activity_dates(db: Session, site_ids: List[str], cutoff) -> Dict[str, List]:
    grouped: Dict[str, List] = defaultdict(list)
    rows = (
        db.query(SiteDailyActivity.site_id, SiteDailyActivity.acq_date)
        .filter(
            SiteDailyActivity.site_id.in_(site_ids),
            SiteDailyActivity.acq_date <= cutoff,
        )
        .order_by(SiteDailyActivity.site_id, SiteDailyActivity.acq_date)
        .all()
    )
    for site_id, acq_date in rows:
        grouped[site_id].append(acq_date)
    return grouped
