"""Regression tests for the fail-closed HLS/Prithvi boundary."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from backend.app.services.hls_service import (
    HLSPatch, HLSCloudRejected, HLSService, HLSUnavailable,
)
from backend.app.services import prithvi_service
from backend.app.api.v1.evidence import _prithvi_retry_due
from backend.app.services.prithvi_service import PrithviService


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


def _clear_patch() -> HLSPatch:
    return HLSPatch(
        site_id="SITE_A",
        acquisition_date=date(2026, 1, 2),
        product="HLSS30",
        bands=np.full((6, 224, 224), 0.1, dtype=np.float32),
        cloud_fraction=0.1,
        source_uri="earthdata://HLS/SITE_A/2026-01-02",
    )


def test_prithvi_preprocessing_restores_hls_scale_and_repeats_scene():
    patch = _clear_patch()
    patch.bands[:, 0, 0] = 0.0
    config = {
        "mean": [1087.0, 1342.0, 1433.0, 2734.0, 1958.0, 1363.0],
        "std": [2248.0, 2179.0, 2178.0, 1850.0, 1242.0, 1049.0],
        "num_frames": 4,
    }

    result = prithvi_service._prepare_prithvi_input(patch, config)

    assert result.shape == (1, 6, 4, 224, 224)
    assert result.dtype == np.float32
    assert result[0, 0, 0, 1, 1] == pytest.approx((1000.0 - 1087.0) / 2248.0)
    assert np.array_equal(result[:, :, 0], result[:, :, 3])
    assert np.all(result[0, :, :, 0, 0] == 0.0)


def test_prithvi_probability_comes_from_frozen_head(monkeypatch):
    embedding = np.linspace(-1.0, 1.0, 1024, dtype=np.float32)

    class StubRuntime:
        def encode(self, input_data):
            assert input_data.shape == (1, 6, 4, 224, 224)
            return embedding

    class StubHead:
        def predict_proba(self, features):
            assert np.array_equal(features, embedding.reshape(1, -1))
            return np.array([[0.13, 0.87]])

    service = PrithviService.__new__(PrithviService)
    service.contract = SimpleNamespace(
        encoder_config={
            "mean": [1087.0, 1342.0, 1433.0, 2734.0, 1958.0, 1363.0],
            "std": [2248.0, 2179.0, 2178.0, 1850.0, 1242.0, 1049.0],
            "num_frames": 4,
        },
        head=StubHead(),
        model_revision="test-revision",
    )
    service.device = "cpu"
    monkeypatch.setattr(prithvi_service, "_get_runtime", lambda device, contract: StubRuntime())

    result = service.score(_clear_patch())

    assert result.probability == pytest.approx(0.87)
    assert np.array_equal(result.embedding, embedding)
    assert result.model_revision == "test-revision"


@pytest.mark.parametrize(
    ("status", "age_minutes", "expected"),
    [("UNAVAILABLE", 120, True), ("UNAVAILABLE", 5, False), ("REJECTED_CLOUD", 120, False)],
)
def test_prithvi_failed_cache_retry_backoff(monkeypatch, status, age_minutes, expected):
    row = SimpleNamespace(
        status=status,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    )

    class StubQuery:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return row

    db = SimpleNamespace(query=lambda model: StubQuery())
    summaries = [SimpleNamespace(status=status)]
    monkeypatch.setenv("PRITHVI_RETRY_AFTER_MINUTES", "60")

    assert _prithvi_retry_due(db, "SITE_A", summaries) is expected
