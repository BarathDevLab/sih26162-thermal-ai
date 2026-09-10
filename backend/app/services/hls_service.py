"""Authenticated Earthdata HLS retrieval and genuine six-band patch caching."""

from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from backend.app.services.rasterio_environment import (
    RasterioEnvironmentUnavailable,
    configure_rasterio_environment,
)


HLS_CHANNELS = {
    "HLSS30": ("B02", "B03", "B04", "B8A", "B11", "B12"),
    "HLSL30": ("B02", "B03", "B04", "B05", "B06", "B07"),
}
PATCH_SIZE = 224


@dataclass
class HLSPatch:
    site_id: str
    acquisition_date: date
    product: str
    bands: np.ndarray
    cloud_fraction: float
    source_uri: str
    cache_path: Optional[str] = None

    def validate(self) -> None:
        if self.product not in HLS_CHANNELS:
            raise ValueError(f"Unsupported HLS product: {self.product}")
        if self.bands.shape != (6, PATCH_SIZE, PATCH_SIZE):
            raise ValueError(f"Expected genuine 6x224x224 HLS patch, got {self.bands.shape}")
        if not np.isfinite(self.bands).all():
            raise ValueError("HLS patch contains non-finite values.")
        if not 0.0 <= self.cloud_fraction <= 1.0:
            raise ValueError("Invalid HLS cloud fraction.")
        max_cloud = float(os.environ.get("HLS_MAX_CLOUD_FRACTION", "0.25"))
        if self.cloud_fraction > max_cloud:
            raise HLSCloudRejected(
                f"HLS patch cloud/invalid fraction {self.cloud_fraction:.3f} exceeds {max_cloud:.3f}."
            )
        if not self.source_uri.startswith(("s3://", "https://", "earthdata://")):
            raise ValueError("HLS source URI must identify a real Earthdata asset.")


class HLSUnavailable(RuntimeError):
    pass


class HLSCloudRejected(HLSUnavailable):
    pass


