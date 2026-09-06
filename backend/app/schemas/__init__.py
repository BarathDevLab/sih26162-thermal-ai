"""
FastAPI Pydantic Schemas Package
"""

from backend.app.schemas.health import HealthCheck, SystemStats
from backend.app.schemas.sites import (
    SiteCompactProperties,
    SiteGeoJSONGeometry,
    SiteGeoJSONFeature,
    SiteGeoJSONFeatureCollection,
    ModelASummary,
    ModelBSummary,
    ModelCSummary,
    AlertSummary,
    SiteDetail
)
from backend.app.schemas.timeline import TimelinePoint, SiteTimelineResponse
from backend.app.schemas.detections import DetectionItem, SiteDetectionsResponse
from backend.app.schemas.evidence import FacilityEvidenceSummary, SiteEvidenceResponse, ImageryCacheSummary
from backend.app.schemas.alerts import AlertItem, AlertFeedResponse, AlertAckRequest, AlertAckResponse
from backend.app.schemas.replay import ReplaySnapshotResponse

__all__ = [
    "HealthCheck",
    "SystemStats",
    "SiteCompactProperties",
    "SiteGeoJSONGeometry",
    "SiteGeoJSONFeature",
    "SiteGeoJSONFeatureCollection",
    "ModelASummary",
    "ModelBSummary",
    "ModelCSummary",
    "AlertSummary",
    "SiteDetail",
    "TimelinePoint",
    "SiteTimelineResponse",
    "DetectionItem",
    "SiteDetectionsResponse",
    "FacilityEvidenceSummary",
    "SiteEvidenceResponse",
    "ImageryCacheSummary",
    "AlertItem",
    "AlertFeedResponse",
    "AlertAckRequest",
    "AlertAckResponse",
    "ReplaySnapshotResponse"
]
