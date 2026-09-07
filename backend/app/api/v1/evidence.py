"""
Facility Evidence & Satellite Imagery API Endpoints
"""

import os
import math
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import SourceSite, FacilityEvidence, ImageryCache
from backend.app.schemas.evidence import (
    SiteEvidenceResponse,
    FacilityEvidenceSummary,
    ImageryCacheSummary
)
from backend.app.services.imagery_service import get_or_create_site_imagery, CACHE_DIR

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
    summary="Co-located GEM power plants, GFMR flaring, and ICAR crop burn evidence"
)
def get_site_evidence(
    site_id: str,
    radius_m: float = Query(10000.0, ge=500.0, le=50000.0, description="Search radius around site in meters (default 10km)"),
    db: Session = Depends(get_db)
):
    """
    Returns verified external facility evidence located within specified radius of the site.
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

    return SiteEvidenceResponse(
        site_id=site_id,
        search_radius_m=radius_m,
        total_evidence_count=len(matched),
        evidence=matched
    )


@router.get(
    "/sites/{site_id}/imagery",
    response_model=List[ImageryCacheSummary],
    summary="Available HLS satellite patches and Prithvi embeddings"
)
def get_site_imagery(site_id: str, db: Session = Depends(get_db)):
    """
    Returns metadata for cached HLS satellite scenes and Prithvi embeddings.
    If no imagery is cached yet, generates/fetches it on demand.
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    try:
        summary = get_or_create_site_imagery(db, site_id)
        return [summary]
    except Exception as e:
        logger.error(f"Error getting/generating imagery for site '{site_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch satellite imagery: {str(e)}")


@router.get(
    "/imagery/patches/{filename}",
    summary="Serve cached satellite patch image"
)
def get_satellite_patch_file(filename: str):
    """
    Returns the binary satellite patch PNG for visual display in the UI.
    """
    file_path = os.path.join(CACHE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Satellite patch '{filename}' not found.")
    return FileResponse(file_path, media_type="image/png")
