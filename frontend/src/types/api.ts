/**
 * SIH26162 Thermal AI - API TypeScript Definitions
 * Mirrors backend Pydantic schemas in backend/app/schemas/
 */

export interface HealthCheck {
  status: 'ok' | 'healthy' | 'degraded' | 'down';
  database: string;
  postgis_enabled: boolean;
  active_models: Record<string, string>;
  timestamp: string;
}

export interface SystemStats {
  total_sites: number;
  active_sites_30d: number;
  model_a_counts: Record<string, number>;
  model_b_counts: Record<string, number>;
  model_c_counts: Record<string, number>;
  alert_counts: Record<string, number>;
  latest_firms_date: string | null;
  data_mode: 'LIVE' | 'REPLAY';
}

export interface SiteCompactProperties {
  site_id: string;
  a_class: 'INDUSTRIAL' | 'NONINDUSTRIAL' | 'UNKNOWN';
  a_prob: number;
  b_state: 'NEW' | 'PERSISTENT' | 'INTERMITTENT' | 'DORMANT' | 'REACTIVATED';
  c_status: 'NORMAL' | 'ELEVATED' | 'ANOMALOUS' | 'CRITICAL' | 'INSUFFICIENT_HISTORY' | 'NO_RECENT_EVENT';
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
}

export interface ModelASummary {
  class_name: 'INDUSTRIAL' | 'NONINDUSTRIAL' | 'UNKNOWN';
  decision: string;
  core_probability: number;
  prithvi_probability: number | null;
  prithvi_status: 'NOT_TRIGGERED' | 'TRIGGERED' | 'RESCUED' | 'CONFIRMED' | 'FAILED';
  model_version: string;
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
}

export interface ImageryCacheSummary {
  cache_id: string;
  site_id: string;
  scene_id: string;
  capture_date: string;
  cloud_cover: number | null;
  bands_available: string[] | null;
  prithvi_score: number | null;
  visual_class: string | null;
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

export interface ReplaySnapshotResponse {
  as_of_date: string;
  active_sites_count: number;
  alerts_count: number;
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
