"""Rasterio-backed ESA WorldCover extraction for static Model A features."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from collections import defaultdict
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import numpy as np

from backend.app.services.rasterio_environment import (
    RasterioEnvironmentUnavailable,
    configure_rasterio_environment as _configure_rasterio_environment,
)


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORLDCOVER_VERSION = "v200-2021"
DEFAULT_BASE_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
)
CLASS_FEATURES = {
    10: "tree_fraction",
    20: "shrub_fraction",
    30: "grass_fraction",
    40: "crop_fraction",
    50: "built_fraction",
    60: "bare_fraction",
    80: "water_fraction",
    90: "wetland_fraction",
    95: "mangrove_fraction",
}
TRANSIENT_REMOTE_ERRORS = (
    "could not resolve host",
    "couldn't resolve host",
    "connection reset",
    "connection timed out",
    "failed to connect",
    "got 0 bytes",
    "http error code: 0",
    "http response code: 429",
    "http response code: 500",
    "http response code: 502",
    "http response code: 503",
    "http response code: 504",
    "ireadblock failed",
    "temporary failure",
    "tifffilltile:read error",
    "tiffreadencodedtile",
)
REMOTE_RETRY_DELAYS_SECONDS = (2, 5, 10)


def configure_rasterio_environment() -> None:
    """Keep Rasterio isolated from incompatible system/PostGIS GDAL data."""
    try:
        _configure_rasterio_environment()
    except RasterioEnvironmentUnavailable as exc:
        raise WorldCoverUnavailable(str(exc)) from exc


class WorldCoverUnavailable(RuntimeError):
    """Raised when authoritative WorldCover fractions cannot be obtained."""


class WorldCoverService:
    """Read a 2 km square from the public WorldCover COG and cache fractions."""

    def __init__(self, cache_dir: Path | str | None = None, base_url: str | None = None) -> None:
        configured_cache = cache_dir or os.environ.get("WORLDCOVER_CACHE_DIR")
        self.cache_dir = Path(configured_cache) if configured_cache else (
            PROJECT_ROOT / "data/cache/worldcover"
        )
        self.base_url = (base_url or os.environ.get("WORLDCOVER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

    def get_fractions(self, latitude: float, longitude: float) -> Dict[str, Optional[float]]:
        latitude = float(latitude)
        longitude = float(longitude)
        self._validate_coordinates(latitude, longitude)
        cache_path = self._cache_path(latitude, longitude)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        tile = self.tile_id(latitude, longitude)
        url = f"{self.base_url}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        try:
            pixels = self._read_window(url, latitude, longitude)
            fractions = self._fractions_from_pixels(pixels)
        except WorldCoverUnavailable:
            raise
        except Exception as exc:
            raise WorldCoverUnavailable(
                f"WorldCover extraction failed for ({latitude}, {longitude}) from {tile}: {exc}"
            ) from exc

        payload = {
            "worldcover_version": WORLDCOVER_VERSION,
            "latitude": latitude,
            "longitude": longitude,
            "tile": tile,
            "source_uri": url,
            "fractions": fractions,
        }
        self._write_cache(cache_path, payload)
        return fractions

    def get_fractions_many(
        self,
        locations: Mapping[str, Tuple[float, float]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Tuple[
        Dict[str, Dict[str, Optional[float]]],
        Dict[str, str],
    ]:
        """Extract many sites while opening each remote COG tile only once."""
        results: Dict[str, Dict[str, Optional[float]]] = {}
        errors: Dict[str, str] = {}
        total_sites = len(locations)

        def processed_count() -> int:
            return len(set(results).union(errors))

        def report_progress(tile: Optional[str], detail: str) -> None:
            if progress_callback is None:
                return
            processed = processed_count()
            try:
                progress_callback({
                    "processed_sites": processed,
                    "total_sites": total_sites,
                    "progress_percent": round(100 * processed / max(1, total_sites)),
                    "current_tile": tile,
                    "detail": detail,
                })
            except Exception:
                logger.warning("WorldCover progress callback failed", exc_info=True)

        grouped = defaultdict(list)
        for site_id, coordinates in locations.items():
            latitude, longitude = map(float, coordinates)
            try:
                self._validate_coordinates(latitude, longitude)
                cache_path = self._cache_path(latitude, longitude)
                cached = self._read_cache(cache_path)
                if cached is not None:
                    results[site_id] = cached
                    continue
                grouped[self.tile_id(latitude, longitude)].append(
                    (site_id, latitude, longitude, cache_path)
                )
            except (ValueError, OSError) as exc:
                errors[site_id] = str(exc)

        report_progress(
            None,
            f"Resolved {len(results)}/{total_sites} WorldCover sites from local cache.",
        )

        try:
            configure_rasterio_environment()
            import rasterio
            from rasterio.windows import from_bounds
        except (ImportError, WorldCoverUnavailable) as exc:
            message = str(exc) or "rasterio is not installed."
            errors = {**errors, **{
                site_id: message
                for entries in grouped.values()
                for site_id, _, _, _ in entries
            }}
            report_progress(None, "WorldCover extraction stopped because rasterio is unavailable.")
            return results, errors

        tile_groups = list(grouped.items())
        for tile_index, (tile, entries) in enumerate(tile_groups, start=1):
            url = f"{self.base_url}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            logger.info(
                "WorldCover tile %d/%d: %s (%d uncached sites)",
                tile_index,
                len(tile_groups),
                tile,
                len(entries),
            )
            try:
                with rasterio.Env(
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                    AWS_NO_SIGN_REQUEST="YES",
                    GDAL_HTTP_MAX_RETRY="3",
                    GDAL_HTTP_RETRY_DELAY="1",
                ):
                    source = self._open_remote_with_retry(rasterio, url)
                    with source:
                        for site_id, latitude, longitude, cache_path in entries:
                            # A previous attempt may have completed part of this tile.
                            cached = self._read_cache(cache_path)
                            if cached is not None:
                                results[site_id] = cached
                                continue
                            try:
                                bounds = self._window_bounds(latitude, longitude)
                                window = from_bounds(*bounds, source.transform)
                                pixels = self._read_source_with_retry(
                                    source, window, site_id=site_id, tile=tile
                                )
                                fractions = self._fractions_from_pixels(pixels)
                                self._write_cache(cache_path, {
                                    "worldcover_version": WORLDCOVER_VERSION,
                                    "latitude": latitude,
                                    "longitude": longitude,
                                    "tile": tile,
                                    "source_uri": url,
                                    "fractions": fractions,
                                })
                                results[site_id] = fractions
                            except WorldCoverUnavailable:
                                raise
                            except Exception as exc:
                                errors[site_id] = str(exc)
                            if processed_count() % 250 == 0:
                                report_progress(
                                    tile,
                                    f"Hydrated WorldCover for {processed_count()}/{total_sites} sites.",
                                )
            except WorldCoverUnavailable:
                raise
            except Exception as exc:
                message = f"Unable to read WorldCover COG {url}: {exc}"
                for site_id, _, _, _ in entries:
                    errors.setdefault(site_id, message)
            report_progress(
                tile,
                f"Completed WorldCover tile {tile_index}/{len(tile_groups)}; "
                f"processed {processed_count()}/{total_sites} sites.",
            )
        report_progress(None, f"WorldCover hydration complete for {len(results)}/{total_sites} sites.")
        return results, errors

    @staticmethod
    def _is_transient_remote_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in TRANSIENT_REMOTE_ERRORS)

    @classmethod
    def _open_remote_with_retry(cls, rasterio, url: str):
        for attempt in range(len(REMOTE_RETRY_DELAYS_SECONDS) + 1):
            try:
                return rasterio.open(url)
            except Exception as exc:
                if not cls._is_transient_remote_error(exc):
                    raise
                if attempt >= len(REMOTE_RETRY_DELAYS_SECONDS):
                    raise WorldCoverUnavailable(
                        f"Transient WorldCover network failure opening {url} after retries: {exc}"
                    ) from exc
                delay = REMOTE_RETRY_DELAYS_SECONDS[attempt]
                logger.warning(
                    "Transient WorldCover open failure; retrying in %ds (%d/%d): %s",
                    delay,
                    attempt + 1,
                    len(REMOTE_RETRY_DELAYS_SECONDS),
                    exc,
                )
                time.sleep(delay)

    @classmethod
    def _read_source_with_retry(cls, source, window, site_id: str, tile: str):
        for attempt in range(len(REMOTE_RETRY_DELAYS_SECONDS) + 1):
            try:
                return source.read(1, window=window, boundless=True, fill_value=0)
            except Exception as exc:
                if not cls._is_transient_remote_error(exc):
                    raise
                if attempt >= len(REMOTE_RETRY_DELAYS_SECONDS):
                    raise WorldCoverUnavailable(
                        f"Transient WorldCover network failure reading {tile} for {site_id} "
                        f"after retries: {exc}"
                    ) from exc
                delay = REMOTE_RETRY_DELAYS_SECONDS[attempt]
                logger.warning(
                    "Transient WorldCover read failure for %s; retrying in %ds (%d/%d)",
                    site_id,
                    delay,
                    attempt + 1,
                    len(REMOTE_RETRY_DELAYS_SECONDS),
                )
                time.sleep(delay)

    @staticmethod
    def tile_id(latitude: float, longitude: float) -> str:
        """Return the 3-degree WorldCover tile origin, including S/W hemispheres."""
        WorldCoverService._validate_coordinates(float(latitude), float(longitude))
        south = int(math.floor(float(latitude) / 3.0) * 3)
        west = int(math.floor(float(longitude) / 3.0) * 3)
        lat_prefix = "N" if south >= 0 else "S"
        lon_prefix = "E" if west >= 0 else "W"
        return f"{lat_prefix}{abs(south):02d}{lon_prefix}{abs(west):03d}"

    @staticmethod
    def _validate_coordinates(latitude: float, longitude: float) -> None:
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise ValueError(f"Invalid WorldCover coordinates: ({latitude}, {longitude})")
        if abs(latitude) >= 89.0:
            raise ValueError("WorldCover extraction is unsupported within one degree of a pole.")

    @staticmethod
    def _read_window(url: str, latitude: float, longitude: float) -> np.ndarray:
        try:
            configure_rasterio_environment()
            import rasterio
            from rasterio.windows import from_bounds
        except (ImportError, WorldCoverUnavailable) as exc:
            raise WorldCoverUnavailable(str(exc) or "rasterio is not installed.") from exc

        try:
            with rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                AWS_NO_SIGN_REQUEST="YES",
                GDAL_HTTP_MAX_RETRY="3",
                GDAL_HTTP_RETRY_DELAY="1",
            ):
                with rasterio.open(url) as source:
                    window = from_bounds(
                        *WorldCoverService._window_bounds(latitude, longitude),
                        source.transform,
                    )
                    return source.read(1, window=window, boundless=True, fill_value=0)
        except Exception as exc:
            raise WorldCoverUnavailable(f"Unable to read WorldCover COG {url}: {exc}") from exc

    @staticmethod
    def _window_bounds(latitude: float, longitude: float) -> Tuple[float, float, float, float]:
        half_metres = 1000.0
        delta_lat = half_metres / 111320.0
        delta_lon = half_metres / (111320.0 * math.cos(math.radians(latitude)))
        return (
            longitude - delta_lon,
            latitude - delta_lat,
            longitude + delta_lon,
            latitude + delta_lat,
        )

    @staticmethod
    def _fractions_from_pixels(pixels: np.ndarray) -> Dict[str, Optional[float]]:
        values = np.asarray(pixels)
        valid = values[values > 0]
        if not valid.size:
            # ESA WorldCover masks open ocean as NoData. Preserve that fact as
            # explicit nulls so Model A's frozen missing-value handling is used.
            return {feature: None for feature in CLASS_FEATURES.values()}
        counts = np.bincount(valid.astype(np.uint8, copy=False), minlength=101)
        total = float(valid.size)
        return {
            feature: float(counts[code] / total)
            for code, feature in CLASS_FEATURES.items()
        }

    def _cache_path(self, latitude: float, longitude: float) -> Path:
        key = hashlib.sha256(
            f"{WORLDCOVER_VERSION}:{latitude:.8f}:{longitude:.8f}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / self.tile_id(latitude, longitude) / f"{key}.json"

    @staticmethod
    def _read_cache(path: Path) -> Dict[str, Optional[float]] | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("worldcover_version") != WORLDCOVER_VERSION:
                return None
            fractions = payload["fractions"]
            if set(fractions) != set(CLASS_FEATURES.values()):
                return None
            return {
                name: None if value is None else float(value)
                for name, value in fractions.items()
            }
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write_cache(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
