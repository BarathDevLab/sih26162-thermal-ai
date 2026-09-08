"""Regression tests for the fail-closed HLS/Prithvi boundary."""

from datetime import date

import numpy as np
import pytest

from backend.app.services.hls_service import (
    HLSPatch, HLSCloudRejected, HLSService, HLSUnavailable,
)
from backend.app.services.prithvi_service import PrithviService, PrithviUnavailable


def test_missing_hls_cache_stays_unavailable(tmp_path):
    service = HLSService(cache_dir=str(tmp_path))
    with pytest.raises(HLSUnavailable):
        service.load_cached_patch("SITE_MISSING", date(2026, 1, 1))


def test_genuine_hls_cache_contract(tmp_path):
    site_id = "SITE_A"
    acquisition_date = date(2026, 1, 2)
    target = tmp_path / site_id
    target.mkdir()
    np.savez_compressed(
        target / f"{acquisition_date.isoformat()}.npz",
        product=np.array("HLSS30"),
        bands=np.ones((6, 224, 224), dtype=np.float32),
        cloud_fraction=np.array(0.1),
        source_uri=np.array("earthdata://HLS/SITE_A/2026-01-02"),
    )
    patch = HLSService(cache_dir=str(tmp_path)).load_cached_patch(site_id, acquisition_date)
    assert patch.bands.shape == (6, 224, 224)
    assert patch.product == "HLSS30"
    assert patch.source_uri.startswith("earthdata://")


def test_rgb_or_procedural_patch_cannot_cross_hls_boundary():
    patch = HLSPatch(
        site_id="SITE_A",
        acquisition_date=date(2026, 1, 2),
        product="HLSS30",
        bands=np.ones((3, 224, 224), dtype=np.float32),
        cloud_fraction=0.1,
        source_uri="synthetic://not-allowed",
    )
    with pytest.raises(ValueError):
        patch.validate()


def test_cloudy_hls_patch_is_rejected_without_probability():
    patch = HLSPatch(
        site_id="SITE_A",
        acquisition_date=date(2026, 1, 2),
        product="HLSS30",
        bands=np.ones((6, 224, 224), dtype=np.float32),
        cloud_fraction=0.9,
        source_uri="earthdata://HLS/cloudy",
    )
    with pytest.raises(HLSCloudRejected):
        patch.validate()


def test_prithvi_never_returns_heuristic_probability():
    try:
        service = PrithviService()
    except PrithviUnavailable:
        return
    patch = HLSPatch(
        site_id="SITE_A",
        acquisition_date=date(2026, 1, 2),
        product="HLSS30",
        bands=np.ones((6, 224, 224), dtype=np.float32),
        cloud_fraction=0.1,
        source_uri="earthdata://HLS/SITE_A/2026-01-02",
    )
    with pytest.raises(PrithviUnavailable):
        service.score(patch)
