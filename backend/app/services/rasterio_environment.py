"""Process-local GDAL/PROJ isolation for Rasterio-backed services."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


class RasterioEnvironmentUnavailable(RuntimeError):
    """Raised when Rasterio's bundled geospatial data files are unavailable."""


def configure_rasterio_environment() -> None:
    """Use Rasterio's matching GDAL/PROJ databases in this Python process.

    PostgreSQL/PostGIS installers commonly put older PROJ data on ``PATH`` or
    in ``PROJ_LIB``.  Rasterio must use the data shipped with its own GDAL
    build; mixing the two produces DATABASE.LAYOUT.VERSION warnings and can
    make coordinate transforms fail.
    """

    spec = importlib.util.find_spec("rasterio")
    if spec is None or spec.origin is None:
        raise RasterioEnvironmentUnavailable("rasterio is not installed.")

    package_dir = Path(spec.origin).resolve().parent
    proj_data = package_dir / "proj_data"
    gdal_data = package_dir / "gdal_data"
    if not (proj_data / "proj.db").is_file() or not gdal_data.is_dir():
        raise RasterioEnvironmentUnavailable(
            f"Rasterio's bundled PROJ/GDAL data directories are incomplete under {package_dir}."
        )

    os.environ["PROJ_DATA"] = str(proj_data)
    os.environ["PROJ_LIB"] = str(proj_data)
    os.environ["GDAL_DATA"] = str(gdal_data)
    # HLS GeoTIFF keys can contain a slightly different UTM definition.  The
    # platform uses official EPSG coordinates for site-centred extraction.
    os.environ["GTIFF_SRS_SOURCE"] = "EPSG"
