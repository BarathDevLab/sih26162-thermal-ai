BEGIN;

CREATE TABLE IF NOT EXISTS site_reviews (
    review_id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL REFERENCES source_sites(site_id),
    alert_id VARCHAR(64) REFERENCES alerts(alert_id),
    supersedes_review_id VARCHAR(64) REFERENCES site_reviews(review_id),
    review_status VARCHAR(32) NOT NULL,
    determination VARCHAR(32),
    confidence VARCHAR(16),
    consensus_status VARCHAR(32) NOT NULL DEFAULT 'NOT_APPLICABLE',
    reason_codes JSONB,
    notes TEXT,
    evidence_refs JSONB,
    reviewed_by VARCHAR(128) NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    country VARCHAR(64) NOT NULL DEFAULT 'INDIA',
    training_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    model_a_class VARCHAR(32),
    model_a_probability DOUBLE PRECISION,
    model_a_decision VARCHAR(64),
    model_stack_version VARCHAR(64) NOT NULL,
    feature_version VARCHAR(64),
    feature_snapshot JSONB,
    CONSTRAINT ck_site_reviews_status CHECK (
        review_status IN ('IN_REVIEW', 'COMPLETED', 'ESCALATED')
    ),
    CONSTRAINT ck_site_reviews_determination CHECK (
        determination IS NULL OR determination IN ('INDUSTRIAL', 'NONINDUSTRIAL', 'REMAIN_UNKNOWN')
    ),
    CONSTRAINT ck_site_reviews_confidence CHECK (
        confidence IS NULL OR confidence IN ('HIGH', 'MEDIUM', 'LOW')
    ),
    CONSTRAINT ck_site_reviews_consensus CHECK (
        consensus_status IN ('NOT_APPLICABLE', 'SINGLE_REVIEW', 'VERIFIED', 'CONFLICT')
    )
);

CREATE INDEX IF NOT EXISTS idx_site_reviews_site_id ON site_reviews (site_id);
CREATE INDEX IF NOT EXISTS idx_site_reviews_alert_id ON site_reviews (alert_id);
CREATE INDEX IF NOT EXISTS idx_site_reviews_status ON site_reviews (review_status);
CREATE INDEX IF NOT EXISTS idx_site_reviews_site_time
    ON site_reviews (site_id, reviewed_at DESC, review_id DESC);
CREATE INDEX IF NOT EXISTS idx_site_reviews_training
    ON site_reviews (training_eligible, determination, country);

-- Review evidence is append-only. Corrections and verification are represented
-- by new rows linked through supersedes_review_id.
CREATE OR REPLACE FUNCTION prevent_site_review_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'site_reviews is append-only; submit a superseding review event';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_prevent_site_review_mutation ON site_reviews;
CREATE TRIGGER trg_prevent_site_review_mutation
    BEFORE UPDATE OR DELETE ON site_reviews
    FOR EACH ROW EXECUTE FUNCTION prevent_site_review_mutation();

COMMIT;
