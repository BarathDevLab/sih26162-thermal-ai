"""Append-only analyst review workflow for UNKNOWN thermal source sites."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Alert,
    SiteModelA,
    SiteModelAFeatures,
    SiteModelB,
    SiteModelC,
    SiteReview,
    SourceSite,
)
from backend.app.db.session import get_db
from backend.app.services.feature_builder import ORDERED_FEATURES
from backend.app.schemas.reviews import (
    ReviewQueueItem,
    ReviewQueueResponse,
    SiteReviewHistoryResponse,
    SiteReviewItem,
    SiteReviewSubmitRequest,
)


router = APIRouter()
REVIEW_ALERT_TYPES = {
    "UNKNOWN_CRITICAL_REVIEW",
    "UNKNOWN_ANOMALY_REVIEW",
    "NEW_SOURCE_REVIEW",
}
REVIEW_STATUSES = {"IN_REVIEW", "COMPLETED", "ESCALATED"}
DETERMINATIONS = {"INDUSTRIAL", "NONINDUSTRIAL", "REMAIN_UNKNOWN"}
CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW"}
REQUIRED_REASON_BY_DETERMINATION = {
    "INDUSTRIAL": "AFFIRMATIVE_INDUSTRIAL_EVIDENCE",
    "NONINDUSTRIAL": "AFFIRMATIVE_NONINDUSTRIAL_EVIDENCE",
    "REMAIN_UNKNOWN": "INSUFFICIENT_OR_CONFLICTING_EVIDENCE",
}


def _serialize_review(review: SiteReview) -> SiteReviewItem:
    return SiteReviewItem(
        review_id=review.review_id,
        site_id=review.site_id,
        alert_id=review.alert_id,
        supersedes_review_id=review.supersedes_review_id,
        review_status=review.review_status,
        determination=review.determination,
        confidence=review.confidence,
        consensus_status=review.consensus_status,
        reason_codes=review.reason_codes if isinstance(review.reason_codes, list) else [],
        notes=review.notes,
        evidence_refs=review.evidence_refs if isinstance(review.evidence_refs, list) else [],
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at.isoformat(),
        country=review.country,
        training_eligible=bool(review.training_eligible),
        model_a_class=review.model_a_class,
        model_a_probability=review.model_a_probability,
        model_a_decision=review.model_a_decision,
        model_stack_version=review.model_stack_version,
        feature_version=review.feature_version,
    )


def _queue_status(review: Optional[SiteReview]) -> str:
    if review is None:
        return "PENDING"
    if review.review_status == "IN_REVIEW":
        return "IN_REVIEW"
    if review.review_status == "ESCALATED" or review.consensus_status == "CONFLICT":
        return "CONFLICT"
    if review.consensus_status == "VERIFIED":
        return "COMPLETED"
    return "AWAITING_VERIFICATION"


def _latest_review(db: Session, site_id: str) -> Optional[SiteReview]:
    return (
        db.query(SiteReview)
        .filter(SiteReview.site_id == site_id)
        .order_by(SiteReview.reviewed_at.desc(), SiteReview.review_id.desc())
        .first()
    )


@router.get("/reviews/queue", response_model=ReviewQueueResponse)
def get_review_queue(
    status: str = Query("OPEN", description="OPEN, PENDING, IN_REVIEW, AWAITING_VERIFICATION, CONFLICT, COMPLETED, or ALL"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    requested_status = status.strip().upper()
    allowed_filters = {
        "OPEN", "PENDING", "IN_REVIEW", "AWAITING_VERIFICATION",
        "CONFLICT", "COMPLETED", "ALL",
    }
    if requested_status not in allowed_filters:
        raise HTTPException(status_code=422, detail=f"Unsupported review queue status '{status}'.")

    rows = (
        db.query(Alert, SourceSite, SiteModelA, SiteModelB, SiteModelC)
        .join(SourceSite, Alert.site_id == SourceSite.site_id)
        .join(SiteModelA, Alert.site_id == SiteModelA.site_id)
        .outerjoin(SiteModelB, Alert.site_id == SiteModelB.site_id)
        .outerjoin(SiteModelC, Alert.site_id == SiteModelC.site_id)
        .filter(
            Alert.alert_type.in_(REVIEW_ALERT_TYPES),
            Alert.evidence_required.is_(True),
            SiteModelA.class_name == "UNKNOWN",
        )
        .order_by(Alert.updated_at.desc(), Alert.alert_id.desc())
        .all()
    )

    items: List[ReviewQueueItem] = []
    seen_sites = set()
    for alert, site, model_a, model_b, model_c in rows:
        if site.site_id in seen_sites:
            continue
        seen_sites.add(site.site_id)
        latest = _latest_review(db, site.site_id)
        queue_status = _queue_status(latest)
        matches = (
            requested_status == "ALL"
            or (requested_status == "OPEN" and queue_status != "COMPLETED")
            or requested_status == queue_status
        )
        if not matches:
            continue
        items.append(ReviewQueueItem(
            site_id=site.site_id,
            latitude=float(site.latitude),
            longitude=float(site.longitude),
            alert_id=alert.alert_id,
            alert_type=alert.alert_type,
            alert_level=alert.alert_level,
            headline=alert.headline,
            site_day=alert.site_day.isoformat(),
            queue_status=queue_status,
            model_a_probability=float(model_a.core_probability),
            prithvi_probability=(
                float(model_a.prithvi_probability)
                if model_a.prithvi_probability is not None else None
            ),
            prithvi_status=model_a.prithvi_status or "NOT_TRIGGERED",
            model_b_state=model_b.state if model_b is not None else None,
            model_c_status=model_c.operational_status if model_c is not None else None,
            latest_review=_serialize_review(latest) if latest is not None else None,
        ))
    return ReviewQueueResponse(total_reviews=len(items), items=items[:limit])


@router.get("/sites/{site_id}/reviews", response_model=SiteReviewHistoryResponse)
def get_site_reviews(site_id: str, db: Session = Depends(get_db)):
    if db.query(SourceSite.site_id).filter(SourceSite.site_id == site_id).first() is None:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")
    reviews = (
        db.query(SiteReview)
        .filter(SiteReview.site_id == site_id)
        .order_by(SiteReview.reviewed_at.desc(), SiteReview.review_id.desc())
        .all()
    )
    return SiteReviewHistoryResponse(
        site_id=site_id,
        queue_status=_queue_status(reviews[0] if reviews else None),
        reviews=[_serialize_review(review) for review in reviews],
    )


@router.post("/sites/{site_id}/reviews", response_model=SiteReviewItem, status_code=201)
def submit_site_review(
    site_id: str,
    request: SiteReviewSubmitRequest,
    db: Session = Depends(get_db),
):
    status = request.review_status.strip().upper()
    determination = request.determination.strip().upper() if request.determination else None
    confidence = request.confidence.strip().upper() if request.confidence else None
    reviewer = request.reviewed_by.strip()
    evidence_refs = sorted({ref.strip() for ref in request.evidence_refs if ref.strip()})
    reason_codes = sorted({code.strip().upper() for code in request.reason_codes if code.strip()})

    if not reviewer:
        raise HTTPException(status_code=422, detail="reviewed_by cannot be blank.")
    if not request.country.strip():
        raise HTTPException(status_code=422, detail="country cannot be blank.")

    if status not in REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unsupported review status '{status}'.")
    if status == "COMPLETED":
        if determination not in DETERMINATIONS or confidence not in CONFIDENCE_LEVELS:
            raise HTTPException(
                status_code=422,
                detail="Completed reviews require a valid determination and confidence level.",
            )
        if not evidence_refs or not reason_codes:
            raise HTTPException(
                status_code=422,
                detail="Completed reviews require evidence references and at least one reason code.",
            )
        required_reason = REQUIRED_REASON_BY_DETERMINATION[determination]
        if required_reason not in reason_codes:
            raise HTTPException(
                status_code=422,
                detail=f"Determination {determination} requires reason code {required_reason}.",
            )
    elif determination is not None or confidence is not None:
        raise HTTPException(
            status_code=422,
            detail="Only completed review events may contain a determination or confidence.",
        )

    site = db.query(SourceSite).filter(SourceSite.site_id == site_id).one_or_none()
    model_a = db.query(SiteModelA).filter(SiteModelA.site_id == site_id).one_or_none()
    model_a_features = (
        db.query(SiteModelAFeatures)
        .filter(SiteModelAFeatures.site_id == site_id)
        .one_or_none()
    )
    if site is None:
        raise HTTPException(status_code=404, detail=f"Source site '{site_id}' not found.")
    if model_a is None:
        raise HTTPException(status_code=409, detail="Model A output is unavailable for this site.")
    if model_a.class_name != "UNKNOWN":
        raise HTTPException(
            status_code=409,
            detail=f"Manual UNKNOWN review is not applicable to Model A class {model_a.class_name}.",
        )
    feature_snapshot = (
        dict(model_a_features.ordered_features)
        if model_a_features is not None and isinstance(model_a_features.ordered_features, dict)
        else None
    )
    complete_feature_snapshot = bool(
        feature_snapshot is not None
        and not set(ORDERED_FEATURES).difference(feature_snapshot)
    )

    alert = None
    if request.alert_id:
        alert = db.query(Alert).filter(Alert.alert_id == request.alert_id).one_or_none()
        if alert is None or alert.site_id != site_id:
            raise HTTPException(status_code=422, detail="The selected alert does not belong to this site.")

    previous = _latest_review(db, site_id)
    prior_completed = (
        db.query(SiteReview)
        .filter(
            SiteReview.site_id == site_id,
            SiteReview.review_status == "COMPLETED",
        )
        .order_by(SiteReview.reviewed_at.desc(), SiteReview.review_id.desc())
        .first()
    )
    consensus = "NOT_APPLICABLE"
    training_eligible = False
    if status == "COMPLETED":
        consensus = "SINGLE_REVIEW"
        if prior_completed is not None and prior_completed.reviewed_by != reviewer:
            if prior_completed.determination == determination:
                consensus = "VERIFIED"
                training_eligible = bool(
                    determination in {"INDUSTRIAL", "NONINDUSTRIAL"}
                    and confidence == "HIGH"
                    and prior_completed.confidence == "HIGH"
                    and evidence_refs
                    and prior_completed.evidence_refs
                    and complete_feature_snapshot
                )
            else:
                consensus = "CONFLICT"

    now = datetime.now(timezone.utc)
    review = SiteReview(
        review_id=f"REVIEW_{uuid.uuid4().hex}",
        site_id=site_id,
        alert_id=alert.alert_id if alert is not None else None,
        supersedes_review_id=previous.review_id if previous is not None else None,
        review_status=status,
        determination=determination,
        confidence=confidence,
        consensus_status=consensus,
        reason_codes=reason_codes,
        notes=request.notes.strip() if request.notes else None,
        evidence_refs=evidence_refs,
        reviewed_by=reviewer,
        reviewed_at=now,
        country=request.country.strip().upper(),
        training_eligible=training_eligible,
        model_a_class=model_a.class_name,
        model_a_probability=float(model_a.core_probability),
        model_a_decision=model_a.decision,
        model_stack_version=os.environ.get("MODEL_STACK_VERSION", model_a.model_version),
        feature_version=model_a.feature_version,
        feature_snapshot=feature_snapshot,
    )
    db.add(review)
    if alert is not None:
        if consensus == "VERIFIED":
            alert.status = "RESOLVED"
        alert.acknowledged_by = reviewer
        alert.updated_at = now
    db.commit()
    db.refresh(review)
    return _serialize_review(review)
