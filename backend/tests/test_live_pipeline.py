"""Tests for live status, simulation isolation, and global Model B refresh."""

from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.session import Base
from backend.app.db.models import (
    Alert, CandidateSource, CandidateSourceDetection, FirmsDetection, SourceSite,
    SiteDailyActivity, SiteModelB,
)
from backend.app.services.live_pipeline import LivePipelineService, run_global_daily_model_b_refresh

client = TestClient(app)


def test_live_status_endpoint():
    resp = client.get("/api/v1/live/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "scheduler" in data
    assert "prithvi_queue" in data
    assert "startup_catchup" in data


def test_live_pipeline_simulation_is_disabled_by_default():
    payload = {
        "latitude": 28.61, "longitude": 77.20, "frp": 150.0,
        "satellite": "20", "acq_date": date.today().isoformat(), "acq_time": "0830",
    }
    resp = client.post("/api/v1/live/simulate-hotspot", json=payload)
    assert resp.status_code == 403


def test_global_daily_model_b_decay():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(SourceSite(site_id="SITE_B_TEST", latitude=20.0, longitude=75.0))
        db.add(SiteDailyActivity(
            site_id="SITE_B_TEST", acq_date=date.today() - timedelta(days=120),
            detections=1, mean_frp=10.0, max_frp=10.0,
        ))
        db.commit()
        res = run_global_daily_model_b_refresh(db, as_of_date=date.today())
        assert res["status"] == "COMPLETED"
        assert res["sites_evaluated"] == 1
        assert db.query(SiteModelB).one().state == "DORMANT"
        rerun = run_global_daily_model_b_refresh(db, as_of_date=date.today())
        assert rerun["status"] == "ALREADY_COMPLETED"
        assert rerun["sites_evaluated"] == 1
    finally:
        db.close()


def test_same_day_non_escalation_does_not_require_new_fingerprint():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    site_id = "SITE_ALERT_EXISTING"
    site_day = date(2026, 1, 1)
    try:
        db.add(SourceSite(site_id=site_id, latitude=20.0, longitude=75.0))
        db.add(Alert(
            alert_id="ALERT_EXISTING",
            site_id=site_id,
            site_day=site_day,
            alert_type="INDUSTRIAL_ANOMALY",
            alert_level="HIGH",
            headline="Existing alert",
            fingerprint="existing-fingerprint",
            status="ACTIVE",
        ))
        db.commit()

        class ExistingDecision:
            def evaluate(self, **kwargs):
                return kwargs["existing_alert"]

        service = object.__new__(LivePipelineService)
        service.decision = ExistingDecision()
        result = service._evaluate_alert(
            db,
            site_id,
            site_day,
            {"decision": "INDUSTRIAL_CORE_STRONG"},
            {"state": "PERSISTENT", "confidence": "HIGH"},
            {"status": "ANOMALOUS"},
        )

        assert result == 0
        assert db.query(Alert).count() == 1
    finally:
        db.close()


def test_candidate_promotion_persists_all_members_without_fk_failure():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    class FakeModelA:
        def score_site(self, db, site_id, **kwargs):
            return {
                "decision": "UNKNOWN", "core_probability": 0.5,
                "should_queue_prithvi": False,
            }

    class FakeModelCReplay:
        def replay_site(self, db, site_id, cutoff=None):
            return {
                "latest": {"status": "INSUFFICIENT_HISTORY"},
                "event_date": cutoff,
            }

    service = LivePipelineService()
    service._model_a = FakeModelA()
    service.model_c_replay = FakeModelCReplay()
    rows = [
        {
            "latitude": 24.0 + offset, "longitude": 75.0 + offset,
            "acq_date": "2026-01-01", "acq_time": f"08{30 + index}",
            "satellite": "20", "frp": 10.0 + index, "daynight": "D",
        }
        for index, offset in enumerate((0.0, 0.0002, 0.0004))
    ]
    try:
        result = service.process_detections_batch(
            rows, db, as_of_date=date(2026, 1, 1)
        )
        assert result["promoted_count"] == 1
        promoted = db.query(CandidateSource).filter_by(status="PROMOTED").one()
        assert promoted.promoted_site_id is not None
        assert db.query(FirmsDetection).filter_by(
            source_site_id=promoted.promoted_site_id
        ).count() == 3
        assert db.query(CandidateSourceDetection).filter_by(
            candidate_id=promoted.candidate_id
        ).count() == 3
    finally:
        db.close()


def test_historical_backfill_can_defer_models_until_final_refresh():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    service = LivePipelineService()
    try:
        db.add(SourceSite(site_id="SITE_DEFER", latitude=20.0, longitude=75.0))
        db.add(FirmsDetection(
            detection_id="HIST_DEFER",
            source_sensor="NOAA20_VIIRS",
            satellite="20",
            instrument="VIIRS",
            latitude=20.0,
            longitude=75.0,
            acq_date=date(2025, 12, 31),
            acq_time="0830",
            frp=10.0,
            confidence="nominal",
            daynight="D",
            version="2.0",
            source_site_id="SITE_DEFER",
        ))
        db.commit()

        result = service.process_detections_batch(
            [{
                "latitude": 20.0001,
                "longitude": 75.0001,
                "acq_date": "2026-01-01",
                "acq_time": "0831",
                "satellite": "20",
                "frp": 11.0,
                "daynight": "D",
            }],
            db,
            source_sensor="VIIRS_NOAA20_SP",
            as_of_date=date(2026, 1, 1),
            refresh_models=False,
        )

        assert result["models_deferred"] is True
        assert result["inserted_count"] == 1
        assert result["touched_site_ids"] == ["SITE_DEFER"]
        assert db.query(SiteDailyActivity).filter_by(
            site_id="SITE_DEFER", acq_date=date(2026, 1, 1)
        ).one().detections == 1
        assert db.query(SiteModelB).count() == 0
    finally:
        db.close()
