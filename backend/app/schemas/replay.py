"""
Historical Replay Mode Schemas
"""

from typing import List
from pydantic import BaseModel, Field
from backend.app.schemas.sites import SiteGeoJSONFeature


class ReplaySnapshotResponse(BaseModel):
    as_of_date: str = Field(..., description="Historical cutoff date (YYYY-MM-DD)")
    active_sites_count: int = Field(..., description="Total active sites as of this historical date")
    alerts_count: int = Field(..., description="Active operational alerts as of this date")
    features: List[SiteGeoJSONFeature] = Field(default_factory=list, description="Historical viewport GeoJSON features")
