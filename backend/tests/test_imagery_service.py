"""
Tests for Satellite Imagery Service & Prithvi Visual Scoring Engine
"""

import pytest
from backend.app.services.imagery_service import (
    fetch_satellite_patch_bytes,
    analyze_multispectral_patch,
    get_or_create_site_imagery,
    PRITHVI_RESCUE_THRESHOLD
)
from backend.app.db.session import SessionLocal
from backend.app.db.models import SourceSite, SiteModelA, ImageryCache


def test_fetch_satellite_patch_bytes():
    # Test fetch for Delhi coords
    png_bytes, provider = fetch_satellite_patch_bytes(28.6139, 77.2090)
    assert len(png_bytes) > 500
    assert png_bytes.startswith(b"\x89PNG")
    assert provider in ["ESRI_WORLD_IMAGERY", "SYNTHETIC_PROCEDURAL"]


def test_analyze_multispectral_patch():
    png_bytes, _ = fetch_satellite_patch_bytes(28.6139, 77.2090)
    analysis = analyze_multispectral_patch(
        png_bytes,
        land_cover={"built_fraction": 0.85, "bare_fraction": 0.1},
        core_probability=0.92
    )

    assert "cloud_fraction" in analysis
    assert 0.0 <= analysis["cloud_fraction"] <= 1.0

    assert "bands_mean" in analysis
    bands = analysis["bands_mean"]
    for b in ["B02_Blue", "B03_Green", "B04_Red", "B05_NIR", "B06_SWIR1", "B07_SWIR2"]:
        assert b in bands
        assert bands[b] >= 0.0

    assert "prithvi_probability" in analysis
    assert 0.0 <= analysis["prithvi_probability"] <= 1.0
    assert "visual_class" in analysis
    assert "morphology_summary" in analysis


def test_imagery_service_guarded_rescue():
    db = SessionLocal()
    try:
        # Pick any active site in database
        site = db.query(SourceSite).first()
        if not site:
            pytest.skip("No sites in database to test")

        summary = get_or_create_site_imagery(db, site.site_id)
        assert summary.site_id == site.site_id
        assert summary.product == "HLSS30"
        assert summary.prithvi_probability is not None
        assert summary.patch_base64 is not None
        assert summary.patch_base64.startswith("data:image/png;base64,")

        # Verify DB records updated
        cache_row = db.query(ImageryCache).filter(ImageryCache.site_id == site.site_id).first()
        assert cache_row is not None
        assert cache_row.status == "AVAILABLE"

        model_a_row = db.query(SiteModelA).filter(SiteModelA.site_id == site.site_id).first()
        if model_a_row:
            assert model_a_row.prithvi_status in ["CONFIRMED", "RESCUED", "EVALUATED"]
            assert model_a_row.prithvi_probability == summary.prithvi_probability
    finally:
        db.close()
