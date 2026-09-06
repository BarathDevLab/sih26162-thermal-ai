"""
Tests for SQLAlchemy Database Layer
Verifies table creation, relationships, composite keys, constraints, and CRUD operations.
"""

from datetime import datetime, date, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.db.session import Base
from backend.app.db.models import (
    SourceSite,
    FirmsDetection,
    CandidateSource,
    SiteDailyActivity,
    SiteModelA,
    SiteModelB,
    SiteModelC,
    SiteDailyInference,
    Alert,
    FacilityEvidence,
    ImageryCache,
    ModelVersion,
    IngestionRun
)


@pytest.fixture
def db_session():
    """
    Creates an isolated in-memory SQLite database for testing.
    """
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_tables_created(db_session):
    table_names = Base.metadata.tables.keys()
    expected = [
        "source_sites",
        "firms_detections",
        "candidate_sources",
        "site_daily_activity",
        "site_model_a",
        "site_model_b",
        "site_model_c",
        "site_daily_inference",
        "alerts",
        "facility_evidence",
        "imagery_cache",
        "model_versions",
        "ingestion_runs"
    ]
    for exp in expected:
        assert exp in table_names


def test_source_site_crud(db_session):
    site = SourceSite(
        site_id="INDIA_SITE_0000001",
        latitude=22.1234,
        longitude=72.5678,
        status="ACTIVE",
        land_cover={"crop_fraction": 0.25, "built_fraction": 0.05}
    )
    db_session.add(site)
    db_session.commit()

    retrieved = db_session.query(SourceSite).filter_by(site_id="INDIA_SITE_0000001").first()
    assert retrieved is not None
    assert retrieved.latitude == 22.1234
    assert retrieved.land_cover["crop_fraction"] == 0.25


def test_firms_detection_relationship(db_session):
    site = SourceSite(site_id="SITE_TEST", latitude=20.0, longitude=75.0)
    det = FirmsDetection(
        detection_id="det_hash_12345",
        source_sensor="VIIRS_NOAA20_NRT",
        satellite="20",
        latitude=20.0001,
        longitude=75.0001,
        acq_date=date(2026, 1, 15),
        acq_time="0830",
        frp=15.6,
        source_site_id="SITE_TEST"
    )
    db_session.add(site)
    db_session.add(det)
    db_session.commit()

    assert len(site.detections) == 1
    assert site.detections[0].frp == 15.6
    assert det.source_site.site_id == "SITE_TEST"


def test_site_daily_activity_composite_key(db_session):
    site = SourceSite(site_id="SITE_DAILY", latitude=21.0, longitude=78.0)
    db_session.add(site)
    db_session.commit()

    act1 = SiteDailyActivity(
        site_id="SITE_DAILY",
        acq_date=date(2026, 1, 1),
        detections=2,
        mean_frp=10.5,
        max_frp=12.0
    )
    db_session.add(act1)
    db_session.commit()

    # Duplicate composite key should fail
    act2 = SiteDailyActivity(
        site_id="SITE_DAILY",
        acq_date=date(2026, 1, 1),
        detections=1,
        mean_frp=8.0,
        max_frp=8.0
    )
    db_session.add(act2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_site_models_a_b_c(db_session):
    site = SourceSite(site_id="SITE_MODELS", latitude=23.0, longitude=72.0)
    db_session.add(site)

    model_a = SiteModelA(
        site_id="SITE_MODELS",
        core_probability=0.92,
        class_name="INDUSTRIAL",
        decision="INDUSTRIAL_CORE_POSITIVE",
        model_version="2026-09-04-r1"
    )
    model_b = SiteModelB(
        site_id="SITE_MODELS",
        state="PERSISTENT",
        confidence="HIGH",
        reason="Active across 12 months",
        model_version="2026-09-04-r1"
    )
    model_c = SiteModelC(
        site_id="SITE_MODELS",
        operational_status="CRITICAL",
        c_score=0.9995,
        model_version="2026-09-04-r1"
    )

    db_session.add_all([model_a, model_b, model_c])
    db_session.commit()

    assert site.model_a.decision == "INDUSTRIAL_CORE_POSITIVE"
    assert site.model_b.state == "PERSISTENT"
    assert site.model_c.operational_status == "CRITICAL"


def test_alert_unique_fingerprint(db_session):
    site = SourceSite(site_id="SITE_ALERT", latitude=22.0, longitude=73.0)
    db_session.add(site)
    db_session.commit()

    alert1 = Alert(
        alert_id="ALERT_001",
        site_id="SITE_ALERT",
        site_day=date(2026, 3, 1),
        alert_type="CRITICAL_INDUSTRIAL_ANOMALY",
        alert_level="CRITICAL",
        headline="Critical anomaly detected",
        fingerprint="fp_unique_123"
    )
    db_session.add(alert1)
    db_session.commit()

    # Inserting same fingerprint must violate uniqueness
    alert2 = Alert(
        alert_id="ALERT_002",
        site_id="SITE_ALERT",
        site_day=date(2026, 3, 1),
        alert_type="CRITICAL_INDUSTRIAL_ANOMALY",
        alert_level="CRITICAL",
        headline="Critical anomaly detected duplicate",
        fingerprint="fp_unique_123"
    )
    db_session.add(alert2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_facility_evidence_crud(db_session):
    ev = FacilityEvidence(
        evidence_id="GEM_00001",
        source_name="GEM_GIPT",
        facility_name="Mundra Ultra Mega Power Plant",
        facility_type="coal",
        latitude=22.82,
        longitude=69.52,
        coordinate_quality="EXACT",
        attributes={"capacity_mw": 4000, "status": "operating"}
    )
    db_session.add(ev)
    db_session.commit()

    found = db_session.query(FacilityEvidence).filter_by(facility_type="coal").first()
    assert found is not None
    assert found.facility_name == "Mundra Ultra Mega Power Plant"
    assert found.attributes["capacity_mw"] == 4000
