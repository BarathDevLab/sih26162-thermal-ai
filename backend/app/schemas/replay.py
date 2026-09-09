"""
Historical Replay Mode Schemas
"""

from typing import List
from pydantic import BaseModel, Field
from backend.app.schemas.sites import SiteGeoJSONFeature


class ReplaySnapshotResponse(BaseModel):
    as_of_date: str = Field(..., description="Historical cutoff date (YYYY-MM-DD)")
    active_sites_count: int = Field(..., description="Total matching sites before response limiting")
    returned_sites_count: int = Field(0, description="Sites included in this response")
    truncated: bool = Field(False, description="Whether the response limit omitted matching sites")
    alerts_count: int = Field(..., description="Qualifying alerts among returned viewport sites")
    cache_status: str = Field("MISS", description="MISS, HIT, or DEMO_CACHE")
    features: List[SiteGeoJSONFeature] = Field(default_factory=list, description="Historical viewport GeoJSON features")
