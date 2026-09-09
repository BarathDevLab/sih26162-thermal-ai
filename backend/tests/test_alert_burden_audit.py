from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Alert, SiteModelAHistory, SourceSite
from backend.app.db.session import Base
from backend.scripts.audit_alert_burden import count_industrial_claim_violations


def _history(site_id: str, cutoff: date, class_name: str) -> SiteModelAHistory:
    decision = "INDUSTRIAL_CORE_POSITIVE" if class_name == "INDUSTRIAL" else "UNKNOWN"
    return SiteModelAHistory(
        inference_id=f"{site_id}-{cutoff}-{class_name}",
        site_id=site_id,
        feature_as_of_detection_date=cutoff,
        core_probability=0.9 if class_name == "INDUSTRIAL" else 0.7,
        class_name=class_name,
        decision=decision,
        prithvi_status="NOT_TRIGGERED",
        model_version="test",
        feature_version="test",
        computed_at=datetime.now(timezone.utc),
    )


def _alert(site_id: str, site_day: date) -> Alert:
    return Alert(
        alert_id=f"alert-{site_id}",
        site_id=site_id,
        site_day=site_day,
        alert_type="HIGH_INDUSTRIAL_ANOMALY",
        alert_level="HIGH",
        headline="Test industrial alert",
        fingerprint=f"fingerprint-{site_id}",
        status="ACTIVE",
    )


def test_claim_audit_uses_model_a_history_at_alert_date():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        valid_site = "SITE_HISTORICALLY_INDUSTRIAL"
        invalid_site = "SITE_HISTORICALLY_UNKNOWN"
        for site_id in (valid_site, invalid_site):
            db.add(SourceSite(site_id=site_id, latitude=20.0, longitude=75.0))
        db.flush()

        db.add(_history(valid_site, date(2026, 1, 1), "INDUSTRIAL"))
        db.add(_history(valid_site, date(2026, 2, 1), "UNKNOWN"))
        db.add(_history(invalid_site, date(2026, 1, 1), "UNKNOWN"))
        db.add(_alert(valid_site, date(2026, 1, 15)))
        db.add(_alert(invalid_site, date(2026, 1, 15)))
        db.commit()

        violations = count_industrial_claim_violations(
            db, date(2026, 1, 1), date(2026, 1, 31)
        )

        assert violations == 1
    finally:
        db.close()
