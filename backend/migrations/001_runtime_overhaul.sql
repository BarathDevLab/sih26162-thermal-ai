BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE imagery_cache
    ADD COLUMN IF NOT EXISTS source_uri VARCHAR(1024),
    ADD COLUMN IF NOT EXISTS model_revision VARCHAR(128),
    ADD COLUMN IF NOT EXISTS failure_reason TEXT;

ALTER TABLE source_sites
    ADD COLUMN IF NOT EXISTS feature_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS geometry geometry(Point, 4326);
UPDATE source_sites
SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
WHERE geometry IS NULL;
CREATE INDEX IF NOT EXISTS idx_source_sites_geometry_gist
    ON source_sites USING GIST (geometry);

CREATE OR REPLACE FUNCTION sync_source_site_geometry() RETURNS trigger AS $$
BEGIN
    NEW.geometry := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_sync_source_site_geometry ON source_sites;
CREATE TRIGGER trg_sync_source_site_geometry
    BEFORE INSERT OR UPDATE OF latitude, longitude ON source_sites
    FOR EACH ROW EXECUTE FUNCTION sync_source_site_geometry();

ALTER TABLE firms_detections
    ADD COLUMN IF NOT EXISTS resolution_status VARCHAR(32),
    ADD COLUMN IF NOT EXISTS is_ambiguous BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS candidate_site_ids JSONB,
    ADD COLUMN IF NOT EXISTS assignment_distance_m DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS geometry geometry(Point, 4326);
UPDATE firms_detections
SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
WHERE geometry IS NULL;
CREATE INDEX IF NOT EXISTS idx_firms_detections_geometry_gist
    ON firms_detections USING GIST (geometry);

CREATE OR REPLACE FUNCTION sync_firms_detection_geometry() RETURNS trigger AS $$
BEGIN
    NEW.geometry := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_sync_firms_detection_geometry ON firms_detections;
CREATE TRIGGER trg_sync_firms_detection_geometry
    BEFORE INSERT OR UPDATE OF latitude, longitude ON firms_detections
    FOR EACH ROW EXECUTE FUNCTION sync_firms_detection_geometry();

ALTER TABLE site_model_a
    ADD COLUMN IF NOT EXISTS feature_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS feature_as_of_detection_date DATE,
    ADD COLUMN IF NOT EXISTS imagery_acquisition_date DATE;

ALTER TABLE site_daily_inference
    ADD COLUMN IF NOT EXISTS raw_signals JSONB;

CREATE TABLE IF NOT EXISTS candidate_source_detections (
    candidate_id VARCHAR(64) NOT NULL REFERENCES candidate_sources(candidate_id) ON DELETE CASCADE,
    detection_id VARCHAR(64) NOT NULL REFERENCES firms_detections(detection_id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (candidate_id, detection_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_members_coords
    ON candidate_source_detections (latitude, longitude);

CREATE TABLE IF NOT EXISTS site_model_a_history (
    inference_id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL REFERENCES source_sites(site_id),
    feature_as_of_detection_date DATE NOT NULL,
    core_probability DOUBLE PRECISION NOT NULL,
    class_name VARCHAR(32) NOT NULL,
    decision VARCHAR(64) NOT NULL,
    prithvi_probability DOUBLE PRECISION,
    prithvi_status VARCHAR(32) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    feature_version VARCHAR(64) NOT NULL,
    imagery_acquisition_date DATE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_a_history_cutoff
    ON site_model_a_history (site_id, feature_as_of_detection_date DESC);

CREATE TABLE IF NOT EXISTS site_model_a_features (
    site_id VARCHAR(64) PRIMARY KEY REFERENCES source_sites(site_id),
    feature_as_of_detection_date DATE NOT NULL,
    feature_version VARCHAR(64) NOT NULL,
    ordered_features JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS site_model_b_history (
    site_id VARCHAR(64) NOT NULL REFERENCES source_sites(site_id),
    as_of_date DATE NOT NULL,
    state VARCHAR(32) NOT NULL,
    confidence VARCHAR(16) NOT NULL,
    reason TEXT,
    days_since_last INTEGER,
    active_days_windows JSONB,
    model_version VARCHAR(64) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (site_id, as_of_date)
);

CREATE TABLE IF NOT EXISTS site_reference_labels (
    site_id VARCHAR(64) PRIMARY KEY REFERENCES source_sites(site_id),
    reference_class VARCHAR(32) NOT NULL,
    label_tier VARCHAR(32),
    industrial_source VARCHAR(255),
    nonindustrial_source VARCHAR(255),
    evidence_metadata JSONB,
    frozen_reference_version VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS event_evidence (
    evidence_id VARCHAR(64) PRIMARY KEY,
    source_name VARCHAR(64) NOT NULL,
    evidence_type VARCHAR(64) NOT NULL,
    reference_id VARCHAR(128),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geometry geometry(Point, 4326),
    event_start TIMESTAMPTZ,
    event_end TIMESTAMPTZ,
    observed_at TIMESTAMPTZ,
    retrieved_at TIMESTAMPTZ,
    source_version VARCHAR(64),
    coordinate_quality VARCHAR(32),
    temporal_quality VARCHAR(32),
    authority_level VARCHAR(32),
    source_url VARCHAR(512),
    attributes JSONB
);
CREATE INDEX IF NOT EXISTS idx_event_evidence_geometry_gist
    ON event_evidence USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_event_evidence_time
    ON event_evidence (event_start, event_end);
UPDATE event_evidence
SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
WHERE geometry IS NULL;
CREATE OR REPLACE FUNCTION sync_event_evidence_geometry() RETURNS trigger AS $$
BEGIN
    NEW.geometry := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_sync_event_evidence_geometry ON event_evidence;
CREATE TRIGGER trg_sync_event_evidence_geometry
    BEFORE INSERT OR UPDATE OF latitude, longitude ON event_evidence
    FOR EACH ROW EXECUTE FUNCTION sync_event_evidence_geometry();

CREATE TABLE IF NOT EXISTS stack_snapshots (
    snapshot_id VARCHAR(64) PRIMARY KEY,
    model_stack_version VARCHAR(64) NOT NULL,
    data_through_date DATE NOT NULL,
    primary_firms_source VARCHAR(64) NOT NULL,
    a_core_artifact_sha256 VARCHAR(64) NOT NULL,
    c_artifact_sha256 VARCHAR(64) NOT NULL,
    feature_version VARCHAR(64) NOT NULL,
    resolver_version VARCHAR(64) NOT NULL,
    backfill_completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(32) NOT NULL,
    CONSTRAINT uq_stack_snapshot_version_date UNIQUE (model_stack_version, data_through_date)
);

CREATE TABLE IF NOT EXISTS firms_backfill_windows (
    source_sensor VARCHAR(64) NOT NULL,
    bbox VARCHAR(64) NOT NULL,
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    records_fetched INTEGER NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    fetch_mode VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (source_sensor, bbox, window_start, window_end)
);
CREATE INDEX IF NOT EXISTS idx_backfill_windows_completion
    ON firms_backfill_windows (status, window_end);

COMMIT;
