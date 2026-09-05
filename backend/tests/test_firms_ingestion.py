"""
Tests for FIRMS Ingestion Service
Verifies normalization, deterministic SHA-256 hashing, batch deduplication, spatial resolution, and daily activity aggregation.
"""

import pandas as pd
import pytest
from backend.app.services.firms_ingestion import FirmsIngestionService
from backend.app.engines.source_resolver import SourceResolver


def test_deterministic_detection_id():
    h1 = FirmsIngestionService.generate_detection_id(
        source_sensor="VIIRS_NOAA20_NRT",
        satellite="20",
        latitude=22.12341,
        longitude=72.56782,
        acq_date="2026-01-10",
        acq_time="0830"
    )
    # Rounding to 4 decimals means 22.12341 and 22.12344 produce identical keys
    h2 = FirmsIngestionService.generate_detection_id(
        source_sensor="VIIRS_NOAA20_NRT",
        satellite="20",
        latitude=22.12344,
        longitude=72.56781,
        acq_date="2026-01-10",
        acq_time="0830"
    )
    assert h1 == h2

    # Different time produces different key
    h3 = FirmsIngestionService.generate_detection_id(
        source_sensor="VIIRS_NOAA20_NRT",
        satellite="20",
        latitude=22.12341,
        longitude=72.56782,
        acq_date="2026-01-10",
        acq_time="0930"
    )
    assert h1 != h3


def test_ingest_batch_deduplication_and_resolution():
    resolver = SourceResolver(eps_m=750.0, min_samples=3)
    resolver.load_sites([
        {"site_id": "SITE_ALPHA", "latitude": 22.0, "longitude": 72.0}
    ])
    service = FirmsIngestionService(resolver)

    raw_batch = [
        # Record 1: near SITE_ALPHA (~30m)
        {
            "latitude": "22.0002", "longitude": "72.0002",
            "acq_date": "2026-01-01", "acq_time": "0830",
            "satellite": "20", "frp": "14.5", "confidence": "nominal"
        },
        # Record 2: identical duplicate of Record 1
        {
            "latitude": "22.0002", "longitude": "72.0002",
            "acq_date": "2026-01-01", "acq_time": "0830",
            "satellite": "20", "frp": "14.5", "confidence": "nominal"
        },
        # Record 3: Far away from existing site -> candidate
        {
            "latitude": "26.0000", "longitude": "76.0000",
            "acq_date": "2026-01-01", "acq_time": "0835",
            "satellite": "20", "frp": "5.2", "confidence": "low"
        }
    ]

    res = service.ingest_batch(raw_batch)
    assert res["processed_count"] == 3
    assert res["unique_count"] == 2
    assert res["duplicate_count"] == 1
    assert res["matched_count"] == 1
    assert res["candidate_count"] == 1

    matched = [d for d in res["resolved_detections"] if d["site_id"] == "SITE_ALPHA"]
    assert len(matched) == 1
    assert matched[0]["resolution_status"] == "MATCHED"


def test_aggregate_daily_activity():
    service = FirmsIngestionService()
    resolved_dets = [
        {"site_id": "SITE_A", "acq_date": "2026-01-01", "frp": 10.0},
        {"site_id": "SITE_A", "acq_date": "2026-01-01", "frp": 20.0},
        {"site_id": "SITE_A", "acq_date": "2026-01-02", "frp": 15.0},
        {"site_id": "SITE_B", "acq_date": "2026-01-01", "frp": 8.0}
    ]

    daily_df = service.aggregate_daily_activity(resolved_dets)
    assert len(daily_df) == 3

    # Check SITE_A on 2026-01-01
    row_a1 = daily_df[(daily_df["site_id"] == "SITE_A") & (daily_df["acq_date"] == "2026-01-01")].iloc[0]
    assert row_a1["detections"] == 2
    assert row_a1["mean_frp"] == 15.0
    assert row_a1["max_frp"] == 20.0

    # Test merging with existing daily activity
    existing_df = pd.DataFrame([
        {"site_id": "SITE_A", "acq_date": "2026-01-01", "detections": 1, "mean_frp": 30.0, "max_frp": 30.0}
    ])
    merged_df = service.aggregate_daily_activity(resolved_dets, existing_daily_df=existing_df)
    row_merged = merged_df[(merged_df["site_id"] == "SITE_A") & (merged_df["acq_date"] == "2026-01-01")].iloc[0]

    # Combined: 1 old + 2 new = 3 detections; max = max(30, 20) = 30.0; mean = (30*1 + 15*2)/3 = 20.0
    assert row_merged["detections"] == 3
    assert row_merged["max_frp"] == 30.0
    assert row_merged["mean_frp"] == 20.0
