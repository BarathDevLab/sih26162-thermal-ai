"""Fail-closed runtime artifact, schema, and snapshot readiness checks."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.app.db.models import ModelVersion, StackSnapshot
from backend.app.engines.model_a import ModelAEngine
from backend.app.engines.model_c import ModelCEngine
from backend.app.services.artifact_hashing import checksum_matches, sha256_variants
from backend.app.services.feature_validation import feature_validation_issue
from backend.app.services.feature_builder import FEATURE_VERSION
from backend.app.services.prithvi_service import prithvi_readiness_issue


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_FILES = (
    "backend/models/MODEL_A_FINAL.joblib",
    "backend/models/MODEL_C_V3_FROZEN.joblib",
    "backend/config/model_a_features.json",
    "backend/config/frozen_thresholds.json",
    "backend/config/model_b.json",
    "backend/config/model_c.json",
    "backend/config/decision_engine.json",
    "backend/config/source/model_a_final_config.json",
    "backend/config/active_stack_manifest.json",
    "data/bootstrap/source_sites_ground_truth_FINAL.csv",
    "data/bootstrap/MODEL_B_SOURCE_STATES_FINAL.csv",
    "data/bootstrap/firms_detections_2025_assigned.parquet",
    "data/bootstrap/source_site_features_2025.parquet",
    "data/bootstrap/site_daily_activity.parquet",
    "data/bootstrap/MODEL_C_EVENT_REPLAY_V3.parquet",
)
REQUIRED_TABLES = {
    "firms_detections",
    "source_sites",
    "candidate_sources",
    "candidate_source_detections",
    "site_daily_activity",
    "site_model_a",
    "site_model_a_history",
    "site_model_a_features",
    "site_model_b",
    "site_model_b_history",
    "site_model_c",
    "site_daily_inference",
    "stack_snapshots",
    "firms_backfill_windows",
    "alerts",
    "facility_evidence",
    "event_evidence",
    "site_reference_labels",
    "imagery_cache",
    "model_versions",
    "ingestion_runs",
}
REQUIRED_COLUMNS = {
    "source_sites": {"feature_version", "latest_seen"},
    "firms_detections": {
        "resolution_status", "is_ambiguous", "candidate_site_ids", "assignment_distance_m",
    },
    "site_model_a": {
        "feature_version", "feature_as_of_detection_date", "imagery_acquisition_date",
    },
    "site_daily_inference": {"raw_signals", "model_b_state"},
    "imagery_cache": {"source_uri", "model_revision", "failure_reason"},
}


@dataclass
class StackReadinessReport:
    status: str
    can_start_live: bool
    missing_files: List[str] = field(default_factory=list)
    checksum_mismatches: List[str] = field(default_factory=list)
    missing_tables: List[str] = field(default_factory=list)
    missing_columns: List[str] = field(default_factory=list)
    data_through_date: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


_shared_model_a: Optional[ModelAEngine] = None
_shared_model_c: Optional[ModelCEngine] = None
_hash_cache: Dict[str, tuple] = {}
_last_report = StackReadinessReport(
    status="DATABASE_NOT_READY", can_start_live=False, detail="Preflight has not run."
)


def get_shared_model_a() -> ModelAEngine:
    global _shared_model_a
    if _shared_model_a is None:
        _shared_model_a = ModelAEngine(str(PROJECT_ROOT / "backend/models/MODEL_A_FINAL.joblib"))
    return _shared_model_a


def get_shared_model_c() -> ModelCEngine:
    global _shared_model_c
    if _shared_model_c is None:
        _shared_model_c = ModelCEngine(str(PROJECT_ROOT / "backend/models/MODEL_C_V3_FROZEN.joblib"))
    return _shared_model_c


def get_last_readiness_report() -> StackReadinessReport:
    return _last_report


def run_stack_preflight(db: Session) -> StackReadinessReport:
    global _last_report
    missing_files = [path for path in REQUIRED_FILES if not (PROJECT_ROOT / path).is_file()]
    checksum_mismatches = _verify_declared_checksums()

    try:
        table_names = set(inspect(db.get_bind()).get_table_names())
        missing_tables = sorted(REQUIRED_TABLES - table_names)
        inspector = inspect(db.get_bind())
        missing_columns = []
        for table_name, expected in REQUIRED_COLUMNS.items():
            if table_name not in table_names:
                continue
            if db.get_bind().dialect.name == "postgresql":
                actual = {
                    row[0]
                    for row in db.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() AND table_name = :table_name"
                        ),
                        {"table_name": table_name},
                    ).all()
                }
            else:
                actual = {column["name"] for column in inspector.get_columns(table_name)}
            missing_columns.extend(
                f"{table_name}.{column}" for column in sorted(expected - actual)
            )
    except Exception as exc:
        _last_report = StackReadinessReport(
            status="DATABASE_NOT_READY",
            can_start_live=False,
            missing_files=missing_files,
            checksum_mismatches=checksum_mismatches,
            missing_columns=[],
            detail=f"Database inspection failed: {exc}",
        )
        return _last_report

    if checksum_mismatches:
        _last_report = StackReadinessReport(
            status="MODEL_ARTIFACT_MISMATCH",
            can_start_live=False,
            missing_files=missing_files,
            checksum_mismatches=checksum_mismatches,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            detail="One or more declared runtime artifacts failed SHA-256 verification.",
        )
        return _last_report

    try:
        get_shared_model_a()
        get_shared_model_c()
    except Exception as exc:
        _last_report = StackReadinessReport(
            status="MODEL_ARTIFACT_MISMATCH",
            can_start_live=False,
            missing_files=missing_files,
            missing_tables=missing_tables,
            detail=f"Model artifact validation failed: {exc}",
        )
        return _last_report

    if missing_tables or missing_columns:
        _last_report = StackReadinessReport(
            status="DATABASE_NOT_READY",
            can_start_live=False,
            missing_files=missing_files,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            detail="Apply backend/migrations/001_runtime_overhaul.sql before starting live mode.",
        )
        return _last_report

    if missing_files:
        _last_report = StackReadinessReport(
            status="STALE_BACKFILL",
            can_start_live=False,
            missing_files=missing_files,
            detail="Authoritative bootstrap inputs are missing; inference must not be fabricated.",
        )
        return _last_report

    manifest_issue = _active_manifest_issue()
    if manifest_issue:
        _last_report = StackReadinessReport(
            status="MODEL_ARTIFACT_MISMATCH",
            can_start_live=False,
            detail=manifest_issue,
        )
        return _last_report

    validation_issue = feature_validation_issue()
    if validation_issue:
        _last_report = StackReadinessReport(
            status="MODEL_ARTIFACT_MISMATCH",
            can_start_live=False,
            detail=validation_issue,
        )
        return _last_report

    snapshot = (
        db.query(StackSnapshot)
        .filter(StackSnapshot.status == "CURRENT")
        .order_by(StackSnapshot.data_through_date.desc())
        .first()
    )
    if snapshot is None or snapshot.data_through_date < date.today() - timedelta(days=1):
        _last_report = StackReadinessReport(
            status="STALE_BACKFILL",
            can_start_live=False,
            data_through_date=str(snapshot.data_through_date) if snapshot else None,
            detail="No current common A/B/C stack snapshot exists through the operational date.",
        )
        return _last_report

    artifact_paths = {
        "A_CORE": PROJECT_ROOT / "backend/models/MODEL_A_FINAL.joblib",
        "MODEL_B": PROJECT_ROOT / "backend/config/model_b.json",
        "MODEL_C": PROJECT_ROOT / "backend/models/MODEL_C_V3_FROZEN.joblib",
        "DECISION_ENGINE": PROJECT_ROOT / "backend/config/decision_engine.json",
    }
    expected_hashes = {component: _sha256(path) for component, path in artifact_paths.items()}
    active_versions = {
        row.component: row
        for row in db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all()
    }
    bad_versions = [
        component
        for component, expected in expected_hashes.items()
        if component not in active_versions
        or active_versions[component].artifact_sha256 not in sha256_variants(artifact_paths[component])
        or active_versions[component].version != snapshot.model_stack_version
    ]
    snapshot_mismatch = (
        snapshot.a_core_artifact_sha256 != expected_hashes["A_CORE"]
        or snapshot.c_artifact_sha256 != expected_hashes["MODEL_C"]
        or snapshot.feature_version != FEATURE_VERSION
        or snapshot.resolver_version != "incremental-member-radius-750m-min3-v1"
    )
    if bad_versions or snapshot_mismatch:
        _last_report = StackReadinessReport(
            status="MODEL_ARTIFACT_MISMATCH",
            can_start_live=False,
            data_through_date=str(snapshot.data_through_date),
            detail=(
                "Active model-version or snapshot provenance disagrees with local artifacts: "
                + ", ".join(bad_versions or ["stack_snapshot"])
            ),
        )
        return _last_report

    if not os.environ.get("FIRMS_MAP_KEY", "").strip():
        _last_report = StackReadinessReport(
            status="FIRMS_CREDENTIALS_MISSING",
            can_start_live=False,
            data_through_date=str(snapshot.data_through_date),
            detail="FIRMS_MAP_KEY is required before live polling can start.",
        )
        return _last_report

    prithvi_enabled = os.environ.get("PRITHVI_ENABLED", "false").lower() == "true"
    prithvi_required = (
        "backend/models/prithvi/Prithvi_EO_V2_300M.pt",
        "backend/models/MODEL_A_PRITHVI_FINAL.joblib",
        "backend/config/source/prithvi_final_config.json",
    )
    prithvi_missing = [path for path in prithvi_required if not (PROJECT_ROOT / path).is_file()]
    prithvi_issue = prithvi_readiness_issue() if prithvi_enabled else None
    status = "DEGRADED_PRITHVI_UNAVAILABLE" if prithvi_issue else "READY"
    _last_report = StackReadinessReport(
        status=status,
        can_start_live=True,
        data_through_date=str(snapshot.data_through_date),
        missing_files=prithvi_missing,
        detail=(
            f"Core stack ready; Prithvi evidence is explicitly unavailable: {prithvi_issue}"
            if status != "READY"
            else "Core runtime artifacts, schema, and common snapshot passed preflight."
        ),
    )
    return _last_report


def _verify_declared_checksums() -> List[str]:
    checksum_file = PROJECT_ROOT / "SHA256SUMS.txt"
    if not checksum_file.is_file():
        return ["SHA256SUMS.txt"]
    optional_artifacts = _optional_manifest_artifacts()
    mismatches: List[str] = []
    for line in checksum_file.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        expected, relative_path = stripped.split(maxsplit=1)
        relative_path = relative_path.strip()
        path = PROJECT_ROOT / relative_path
        if not path.is_file():
            # Optional artifacts are checksummed when packaged, but their absence
            # must not block the core stack. Their service reports its own
            # explicit degraded/unavailable readiness state later in preflight.
            if relative_path not in optional_artifacts:
                mismatches.append(relative_path)
            continue
        if not checksum_matches(path, expected):
            mismatches.append(relative_path)
    return mismatches


def _optional_manifest_artifacts() -> set[str]:
    """Return artifacts explicitly marked optional by the active manifest.

    Fail closed when the manifest is missing or unreadable: no checksum entry is
    considered optional unless the packaged manifest explicitly declares it so.
    """
    manifest_path = PROJECT_ROOT / "backend/config/active_stack_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        item["repo_path"]
        for item in manifest.get("artifacts", [])
        if item.get("repo_path") and item.get("required") is False
    }


def _active_manifest_issue() -> Optional[str]:
    path = PROJECT_ROOT / "backend/config/active_stack_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"Active stack manifest is unreadable: {exc}"
    if manifest.get("status") != "READY_FOR_BOOTSTRAP":
        return "Active stack manifest is not marked READY_FOR_BOOTSTRAP."
    entries = {
        item.get("repo_path"): item.get("sha256")
        for item in manifest.get("artifacts", [])
        if item.get("repo_path")
    }
    for relative in REQUIRED_FILES:
        if relative == "backend/config/active_stack_manifest.json":
            continue
        artifact = PROJECT_ROOT / relative
        expected = entries.get(relative)
        if not expected or not checksum_matches(artifact, expected):
            return f"Active stack manifest hash is missing or stale for {relative}."
    return None


def _sha256(path: Path) -> str:
    stat = path.stat()
    key = str(path.resolve())
    cached = _hash_cache.get(key)
    signature = (stat.st_size, stat.st_mtime_ns)
    if cached and cached[:2] == signature:
        return cached[2]
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _hash_cache[key] = (stat.st_size, stat.st_mtime_ns, value)
    return value
