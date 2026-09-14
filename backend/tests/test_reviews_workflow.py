"""Regression tests for append-only UNKNOWN analyst adjudication."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.v1.reviews import get_review_queue, submit_site_review
from backend.app.db.models import Alert, SiteModelA, SiteModelAFeatures, SiteReview, SourceSite
from backend.app.db.session import Base
from backend.app.schemas.reviews import SiteReviewSubmitRequest
from backend.app.services.feature_builder import ORDERED_FEATURES


def _review_request(reviewer: str) -> SiteReviewSubmitRequest:
    return SiteReviewSubmitRequest(
        reviewed_by=reviewer,
        review_status="COMPLETED",
        determination="INDUSTRIAL",
        confidence="HIGH",
        reason_codes=["AFFIRMATIVE_INDUSTRIAL_EVIDENCE"],
        evidence_refs=["FACILITY_EVIDENCE:SITE_REVIEW"],
        alert_id="ALERT_REVIEW",
        notes="Facility identity independently corroborated.",
    )


def test_two_independent_reviews_create_training_eligible_consensus():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(SourceSite(site_id="SITE_REVIEW", latitude=20.0, longitude=75.0))
        db.add(SiteModelA(
            site_id="SITE_REVIEW",
            core_probability=0.61,
            class_name="UNKNOWN",
            decision="UNKNOWN",
            prithvi_status="AVAILABLE",
            model_version="test-stack",
            feature_version="test-features",
        ))
        db.add(SiteModelAFeatures(
            site_id="SITE_REVIEW",
            feature_as_of_detection_date=date(2026, 9, 14),
            feature_version="test-features",
            ordered_features={name: 0.0 for name in ORDERED_FEATURES},
        ))
        db.add(Alert(
            alert_id="ALERT_REVIEW",
            site_id="SITE_REVIEW",
            site_day=date(2026, 9, 14),
            alert_type="UNKNOWN_ANOMALY_REVIEW",
            alert_level="MEDIUM",
            headline="Unknown site requires review",
            reason_codes=["A=UNKNOWN", "C=ANOMALOUS"],
            evidence_required=True,
            fingerprint="review-fingerprint",
            status="ACTIVE",
        ))
        db.commit()

        first = submit_site_review("SITE_REVIEW", _review_request("analyst_one"), db)
        assert first.consensus_status == "SINGLE_REVIEW"
        assert first.training_eligible is False
        assert db.query(SiteModelA).one().class_name == "UNKNOWN"

        awaiting = get_review_queue("AWAITING_VERIFICATION", 100, db)
        assert [item.site_id for item in awaiting.items] == ["SITE_REVIEW"]

        second = submit_site_review("SITE_REVIEW", _review_request("analyst_two"), db)
        assert second.consensus_status == "VERIFIED"
        assert second.training_eligible is True
        assert second.supersedes_review_id == first.review_id
        assert db.query(SiteReview).count() == 2
        assert db.query(SiteModelA).one().class_name == "UNKNOWN"
        assert db.query(Alert).one().status == "RESOLVED"
    finally:
        db.close()
