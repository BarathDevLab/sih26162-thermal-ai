-- Reverse lookup required for FIRMS observation reconciliation and FK checks.
-- PostgreSQL does not automatically index the referencing side of a foreign key.
CREATE INDEX IF NOT EXISTS idx_candidate_members_detection
    ON candidate_source_detections (detection_id);
