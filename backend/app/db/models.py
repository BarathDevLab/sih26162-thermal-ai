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
    PrimaryKeyConstraint,
    UniqueConstraint,
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
    feature_version = Column(String(64), nullable=True)

    # Relationships
    detections = relationship("FirmsDetection", back_populates="source_site")
    daily_activities = relationship("SiteDailyActivity", back_populates="source_site")
    model_a = relationship("SiteModelA", back_populates="source_site", uselist=False)
    model_b = relationship("SiteModelB", back_populates="source_site", uselist=False)
    model_c = relationship("SiteModelC", back_populates="source_site", uselist=False)
    alerts = relationship("Alert", back_populates="source_site")
    reviews = relationship("SiteReview", back_populates="source_site")

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
    resolution_status = Column(String(32), nullable=True, index=True)
    is_ambiguous = Column(Boolean, nullable=False, default=False)
    candidate_site_ids = Column(JSON, nullable=True)
    assignment_distance_m = Column(Float, nullable=True)

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


class CandidateSourceDetection(Base):
    """Persistent candidate membership used by the incremental resolver."""
    __tablename__ = "candidate_source_detections"

    candidate_id = Column(String(64), ForeignKey("candidate_sources.candidate_id"), nullable=False)
    detection_id = Column(String(64), ForeignKey("firms_detections.detection_id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    observed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("candidate_id", "detection_id"),
        Index("idx_candidate_members_coords", "latitude", "longitude"),
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
    feature_version = Column(String(64), nullable=True)
    feature_as_of_detection_date = Column(Date, nullable=True, index=True)
    imagery_acquisition_date = Column(Date, nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_site = relationship("SourceSite", back_populates="model_a")


class SiteModelAHistory(Base):
    """Append-only Model A inference history for audit and replay."""
    __tablename__ = "site_model_a_history"

    inference_id = Column(String(64), primary_key=True)
    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False, index=True)
    feature_as_of_detection_date = Column(Date, nullable=False, index=True)
    core_probability = Column(Float, nullable=False)
    class_name = Column(String(32), nullable=False, index=True)
    decision = Column(String(64), nullable=False)
    prithvi_probability = Column(Float, nullable=True)
    prithvi_status = Column(String(32), nullable=False, default="NOT_TRIGGERED")
    model_version = Column(String(64), nullable=False)
    feature_version = Column(String(64), nullable=False)
    imagery_acquisition_date = Column(Date, nullable=True)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_model_a_history_cutoff", "site_id", "feature_as_of_detection_date"),
    )


class SiteModelAFeatures(Base):
    """Latest exact ordered Model A feature vector and provenance."""
    __tablename__ = "site_model_a_features"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), primary_key=True)
    feature_as_of_detection_date = Column(Date, nullable=False, index=True)
    feature_version = Column(String(64), nullable=False)
    ordered_features = Column(JSON, nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


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


class SiteModelBHistory(Base):
    """Materialized Model B state by as-of date for deterministic replay."""
    __tablename__ = "site_model_b_history"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False)
    as_of_date = Column(Date, nullable=False)
    state = Column(String(32), nullable=False, index=True)
    confidence = Column(String(16), nullable=False)
    reason = Column(Text, nullable=True)
    days_since_last = Column(Integer, nullable=True)
    active_days_windows = Column(JSON, nullable=True)
    model_version = Column(String(64), nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("site_id", "as_of_date"),
        Index("idx_model_b_history_cutoff", "site_id", "as_of_date"),
    )


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
    raw_signals = Column(JSON, nullable=True)
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
        Index("idx_alerts_site_status_updated", "site_id", "status", "updated_at", "alert_id"),
    )


