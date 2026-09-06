"""
Facility Evidence & Satellite Imagery API Endpoints
"""

import math
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import SourceSite, FacilityEvidence, ImageryCache
from backend.app.schemas.evidence import (
    SiteEvidenceResponse,
    FacilityEvidenceSummary,
    ImageryCacheSummary
)

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
    """
    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")

    records = db.query(ImageryCache).filter(ImageryCache.site_id == site_id).all()
    results: List[ImageryCacheSummary] = []
    for r in records:
        results.append(
            ImageryCacheSummary(
                site_id=r.site_id,
                acquisition_date=str(r.acquisition_date),
                product=r.product or "HLS.L30/S30",
                cloud_fraction=float(r.cloud_fraction) if r.cloud_fraction is not None else None,
                prithvi_probability=float(r.prithvi_probability) if r.prithvi_probability is not None else None,
                status=r.status or "AVAILABLE",
                patch_uri=r.patch_uri,
                embedding_uri=r.embedding_uri
            )
        )
    return results
