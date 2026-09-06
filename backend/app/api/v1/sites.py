"""
Spatial Source Sites API Endpoints
Implements Section 18.2 Map Viewport Optimization & Site Intelligence Drawer
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.db.session import get_db
from backend.app.db.models import (
    SourceSite,
    SiteModelA,
    SiteModelB,
    SiteModelC,
    Alert
)
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
                Alert.alert_level.label("alert_severity"),
                Alert.alert_type.label("alert_type")
            )
            .outerjoin(SiteModelA, SourceSite.site_id == SiteModelA.site_id)
            .outerjoin(SiteModelB, SourceSite.site_id == SiteModelB.site_id)
            .outerjoin(SiteModelC, SourceSite.site_id == SiteModelC.site_id)
            .outerjoin(Alert, (SourceSite.site_id == Alert.site_id) & (Alert.status == "ACTIVE"))
        )

        # 1. Bounding Box Filter
        if bbox:
            try:
                parts = [float(p.strip()) for p in bbox.split(",")]
                if len(parts) != 4:
                    raise ValueError("BBox must have 4 comma-separated values.")
                min_lon, min_lat, max_lon, max_lat = parts
                query = query.filter(
                    SourceSite.longitude >= min_lon,
                    SourceSite.longitude <= max_lon,
                    SourceSite.latitude >= min_lat,
                    SourceSite.latitude <= max_lat
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid bbox parameter: {e}")

        # 2. Filter by Model A Identity
        if a_class:
            query = query.filter(SiteModelA.class_name == a_class.upper())

        # 3. Filter by Model B Temporal State
        if b_state:
            query = query.filter(SiteModelB.state == b_state.upper())

        # 4. Filter by Model C Anomaly Status
        if c_status:
            query = query.filter(SiteModelC.operational_status == c_status.upper())

        # 5. Filter by Alert Severity
        if alert_severity:
            query = query.filter(Alert.alert_level == alert_severity.upper())

        # Fetch limited records
        rows = query.limit(limit).all()

        features: List[SiteGeoJSONFeature] = []
        for r in rows:
            features.append(
                SiteGeoJSONFeature(
                    geometry=SiteGeoJSONGeometry(
                        coordinates=[round(float(r.longitude), 5), round(float(r.latitude), 5)]
                    ),
                    properties=SiteCompactProperties(
                        site_id=r.site_id,
                        a_class=r.a_class or "UNKNOWN",
                        a_prob=round(float(r.a_prob or 0.5), 4),
                        b_state=r.b_state or "DORMANT",
                        c_status=r.c_status or "INSUFFICIENT_HISTORY",
                        c_score=round(float(r.c_score), 4) if r.c_score is not None else None,
                        alert_severity=r.alert_severity,
                        alert_type=r.alert_type,
                        latest_seen=str(r.latest_seen) if r.latest_seen else None
                    )
                )
            )

        return SiteGeoJSONFeatureCollection(
            features=features,
            total_count=len(features)
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
def get_site_detail(site_id: str, db: Session = Depends(get_db)):
    """
    Returns complete site profile including spatial coordinates, static WorldCover,
    A-Core + guarded Prithvi prediction, Model B temporal state, Model C anomaly metrics,
    and active operational alert.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

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
            model_version=ma.model_version
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
            evidence_99=mc.evidence_99,
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
