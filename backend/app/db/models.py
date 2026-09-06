"""
PostgreSQL / PostGIS Data Models for SIH26162
Declares all 12 core tables: firms_detections, source_sites, candidate_sources,
site_daily_activity, site_model_a, site_model_b, site_model_c, site_daily_inference,
alerts, facility_evidence, imagery_cache, model_versions, and ingestion_runs.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Date,
    JSON,
    ForeignKey,
    Index,
    Text,
    PrimaryKeyConstraint
)
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class SourceSite(Base):
    """
    Physical thermal source sites derived from 750m DBSCAN clustering.
    """
    __tablename__ = "source_sites"

    site_id = Column(String(64), primary_key=True, index=True)
    cluster_id = Column(String(64), nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    promoted_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="ACTIVE", index=True)  # ACTIVE, PROMOTED, RETIRED
    land_cover = Column(JSON, nullable=True)  # WorldCover static fractions
    spatial_stats = Column(JSON, nullable=True)
    latest_seen = Column(Date, nullable=True, index=True)

    # Relationships
    detections = relationship("FirmsDetection", back_populates="source_site")
    daily_activities = relationship("SiteDailyActivity", back_populates="source_site")
    model_a = relationship("SiteModelA", back_populates="source_site", uselist=False)
    model_b = relationship("SiteModelB", back_populates="source_site", uselist=False)
    model_c = relationship("SiteModelC", back_populates="source_site", uselist=False)
    alerts = relationship("Alert", back_populates="source_site")

    __table_args__ = (
        Index("idx_source_sites_coords", "latitude", "longitude"),
    )


class FirmsDetection(Base):
    """
    Raw and normalized FIRMS active fire detection records.
    """
    __tablename__ = "firms_detections"

    detection_id = Column(String(64), primary_key=True, index=True)  # Deterministic SHA-256
    source_sensor = Column(String(64), nullable=False, default="VIIRS_NOAA20_NRT", index=True)
    satellite = Column(String(16), nullable=False)
    instrument = Column(String(32), default="VIIRS")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    acq_date = Column(Date, nullable=False, index=True)
    acq_time = Column(String(8), nullable=False)
    frp = Column(Float, nullable=False, default=0.0)
    bright_ti4 = Column(Float, nullable=True)
    bright_ti5 = Column(Float, nullable=True)
    scan = Column(Float, nullable=True)
    track = Column(Float, nullable=True)
    confidence = Column(String(32), nullable=True)
    daynight = Column(String(4), nullable=False, default="D")
    version = Column(String(32), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=True, index=True)
    source_site = relationship("SourceSite", back_populates="detections")

    __table_args__ = (
        Index("idx_firms_detections_coords", "latitude", "longitude"),
        Index("idx_firms_detections_site_date", "source_site_id", "acq_date"),
    )


class CandidateSource(Base):
    """
    Candidate spatial accumulator pool awaiting 3-sample threshold promotion.
    """
    __tablename__ = "candidate_sources"

    candidate_id = Column(String(64), primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    detection_count = Column(Integer, default=1)
    status = Column(String(32), default="ACCUMULATING")  # ACCUMULATING, PROMOTED, EXPIRED
    promoted_site_id = Column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_candidates_coords", "latitude", "longitude"),
    )


class SiteDailyActivity(Base):
    """
    Aggregated daily activity timeline per source site.
    Matches site_daily_activity.parquet exactly.
    """
    __tablename__ = "site_daily_activity"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False, index=True)
    acq_date = Column(Date, nullable=False, index=True)
    detections = Column(Integer, nullable=False, default=1)
    mean_frp = Column(Float, nullable=False, default=0.0)
    max_frp = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site = relationship("SourceSite", back_populates="daily_activities")

    __table_args__ = (
        PrimaryKeyConstraint("site_id", "acq_date"),
        Index("idx_daily_activity_lookup", "site_id", "acq_date"),
    )


class SiteModelA(Base):
    """
    Latest Model A identity classification per source site.
    """
    __tablename__ = "site_model_a"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), primary_key=True)
    core_probability = Column(Float, nullable=False)
    class_name = Column(String(32), nullable=False, index=True)  # INDUSTRIAL, NONINDUSTRIAL, UNKNOWN
    decision = Column(String(64), nullable=False)  # INDUSTRIAL_CORE_STRONG, etc.
    prithvi_probability = Column(Float, nullable=True)
    prithvi_status = Column(String(32), default="NOT_TRIGGERED")
    model_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site = relationship("SourceSite", back_populates="model_a")


class SiteModelB(Base):
    """
    Latest Model B temporal state per source site.
    """
    __tablename__ = "site_model_b"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), primary_key=True)
    state = Column(String(32), nullable=False, index=True)  # REACTIVATED, NEW, PERSISTENT, DORMANT, INTERMITTENT
    confidence = Column(String(16), nullable=False)  # HIGH, MEDIUM, LOW
    reason = Column(Text, nullable=True)
    days_since_last = Column(Integer, nullable=True)
    active_days_windows = Column(JSON, nullable=True)
    model_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site = relationship("SourceSite", back_populates="model_b")


class SiteModelC(Base):
    """
    Materialized latest Model C anomaly status per source site.
    """
    __tablename__ = "site_model_c"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), primary_key=True)
    event_date = Column(Date, nullable=True)
    operational_status = Column(String(32), nullable=False, index=True)  # NORMAL, ELEVATED, ANOMALOUS, CRITICAL, etc.
    c_score = Column(Float, nullable=True)
    c_raw = Column(Float, nullable=True)
    group_scores = Column(JSON, nullable=True)
    evidence_99 = Column(Integer, default=0)
    drivers = Column(JSON, nullable=True)
    history_counts = Column(JSON, nullable=True)
    model_version = Column(String(32), nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site = relationship("SourceSite", back_populates="model_c")


class SiteDailyInference(Base):
    """
    Historical Model C (and replayed B) outputs per site-day.
    Matches MODEL_C_EVENT_REPLAY_V3.parquet for timeline and replay APIs.
    """
    __tablename__ = "site_daily_inference"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False)
    acq_date = Column(Date, nullable=False)
    model_c_status = Column(String(32), nullable=False, index=True)
    c_score = Column(Float, nullable=True)
    c_raw = Column(Float, nullable=True)
    group_scores = Column(JSON, nullable=True)
    evidence_99 = Column(Integer, default=0)
    drivers = Column(JSON, nullable=True)
    model_c_version = Column(String(32), nullable=False)
    model_b_state = Column(String(32), nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        PrimaryKeyConstraint("site_id", "acq_date"),
        Index("idx_daily_inference_site_date", "site_id", "acq_date"),
    )


class Alert(Base):
    """
    Operational alerts synthesized by the Unified Decision Engine.
    """
    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False, index=True)
    site_day = Column(Date, nullable=False, index=True)
    alert_type = Column(String(64), nullable=False, index=True)
    alert_level = Column(String(16), nullable=False, index=True)  # CRITICAL, HIGH, MEDIUM, LOW, INFO, NONE
    headline = Column(String(255), nullable=False)
    reason_codes = Column(JSON, nullable=True)
    evidence_required = Column(Boolean, default=False)
    fingerprint = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="ACTIVE", index=True)  # ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED
    is_escalation = Column(Boolean, default=False)
    previous_alert_type = Column(String(64), nullable=True)
    previous_alert_level = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    acknowledged_by = Column(String(64), nullable=True)

    source_site = relationship("SourceSite", back_populates="alerts")

    __table_args__ = (
        Index("idx_alerts_severity_updated", "alert_level", "updated_at"),
    )


class FacilityEvidence(Base):
    """
    External GIS evidence layers: GEM power plants, World Bank flaring, FSI fires, ICAR crop burns.
    """
    __tablename__ = "facility_evidence"

    evidence_id = Column(String(64), primary_key=True, index=True)
    source_name = Column(String(64), nullable=False, index=True)  # GEM_GIPT, WORLDBANK_GFMR, FSI_FIRE, ICAR_CROP
    facility_name = Column(String(255), nullable=True)
    facility_type = Column(String(64), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    coordinate_quality = Column(String(32), nullable=True)
    source_url = Column(String(512), nullable=True)
    attributes = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_facility_evidence_coords", "latitude", "longitude"),
        Index("idx_facility_evidence_type", "source_name", "facility_type"),
    )


class ImageryCache(Base):
    """
    Cached HLS satellite scene metadata and Prithvi embeddings.
    """
    __tablename__ = "imagery_cache"

    cache_id = Column(String(64), primary_key=True, index=True)
    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False, index=True)
    acquisition_date = Column(Date, nullable=False, index=True)
    hls_product = Column(String(32), default="HLSS30")
    cloud_fraction = Column(Float, nullable=True)
    patch_uri = Column(String(512), nullable=True)
    embedding_uri = Column(String(512), nullable=True)
    prithvi_probability = Column(Float, nullable=True)
    status = Column(String(32), default="PENDING")  # PENDING, CACHED, FAILED, REJECTED_CLOUD
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ModelVersion(Base):
    """
    Track active frozen stack versions and artifact SHA256 hashes.
    """
    __tablename__ = "model_versions"

    component = Column(String(32), primary_key=True)  # A_CORE, MODEL_B, MODEL_C, DECISION_ENGINE
    version = Column(String(64), primary_key=True)
    artifact_sha256 = Column(String(64), nullable=True)
    config = Column(JSON, nullable=True)
    activated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class IngestionRun(Base):
    """
    Telemetry and audit log of data ingestion cycles.
    """
    __tablename__ = "ingestion_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    source = Column(String(64), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    records_read = Column(Integer, default=0)
    inserted = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    status = Column(String(32), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    error_summary = Column(Text, nullable=True)
