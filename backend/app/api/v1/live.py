"""
Live Scheduler, Simulation & Control Endpoints
Provides real-time telemetry, manual triggers, and interactive hotspot injection
for demonstration and continuous operations.
"""

import uuid
import logging
from datetime import date, datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.scheduler import (
    get_scheduler_status,
    trigger_manual_poll,
    trigger_manual_decay
)
from backend.app.services.live_pipeline import get_live_pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter()


class HotspotSimulationRequest(BaseModel):
    latitude: float = Field(..., description="Hotspot latitude", ge=6.0, le=38.0)
    longitude: float = Field(..., description="Hotspot longitude", ge=67.0, le=98.0)
    frp: float = Field(45.0, description="Fire Radiative Power (MW)", ge=0.1, le=5000.0)
    bright_ti4: float = Field(340.0, description="Brightness temperature I4 (Kelvin)", ge=200.0, le=500.0)
    confidence: str = Field("nominal", description="nominal, high, low")
    satellite: str = Field("20", description="NOAA-20 / NOAA-21 satellite designation")
    acq_date: Optional[str] = Field(None, description="YYYY-MM-DD (defaults to today)")
    acq_time: Optional[str] = Field(None, description="HHMM format (defaults to current time)")


@router.get(
    "/live/status",
    summary="Operational status of scheduler and async queues"
)
def get_status():
    """
    Returns the real-time execution status of APScheduler, FIRMS NRT polling jobs,
    daily Model B temporal decay cron, and the Prithvi worker queue.
    """
    return get_scheduler_status()


@router.post(
    "/live/trigger-poll",
    summary="Manually trigger an immediate FIRMS NRT polling cycle"
)
async def trigger_poll(db: Session = Depends(get_db)):
    """
    Forces an immediate query to NASA FIRMS Area API and executes the
    incremental spatial resolution, Model B/C rescoring, and alert generation pipeline.
    """
    try:
        res = await trigger_manual_poll(db)
        return {"status": "SUCCESS", "result": res}
    except Exception as e:
        logger.error(f"Manual FIRMS poll failed: {e}")
        raise HTTPException(status_code=500, detail=f"Manual poll error: {str(e)}")


@router.post(
    "/live/trigger-decay",
    summary="Manually trigger global Model B daily decay refresh"
)
async def trigger_decay(db: Session = Depends(get_db)):
    """
    Forces an immediate daily Model B temporal decay maintenance run,
    transitioning sites inactive past 30 days to DORMANT.
    """
    try:
        res = await trigger_manual_decay(db)
        return {"status": "SUCCESS", "result": res}
    except Exception as e:
        logger.error(f"Manual Model B decay failed: {e}")
        raise HTTPException(status_code=500, detail=f"Manual decay error: {str(e)}")


@router.post(
    "/live/simulate-hotspot",
    summary="Inject a synthetic hotspot to demonstrate live ingestion & SSE alert push"
)
async def simulate_hotspot(
    req: HotspotSimulationRequest,
    db: Session = Depends(get_db)
):
    """
    Injects a live active fire hotspot into the pipeline.
    Demonstrates:
    - 750m spatial matching to existing sites or candidate promotion
    - Today's daily activity aggregation
    - Live Model B and Model C rescoring
    - Decision Engine alert synthesis and instant SSE broadcast to the command center
    """
    now = datetime.now(timezone.utc)
    acq_d = req.acq_date or date.today().isoformat()
    acq_t = req.acq_time or now.strftime("%H%M")

    raw_record = {
        "latitude": req.latitude,
        "longitude": req.longitude,
        "frp": req.frp,
        "bright_ti4": req.bright_ti4,
        "bright_ti5": req.bright_ti4 - 20.0,
        "confidence": req.confidence,
        "satellite": req.satellite,
        "instrument": "VIIRS",
        "acq_date": acq_d,
        "acq_time": acq_t,
        "daynight": "D",
        "version": "2.0NRT",
        "scan": 0.35,
        "track": 0.35
    }

    try:
        pipeline = get_live_pipeline_service()
        result = pipeline.process_detections_batch(
            raw_records=[raw_record],
            db=db,
            source_sensor="VIIRS_NOAA20_SIMULATED"
        )
        return {
            "status": "SUCCESS",
            "simulation": raw_record,
            "pipeline_result": result
        }
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")
