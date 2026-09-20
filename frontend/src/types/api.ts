/**
 * SIH26162 Thermal AI - API TypeScript Definitions
 * Mirrors backend Pydantic schemas in backend/app/schemas/
 */

export interface HealthCheck {
  status: 'READY' | 'DEGRADED_PRITHVI_UNAVAILABLE' | 'STALE_BACKFILL' | 'MODEL_ARTIFACT_MISMATCH' | 'DATABASE_NOT_READY' | 'FIRMS_CREDENTIALS_MISSING';
  database: string;
  postgis_enabled: boolean;
  active_models: Record<string, string>;
  timestamp: string;
}

export interface StartupCatchupStatus {
  status: 'IDLE' | 'RUNNING' | 'SKIPPED_ALREADY_RUNNING' | 'COMPLETED' | 'COMPLETED_NOT_READY' | 'FAILED';
  running: boolean;
  phase: string;
  progress_percent: number;
  phase_progress_percent: number;
  source_date: string | null;
  target_date: string | null;
  completed_windows: number;
  total_windows: number;
  current_window_start: string | null;
  current_window_end: string | null;
  records_processed: number;
  records_fetched: number;
  records_unique: number;
  records_revised: number;
  promoted_sites: number;
  alerts_generated: number;
  current_source: string | null;
  model_b_processed_sites: number;
  model_b_total_sites: number;
  worldcover_processed_sites: number;
  worldcover_total_sites: number;
  worldcover_current_tile: string | null;
  processed_sites: number;
  total_sites: number;
  started_at: string | null;
  ended_at: string | null;
  updated_at: string | null;
  elapsed_seconds: number;
  estimated_remaining_seconds: number | null;
  estimated_completion_at: string | null;
  progress_rate_percent_per_minute: number | null;
  activity_log: StartupActivityEvent[];
  detail: string;
}

export interface StartupActivityEvent {
  timestamp: string;
  phase: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

export interface LiveRuntimeStatus {
  scheduler: Record<string, unknown>;
  prithvi_queue: Record<string, unknown>;
  startup_catchup: StartupCatchupStatus;
  runtime_readiness: {
    status: HealthCheck['status'];
    can_start_live: boolean;
    data_through_date?: string | null;
    detail: string;
  };
}

export type StartupRuntimeUpdate = Pick<
  LiveRuntimeStatus,
  'startup_catchup' | 'runtime_readiness'
>;

export interface SystemStats {
  total_sites: number;
  active_sites_30d: number;
  model_a_counts: Record<string, number>;
  model_b_counts: Record<string, number>;
  model_c_counts: Record<string, number>;
  alert_counts: Record<string, number>;
  latest_firms_date: string | null;
  data_mode: 'LIVE' | 'STALE_BLOCKED';
}

export interface SiteCompactProperties {
  site_id: string;
  a_class: 'INDUSTRIAL' | 'NONINDUSTRIAL' | 'UNKNOWN' | 'UNAVAILABLE';
  a_prob: number | null;
  b_state: 'NEW' | 'PERSISTENT' | 'INTERMITTENT' | 'DORMANT' | 'REACTIVATED' | 'UNAVAILABLE';
  c_status: 'NORMAL' | 'ELEVATED' | 'ANOMALOUS' | 'CRITICAL' | 'INSUFFICIENT_HISTORY' | 'NO_RECENT_EVENT' | 'UNAVAILABLE';
  c_score: number | null;
  alert_severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO' | 'NONE';
  alert_type?: string | null;
  latest_seen?: string | null;
  latest_frp?: number | null;
}

export interface SiteGeoJSONGeometry {
  type: 'Point';
  coordinates: [number, number]; // [longitude, latitude]
}

export interface SiteGeoJSONFeature {
  type: 'Feature';
  geometry: SiteGeoJSONGeometry;
  properties: SiteCompactProperties;
}

export interface SiteGeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: SiteGeoJSONFeature[];
  total_count: number;
  returned_count: number;
  truncated: boolean;
}

