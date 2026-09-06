"""
Historical Replay Mode API Endpoints
Enforces strict historical cutoff without future data leakage
"""

import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import (
    SourceSite,
    SiteModelA,
    SiteDailyInference,
    SiteDailyActivity,
    Alert
)
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.schemas.sites import (
    SiteGeoJSONFeature,
    SiteGeoJSONGeometry,
    SiteCompactProperties
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/replay",
    response_model=ReplaySnapshotResponse,
    summary="Historical snapshot reconstruction for replay mode"
)
def get_replay_snapshot(
    date: str = Query(..., description="Historical cutoff date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    bbox: str = Query(None, description="Optional bounding box 'min_lon,min_lat,max_lon,max_lat'"),
    limit: int = Query(5000, ge=1, le=10000, description="Max sites to return"),
    db: Session = Depends(get_db)
):
    """
    Reconstructs the spatial state of thermal sources and anomalies as of the exact specified date.
    Never uses post-cutoff observations or states.
    """
    try:
        cutoff_date = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    try:
        # Query historical inferences on this specific date
        query = (
            db.query(
                SourceSite.site_id,
                SourceSite.latitude,
                SourceSite.longitude,
                SiteModelA.class_name.label("a_class"),
                SiteModelA.core_probability.label("a_prob"),
                SiteDailyInference.model_b_state.label("b_state"),
                SiteDailyInference.model_c_status.label("c_status"),
                SiteDailyInference.c_score.label("c_score"),
                Alert.alert_level.label("alert_severity"),
                Alert.alert_type.label("alert_type")
            )
            .join(SiteDailyInference, SourceSite.site_id == SiteDailyInference.site_id)
            .outerjoin(SiteModelA, SourceSite.site_id == SiteModelA.site_id)
            .outerjoin(
                Alert,
                (SourceSite.site_id == Alert.site_id) &
                (Alert.site_day == cutoff_date)
            )
            .filter(SiteDailyInference.acq_date == cutoff_date)
        )

        # Bounding box filter
        if bbox:
            try:
                parts = [float(p.strip()) for p in bbox.split(",")]
                if len(parts) == 4:
                    min_lon, min_lat, max_lon, max_lat = parts
                    query = query.filter(
                        SourceSite.longitude >= min_lon,
                        SourceSite.longitude <= max_lon,
                        SourceSite.latitude >= min_lat,
                        SourceSite.latitude <= max_lat
                    )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid bbox: {e}")

        rows = query.limit(limit).all()

        features: List[SiteGeoJSONFeature] = []
        alerts_count = 0
        for r in rows:
            if r.alert_severity:
                alerts_count += 1
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
                        c_status=r.c_status or "NORMAL",
                        c_score=round(float(r.c_score), 4) if r.c_score is not None else None,
                        alert_severity=r.alert_severity,
                        alert_type=r.alert_type,
                        latest_seen=date
                    )
                )
            )

        return ReplaySnapshotResponse(
            as_of_date=date,
            active_sites_count=len(features),
            alerts_count=alerts_count,
            features=features
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching replay snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate replay snapshot: {str(e)}")
