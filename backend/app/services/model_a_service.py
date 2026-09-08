"""Current, source-centric Model A inference and persistence."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.db.models import (
    FirmsDetection,
    SiteModelA,
    SiteModelAFeatures,
    SiteModelAHistory,
    SourceSite,
)
from backend.app.engines.model_a import ModelAEngine
from backend.app.services.feature_builder import FEATURE_VERSION, ORDERED_FEATURES, FeatureBuilder
from backend.app.services.worldcover_service import WorldCoverService, WorldCoverUnavailable


MODEL_STACK_VERSION = os.environ.get("MODEL_STACK_VERSION", "2026-09-04-r1")
PRIMARY_SENSOR = os.environ.get("FIRMS_PRIMARY_SOURCE", "VIIRS_NOAA20_NRT")
LAND_COVER_FEATURES = ORDERED_FEATURES[-9:]
NOAA20_SENSOR_ALIASES = frozenset({
    "NOAA20_VIIRS",
    "VIIRS_NOAA20_ARCHIVE",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA20_NRT",
})


class ModelAInputUnavailable(RuntimeError):
    """Raised when authoritative source history/static context is unavailable."""


class ModelAService:
    def __init__(
        self,
        engine: Optional[ModelAEngine] = None,
        feature_builder: Optional[FeatureBuilder] = None,
        worldcover_service: Optional[WorldCoverService] = None,
    ) -> None:
        self.engine = engine or ModelAEngine()
        self.feature_builder = feature_builder or FeatureBuilder()
        self.worldcover = worldcover_service or WorldCoverService()
        if self.feature_builder.feature_names != self.engine.feature_names:
            raise ValueError("FeatureBuilder and Model A artifact feature order disagree.")

    def score_site(
        self,
        db: Session,
        site_id: str,
        cutoff: Optional[date] = None,
        prithvi_probability: Optional[float] = None,
        imagery_acquisition_date: Optional[date] = None,
        source_sensor: str = PRIMARY_SENSOR,
    ) -> Dict[str, Any]:
        site = db.query(SourceSite).filter(SourceSite.site_id == site_id).one_or_none()
        if site is None:
            raise ModelAInputUnavailable(f"Source site '{site_id}' does not exist.")

        land_cover = site.land_cover or {}
        # A present JSON null is authoritative WorldCover NoData (commonly ocean),
        # while an absent key means extraction has not been attempted yet.
        missing_lc = [name for name in LAND_COVER_FEATURES if name not in land_cover]
        if missing_lc:
            try:
                extracted = self.worldcover.get_fractions(site.latitude, site.longitude)
            except (WorldCoverUnavailable, ValueError) as exc:
                raise ModelAInputUnavailable(
                    f"Source site '{site_id}' is missing authoritative WorldCover features "
                    f"and automatic extraction failed: {exc}"
                ) from exc
            land_cover = {**land_cover, **extracted}
            site.land_cover = land_cover
            db.flush()

        accepted_sensors = self._accepted_sensor_sources(source_sensor)
        query = db.query(FirmsDetection).filter(
            FirmsDetection.source_site_id == site_id,
            FirmsDetection.source_sensor.in_(accepted_sensors),
        )
        if cutoff is not None:
            query = query.filter(FirmsDetection.acq_date <= cutoff)
        rows = query.order_by(FirmsDetection.acq_date, FirmsDetection.acq_time).all()
        if not rows:
            raise ModelAInputUnavailable(
                f"Source site '{site_id}' has no assigned {source_sensor} detections for Model A."
            )

        detections = [
            {
                "detection_id": row.detection_id,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "acq_date": row.acq_date,
                "acq_time": row.acq_time,
                "frp": row.frp,
                "daynight": row.daynight,
            }
            for row in rows
        ]
        feature_cutoff = max(row.acq_date for row in rows)
        features_df = self.feature_builder.build_features_from_detections(
            detections,
            centroid_lat=site.latitude,
            centroid_lon=site.longitude,
            land_cover=land_cover,
        )
        result = self.engine.predict(features_df, prithvi_probability=prithvi_probability)
        now = datetime.now(timezone.utc)
        prithvi_status = self._prithvi_status(result, prithvi_probability)

        feature_payload = {
            name: self._json_number(features_df.iloc[0][name]) for name in ORDERED_FEATURES
        }
        snapshot = db.query(SiteModelAFeatures).filter_by(site_id=site_id).one_or_none()
        if snapshot is None:
            snapshot = SiteModelAFeatures(site_id=site_id)
            db.add(snapshot)
        snapshot.feature_as_of_detection_date = feature_cutoff
        snapshot.feature_version = FEATURE_VERSION
        snapshot.ordered_features = feature_payload
        snapshot.computed_at = now

        latest = db.query(SiteModelA).filter_by(site_id=site_id).one_or_none()
        if latest is None:
            latest = SiteModelA(site_id=site_id)
            db.add(latest)
        latest.core_probability = result["core_probability"]
        latest.class_name = result["class"]
        latest.decision = result["decision"]
        latest.prithvi_probability = result["prithvi_probability"]
        latest.prithvi_status = prithvi_status
        latest.model_version = MODEL_STACK_VERSION
        latest.feature_version = FEATURE_VERSION
        latest.feature_as_of_detection_date = feature_cutoff
        latest.imagery_acquisition_date = imagery_acquisition_date
        latest.computed_at = now

        identity = json.dumps(
            {
                "site_id": site_id,
                "features": feature_payload,
                "feature_as_of_detection_date": feature_cutoff.isoformat(),
                "model_version": MODEL_STACK_VERSION,
                "feature_version": FEATURE_VERSION,
                "prithvi_probability": prithvi_probability,
                "imagery_acquisition_date": (
                    imagery_acquisition_date.isoformat() if imagery_acquisition_date else None
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        inference_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if db.query(SiteModelAHistory).filter_by(inference_id=inference_id).one_or_none() is None:
            db.add(SiteModelAHistory(
                inference_id=inference_id,
                site_id=site_id,
                feature_as_of_detection_date=feature_cutoff,
                core_probability=result["core_probability"],
                class_name=result["class"],
                decision=result["decision"],
                prithvi_probability=result["prithvi_probability"],
                prithvi_status=prithvi_status,
                model_version=MODEL_STACK_VERSION,
                feature_version=FEATURE_VERSION,
                imagery_acquisition_date=imagery_acquisition_date,
                computed_at=now,
            ))
        db.flush()

        return {
            **result,
            "feature_as_of_detection_date": feature_cutoff,
            "feature_version": FEATURE_VERSION,
            "computed_at": now,
            "prithvi_status": prithvi_status,
            "should_queue_prithvi": (
                self.engine.thresh_low <= result["core_probability"] < self.engine.thresh_core
                and prithvi_probability is None
                and os.environ.get("PRITHVI_ENABLED", "false").lower() == "true"
            ),
        }

    @staticmethod
    def _prithvi_status(result: Dict[str, Any], probability: Optional[float]) -> str:
        if probability is None:
            in_uncertainty_band = (
                float(result["thresholds"]["low"])
                <= float(result["core_probability"])
                < float(result["thresholds"]["core"])
            )
            if in_uncertainty_band:
                enabled = os.environ.get("PRITHVI_ENABLED", "false").lower() == "true"
                return "PENDING" if enabled else "UNAVAILABLE"
            return "NOT_TRIGGERED"
        if result["decision"] == "INDUSTRIAL_PRITHVI_RESCUE":
            return "AVAILABLE"
        return "AVAILABLE"

    @staticmethod
    def _json_number(value: Any) -> Optional[float]:
        number = float(value)
        if number != number:  # NaN
            return None
        return number

    @staticmethod
    def _accepted_sensor_sources(source_sensor: str) -> tuple[str, ...]:
        """Join frozen archive and NRT labels without admitting NOAA-21 into A-Core."""
        if source_sensor in NOAA20_SENSOR_ALIASES:
            return tuple(sorted(NOAA20_SENSOR_ALIASES))
        return (source_sensor,)