export interface ModelASummary {
  class_name: 'INDUSTRIAL' | 'NONINDUSTRIAL' | 'UNKNOWN';
  decision: string;
  core_probability: number;
  prithvi_probability: number | null;
  prithvi_status: 'NOT_TRIGGERED' | 'PENDING' | 'AVAILABLE' | 'UNAVAILABLE' | 'FAILED' | 'REJECTED_CLOUD';
  model_version: string;
  feature_version: string | null;
  feature_as_of_detection_date: string | null;
  imagery_acquisition_date: string | null;
  computed_at: string | null;
}

export interface ModelBSummary {
  state: 'NEW' | 'PERSISTENT' | 'INTERMITTENT' | 'DORMANT' | 'REACTIVATED';
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  reason: string | null;
  days_since_last: number | null;
  active_days_windows: Record<string, number> | null;
  model_version: string;
}

export interface ModelCSummary {
  operational_status: 'NORMAL' | 'ELEVATED' | 'ANOMALOUS' | 'CRITICAL' | 'INSUFFICIENT_HISTORY' | 'NO_RECENT_EVENT';
  c_score: number | null;
  c_raw: number | null;
  group_scores: Record<string, number | null> | null;
  evidence_99: number;
  drivers: string[] | null;
  event_date: string | null;
  model_version: string;
}

export interface AlertSummary {
  alert_id: string;
  alert_type: string;
  alert_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  headline: string;
  reason_codes: string[] | null;
  evidence_required: boolean;
  is_escalation: boolean;
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';
  created_at: string;
  updated_at: string;
}

export interface SiteDetail {
  site_id: string;
  latitude: number;
  longitude: number;
  status: string;
  created_at: string;
  latest_seen: string | null;
  land_cover: Record<string, number | null> | null;
  spatial_stats: Record<string, number | null> | null;
  model_a: ModelASummary | null;
  model_b: ModelBSummary | null;
  model_c: ModelCSummary | null;
  active_alert: AlertSummary | null;
}

export interface TimelinePoint {
  acq_date: string;
  detections: number;
  mean_frp: number;
  max_frp: number;
  c_status?: string | null;
  c_score?: number | null;
  c_raw?: number | null;
  b_state?: string | null;
  drivers?: string[] | null;
}

export interface SiteTimelineResponse {
  site_id: string;
  total_active_days: number;
  first_date: string | null;
  last_date: string | null;
  history: TimelinePoint[];
}

export interface DetectionItem {
  detection_id: string;
  source_sensor: string;
  satellite: string;
  acq_date: string;
  acq_time: string;
  frp: number;
  bright_ti4: number | null;
  bright_ti5: number | null;
  confidence: string;
  daynight: string;
  latitude: number;
  longitude: number;
}

export interface SiteDetectionsResponse {
  site_id: string;
  count: number;
  detections: DetectionItem[];
}

export interface FacilityEvidenceSummary {
  evidence_id: string;
  source_name: 'GEM' | 'GFMR' | 'ICAR' | 'FSI' | 'OSM' | string;
  facility_name: string;
  facility_type: string;
  latitude: number;
  longitude: number;
  distance_m: number;
  coordinate_quality: 'HIGH' | 'APPROXIMATE' | 'CENTROID' | string;
  source_url: string | null;
  attributes: Record<string, any> | null;
}

export interface SiteEvidenceResponse {
  site_id: string;
  search_radius_m: number;
  total_evidence_count: number;
  evidence: FacilityEvidenceSummary[];
  as_of_date: string | null;
  temporal_window_days: number;
  total_event_evidence_count: number;
  event_evidence: EventEvidenceSummary[];
}

export interface EventEvidenceSummary {
  evidence_id: string;
  source_name: string;
  evidence_type: string;
  reference_id: string | null;
  latitude: number;
  longitude: number;
  distance_m: number | null;
  event_start: string | null;
  event_end: string | null;
  authority_level: string | null;
  source_url: string | null;
  attributes: Record<string, any> | null;
}

