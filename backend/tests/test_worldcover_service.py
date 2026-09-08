import os
from pathlib import Path

import numpy as np

from backend.app.services.worldcover_service import (
    WorldCoverService,
    configure_rasterio_environment,
)


def test_worldcover_tile_id_supports_all_hemispheres():
    assert WorldCoverService.tile_id(22.1, 72.5) == "N21E072"
    assert WorldCoverService.tile_id(-1.0, -70.0) == "S03W072"


def test_worldcover_fraction_mapping_excludes_non_model_classes():
    pixels = np.array([[10, 10, 20, 40], [50, 60, 70, 80], [90, 95, 100, 0]])
    fractions = WorldCoverService._fractions_from_pixels(pixels)
    assert set(fractions) == {
        "tree_fraction", "shrub_fraction", "grass_fraction", "crop_fraction",
        "built_fraction", "bare_fraction", "water_fraction",
        "wetland_fraction", "mangrove_fraction",
    }
    assert fractions["tree_fraction"] == 2 / 11
    assert fractions["grass_fraction"] == 0.0
    assert fractions["mangrove_fraction"] == 1 / 11


def test_worldcover_site_cache_avoids_second_cog_read(tmp_path, monkeypatch):
    service = WorldCoverService(cache_dir=tmp_path)
    calls = []

    def fake_read(url, latitude, longitude):
        calls.append((url, latitude, longitude))
        return np.array([[10, 40], [50, 80]])

    monkeypatch.setattr(service, "_read_window", fake_read)
    first = service.get_fractions(22.1, 72.5)
    second = service.get_fractions(22.1, 72.5)

    assert first == second
    assert len(calls) == 1
    assert first["tree_fraction"] == 0.25


def test_worldcover_ocean_nodata_is_cached_as_explicit_nulls(tmp_path, monkeypatch):
    service = WorldCoverService(cache_dir=tmp_path)
    calls = []

    def fake_read(url, latitude, longitude):
        calls.append((url, latitude, longitude))
        return np.zeros((10, 10), dtype=np.uint8)

    monkeypatch.setattr(service, "_read_window", fake_read)
    first = service.get_fractions(13.05, 96.87)
    second = service.get_fractions(13.05, 96.87)

    assert first == second
    assert all(value is None for value in first.values())
    assert len(calls) == 1


def test_rasterio_uses_its_bundled_proj_and_gdal_data(monkeypatch):
    monkeypatch.setenv("PROJ_LIB", r"C:\Program Files\PostgreSQL\18\postgis\proj")
    monkeypatch.setenv("GDAL_DATA", r"C:\Program Files\PostgreSQL\18\gdal-data")

    configure_rasterio_environment()

    import rasterio

    package_dir = Path(rasterio.__file__).resolve().parent
    assert Path(os.environ["PROJ_LIB"]) == package_dir / "proj_data"
    assert Path(os.environ["PROJ_DATA"]) == package_dir / "proj_data"
    assert Path(os.environ["GDAL_DATA"]) == package_dir / "gdal_data"
