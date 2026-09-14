"""Analyst review and future-training evidence API contracts."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SiteReviewSubmitRequest(BaseModel):
    reviewed_by: str = Field(..., min_length=2, max_length=128)
    review_status: str = Field("COMPLETED", description="IN_REVIEW, COMPLETED, or ESCALATED")
    determination: Optional[str] = Field(
        None, description="INDUSTRIAL, NONINDUSTRIAL, or REMAIN_UNKNOWN"
    )
    confidence: Optional[str] = Field(None, description="HIGH, MEDIUM, or LOW")
    reason_codes: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(None, max_length=4000)
    evidence_refs: List[str] = Field(default_factory=list)
    alert_id: Optional[str] = None
    country: str = Field("INDIA", min_length=2, max_length=64)


class SiteReviewItem(BaseModel):
    review_id: str
    site_id: str
    alert_id: Optional[str] = None
    supersedes_review_id: Optional[str] = None
    review_status: str
    determination: Optional[str] = None
    confidence: Optional[str] = None
    consensus_status: str
    reason_codes: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    reviewed_by: str
    reviewed_at: str
    country: str
    training_eligible: bool
    model_a_class: Optional[str] = None
    model_a_probability: Optional[float] = None
    model_a_decision: Optional[str] = None
    model_stack_version: str
    feature_version: Optional[str] = None


class SiteReviewHistoryResponse(BaseModel):
    site_id: str
    queue_status: str
    reviews: List[SiteReviewItem] = Field(default_factory=list)


class ReviewQueueItem(BaseModel):
    site_id: str
    latitude: float
    longitude: float
    alert_id: str
    alert_type: str
    alert_level: str
    headline: str
    site_day: str
    queue_status: str
    model_a_probability: Optional[float] = None
    prithvi_probability: Optional[float] = None
    prithvi_status: str
    model_b_state: Optional[str] = None
    model_c_status: Optional[str] = None
    latest_review: Optional[SiteReviewItem] = None


class ReviewQueueResponse(BaseModel):
    total_reviews: int
    items: List[ReviewQueueItem] = Field(default_factory=list)
