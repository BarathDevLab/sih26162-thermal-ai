"""
Facility Evidence & Satellite Imagery API Endpoints
"""

import os
import math
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import (
    EventEvidence,
    FacilityEvidence,
    ImageryCache,
    SiteModelA,
    SourceSite,
)
from backend.app.schemas.evidence import (
    SiteEvidenceResponse,
    FacilityEvidenceSummary,
    EventEvidenceSummary,
    ImageryCacheSummary
)
from backend.app.services.imagery_service import get_site_imagery_cache, CACHE_DIR
from backend.app.services.prithvi_queue import enqueue_site_for_prithvi
from backend.app.services.stack_readiness import get_shared_model_a

logger = logging.getLogger(__name__)

router = APIRouter()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


@router.get(
    "/sites/{site_id}/evidence",
    response_model=SiteEvidenceResponse,
    summary="Co-located persistent facilities and separately time-filtered event evidence"
)
def get_site_evidence(
    site_id: str,
    radius_m: float = Query(10000.0, ge=500.0, le=50000.0, description="Search radius around site in meters (default 10km)"),
    as_of_date: Optional[date] = Query(None, description="Event-evidence temporal cutoff"),
    temporal_window_days: int = Query(7, ge=0, le=90),
    db: Session = Depends(get_db)
):
    """
    Returns persistent facility evidence and time-bound event evidence as distinct lists.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    site_lat = float(site.latitude)
    site_lon = float(site.longitude)

    # Coarse bounding-box pre-filter (~1 deg lat = 111 km)
    deg_delta = (radius_m / 111000.0) * 1.2
    min_lat, max_lat = site_lat - deg_delta, site_lat + deg_delta
    min_lon, max_lon = site_lon - deg_delta, site_lon + deg_delta

    candidates = (
        db.query(FacilityEvidence)
        .filter(
            FacilityEvidence.latitude >= min_lat,
            FacilityEvidence.latitude <= max_lat,
            FacilityEvidence.longitude >= min_lon,
            FacilityEvidence.longitude <= max_lon
        )
        .all()
    )

    matched: List[FacilityEvidenceSummary] = []
    for cand in candidates:
        dist = haversine_m(site_lat, site_lon, float(cand.latitude), float(cand.longitude))
        if dist <= radius_m:
            matched.append(
                FacilityEvidenceSummary(
                    evidence_id=cand.evidence_id,
                    source_name=cand.source_name,
                    facility_name=cand.facility_name,
                    facility_type=cand.facility_type,
                    latitude=float(cand.latitude),
                    longitude=float(cand.longitude),
                    distance_m=round(dist, 1),
                    coordinate_quality=cand.coordinate_quality or "HIGH",
                    source_url=cand.source_url,
                    attributes=cand.attributes
                )
            )

    matched.sort(key=lambda x: x.distance_m or 0.0)

    cutoff = as_of_date or site.latest_seen or date.today()
    window_start = datetime.combine(
        cutoff - timedelta(days=temporal_window_days), time.min, tzinfo=timezone.utc
    )
    window_end = datetime.combine(
        cutoff + timedelta(days=temporal_window_days), time.max, tzinfo=timezone.utc
    )
    event_candidates = (
        db.query(EventEvidence)
        .filter(
            EventEvidence.latitude >= min_lat,
            EventEvidence.latitude <= max_lat,
            EventEvidence.longitude >= min_lon,
            EventEvidence.longitude <= max_lon,
            EventEvidence.event_start <= window_end,
            (EventEvidence.event_end.is_(None)) | (EventEvidence.event_end >= window_start),
        )
        .all()
    )
    matched_events: List[EventEvidenceSummary] = []
    for event in event_candidates:
        distance = haversine_m(site_lat, site_lon, float(event.latitude), float(event.longitude))
        if distance <= radius_m:
            matched_events.append(EventEvidenceSummary(
                evidence_id=event.evidence_id,
                source_name=event.source_name,
                evidence_type=event.evidence_type,
                reference_id=event.reference_id,
                latitude=float(event.latitude),
                longitude=float(event.longitude),
                distance_m=round(distance, 1),
                event_start=event.event_start.isoformat() if event.event_start else None,
                event_end=event.event_end.isoformat() if event.event_end else None,
                authority_level=event.authority_level,
                source_url=event.source_url,
                attributes=event.attributes,
            ))
    matched_events.sort(key=lambda item: item.distance_m or 0.0)

    return SiteEvidenceResponse(
        site_id=site_id,
        search_radius_m=radius_m,
        total_evidence_count=len(matched),
        evidence=matched,
        as_of_date=cutoff.isoformat(),
        temporal_window_days=temporal_window_days,
        total_event_evidence_count=len(matched_events),
        event_evidence=matched_events,
    )


@router.get(
    "/sites/{site_id}/imagery",
    response_model=List[ImageryCacheSummary],
    summary="Available HLS satellite patches and Prithvi embeddings"
)
def get_site_imagery(
    site_id: str,
    as_of_date: Optional[date] = Query(None, description="Historical acquisition cutoff"),
    db: Session = Depends(get_db),
):
    """
    Returns metadata for genuine cached HLS/Prithvi evidence. Missing or expired
    failed work is queued asynchronously and no probability is fabricated.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    try:
        summaries = get_site_imagery_cache(db, site_id)
        if as_of_date is not None:
            summaries = [item for item in summaries if item.acquisition_date <= as_of_date.isoformat()]
        model_a = db.query(SiteModelA).filter_by(site_id=site_id).one_or_none()
        prithvi_enabled = os.environ.get("PRITHVI_ENABLED", "false").lower() == "true"
        if as_of_date is None and prithvi_enabled and model_a is not None:
            engine = get_shared_model_a()
            if (
                engine.thresh_low <= model_a.core_probability < engine.thresh_core
                and _prithvi_retry_due(db, site_id, summaries)
                and enqueue_site_for_prithvi(site_id)
            ):
                model_a.prithvi_status = "PENDING"
                db.commit()
        return summaries
    except Exception as e:
        logger.error(f"Error reading imagery status for site '{site_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read imagery status: {str(e)}")


def _prithvi_retry_due(
    db: Session, site_id: str, summaries: List[ImageryCacheSummary]
) -> bool:
    """Allow failed asynchronous imagery work to recover without request-loop churn."""

    if any(item.status == "AVAILABLE" for item in summaries):
        return False
    latest = (
        db.query(ImageryCache)
        .filter(ImageryCache.site_id == site_id)
        .order_by(ImageryCache.updated_at.desc())
        .first()
    )
    if latest is None:
        return True
    if latest.status != "UNAVAILABLE":
        return False
    updated_at = latest.updated_at
    if updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    try:
        retry_minutes = max(1, int(os.environ.get("PRITHVI_RETRY_AFTER_MINUTES", "60")))
    except ValueError:
        logger.warning("Invalid PRITHVI_RETRY_AFTER_MINUTES; using 60 minutes.")
        retry_minutes = 60
    return datetime.now(timezone.utc) - updated_at >= timedelta(minutes=retry_minutes)


@router.get(
    "/imagery/patches/{filename}",
    summary="Serve cached satellite patch image"
)
def get_satellite_patch_file(filename: str):
    """
    Returns the binary satellite patch PNG for visual display in the UI.
    """
    cache_root = os.path.abspath(CACHE_DIR)
    file_path = os.path.abspath(os.path.join(cache_root, filename))
    if os.path.commonpath([cache_root, file_path]) != cache_root or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"Satellite patch '{filename}' not found.")
    return FileResponse(file_path, media_type="image/png")
