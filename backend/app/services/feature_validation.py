"""Golden validation of runtime FeatureBuilder against authoritative 2025 snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from backend.app.services.feature_builder import FeatureBuilder, ORDERED_FEATURES


ROOT = Path(__file__).resolve().parents[3]
ASSIGNED_PATH = ROOT / "data/bootstrap/firms_detections_2025_assigned.parquet"
FEATURE_PATH = ROOT / "data/bootstrap/source_site_features_2025.parquet"
SITE_PATH = ROOT / "data/bootstrap/source_sites_ground_truth_FINAL.csv"
CONFIG_PATH = ROOT / "backend/config/model_a_features.json"
MODEL_PATH = ROOT / "backend/models/MODEL_A_FINAL.joblib"
REPORT_PATH = ROOT / "data/bootstrap/feature_builder_validation.json"
VALIDATION_SAMPLE_SIZE = 100
_HASH_CACHE: Dict[str, tuple] = {}


def validate_feature_builder_snapshot(
    sample_size: int = VALIDATION_SAMPLE_SIZE,
    report_path: Path = REPORT_PATH,
) -> Dict[str, object]:
    """Rebuild a deterministic site sample and fail on any semantic mismatch."""
    for path in (ASSIGNED_PATH, FEATURE_PATH, SITE_PATH, CONFIG_PATH, MODEL_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Feature validation input is missing: {path.relative_to(ROOT)}")

    assigned = pd.read_parquet(ASSIGNED_PATH)
    snapshot = pd.read_parquet(FEATURE_PATH)
    sites = pd.read_csv(SITE_PATH, usecols=["site_id", "latitude", "longitude"])
    required_assigned = {
        "detection_id", "site_id", "latitude", "longitude", "acq_date", "acq_time",
        "frp", "daynight", "source_sensor", "satellite", "version",
    }
    missing_assigned = sorted(required_assigned - set(assigned.columns))
    missing_snapshot = sorted({"site_id", *ORDERED_FEATURES} - set(snapshot.columns))
    if missing_assigned or missing_snapshot:
        raise ValueError(
            f"Feature validation schema mismatch; assigned={missing_assigned}, snapshot={missing_snapshot}"
        )
    if "feature_as_of_detection_date" not in snapshot.columns:
        raise ValueError("Feature snapshot is missing feature_as_of_detection_date provenance.")

    common = set(assigned["site_id"].astype(str)) & set(snapshot["site_id"].astype(str))
    ranked = sorted(common, key=lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest())
    selected = ranked[: min(sample_size, len(ranked))]
    if not selected:
        raise ValueError("No common sites exist between assigned detections and feature snapshot.")

    assigned = assigned.assign(site_id=assigned["site_id"].astype(str))
    assigned = assigned[assigned["site_id"].isin(selected)].copy()
    assigned["_acq_date"] = pd.to_datetime(assigned["acq_date"]).dt.date
    snapshot = snapshot.assign(site_id=snapshot["site_id"].astype(str)).set_index("site_id")
    sites = sites.assign(site_id=sites["site_id"].astype(str)).set_index("site_id")
    builder = FeatureBuilder()
    failures = []
    max_absolute_error = 0.0

    for site_id in selected:
        if site_id not in sites.index:
            failures.append({"site_id": site_id, "reason": "missing frozen centroid"})
            continue
        expected_row = snapshot.loc[site_id]
        if isinstance(expected_row, pd.DataFrame):
            failures.append({"site_id": site_id, "reason": "duplicate feature snapshot rows"})
            continue
        cutoff = pd.to_datetime(expected_row["feature_as_of_detection_date"]).date()
        members = assigned[
            (assigned["site_id"] == site_id)
            & (assigned["_acq_date"] <= cutoff)
        ]
        if members.empty:
            failures.append({"site_id": site_id, "reason": "no detections through feature cutoff"})
            continue
        land_cover = {
            name: float(expected_row[name]) if pd.notna(expected_row[name]) else np.nan
            for name in ORDERED_FEATURES[-9:]
        }
        actual = builder.build_features_from_detections(
            members.to_dict("records"),
            centroid_lat=float(sites.loc[site_id, "latitude"]),
            centroid_lon=float(sites.loc[site_id, "longitude"]),
            land_cover=land_cover,
        ).iloc[0]
        expected = expected_row[ORDERED_FEATURES].astype(float).to_numpy()
        actual_values = actual[ORDERED_FEATURES].astype(float).to_numpy()
        differences = np.abs(actual_values - expected)
        finite = differences[np.isfinite(differences)]
        if finite.size:
            max_absolute_error = max(max_absolute_error, float(finite.max()))
        matches = np.isclose(actual_values, expected, rtol=1e-7, atol=1e-7, equal_nan=True)
        if not bool(matches.all()):
            bad = [ORDERED_FEATURES[index] for index, value in enumerate(matches) if not value]
            failures.append({"site_id": site_id, "features": bad})

    report = {
        "status": "PASS" if not failures else "FAIL",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(selected),
        "required_sample_size": VALIDATION_SAMPLE_SIZE,
        "feature_count": len(ORDERED_FEATURES),
        "max_absolute_error": max_absolute_error,
        "failures": failures[:25],
        "input_sha256": _input_hashes(),
    }
    if failures:
        raise ValueError(f"FeatureBuilder golden validation failed: {failures[:3]}")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def feature_validation_issue(report_path: Path = REPORT_PATH) -> Optional[str]:
    if not report_path.is_file():
        return "FeatureBuilder golden validation report is missing."
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"FeatureBuilder validation report is unreadable: {exc}"
    if report.get("status") != "PASS":
        return "FeatureBuilder validation report does not pass."
    if int(report.get("sample_size", 0)) < VALIDATION_SAMPLE_SIZE:
        return "FeatureBuilder validation sample is too small."
    try:
        current_hashes = _input_hashes()
    except FileNotFoundError as exc:
        return str(exc)
    if report.get("input_sha256") != current_hashes:
        return "FeatureBuilder validation report is stale for the current inputs."
    return None


def _input_hashes() -> Dict[str, str]:
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path)
        for path in (ASSIGNED_PATH, FEATURE_PATH, SITE_PATH, CONFIG_PATH, MODEL_PATH)
    }


def _sha256(path: Path) -> str:
    stat = path.stat()
    key = str(path.resolve())
    cached = _HASH_CACHE.get(key)
    signature = (stat.st_size, stat.st_mtime_ns)
    if cached and cached[:2] == signature:
        return cached[2]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _HASH_CACHE[key] = (stat.st_size, stat.st_mtime_ns, value)
    return value
