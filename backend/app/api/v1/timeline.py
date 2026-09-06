"""
Site Daily Activity Timeline & Raw FIRMS Detections API Endpoints
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import (
    SourceSite,
    SiteDailyActivity,
    SiteDailyInference,
    FirmsDetection
)
from backend.app.schemas.timeline import SiteTimelineResponse, TimelinePoint
from backend.app.schemas.detections import SiteDetectionsResponse, DetectionItem

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sites/{site_id}/timeline",
    response_model=SiteTimelineResponse,
    summary="Daily FRP history and historical Model C anomaly scores"
)
def get_site_timeline(site_id: str, db: Session = Depends(get_db)):
    """
    Returns full chronological daily activity sequence for a site,
    joined with historical Model C scores and anomaly drivers.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    # Query daily activity joined with daily inferences
    rows = (
        db.query(
            SiteDailyActivity.acq_date,
            SiteDailyActivity.detections,
            SiteDailyActivity.mean_frp,
            SiteDailyActivity.max_frp,
            SiteDailyInference.model_c_status,
            SiteDailyInference.c_score,
            SiteDailyInference.c_raw,
            SiteDailyInference.model_b_state,
            SiteDailyInference.drivers
        )
        .outerjoin(
            SiteDailyInference,
            (SiteDailyActivity.site_id == SiteDailyInference.site_id) &
            (SiteDailyActivity.acq_date == SiteDailyInference.acq_date)
        )
        .filter(SiteDailyActivity.site_id == site_id)
        .order_by(SiteDailyActivity.acq_date.asc())
        .all()
    )

    history: List[TimelinePoint] = []
    for r in rows:
        history.append(
            TimelinePoint(
                acq_date=str(r.acq_date),
                detections=int(r.detections),
                mean_frp=round(float(r.mean_frp), 2),
                max_frp=round(float(r.max_frp), 2),
                c_status=r.model_c_status,
                c_score=round(float(r.c_score), 4) if r.c_score is not None else None,
                c_raw=round(float(r.c_raw), 4) if r.c_raw is not None else None,
                b_state=r.model_b_state,
                drivers=r.drivers if isinstance(r.drivers, list) else None
            )
        )

    first_date = str(history[0].acq_date) if history else None
    last_date = str(history[-1].acq_date) if history else None

    return SiteTimelineResponse(
        site_id=site_id,
        total_active_days=len(history),
        first_date=first_date,
        last_date=last_date,
        history=history
    )


@router.get(
    "/sites/{site_id}/detections",
    response_model=SiteDetectionsResponse,
    summary="Raw individual FIRMS detections for a source site"
)
def get_site_detections(
    site_id: str,
    limit: int = Query(200, ge=1, le=1000, description="Max detection records to return"),
    db: Session = Depends(get_db)
):
    """
    Returns individual FIRMS detections linked to this physical source site.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    records = (
        db.query(FirmsDetection)
        .filter(FirmsDetection.source_site_id == site_id)
        .order_by(FirmsDetection.acq_date.desc(), FirmsDetection.acq_time.desc())
        .limit(limit)
        .all()
    )

    items: List[DetectionItem] = []
    for r in records:
        items.append(
            DetectionItem(
                detection_id=r.detection_id,
                source_sensor=r.source_sensor,
                satellite=r.satellite,
                latitude=float(r.latitude),
                longitude=float(r.longitude),
                acq_date=str(r.acq_date),
                acq_time=str(r.acq_time),
                frp=float(r.frp),
                bright_ti4=float(r.bright_ti4) if r.bright_ti4 is not None else None,
                bright_ti5=float(r.bright_ti5) if r.bright_ti5 is not None else None,
                confidence=r.confidence,
                daynight=r.daynight
            )
        )

    return SiteDetectionsResponse(
        site_id=site_id,
        count=len(items),
        detections=items
    )
