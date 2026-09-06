"""
Site Schemas for Map Viewport (GeoJSON) and Detailed Analyst Intelligence
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SiteCompactProperties(BaseModel):
    site_id: str = Field(..., description="Unique physical site ID")
    a_class: str = Field(..., description="Model A identity: INDUSTRIAL, NONINDUSTRIAL, UNKNOWN")
    a_prob: float = Field(..., description="Model A core industrial probability")
    b_state: str = Field(..., description="Model B temporal state")
    c_status: str = Field(..., description="Model C anomaly status: NORMAL, ELEVATED, ANOMALOUS, CRITICAL, etc.")
    c_score: Optional[float] = Field(None, description="Model C anomaly score [0, 1]")
    alert_severity: Optional[str] = Field(None, description="Active alert severity if any: CRITICAL, HIGH, MEDIUM, LOW, INFO, NONE")
    alert_type: Optional[str] = Field(None, description="Active alert classification type")
    latest_seen: Optional[str] = Field(None, description="Date when site was last thermally active")


class SiteGeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., description="[longitude, latitude]")


class SiteGeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: SiteGeoJSONGeometry
    properties: SiteCompactProperties


class SiteGeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[SiteGeoJSONFeature]
    total_count: int = Field(..., description="Total count matching query filters")


# Detailed Site Intelligence Schemas

class ModelASummary(BaseModel):
    class_name: str
    decision: str
    core_probability: float
    prithvi_probability: Optional[float] = None
    prithvi_status: str = "NOT_TRIGGERED"
    model_version: str


class ModelBSummary(BaseModel):
    state: str
    confidence: str
    reason: Optional[str] = None
    days_since_last: Optional[int] = None
    active_days_windows: Optional[Dict[str, int]] = None
    model_version: str


class ModelCSummary(BaseModel):
    operational_status: str
    c_score: Optional[float] = None
    c_raw: Optional[float] = None
    group_scores: Optional[Dict[str, Optional[float]]] = None
    evidence_99: int = 0
    drivers: Optional[List[str]] = None
    event_date: Optional[str] = None
    model_version: str


class AlertSummary(BaseModel):
    alert_id: str
    alert_type: str
    alert_level: str
    headline: str
    reason_codes: Optional[List[str]] = None
    evidence_required: bool = False
    is_escalation: bool = False
    status: str
    created_at: str
    updated_at: str


class SiteDetail(BaseModel):
    site_id: str
    latitude: float
    longitude: float
    status: str
    created_at: str
    latest_seen: Optional[str] = None
    land_cover: Optional[Dict[str, Optional[float]]] = None
    spatial_stats: Optional[Dict[str, Optional[float]]] = None
    model_a: Optional[ModelASummary] = None
    model_b: Optional[ModelBSummary] = None
    model_c: Optional[ModelCSummary] = None
    active_alert: Optional[AlertSummary] = None
