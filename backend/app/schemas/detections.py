"""
Raw FIRMS Detections Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DetectionItem(BaseModel):
    detection_id: str = Field(..., description="Deterministic SHA-256 detection hash")
    source_sensor: str = Field("VIIRS_NOAA20_NRT", description="Sensor name")
    satellite: str = Field(..., description="Satellite platform (e.g. NOAA-20)")
    latitude: float = Field(..., description="Detection latitude")
    longitude: float = Field(..., description="Detection longitude")
    acq_date: str = Field(..., description="Acquisition date (YYYY-MM-DD)")
    acq_time: str = Field(..., description="Acquisition time (HHMM)")
    frp: float = Field(..., description="Fire Radiative Power (MW)")
    bright_ti4: Optional[float] = Field(None, description="Brightness temperature I4 channel (K)")
    bright_ti5: Optional[float] = Field(None, description="Brightness temperature I5 channel (K)")
    confidence: Optional[str] = Field(None, description="Detection confidence")
    daynight: str = Field("D", description="Day (D) or Night (N)")


class SiteDetectionsResponse(BaseModel):
    site_id: str = Field(..., description="Source site ID")
    count: int = Field(..., description="Number of detections returned")
    detections: List[DetectionItem] = Field(default_factory=list, description="Raw FIRMS detection points")