class SiteReview(Base):
    """Append-only analyst adjudication event for an unclassified source site."""
    __tablename__ = "site_reviews"

    review_id = Column(String(64), primary_key=True)
    site_id = Column(String(64), ForeignKey("source_sites.site_id"), nullable=False, index=True)
    alert_id = Column(String(64), ForeignKey("alerts.alert_id"), nullable=True, index=True)
    supersedes_review_id = Column(String(64), ForeignKey("site_reviews.review_id"), nullable=True)
    review_status = Column(String(32), nullable=False, index=True)
    determination = Column(String(32), nullable=True, index=True)
    confidence = Column(String(16), nullable=True)
    consensus_status = Column(String(32), nullable=False, default="NOT_APPLICABLE", index=True)
    reason_codes = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    evidence_refs = Column(JSON, nullable=True)
    reviewed_by = Column(String(128), nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    country = Column(String(64), nullable=False, default="INDIA", index=True)
    training_eligible = Column(Boolean, nullable=False, default=False, index=True)

    # Snapshot the machine output at review time. Human review never mutates it.
    model_a_class = Column(String(32), nullable=True)
    model_a_probability = Column(Float, nullable=True)
    model_a_decision = Column(String(64), nullable=True)
    model_stack_version = Column(String(64), nullable=False)
    feature_version = Column(String(64), nullable=True)
    feature_snapshot = Column(JSON, nullable=True)

    source_site = relationship("SourceSite", back_populates="reviews")
    alert = relationship("Alert")
    supersedes = relationship("SiteReview", remote_side=[review_id])

    __table_args__ = (
        Index("idx_site_reviews_site_time", "site_id", "reviewed_at", "review_id"),
        Index("idx_site_reviews_training", "training_eligible", "determination", "country"),
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


class EventEvidence(Base):
    """Time-bound external fire/crop-burn evidence, separate from facilities."""
    __tablename__ = "event_evidence"

    evidence_id = Column(String(64), primary_key=True, index=True)
    source_name = Column(String(64), nullable=False, index=True)
    evidence_type = Column(String(64), nullable=False, index=True)
    reference_id = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    event_start = Column(DateTime, nullable=True, index=True)
    event_end = Column(DateTime, nullable=True)
    observed_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, nullable=True)
    source_version = Column(String(64), nullable=True)
    coordinate_quality = Column(String(32), nullable=True)
    temporal_quality = Column(String(32), nullable=True)
    authority_level = Column(String(32), nullable=True)
    source_url = Column(String(512), nullable=True)
    attributes = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_event_evidence_coords", "latitude", "longitude"),
        Index("idx_event_evidence_time", "event_start", "event_end"),
    )


class SiteReferenceLabel(Base):
    """Research/reference truth kept strictly separate from runtime inference."""
    __tablename__ = "site_reference_labels"

    site_id = Column(String(64), ForeignKey("source_sites.site_id"), primary_key=True)
    reference_class = Column(String(32), nullable=False, index=True)
    label_tier = Column(String(32), nullable=True)
    industrial_source = Column(String(255), nullable=True)
    nonindustrial_source = Column(String(255), nullable=True)
    evidence_metadata = Column(JSON, nullable=True)
    frozen_reference_version = Column(String(64), nullable=False)


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
    source_uri = Column(String(1024), nullable=True)
    patch_uri = Column(String(512), nullable=True)
    embedding_uri = Column(String(512), nullable=True)
    prithvi_probability = Column(Float, nullable=True)
    model_revision = Column(String(128), nullable=True)
    failure_reason = Column(Text, nullable=True)
    status = Column(String(32), default="PENDING")
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


class StackSnapshot(Base):
    """Atomic runtime readiness record shared by current A/B/C materializations."""
    __tablename__ = "stack_snapshots"

    snapshot_id = Column(String(64), primary_key=True)
    model_stack_version = Column(String(64), nullable=False, index=True)
    data_through_date = Column(Date, nullable=False, index=True)
    primary_firms_source = Column(String(64), nullable=False)
    a_core_artifact_sha256 = Column(String(64), nullable=False)
    c_artifact_sha256 = Column(String(64), nullable=False)
    feature_version = Column(String(64), nullable=False)
    resolver_version = Column(String(64), nullable=False)
    backfill_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(32), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("model_stack_version", "data_through_date", name="uq_stack_snapshot_version_date"),
    )


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


class FirmsBackfillWindow(Base):
    """Auditable proof that a requested FIRMS window was fetched and processed."""
    __tablename__ = "firms_backfill_windows"

    source_sensor = Column(String(64), nullable=False)
    bbox = Column(String(64), nullable=False)
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    records_fetched = Column(Integer, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    fetch_mode = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("source_sensor", "bbox", "window_start", "window_end"),
        Index("idx_backfill_windows_completion", "status", "window_end"),
    )
