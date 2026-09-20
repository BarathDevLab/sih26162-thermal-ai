-- Promotions occur exactly at the frozen min_samples=3 threshold. Older code
-- persisted all three memberships but left detection_count at its prior value.
WITH candidate_stats AS (
    SELECT c.candidate_id,
           count(d.detection_id) AS member_count,
           avg(d.latitude) AS latitude,
           avg(d.longitude) AS longitude,
           min(d.observed_at) AS first_seen,
           max(d.observed_at) AS last_seen
    FROM candidate_sources c
    JOIN candidate_source_detections d ON d.candidate_id = c.candidate_id
    WHERE c.status = 'PROMOTED'
    GROUP BY c.candidate_id
)
UPDATE candidate_sources c
SET detection_count = s.member_count,
    latitude = s.latitude,
    longitude = s.longitude,
    first_seen = s.first_seen,
    last_seen = s.last_seen
FROM candidate_stats s
WHERE c.candidate_id = s.candidate_id;
