"""
Tests for NASA FIRMS Client
Verifies URL construction, day_range boundary validation, CSV parsing, and offline caching.
"""

import os
import tempfile
import pytest
from backend.app.services.firms_client import (
    FirmsClient,
    DEFAULT_INDIA_BBOX,
    DEFAULT_PRIMARY_SOURCE
)


def test_build_area_url_defaults():
    client = FirmsClient(map_key="TEST_MAP_KEY_123")
    url = client.build_area_url(day_range=1)
    expected = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/TEST_MAP_KEY_123/{DEFAULT_PRIMARY_SOURCE}/{DEFAULT_INDIA_BBOX}/1"
    assert url == expected


def test_build_area_url_with_date():
    client = FirmsClient(map_key="TEST_MAP_KEY_123")
    url = client.build_area_url(
        source="VIIRS_NOAA21_NRT",
        bbox="70,10,90,30",
        day_range=5,
        date="2026-02-15"
    )
    expected = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/TEST_MAP_KEY_123/VIIRS_NOAA21_NRT/70,10,90,30/5/2026-02-15"
    assert url == expected


def test_build_area_url_invalid_day_range():
    client = FirmsClient(map_key="TEST_KEY")
    # Day range must be 1-5
    with pytest.raises(ValueError):
        client.build_area_url(day_range=0)

    with pytest.raises(ValueError):
        client.build_area_url(day_range=6)


def test_parse_csv_content():
    client = FirmsClient(map_key="TEST_KEY", offline_mode=True)
    sample_csv = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
22.4512,71.9821,345.6,0.4,0.4,2026-01-05,0830,20,VIIRS,nominal,2.0NRT,298.2,12.5,D
23.1111,72.2222,350.1,0.5,0.4,2026-01-05,0830,20,VIIRS,high,2.0NRT,300.0,24.8,D"""

    parsed = client.parse_csv_content(sample_csv)
    assert len(parsed) == 2
    assert parsed[0]["latitude"] == "22.4512"
    assert parsed[0]["acq_date"] == "2026-01-05"
    assert parsed[1]["frp"] == "24.8"
    assert parsed[1]["confidence"] == "high"


def test_offline_mode_returns_empty():
    client = FirmsClient(map_key=None, offline_mode=True)
    dets = client.fetch_area_detections()
    assert dets == []


def test_cache_read_and_write():
    with tempfile.TemporaryDirectory() as tmp_dir:
        client = FirmsClient(map_key=None, cache_dir=tmp_dir, offline_mode=True)
        sample_csv = "latitude,longitude,frp,acq_date\n22.0,72.0,15.2,2026-01-01"
        client._write_cache(DEFAULT_PRIMARY_SOURCE, DEFAULT_INDIA_BBOX, 1, "2026-01-01", sample_csv)

        # Read back through fetch
        dets = client.fetch_area_detections(day_range=1, date="2026-01-01")
        assert len(dets) == 1
        assert dets[0]["frp"] == "15.2"
