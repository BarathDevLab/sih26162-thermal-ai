"""
External GIS Facility Evidence & Satellite Imagery Schemas
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class FacilityEvidenceSummary(BaseModel):
    evidence_id: str = Field(..., description="Unique evidence ID")
    source_name: str = Field(..., description="Evidence authority: GEM_GIPT, WORLDBANK_GFMR, ICAR_CROP, etc.")
    facility_name: str = Field(..., description="Facility or event name")
    facility_type: str = Field(..., description="Facility subclass: power_plant, gas_flare, crop_residue_burn, etc.")
    latitude: float = Field(..., description="Evidence latitude")
    longitude: float = Field(..., description="Evidence longitude")
    distance_m: Optional[float] = Field(None, description="Distance from source site centroid in meters")
    coordinate_quality: str = Field("HIGH", description="EXACT, HIGH, SATELLITE, APPROXIMATE")
    source_url: Optional[str] = Field(None, description="Reference URL")
    attributes: Optional[Dict[str, Any]] = Field(None, description="Full source attributes")


class SiteEvidenceResponse(BaseModel):
    site_id: str = Field(..., description="Source site ID")
    search_radius_m: float = Field(..., description="Radial distance searched around site in meters")
    total_evidence_count: int = Field(..., description="Number of evidence facilities found")
    evidence: List[FacilityEvidenceSummary] = Field(default_factory=list, description="Co-located facility evidence records")
    as_of_date: Optional[str] = Field(None, description="Temporal cutoff used for event evidence")
    temporal_window_days: int = Field(7, description="Days either side of cutoff searched")
    total_event_evidence_count: int = 0
    event_evidence: List["EventEvidenceSummary"] = Field(default_factory=list)


class EventEvidenceSummary(BaseModel):
    evidence_id: str
    source_name: str
    evidence_type: str
    reference_id: Optional[str] = None
    latitude: float
    longitude: float
    distance_m: Optional[float] = None
    event_start: Optional[str] = None
    event_end: Optional[str] = None
    authority_level: Optional[str] = None
    source_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


SiteEvidenceResponse.model_rebuild()


class ImageryCacheSummary(BaseModel):
    cache_id: str
    site_id: str
    acquisition_date: str
    product: str = "HLSS30"
    cloud_fraction: Optional[float] = None
    prithvi_probability: Optional[float] = None
    status: str = "AVAILABLE"
    source_uri: Optional[str] = None
    patch_uri: Optional[str] = None
    embedding_uri: Optional[str] = None
    model_revision: Optional[str] = None
    failure_reason: Optional[str] = None
