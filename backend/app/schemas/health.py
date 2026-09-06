"""
Health & System Statistics Schemas
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str = Field(..., description="Overall service health status")
    database: str = Field(..., description="Database connection status")
    postgis_enabled: bool = Field(..., description="Whether PostGIS extension is active")
    active_models: Dict[str, str] = Field(default_factory=dict, description="Active model stack component versions")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class SystemStats(BaseModel):
    total_sites: int = Field(..., description="Total physical source sites in the system")
    active_sites_30d: int = Field(..., description="Sites active within the last 30 days")
    model_a_counts: Dict[str, int] = Field(..., description="Counts by Model A identity class")
    model_b_counts: Dict[str, int] = Field(..., description="Counts by Model B temporal state")
    model_c_counts: Dict[str, int] = Field(..., description="Counts by Model C anomaly operational status")
    alert_counts: Dict[str, int] = Field(..., description="Counts by active operational alert severity")
    latest_firms_date: Optional[str] = Field(None, description="Latest ingested FIRMS observation date")
    data_mode: str = Field("LIVE", description="Current operating mode: LIVE or REPLAY")
