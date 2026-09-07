"""
Tests for Phase 7 Live Ingestion Pipeline, Scheduler & Simulation Endpoints
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models import SourceSite, SiteModelB
from backend.app.services.live_pipeline import get_live_pipeline_service, run_global_daily_model_b_refresh
from backend.app.services.scheduler import get_scheduler_status

client = TestClient(app)


def test_live_status_endpoint():
    resp = client.get("/api/v1/live/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "scheduler" in data
    assert "prithvi_queue" in data


def test_live_pipeline_simulate_hotspot():
    db = SessionLocal()
    try:
        # Find any existing site
        site = db.query(SourceSite).first()
        if not site:
            pytest.skip("No sites in database to test")

        lat = float(site.latitude)
        lon = float(site.longitude)

        import random
        from datetime import datetime
        now_str = datetime.now().strftime("%H%M") + str(random.randint(10, 99))
        payload = {
            "latitude": lat,
            "longitude": lon,
            "frp": 150.0,
            "bright_ti4": 380.0,
            "confidence": "high",
            "satellite": "20",
            "acq_date": date.today().isoformat(),
            "acq_time": now_str
        }

        resp = client.post("/api/v1/live/simulate-hotspot", json=payload)
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "SUCCESS"
        assert res_data["pipeline_result"]["matched_count"] >= 1
    finally:
        db.close()


def test_global_daily_model_b_decay():
    db = SessionLocal()
    try:
        res = run_global_daily_model_b_refresh(db, as_of_date=date.today())
        assert res["status"] == "COMPLETED"
        assert "sites_evaluated" in res
        assert "decayed_to_dormant" in res
    finally:
        db.close()
