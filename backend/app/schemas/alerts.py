"""
Operational Alert Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AlertItem(BaseModel):
    alert_id: str = Field(..., description="Unique alert identifier")
    site_id: str = Field(..., description="Target source site ID")
    site_day: str = Field(..., description="Event date (YYYY-MM-DD)")
    alert_type: str = Field(..., description="Operational classification type")
    alert_level: str = Field(..., description="Severity level: CRITICAL, HIGH, MEDIUM, LOW, INFO, NONE")
    headline: str = Field(..., description="Human-readable operational alert headline")
    reason_codes: Optional[List[str]] = Field(None, description="Diagnostic reason codes from A/B/C fusion")
    evidence_required: bool = Field(False, description="Whether analyst evidence review is required")
    fingerprint: str = Field(..., description="SHA-256 deduplication fingerprint")
    status: str = Field("ACTIVE", description="Alert status: ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED")
    is_escalation: bool = Field(False, description="Whether this alert was escalated from a lower severity")
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of latest update")
    latitude: Optional[float] = Field(None, description="Site centroid latitude")
    longitude: Optional[float] = Field(None, description="Site centroid longitude")
    a_class: Optional[str] = Field(None, description="Model A identity class of site")


class AlertFeedResponse(BaseModel):
    total_alerts: int = Field(..., description="Count of alerts matching filters")
    alerts: List[AlertItem] = Field(default_factory=list, description="List of operational alerts")


class AlertAckRequest(BaseModel):
    acknowledged_by: str = Field(..., description="Analyst username or operator badge ID")
    notes: Optional[str] = Field(None, description="Optional triage notes or comments")


class AlertAckResponse(BaseModel):
    alert_id: str
    status: str
    acknowledged_by: str
    updated_at: str
    message: str = "Alert successfully acknowledged."
