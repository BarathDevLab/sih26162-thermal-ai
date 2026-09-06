"""
Integration & Functional Tests for SIH26162 API v1 Endpoints
Tests all routes: /health, /stats, /sites, /timeline, /detections, /evidence, /alerts, /replay, and /stream/alerts
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.db.models import SourceSite, Alert

client = TestClient(app)


def test_root_endpoint():
    """Verify root / returns 200 and points to OpenAPI docs."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "docs_url" in data
    assert data["api_v1_prefix"] == "/api/v1"


def test_health_endpoint():
    """Verify /api/v1/health returns system status and registered model versions."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "healthy", "degraded")
    assert "database" in data
    assert "active_models" in data
    assert isinstance(data["active_models"], dict)


def test_stats_endpoint():
    """Verify /api/v1/stats returns national aggregated statistics."""
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_sites" in data
    assert data["total_sites"] > 0
    assert "model_a_counts" in data
    assert "model_b_counts" in data
    assert "model_c_counts" in data
    assert "alert_counts" in data


def test_sites_geojson_endpoint():
    """Verify /api/v1/sites returns GeoJSON FeatureCollection with compact properties."""
    response = client.get("/api/v1/sites?limit=25")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert len(geojson["features"]) <= 25
    assert "total_count" in geojson

    if geojson["features"]:
        feat = geojson["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert len(feat["geometry"]["coordinates"]) == 2
        props = feat["properties"]
        assert "site_id" in props
        assert "a_class" in props
        assert "b_state" in props
        assert "c_status" in props


def test_sites_bbox_filtering():
    """Verify /api/v1/sites correctly applies geographic bounding box filtering."""
    # Central India bounding box
    bbox_str = "75.0,20.0,82.0,26.0"
    response = client.get(f"/api/v1/sites?bbox={bbox_str}&limit=20")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"

    for feat in geojson["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        assert 75.0 <= lon <= 82.0
        assert 20.0 <= lat <= 26.0


def test_sites_invalid_bbox():
    """Verify /api/v1/sites handles invalid bbox strings gracefully with 400."""
    response = client.get("/api/v1/sites?bbox=invalid_bbox_str")
    assert response.status_code == 400


def test_sites_class_filtering():
    """Verify /api/v1/sites filters by Model A class."""
    response = client.get("/api/v1/sites?a_class=INDUSTRIAL_SURFACE&limit=10")
    assert response.status_code == 200
    geojson = response.json()
    for feat in geojson["features"]:
        assert feat["properties"]["a_class"] == "INDUSTRIAL_SURFACE"


def test_site_detail_found():
    """Verify /api/v1/sites/{site_id} returns complete profile for existing site."""
    with SessionLocal() as db:
        site = db.query(SourceSite).first()
        site_id = site.site_id if site else "INDIA_SITE_0000001"

    response = client.get(f"/api/v1/sites/{site_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["site_id"] == site_id
    assert "latitude" in detail
    assert "longitude" in detail
    assert "model_a" in detail
    assert "model_b" in detail
    assert "model_c" in detail
    assert "active_alert" in detail


def test_site_detail_not_found():
    """Verify /api/v1/sites/{site_id} returns 404 for unknown site ID."""
    response = client.get("/api/v1/sites/NONEXISTENT_SITE_XYZ")
    assert response.status_code == 404


def test_site_timeline():
    """Verify /api/v1/sites/{site_id}/timeline returns daily history points."""
    with SessionLocal() as db:
        site = db.query(SourceSite).first()
        site_id = site.site_id if site else "INDIA_SITE_0000001"

    response = client.get(f"/api/v1/sites/{site_id}/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == site_id
    assert "history" in data
    assert "total_active_days" in data
    assert isinstance(data["history"], list)

    if data["history"]:
        pt = data["history"][0]
        assert "acq_date" in pt
        assert "detections" in pt
        assert "mean_frp" in pt


def test_site_detections():
    """Verify /api/v1/sites/{site_id}/detections returns raw detections."""
    with SessionLocal() as db:
        site = db.query(SourceSite).first()
        site_id = site.site_id if site else "INDIA_SITE_0000001"

    response = client.get(f"/api/v1/sites/{site_id}/detections")
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == site_id
    assert "detections" in data
    assert isinstance(data["detections"], list)


def test_site_evidence():
    """Verify /api/v1/sites/{site_id}/evidence returns radial evidence matches."""
    with SessionLocal() as db:
        site = db.query(SourceSite).first()
        site_id = site.site_id if site else "INDIA_SITE_0000001"

    response = client.get(f"/api/v1/sites/{site_id}/evidence?radius_m=2000")
    assert response.status_code == 200
    data = response.json()
    assert data["site_id"] == site_id
    assert "evidence" in data
    assert isinstance(data["evidence"], list)


def test_site_imagery():
    """Verify /api/v1/sites/{site_id}/imagery returns cached imagery records."""
    with SessionLocal() as db:
        site = db.query(SourceSite).first()
        site_id = site.site_id if site else "INDIA_SITE_0000001"

    response = client.get(f"/api/v1/sites/{site_id}/imagery")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_alerts_feed():
    """Verify /api/v1/alerts returns operational alerts feed."""
    response = client.get("/api/v1/alerts?limit=15")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
    assert "alerts" in data
    assert isinstance(data["alerts"], list)

    if data["alerts"]:
        alert = data["alerts"][0]
        assert "alert_id" in alert
        assert "site_id" in alert
        assert "alert_level" in alert
        assert "fingerprint" in alert
        assert "status" in alert


def test_alert_ack_workflow():
    """Verify acknowledging an active alert updates status to ACKNOWLEDGED."""
    with SessionLocal() as db:
        alert = db.query(Alert).filter(Alert.status == "ACTIVE").first()

    if alert:
        alert_id = alert.alert_id
        ack_payload = {"acknowledged_by": "qa_analyst_agent"}
        response = client.post(f"/api/v1/alerts/{alert_id}/ack", json=ack_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == alert_id
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_by"] == "qa_analyst_agent"

        # Verify 404 on invalid alert
        bad_response = client.post("/api/v1/alerts/ALT_NONEXISTENT_9999/ack", json=ack_payload)
        assert bad_response.status_code == 404


def test_layers_firms():
    """Verify /api/v1/layers/firms returns GeoJSON."""
    response = client.get("/api/v1/layers/firms?limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert "count" in data


def test_replay_endpoint():
    """Verify /api/v1/replay reconstructs historical cutoff correctly without leakage."""
    cutoff = "2025-06-01"
    response = client.get(f"/api/v1/replay?date={cutoff}&limit=30")
    assert response.status_code == 200
    data = response.json()
    assert data["as_of_date"] == cutoff
    assert "features" in data
    assert isinstance(data["features"], list)

    for feat in data["features"]:
        props = feat["properties"]
        if props.get("latest_seen"):
            assert props["latest_seen"] <= cutoff


def test_stream_alerts_sse():
    """Verify /api/v1/stream/alerts yields SSE headers and connection event."""
    response = client.get("/api/v1/stream/alerts?limit=1")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "event: connected" in response.text
