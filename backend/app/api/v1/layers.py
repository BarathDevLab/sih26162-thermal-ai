"""
Map Layers API Endpoints: Raw FIRMS Hotspots & Auxiliary Overlays
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import FirmsDetection

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/layers/firms",
    summary="Raw FIRMS active fire hotspots as GeoJSON"
)
def get_firms_layer(
    bbox: Optional[str] = Query(None, description="Bounding box 'min_lon,min_lat,max_lon,max_lat'"),
    date: Optional[str] = Query(None, description="Observation date (YYYY-MM-DD)"),
    limit: int = Query(2000, ge=1, le=5000, description="Max hotspot points to return"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns raw FIRMS detection points formatted as GeoJSON for deck.gl/MapLibre hotspot layer.
    """
    try:
        query = db.query(FirmsDetection)

        if date:
            query = query.filter(FirmsDetection.acq_date == date)

        if bbox:
            try:
                parts = [float(p.strip()) for p in bbox.split(",")]
                if len(parts) == 4:
                    min_lon, min_lat, max_lon, max_lat = parts
                    query = query.filter(
                        FirmsDetection.longitude >= min_lon,
                        FirmsDetection.longitude <= max_lon,
                        FirmsDetection.latitude >= min_lat,
                        FirmsDetection.latitude <= max_lat
                    )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid bbox: {e}")

        records = query.order_by(FirmsDetection.acq_date.desc(), FirmsDetection.frp.desc()).limit(limit).all()

        features: List[Dict[str, Any]] = []
        for r in records:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(float(r.longitude), 5), round(float(r.latitude), 5)]
                },
                "properties": {
                    "detection_id": r.detection_id,
                    "sensor": r.source_sensor,
                    "satellite": r.satellite,
                    "acq_date": str(r.acq_date),
                    "acq_time": r.acq_time,
                    "frp": round(float(r.frp), 2),
                    "bright_ti4": round(float(r.bright_ti4), 2) if r.bright_ti4 is not None else None,
                    "confidence": r.confidence,
                    "daynight": r.daynight,
                    "source_site_id": r.source_site_id
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "count": len(features)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching FIRMS layer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch FIRMS layer: {str(e)}")