class HLSService:
    """Load cached HLS or retrieve a single best real scene from NASA Earthdata."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self.cache_dir = Path(cache_dir or os.environ.get("HLS_CACHE_DIR", "data/cache/hls"))

    def load_cached_patch(self, site_id: str, acquisition_date: date) -> HLSPatch:
        path = self.cache_dir / site_id / f"{acquisition_date.isoformat()}.npz"
        if not path.is_file():
            raise HLSUnavailable("No genuine cached HLS patch is available.")
        patch = self._read_cache(path)
        if patch.site_id != site_id:
            raise ValueError("HLS cache site provenance mismatch.")
        patch.cache_path = str(path)
        patch.validate()
        return patch

    def get_or_fetch_patch(
        self,
        site_id: str,
        latitude: float,
        longitude: float,
        target_date: date,
    ) -> HLSPatch:
        try:
            return self.load_cached_patch(site_id, target_date)
        except HLSCloudRejected:
            raise
        except HLSUnavailable:
            pass
        return self.fetch_patch(site_id, latitude, longitude, target_date)

    def fetch_patch(
        self,
        site_id: str,
        latitude: float,
        longitude: float,
        target_date: date,
    ) -> HLSPatch:
        if not os.environ.get("EARTHDATA_USERNAME") or not os.environ.get("EARTHDATA_PASSWORD"):
            raise HLSUnavailable("Earthdata credentials are not configured.")
        try:
            import earthaccess
        except ImportError as exc:
            raise HLSUnavailable("earthaccess is not installed.") from exc

        auth = earthaccess.login(strategy="environment", persist=False)
        authenticated = getattr(auth, "authenticated", None)
        if callable(authenticated):
            authenticated = authenticated()
        if authenticated is False:
            raise HLSUnavailable("Earthdata authentication failed.")

        lookback = int(os.environ.get("HLS_LOOKBACK_DAYS", "30"))
        temporal = (
            (target_date - timedelta(days=lookback)).isoformat(),
            (target_date + timedelta(days=lookback)).isoformat(),
        )
        delta = 0.0001
        bounding_box = (
            longitude - delta, latitude - delta, longitude + delta, latitude + delta
        )
        candidates = []
        for product in ("HLSS30", "HLSL30"):
            granules = earthaccess.search_data(
                short_name=product,
                version="2.0",
                bounding_box=bounding_box,
                temporal=temporal,
                count=int(os.environ.get("HLS_MAX_SEARCH_RESULTS", "10")),
            )
            candidates.extend((product, granule) for granule in granules)
        if not candidates:
            raise HLSUnavailable("No HLS v2.0 granule intersects the site/date search window.")

        best_patch = None
        failures: List[str] = []
        for product, granule in candidates:
            try:
                patch = self._download_and_extract(
                    earthaccess, granule, product, site_id, latitude, longitude, target_date
                )
                if best_patch is None or patch.cloud_fraction < best_patch.cloud_fraction:
                    best_patch = patch
            except (HLSUnavailable, ValueError) as exc:
                failures.append(str(exc))
        if best_patch is None:
            raise HLSUnavailable("No usable genuine HLS scene: " + "; ".join(failures[:3]))
        best_patch.validate()
        self._write_cache(best_patch, lookup_date=target_date)
        return best_patch

    def _download_and_extract(
        self,
        earthaccess,
        granule,
        product: str,
        site_id: str,
        latitude: float,
        longitude: float,
        target_date: date,
    ) -> HLSPatch:
        links = granule.data_links()
        selected: Dict[str, str] = {}
        for band in (*HLS_CHANNELS[product], "Fmask"):
            selected[band] = next(
                (
                    url
                    for url in links
                    if re.search(
                        rf"\.{re.escape(band)}\.tif(?:\?|$)", url, re.IGNORECASE
                    )
                ),
                "",
            )
        missing = [band for band, url in selected.items() if not url]
        if missing:
            raise HLSUnavailable(f"HLS granule is missing assets: {missing}")

        granule_key = hashlib.sha256(
            selected[HLS_CHANNELS[product][0]].encode("utf-8")
        ).hexdigest()[:16]
        download_dir = self.cache_dir / "_earthdata" / site_id / granule_key
        download_dir.mkdir(parents=True, exist_ok=True)
        downloaded = earthaccess.download(
            list(selected.values()), local_path=download_dir, threads=4, show_progress=False
        )
        path_by_band = {}
        for band in selected:
            match = next(
                (Path(path) for path in downloaded if re.search(
                    rf"\.{re.escape(band)}\.tif$", Path(path).name, re.IGNORECASE
                )),
                None,
            )
            if match is None or not match.is_file():
                raise HLSUnavailable(f"Earthdata download did not produce {band} asset.")
            path_by_band[band] = match

        arrays = [
            self._read_centered_band(path_by_band[band], latitude, longitude, reflectance=True)
            for band in HLS_CHANNELS[product]
        ]
        fmask = self._read_centered_band(
            path_by_band["Fmask"], latitude, longitude, reflectance=False
        )
        invalid = fmask == 255
        cloudy = ((fmask.astype(np.uint8) & np.uint8(0b00011111)) != 0) | invalid
        bands = np.stack(arrays).astype(np.float32)
        cloudy |= ~np.isfinite(bands).all(axis=0)
        cloud_fraction = float(np.mean(cloudy))
        bands[:, cloudy] = 0.0
        acquisition_date = _date_from_hls_name(path_by_band["Fmask"].name) or target_date
        return HLSPatch(
            site_id=site_id,
            acquisition_date=acquisition_date,
            product=product,
            bands=bands,
            cloud_fraction=cloud_fraction,
            source_uri=selected[HLS_CHANNELS[product][0]],
        )

    @staticmethod
    def _read_centered_band(
        path: Path, latitude: float, longitude: float, reflectance: bool
    ) -> np.ndarray:
        try:
            configure_rasterio_environment()
            import rasterio
            from rasterio.windows import Window
            from rasterio.warp import transform
        except (ImportError, RasterioEnvironmentUnavailable) as exc:
            raise HLSUnavailable(str(exc) or "rasterio is not installed.") from exc
        try:
            with rasterio.Env(GTIFF_SRS_SOURCE="EPSG"):
                with rasterio.open(path) as source:
                    xs, ys = transform("EPSG:4326", source.crs, [longitude], [latitude])
                    row, column = source.index(xs[0], ys[0])
                    half = PATCH_SIZE // 2
                    window = Window(column - half, row - half, PATCH_SIZE, PATCH_SIZE)
                    data = source.read(1, window=window, boundless=True, masked=True)
                    if reflectance:
                        array = data.astype(np.float32).filled(np.nan)
                        scale = (
                            float(source.scales[0])
                            if source.scales and source.scales[0] != 1
                            else 0.0001
                        )
                        offset = float(source.offsets[0]) if source.offsets else 0.0
                        return array * scale + offset
                    return data.astype(np.uint8).filled(255)
        except HLSUnavailable:
            raise
        except Exception as exc:
            raise HLSUnavailable(f"Unable to read HLS band {path.name}: {exc}") from exc

    def _write_cache(self, patch: HLSPatch, lookup_date: date) -> Path:
        target_dir = self.cache_dir / patch.site_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{lookup_date.isoformat()}.npz"
        temporary = target.with_suffix(".npz.tmp")
        with temporary.open("wb") as handle:
            np.savez_compressed(
                handle,
                site_id=np.array(patch.site_id),
                acquisition_date=np.array(patch.acquisition_date.isoformat()),
                product=np.array(patch.product),
                bands=patch.bands,
                cloud_fraction=np.array(patch.cloud_fraction),
                source_uri=np.array(patch.source_uri),
            )
        temporary.replace(target)
        patch.cache_path = str(target)
        return target

    @staticmethod
    def _read_cache(path: Path) -> HLSPatch:
        with np.load(path, allow_pickle=False) as payload:
            acquisition = (
                datetime.strptime(str(payload["acquisition_date"].item()), "%Y-%m-%d").date()
                if "acquisition_date" in payload
                else datetime.strptime(path.stem, "%Y-%m-%d").date()
            )
            site_id = str(payload["site_id"].item()) if "site_id" in payload else path.parent.name
            return HLSPatch(
                site_id=site_id,
                acquisition_date=acquisition,
                product=str(payload["product"].item()),
                bands=payload["bands"],
                cloud_fraction=float(payload["cloud_fraction"].item()),
                source_uri=str(payload["source_uri"].item()),
            )


def _date_from_hls_name(name: str) -> Optional[date]:
    match = re.search(r"\.(20\d{2})(\d{3})T", name)
    if not match:
        return None
    return datetime.strptime("".join(match.groups()), "%Y%j").date()
