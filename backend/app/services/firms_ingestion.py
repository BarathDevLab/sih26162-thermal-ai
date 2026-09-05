"""
FIRMS Ingestion and Normalization Pipeline
Standardizes raw NASA FIRMS detections, generates deterministic SHA-256 keys,
performs deduplication, resolves spatial locations via SourceResolver, and aggregates daily activity.
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from backend.app.engines.source_resolver import SourceResolver

logger = logging.getLogger(__name__)


class FirmsIngestionService:
    """
    Ingestion pipeline for FIRMS active fire detections.
    """

    def __init__(self, source_resolver: Optional[SourceResolver] = None):
        self.resolver = source_resolver

    @staticmethod
    def generate_detection_id(
        source_sensor: str,
        satellite: str,
        latitude: float,
        longitude: float,
        acq_date: str,
        acq_time: str
    ) -> str:
        """
        Generates deterministic SHA-256 hash for a FIRMS detection.
        Key elements: source_sensor + satellite + round(lat, 4) + round(lon, 4) + acq_date + acq_time.
        """
        clean_lat = f"{round(float(latitude), 4):.4f}"
        clean_lon = f"{round(float(longitude), 4):.4f}"
        clean_time = str(acq_time).strip().zfill(4)
        clean_date = str(acq_date).strip()
        clean_sat = str(satellite).strip()
        clean_sensor = str(source_sensor).strip()

        key = f"{clean_sensor}_{clean_sat}_{clean_lat}_{clean_lon}_{clean_date}_{clean_time}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def normalize_record(
        self,
        raw_row: Dict[str, Any],
        source_sensor: str = "VIIRS_NOAA20_NRT"
    ) -> Dict[str, Any]:
        """
        Normalizes a single FIRMS detection row into typed, standardized schema.
        """
        lat = float(raw_row.get("latitude", 0.0))
        lon = float(raw_row.get("longitude", 0.0))
        acq_date = str(raw_row.get("acq_date", "")).strip()
        acq_time = str(raw_row.get("acq_time", "0000")).strip().zfill(4)
        satellite = str(raw_row.get("satellite", "20")).strip()
        instrument = str(raw_row.get("instrument", "VIIRS")).strip()
        confidence = str(raw_row.get("confidence", "nominal")).strip().lower()
        version = str(raw_row.get("version", "2.0NRT")).strip()
        daynight = str(raw_row.get("daynight", "D")).strip().upper()

        # Numeric fields with safe float conversion
        def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
            if val is None or val == "":
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        bright_ti4 = safe_float(raw_row.get("bright_ti4"))
        bright_ti5 = safe_float(raw_row.get("bright_ti5"))
        frp = safe_float(raw_row.get("frp"), default=0.0) or 0.0
        scan = safe_float(raw_row.get("scan"))
        track = safe_float(raw_row.get("track"))

        detection_id = self.generate_detection_id(
            source_sensor=source_sensor,
            satellite=satellite,
            latitude=lat,
            longitude=lon,
            acq_date=acq_date,
            acq_time=acq_time
        )

        return {
            "detection_id": detection_id,
            "source_sensor": source_sensor,
            "satellite": satellite,
            "instrument": instrument,
            "latitude": lat,
            "longitude": lon,
            "bright_ti4": bright_ti4,
            "bright_ti5": bright_ti5,
            "frp": frp,
            "scan": scan,
            "track": track,
            "acq_date": acq_date,
            "acq_time": acq_time,
            "confidence": confidence,
            "version": version,
            "daynight": daynight,
            "raw_payload": raw_row
        }

    def ingest_batch(
        self,
        raw_records: List[Dict[str, Any]],
        source_resolver: Optional[SourceResolver] = None,
        source_sensor: str = "VIIRS_NOAA20_NRT",
        existing_ids: Optional[set] = None
    ) -> Dict[str, Any]:
        """
        Processes a batch of raw FIRMS records:
        1. Normalizes all records
        2. Deduplicates against existing_ids and within-batch
        3. Spatially resolves detections against frozen/candidate sites
        """
        resolver = source_resolver or self.resolver
        if resolver is None:
            raise ValueError("A SourceResolver must be provided for spatial ingestion.")

        seen_ids = set(existing_ids) if existing_ids else set()
        normalized_detections: List[Dict[str, Any]] = []
        duplicate_count = 0

        for row in raw_records:
            norm = self.normalize_record(row, source_sensor=source_sensor)
            det_id = norm["detection_id"]
            if det_id in seen_ids:
                duplicate_count += 1
                continue
            seen_ids.add(det_id)
            normalized_detections.append(norm)

        # Spatially resolve each detection
        resolved_detections: List[Dict[str, Any]] = []
        matched_count = 0
        candidate_count = 0
        promoted_count = 0
        promoted_sites: List[Dict[str, Any]] = []

        for det in normalized_detections:
            res = resolver.resolve_detection(
                latitude=det["latitude"],
                longitude=det["longitude"],
                detection_id=det["detection_id"],
                detection_payload=det
            )

            det["resolution_status"] = res["status"]
            det["distance_m"] = res.get("distance_m")
            det["is_ambiguous"] = res.get("is_ambiguous", False)
            det["candidate_site_ids"] = res.get("candidate_site_ids", [])
            
            if res["status"] == "MATCHED":
                det["site_id"] = res["site_id"]
                matched_count += 1
            elif res["status"] == "PROMOTED":
                det["site_id"] = res["site_id"]
                promoted_count += 1
                promoted_sites.append(res)
            elif res["status"] in ("NEW_CANDIDATE", "CANDIDATE_ACCUMULATED"):
                det["site_id"] = None
                det["candidate_id"] = res.get("candidate_id")
                candidate_count += 1
            else:
                det["site_id"] = None

            resolved_detections.append(det)

        return {
            "processed_count": len(raw_records),
            "unique_count": len(normalized_detections),
            "duplicate_count": duplicate_count,
            "matched_count": matched_count,
            "candidate_count": candidate_count,
            "promoted_count": promoted_count,
            "promoted_sites": promoted_sites,
            "resolved_detections": resolved_detections
        }

    @staticmethod
    def aggregate_daily_activity(
        resolved_detections: List[Dict[str, Any]],
        existing_daily_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Aggregates resolved detections by (site_id, acq_date).
        Returns a DataFrame matching the schema of site_daily_activity.parquet:
        [site_id (str), acq_date (datetime64[ns]), detections (int64), mean_frp (float64), max_frp (float64)]
        """
        # Filter for detections associated with an active site
        valid_dets = [
            d for d in resolved_detections
            if d.get("site_id") is not None
        ]

        if not valid_dets and (existing_daily_df is None or len(existing_daily_df) == 0):
            return pd.DataFrame(columns=["site_id", "acq_date", "detections", "mean_frp", "max_frp"])

        if valid_dets:
            records = []
            for d in valid_dets:
                records.append({
                    "site_id": d["site_id"],
                    "acq_date": pd.to_datetime(d["acq_date"]),
                    "frp": float(d["frp"])
                })

            df_new = pd.DataFrame(records)
            aggregated = df_new.groupby(["site_id", "acq_date"]).agg(
                detections=("frp", "count"),
                mean_frp=("frp", "mean"),
                max_frp=("frp", "max")
            ).reset_index()

            aggregated["detections"] = aggregated["detections"].astype("int64")
            aggregated["mean_frp"] = aggregated["mean_frp"].round(2).astype("float64")
            aggregated["max_frp"] = aggregated["max_frp"].round(2).astype("float64")
        else:
            aggregated = pd.DataFrame(columns=["site_id", "acq_date", "detections", "mean_frp", "max_frp"])

        if existing_daily_df is None or len(existing_daily_df) == 0:
            return aggregated.sort_values(by=["site_id", "acq_date"]).reset_index(drop=True)

        # Merge with existing daily activity
        base_df = existing_daily_df.copy()
        base_df["acq_date"] = pd.to_datetime(base_df["acq_date"])

        merged = pd.merge(
            base_df,
            aggregated,
            on=["site_id", "acq_date"],
            how="outer",
            suffixes=("_old", "_new")
        )

        def combine_rows(row):
            d_old = row["detections_old"] if pd.notna(row["detections_old"]) else 0
            d_new = row["detections_new"] if pd.notna(row["detections_new"]) else 0
            total_d = int(d_old + d_new)

            max_old = row["max_frp_old"] if pd.notna(row["max_frp_old"]) else 0.0
            max_new = row["max_frp_new"] if pd.notna(row["max_frp_new"]) else 0.0
            max_val = round(max(max_old, max_new), 2)

            if total_d == 0:
                mean_val = 0.0
            elif d_old > 0 and d_new > 0:
                mean_val = round((row["mean_frp_old"] * d_old + row["mean_frp_new"] * d_new) / total_d, 2)
            elif d_new > 0:
                mean_val = round(row["mean_frp_new"], 2)
            else:
                mean_val = round(row["mean_frp_old"], 2)

            return pd.Series({
                "detections": total_d,
                "mean_frp": mean_val,
                "max_frp": max_val
            })

        combined_metrics = merged.apply(combine_rows, axis=1)
        merged["detections"] = combined_metrics["detections"].astype("int64")
        merged["mean_frp"] = combined_metrics["mean_frp"].astype("float64")
        merged["max_frp"] = combined_metrics["max_frp"].astype("float64")

        final_df = merged[["site_id", "acq_date", "detections", "mean_frp", "max_frp"]]
        return final_df.sort_values(by=["site_id", "acq_date"]).reset_index(drop=True)
