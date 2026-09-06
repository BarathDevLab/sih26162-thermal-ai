"""
Site Thermal Activity Timeline Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TimelinePoint(BaseModel):
    acq_date: str = Field(..., description="Observation date (YYYY-MM-DD)")
    detections: int = Field(..., description="Hotspot detection count on this day")
    mean_frp: float = Field(..., description="Mean Fire Radiative Power in MW")
    max_frp: float = Field(..., description="Maximum Fire Radiative Power in MW")
    c_status: Optional[str] = Field(None, description="Historical Model C status on this day")
    c_score: Optional[float] = Field(None, description="Historical Model C anomaly score")
    c_raw: Optional[float] = Field(None, description="Raw anomaly intensity metric")
    b_state: Optional[str] = Field(None, description="Historical Model B state on this day if evaluated")
    drivers: Optional[List[str]] = Field(None, description="Anomaly drivers active on this day")


class SiteTimelineResponse(BaseModel):
    site_id: str = Field(..., description="Source site ID")
    total_active_days: int = Field(..., description="Total days with thermal activity recorded")
    first_date: Optional[str] = Field(None, description="Earliest recorded activity date")
    last_date: Optional[str] = Field(None, description="Latest recorded activity date")
    history: List[TimelinePoint] = Field(default_factory=list, description="Chronological daily activity sequence")