export interface ImageryCacheSummary {
  cache_id: string;
  site_id: string;
  acquisition_date: string;
  product: string;
  cloud_fraction: number | null;
  prithvi_probability: number | null;
  status: string;
  source_uri: string | null;
  patch_uri: string | null;
  embedding_uri: string | null;
  model_revision: string | null;
  failure_reason: string | null;
}

export interface AlertItem {
  alert_id: string;
  site_id: string;
  site_day: string;
  alert_type: string;
  alert_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  headline: string;
  reason_codes: string[];
  evidence_required: boolean;
  fingerprint: string;
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';
  is_escalation: boolean;
  created_at: string;
  updated_at: string;
  latitude: number | null;
  longitude: number | null;
  a_class: string;
}

export interface AlertFeedResponse {
  total_alerts: number;
  alerts: AlertItem[];
}

export interface AlertAckRequest {
  acknowledged_by: string;
  notes?: string;
}

export interface AlertAckResponse {
  alert_id: string;
  status: string;
  acknowledged_by: string;
  updated_at: string;
  message: string;
}

export type ReviewDetermination = 'INDUSTRIAL' | 'NONINDUSTRIAL' | 'REMAIN_UNKNOWN';
export type ReviewConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

export interface SiteReviewItem {
  review_id: string;
  site_id: string;
  alert_id: string | null;
  supersedes_review_id: string | null;
  review_status: 'IN_REVIEW' | 'COMPLETED' | 'ESCALATED';
  determination: ReviewDetermination | null;
  confidence: ReviewConfidence | null;
  consensus_status: 'NOT_APPLICABLE' | 'SINGLE_REVIEW' | 'VERIFIED' | 'CONFLICT';
  reason_codes: string[];
  notes: string | null;
  evidence_refs: string[];
  reviewed_by: string;
  reviewed_at: string;
  country: string;
  training_eligible: boolean;
  model_a_class: string | null;
  model_a_probability: number | null;
  model_a_decision: string | null;
  model_stack_version: string;
  feature_version: string | null;
}

export interface SiteReviewHistoryResponse {
  site_id: string;
  queue_status: 'PENDING' | 'IN_REVIEW' | 'AWAITING_VERIFICATION' | 'CONFLICT' | 'COMPLETED';
  reviews: SiteReviewItem[];
}

export interface SiteReviewSubmitRequest {
  reviewed_by: string;
  review_status: 'IN_REVIEW' | 'COMPLETED' | 'ESCALATED';
  determination?: ReviewDetermination;
  confidence?: ReviewConfidence;
  reason_codes: string[];
  notes?: string;
  evidence_refs: string[];
  alert_id?: string;
  country?: string;
}

export interface ReviewQueueItem {
  site_id: string;
  latitude: number;
  longitude: number;
  alert_id: string;
  alert_type: string;
  alert_level: string;
  headline: string;
  site_day: string;
  queue_status: SiteReviewHistoryResponse['queue_status'];
  model_a_probability: number | null;
  prithvi_probability: number | null;
  prithvi_status: string;
  model_b_state: string | null;
  model_c_status: string | null;
  latest_review: SiteReviewItem | null;
}

export interface ReviewQueueResponse {
  total_reviews: number;
  items: ReviewQueueItem[];
}

export interface ReplaySnapshotResponse {
  as_of_date: string;
  active_sites_count: number;
  returned_sites_count: number;
  truncated: boolean;
  alerts_count: number;
  cache_status: 'MISS' | 'HIT' | 'DEMO_CACHE';
  features: SiteGeoJSONFeature[];
}

export interface FilterState {
  aClasses: string[];
  bStates: string[];
  cStatuses: string[];
  alertSeverities: string[];
  evidenceLayers: {
    gem: boolean;
    gfmr: boolean;
    icar: boolean;
    fsi: boolean;
  };
  firmsHotspots: boolean;
  mode3D: boolean;
  terrain3D: boolean;
  spikeHeightScale: number;
}
