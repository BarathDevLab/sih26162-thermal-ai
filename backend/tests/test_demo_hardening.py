"""Phase 8 deterministic replay, cache, and offline-demo regressions."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import (
    SiteDailyActivity,
    SiteDailyInference,
    SiteModelAHistory,
    SourceSite,
)
from backend.app.main import app
from backend.app.schemas.replay import ReplaySnapshotResponse
from backend.app.services.demo_service import DemoService
from backend.app.services.replay_service import build_replay_snapshot
from backend.app.services.runtime_replay_cache import RuntimeReplayCache


def test_replay_reports_true_total_before_limit():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    cutoff = date(2026, 4, 23)
    try:
        for index in range(2):
            site_id = f"SITE_{index}"
            db.add(SourceSite(site_id=site_id, latitude=20 + index, longitude=75 + index))
            db.add(SiteDailyActivity(
                site_id=site_id,
                acq_date=cutoff,
                detections=1,
                mean_frp=10,
                max_frp=10,
            ))
            db.add(SiteModelAHistory(
                inference_id=f"A_{index}",
                site_id=site_id,
                feature_as_of_detection_date=cutoff,
                core_probability=0.9,
                class_name="INDUSTRIAL",
                decision="INDUSTRIAL_CORE_POSITIVE",
                model_version="test",
                feature_version="test",
            ))
            db.add(SiteDailyInference(
                site_id=site_id,
                acq_date=cutoff,
                model_c_status="NORMAL",
                c_score=0.1,
                model_c_version="test",
            ))
        db.commit()

        response = build_replay_snapshot(db, cutoff=cutoff, limit=1)
        assert response.active_sites_count == 2
        assert response.returned_sites_count == 1
        assert response.truncated is True
        assert len(response.features) == 1
    finally:
        db.close()


def test_runtime_replay_cache_round_trip(tmp_path):
    cache = RuntimeReplayCache(namespace="test", root=tmp_path)
    response = ReplaySnapshotResponse(
        as_of_date="2026-04-23",
        active_sites_count=0,
        returned_sites_count=0,
        truncated=False,
        alerts_count=0,
        features=[],
    )
    cache.store("2026-04-23", "75,20,76,21", 100, response)
    loaded = cache.load("2026-04-23", "75.00000,20,76,21", 100)
    assert loaded is not None
    assert loaded.as_of_date == response.as_of_date


def test_offline_demo_bundle_is_complete_and_focal_states_match():
    service = DemoService()
    status = service.status()
    assert status.status == "READY"
    assert status.scenario_count == 4
    assert status.cached_snapshot_count == status.expected_snapshot_count == 38

    for scenario in service.collection.scenarios:
        response = service.snapshot(scenario.scenario_id)
        focal = next(
            item.properties
            for item in response.features
            if item.properties.site_id == scenario.site_id
        )
        for key, expected in scenario.expected.items():
            assert getattr(focal, key) == expected
        assert response.cache_status == "DEMO_CACHE"


def test_demo_endpoints_require_no_database_session():
    client = TestClient(app)
    status = client.get("/api/v1/demo/status")
    assert status.status_code == 200
    assert status.json()["status"] == "READY"

    scenarios = client.get("/api/v1/demo/scenarios")
    assert scenarios.status_code == 200
    scenario = scenarios.json()["scenarios"][0]
    snapshot = client.get(
        f"/api/v1/demo/scenarios/{scenario['scenario_id']}/snapshot"
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["cache_status"] == "DEMO_CACHE"
