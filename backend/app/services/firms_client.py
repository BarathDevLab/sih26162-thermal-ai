"""
NASA FIRMS Area API Client
Handles queries to the NASA FIRMS Area API for VIIRS NRT active fire data.
Enforces 1-5 day window limits, rate limit handling, and India bounding box defaults.
"""

import os
import io
import csv
import time
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Default bounding box for India: [west, south, east, north]
DEFAULT_INDIA_BBOX = "67,6,98,38"
DEFAULT_PRIMARY_SOURCE = "VIIRS_NOAA20_NRT"
DEFAULT_CORROBORATING_SOURCE = "VIIRS_NOAA21_NRT"

AREA_API_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
DATA_AVAILABILITY_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"


class FirmsClient:
    """
    Client for interacting with the official NASA FIRMS Area API.
    """

    def __init__(
        self,
        map_key: Optional[str] = None,
        default_bbox: str = DEFAULT_INDIA_BBOX,
        cache_dir: Optional[str] = None,
        offline_mode: bool = False
    ):
        self.map_key = map_key or os.environ.get("FIRMS_MAP_KEY", "")
        self.default_bbox = default_bbox
        self.cache_dir = cache_dir
        self.offline_mode = offline_mode
        
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

    def build_area_url(
        self,
        source: str = DEFAULT_PRIMARY_SOURCE,
        bbox: Optional[str] = None,
        day_range: int = 1,
        date: Optional[str] = None
    ) -> str:
        """
        Builds the FIRMS Area API URL.
        Pattern: https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAY_RANGE}[/{DATE}]
        """
        if not (1 <= day_range <= 5):
            raise ValueError(f"FIRMS Area API day_range must be between 1 and 5, got {day_range}")
        
        target_bbox = bbox or self.default_bbox
        key = self.map_key if self.map_key else "NO_MAP_KEY"
        
        url = f"{AREA_API_BASE_URL}/{key}/{source}/{target_bbox}/{day_range}"
        if date:
            url = f"{url}/{date}"
        return url

    def fetch_area_detections(
        self,
        source: str = DEFAULT_PRIMARY_SOURCE,
        bbox: Optional[str] = None,
        day_range: int = 1,
        date: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Fetches active fire detection records from FIRMS Area API as a list of raw dicts.
        """
        if self.offline_mode or not self.map_key:
            logger.info("FirmsClient running in offline mode or without FIRMS_MAP_KEY.")
            if self.cache_dir:
                cached = self._read_cache(source, bbox or self.default_bbox, day_range, date)
                if cached is not None:
                    return cached
            return []

        url = self.build_area_url(source=source, bbox=bbox, day_range=day_range, date=date)
        
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.get(url)
                
                # Check for rate limit
                if resp.status_code == 429:
                    wait_sec = attempt * 5.0
                    logger.warning(f"FIRMS 429 Rate Limit. Backing off for {wait_sec}s (attempt {attempt}/{max_retries})")
                    time.sleep(wait_sec)
                    continue
                
                # Server errors: retry with backoff
                if resp.status_code >= 500:
                    wait_sec = attempt * 3.0
                    logger.warning(f"FIRMS {resp.status_code} Server Error. Backing off {wait_sec}s (attempt {attempt}/{max_retries})")
                    time.sleep(wait_sec)
                    continue
                
                resp.raise_for_status()
                text = resp.text.strip()
                
                # NASA FIRMS returns plain text errors in HTTP 200 sometimes
                if "Bad Map Key" in text or "Invalid MAP_KEY" in text:
                    raise PermissionError("NASA FIRMS Area API rejected MAP_KEY: Bad Map Key")
                if "Transaction limit exceeded" in text:
                    raise RuntimeError("NASA FIRMS Area API transaction limit exceeded")

                detections = self.parse_csv_content(text)
                
                # Save to cache if cache directory configured
                if self.cache_dir:
                    self._write_cache(source, bbox or self.default_bbox, day_range, date, text)
                
                return detections

            except httpx.RequestError as e:
                logger.error(f"Network error on attempt {attempt}/{max_retries} connecting to FIRMS: {e}")
                if attempt == max_retries:
                    raise
                time.sleep(attempt * 2.0)

        raise RuntimeError(f"Failed to fetch FIRMS data after {max_retries} attempts.")

    def parse_csv_content(self, csv_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw FIRMS CSV response into a list of row dicts.
        """
        if not csv_text:
            return []
        
        f = io.StringIO(csv_text)
        reader = csv.DictReader(f)
        return list(reader)

    def check_availability(
        self,
        source: str = DEFAULT_PRIMARY_SOURCE,
        timeout: float = 15.0
    ) -> List[Dict[str, Any]]:
        """
        Queries the FIRMS data availability endpoint for valid date ranges.
        """
        if not self.map_key:
            return []
        
        url = f"{DATA_AVAILABILITY_BASE_URL}/{self.map_key}/{source}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return self.parse_csv_content(resp.text)

    def _cache_filename(self, source: str, bbox: str, day_range: int, date: Optional[str]) -> str:
        clean_bbox = bbox.replace(",", "_")
        date_str = date or "latest"
        return f"firms_{source}_{clean_bbox}_{day_range}d_{date_str}.csv"

    def _read_cache(self, source: str, bbox: str, day_range: int, date: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        if not self.cache_dir:
            return None
        filepath = os.path.join(self.cache_dir, self._cache_filename(source, bbox, day_range, date))
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return self.parse_csv_content(f.read())
        return None

    def _write_cache(self, source: str, bbox: str, day_range: int, date: Optional[str], text: str) -> None:
        if not self.cache_dir:
            return
        filepath = os.path.join(self.cache_dir, self._cache_filename(source, bbox, day_range, date))
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
