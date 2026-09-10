"""
Spatial Source Sites API Endpoints
Implements Section 18.2 Map Viewport Optimization & Site Intelligence Drawer
"""

import logging
import os
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, select, or_, text
from sqlalchemy.orm import aliased

from backend.app.db.session import get_db
from backend.app.db.models import (
    SourceSite,
    SiteModelA,
    SiteModelB,
    SiteModelC,
    SiteModelAHistory,
    SiteDailyActivity,
    SiteDailyInference,
    Alert
)
from backend.app.engines.model_b import ModelBEngine
from backend.app.schemas.sites import (
    SiteGeoJSONFeatureCollection,
    SiteGeoJSONFeature,
    SiteGeoJSONGeometry,
    SiteCompactProperties,
    SiteDetail,
    ModelASummary,
    ModelBSummary,
    ModelCSummary,
    AlertSummary
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sites",
    response_model=SiteGeoJSONFeatureCollection,
    summary="Viewport-filtered source sites as compact GeoJSON"
)
def get_sites(
    bbox: Optional[str] = Query(
        None,
        description="Bounding box in format 'min_lon,min_lat,max_lon,max_lat' (e.g. '68.0,8.0,97.0,37.0')"
    ),
    a_class: Optional[str] = Query(None, description="Model A class: INDUSTRIAL, NONINDUSTRIAL, UNKNOWN"),
    b_state: Optional[str] = Query(None, description="Model B state: PERSISTENT, DORMANT, REACTIVATED, INTERMITTENT, NEW"),
    c_status: Optional[str] = Query(None, description="Model C status: NORMAL, ELEVATED, ANOMALOUS, CRITICAL, INSUFFICIENT_HISTORY"),
    alert_severity: Optional[str] = Query(None, description="Alert severity: CRITICAL, HIGH, MEDIUM, LOW, INFO"),
    limit: int = Query(5000, ge=1, le=10000, description="Max sites to return (default 5000, max 10000)"),
    db: Session = Depends(get_db)
):
    """
    Returns a lightweight, high-performance GeoJSON FeatureCollection optimized for deck.gl/MapLibre.
    Enforces Section 18.2 map performance rules: returns compact properties only.
    """
    try:
        # Base query joining latest A, B, C and optional active alert
        active_alert = aliased(Alert)
        latest_active_alert_id = (
            select(Alert.alert_id)
            .where(Alert.site_id == SourceSite.site_id, Alert.status == "ACTIVE")
            .order_by(Alert.updated_at.desc(), Alert.alert_id.desc())
            .limit(1)
            .correlate(SourceSite)
            .scalar_subquery()
        )
        query = (
            db.query(
                SourceSite.site_id,
                SourceSite.latitude,
                SourceSite.longitude,
                SourceSite.latest_seen,
                SiteModelA.class_name.label("a_class"),
                SiteModelA.core_probability.label("a_prob"),
                SiteModelB.state.label("b_state"),
                SiteModelC.operational_status.label("c_status"),
                SiteModelC.c_score.label("c_score"),
                active_alert.alert_level.label("alert_severity"),
                active_alert.alert_type.label("alert_type"),
            )
            .outerjoin(SiteModelA, SourceSite.site_id == SiteModelA.site_id)
            .outerjoin(SiteModelB, SourceSite.site_id == SiteModelB.site_id)
            .outerjoin(SiteModelC, SourceSite.site_id == SiteModelC.site_id)
            .outerjoin(active_alert, active_alert.alert_id == latest_active_alert_id)
        )
        count_query = db.query(func.count(SourceSite.site_id))

        # 1. Bounding Box Filter
        if bbox:
            try:
                parts = [float(p.strip()) for p in bbox.split(",")]
                if len(parts) != 4:
                    raise ValueError("BBox must have 4 comma-separated values.")
                min_lon, min_lat, max_lon, max_lat = parts
                if min_lon > max_lon or min_lat > max_lat:
                    raise ValueError("BBox minimums must not exceed maximums.")
                if db.get_bind().dialect.name == "postgresql":
                    # Use the migration-managed geometry column so PostgreSQL can
                    # satisfy viewport requests through the PostGIS GIST index.
                    query = query.filter(
                        text(
                            "source_sites.geometry && "
                            "ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)"
                        )
                    ).params(
                        min_lon=min_lon,
                        min_lat=min_lat,
                        max_lon=max_lon,
                        max_lat=max_lat,
                    )
                    count_query = count_query.filter(
                        text(
                            "source_sites.geometry && "
                            "ST_MakeEnvelope(:count_min_lon, :count_min_lat, "
                            ":count_max_lon, :count_max_lat, 4326)"
                        )
                    ).params(
                        count_min_lon=min_lon,
                        count_min_lat=min_lat,
                        count_max_lon=max_lon,
                        count_max_lat=max_lat,
                    )
                else:
                    query = query.filter(
                        SourceSite.longitude >= min_lon,
                        SourceSite.longitude <= max_lon,
                        SourceSite.latitude >= min_lat,
                        SourceSite.latitude <= max_lat
                    )
                    count_query = count_query.filter(
                        SourceSite.longitude >= min_lon,
                        SourceSite.longitude <= max_lon,
                        SourceSite.latitude >= min_lat,
                        SourceSite.latitude <= max_lat,
                    )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid bbox parameter: {e}")

        # 2. Filter by Model A Identity
        if a_class:
            query = query.filter(SiteModelA.class_name == a_class.upper())
            count_query = count_query.join(
                SiteModelA, SourceSite.site_id == SiteModelA.site_id
            ).filter(SiteModelA.class_name == a_class.upper())

        # 3. Filter by Model B Temporal State
        if b_state:
            query = query.filter(SiteModelB.state == b_state.upper())
            count_query = count_query.join(
                SiteModelB, SourceSite.site_id == SiteModelB.site_id
            ).filter(SiteModelB.state == b_state.upper())

        # 4. Filter by Model C Anomaly Status
        if c_status:
            query = query.filter(SiteModelC.operational_status == c_status.upper())
            count_query = count_query.join(
                SiteModelC, SourceSite.site_id == SiteModelC.site_id
            ).filter(SiteModelC.operational_status == c_status.upper())

        # 5. Filter by Alert Severity
        if alert_severity:
            query = query.filter(active_alert.alert_level == alert_severity.upper())
            count_alert = aliased(Alert)
            count_latest_alert_id = (
                select(Alert.alert_id)
                .where(Alert.site_id == SourceSite.site_id, Alert.status == "ACTIVE")
                .order_by(Alert.updated_at.desc(), Alert.alert_id.desc())
                .limit(1)
                .correlate(SourceSite)
                .scalar_subquery()
            )
            count_query = count_query.join(
                count_alert, count_alert.alert_id == count_latest_alert_id
            ).filter(count_alert.alert_level == alert_severity.upper())

        # Count separately so the capped payload query can use a top-N plan. A
        # COUNT(*) window forced PostgreSQL to materialize every matching viewport
        # row before it could return even a small map payload.
        total_count = int(
            count_query.scalar() or 0
        )

        # Prioritize actionable/recent sites and keep the capped result stable.
        rows = (
            query.order_by(
                active_alert.updated_at.desc().nullslast(),
                SiteModelC.c_score.desc().nullslast(),
                SourceSite.latest_seen.desc().nullslast(),
                SourceSite.site_id,
            )
            .limit(limit)
            .all()
        )

        features: List[SiteGeoJSONFeature] = []
        for r in rows:
            features.append(
                SiteGeoJSONFeature(
                    geometry=SiteGeoJSONGeometry(
                        coordinates=[round(float(r.longitude), 5), round(float(r.latitude), 5)]
                    ),
                    properties=SiteCompactProperties(
                        site_id=r.site_id,
                        a_class=r.a_class or "UNAVAILABLE",
                        a_prob=round(float(r.a_prob), 4) if r.a_prob is not None else None,
                        b_state=r.b_state or "UNAVAILABLE",
                        c_status=r.c_status or "UNAVAILABLE",
                        c_score=round(float(r.c_score), 4) if r.c_score is not None else None,
                        alert_severity=r.alert_severity,
                        alert_type=r.alert_type,
                        latest_seen=str(r.latest_seen) if r.latest_seen else None
                    )
                )
            )

        response = SiteGeoJSONFeatureCollection(
            features=features,
            total_count=total_count,
            returned_count=len(features),
            truncated=total_count > len(features),
        )
        # The collection is already validated while it is constructed above.
        # Returning Pydantic's native JSON avoids FastAPI recursively encoding and
        # validating thousands of nested feature models a second time.
        return Response(
            content=response.model_dump_json(),
            media_type="application/json",
            headers={"Cache-Control": "private, max-age=15"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing viewport sites query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query sites: {str(e)}")


@router.get(
    "/sites/{site_id}",
    response_model=SiteDetail,
    summary="Full intelligence summary for selected source site"
)
def get_site_detail(
    site_id: str,
    as_of_date: Optional[date] = Query(None, description="Leakage-safe historical cutoff"),
    db: Session = Depends(get_db),
):
    """
    Returns complete site profile including spatial coordinates, static WorldCover,
    A-Core + guarded Prithvi prediction, Model B temporal state, Model C anomaly metrics,
    and active operational alert.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")
    if as_of_date is not None:
        return _historical_site_detail(db, site, as_of_date)

    # 1. Model A
    model_a_summary = None
    if site.model_a:
        ma = site.model_a
        model_a_summary = ModelASummary(
            class_name=ma.class_name,
            decision=ma.decision,
            core_probability=round(float(ma.core_probability), 4),
            prithvi_probability=round(float(ma.prithvi_probability), 4) if ma.prithvi_probability is not None else None,
            prithvi_status=ma.prithvi_status or "NOT_TRIGGERED",
            model_version=ma.model_version,
            feature_version=ma.feature_version,
            feature_as_of_detection_date=(
                str(ma.feature_as_of_detection_date) if ma.feature_as_of_detection_date else None
            ),
            imagery_acquisition_date=(
                str(ma.imagery_acquisition_date) if ma.imagery_acquisition_date else None
            ),
            computed_at=ma.computed_at.isoformat() if ma.computed_at else None,
        )

    # 2. Model B
    model_b_summary = None
    if site.model_b:
        mb = site.model_b
        model_b_summary = ModelBSummary(
            state=mb.state,
            confidence=mb.confidence,
            reason=mb.reason,
            days_since_last=mb.days_since_last,
            active_days_windows=mb.active_days_windows,
            model_version=mb.model_version
        )

    # 3. Model C
    model_c_summary = None
    if site.model_c:
        mc = site.model_c
        model_c_summary = ModelCSummary(
            operational_status=mc.operational_status,
            c_score=round(float(mc.c_score), 4) if mc.c_score is not None else None,
            c_raw=round(float(mc.c_raw), 4) if mc.c_raw is not None else None,
            group_scores=mc.group_scores,
            evidence_99=mc.evidence_99 or 0,
            drivers=mc.drivers,
            event_date=str(mc.event_date) if mc.event_date else None,
            model_version=mc.model_version
        )

    # 4. Active Alert
    active_alert_summary = None
    alert_rec = (
        db.query(Alert)
        .filter(Alert.site_id == site_id, Alert.status == "ACTIVE")
        .order_by(Alert.created_at.desc())
        .first()
    )
    if alert_rec:
        active_alert_summary = AlertSummary(
            alert_id=alert_rec.alert_id,
            alert_type=alert_rec.alert_type,
            alert_level=alert_rec.alert_level,
            headline=alert_rec.headline,
            reason_codes=alert_rec.reason_codes,
            evidence_required=alert_rec.evidence_required,
            is_escalation=alert_rec.is_escalation,
            status=alert_rec.status,
            created_at=alert_rec.created_at.isoformat() if alert_rec.created_at else "",
            updated_at=alert_rec.updated_at.isoformat() if alert_rec.updated_at else ""
        )

    return SiteDetail(
        site_id=site.site_id,
        latitude=float(site.latitude),
        longitude=float(site.longitude),
        status=site.status or "ACTIVE",
        created_at=site.created_at.isoformat() if site.created_at else "",
        latest_seen=str(site.latest_seen) if site.latest_seen else None,
        land_cover=site.land_cover,
        spatial_stats=site.spatial_stats,
        model_a=model_a_summary,
        model_b=model_b_summary,
        model_c=model_c_summary,
        active_alert=active_alert_summary
    )


def _historical_site_detail(db: Session, site: SourceSite, cutoff: date) -> SiteDetail:
    active_dates = [
        row[0]
        for row in db.query(SiteDailyActivity.acq_date)
        .filter(
            SiteDailyActivity.site_id == site.site_id,
            SiteDailyActivity.acq_date <= cutoff,
        )
        .order_by(SiteDailyActivity.acq_date)
        .all()
    ]
    if not active_dates:
        raise HTTPException(
            status_code=404,
            detail=f"Source site '{site.site_id}' did not exist at cutoff {cutoff}.",
        )

    a_row = (
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
    model_a = None
    if a_row is not None:
        model_a = ModelASummary(
            class_name=a_row.class_name,
            decision=a_row.decision,
            core_probability=round(float(a_row.core_probability), 4),
            prithvi_probability=(
                round(float(a_row.prithvi_probability), 4)
                if a_row.prithvi_probability is not None else None
            ),
            prithvi_status=a_row.prithvi_status,
            model_version=a_row.model_version,
            feature_version=a_row.feature_version,
            feature_as_of_detection_date=str(a_row.feature_as_of_detection_date),
            imagery_acquisition_date=(
                str(a_row.imagery_acquisition_date) if a_row.imagery_acquisition_date else None
            ),
            computed_at=a_row.computed_at.isoformat() if a_row.computed_at else None,
        )

    b_result = ModelBEngine().predict(active_dates, as_of_date=cutoff)
    b_stats = b_result.get("stats", {})
    model_b = ModelBSummary(
        state=b_result["state"],
        confidence=b_result["confidence"],
        reason=b_result.get("reason"),
        days_since_last=b_stats.get("days_since_last"),
        active_days_windows={
            key: b_stats.get(f"active_days_{key}", 0)
            for key in ("30", "90", "180", "365")
        },
        model_version=os.environ.get("MODEL_STACK_VERSION", "2026-09-04-r1"),
    )

    c_row = (
        db.query(SiteDailyInference)
        .filter(
            SiteDailyInference.site_id == site.site_id,
            SiteDailyInference.acq_date <= cutoff,
        )
        .order_by(SiteDailyInference.acq_date.desc())
        .first()
    )
    model_c = None
    if c_row is not None:
        no_recent_event = (cutoff - c_row.acq_date).days > 30
        model_c = ModelCSummary(
            operational_status=("NO_RECENT_EVENT" if no_recent_event else c_row.model_c_status),
            c_score=None if no_recent_event else c_row.c_score,
            c_raw=None if no_recent_event else c_row.c_raw,
            group_scores=None if no_recent_event else c_row.group_scores,
            evidence_99=0 if no_recent_event else (c_row.evidence_99 or 0),
            drivers=None if no_recent_event else c_row.drivers,
            event_date=str(c_row.acq_date),
            model_version=c_row.model_c_version,
        )

    return SiteDetail(
        site_id=site.site_id,
        latitude=float(site.latitude),
        longitude=float(site.longitude),
        status=site.status or "ACTIVE",
        created_at=site.created_at.isoformat() if site.created_at else "",
        latest_seen=str(active_dates[-1]),
        land_cover=site.land_cover,
        spatial_stats=site.spatial_stats,
        model_a=model_a,
        model_b=model_b,
        model_c=model_c,
        active_alert=None,
    )
