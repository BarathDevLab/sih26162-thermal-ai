/**
 * SIH26162 Thermal AI - API Client Service
 * Handles normalized calls to FastAPI endpoints and SSE streams.
 */

import type {
  HealthCheck,
  SystemStats,
  SiteGeoJSONFeatureCollection,
  SiteDetail,
  SiteTimelineResponse,
  SiteDetectionsResponse,
  SiteEvidenceResponse,
  ImageryCacheSummary,
  AlertFeedResponse,
  AlertAckResponse,
  ReplaySnapshotResponse,
  AlertItem
} from '../types/api';

const API_BASE = '/api/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const err = await res.json();
      errorDetail = err.detail || JSON.stringify(err);
    } catch {
      // ignore
    }
    throw new Error(`API Error ${res.status}: ${errorDetail}`);
  }
  return res.json();
}

export async function fetchHealth(): Promise<HealthCheck> {
  const res = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthCheck>(res);
}

export async function fetchStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/stats`);
  return handleResponse<SystemStats>(res);
}

export interface BBoxSiteFilters {
  aClass?: string;
  bState?: string;
  cStatus?: string;
  severity?: string;
  limit?: number;
}

export async function fetchSitesInBBox(
  bbox?: [number, number, number, number], // [min_lon, min_lat, max_lon, max_lat]
  filters: BBoxSiteFilters = {}
): Promise<SiteGeoJSONFeatureCollection> {
  const params = new URLSearchParams();
  if (bbox) {
    params.set('bbox', bbox.map(b => b.toFixed(5)).join(','));
  }
  if (filters.aClass) params.set('a_class', filters.aClass);
  if (filters.bState) params.set('b_state', filters.bState);
  if (filters.cStatus) params.set('c_status', filters.cStatus);
  if (filters.severity) params.set('severity', filters.severity);
  params.set('limit', String(filters.limit || 3000));

  const res = await fetch(`${API_BASE}/sites?${params.toString()}`);
  return handleResponse<SiteGeoJSONFeatureCollection>(res);
}

export async function fetchSiteDetail(siteId: string): Promise<SiteDetail> {
  const res = await fetch(`${API_BASE}/sites/${encodeURIComponent(siteId)}`);
  return handleResponse<SiteDetail>(res);
}

export async function fetchSiteTimeline(siteId: string): Promise<SiteTimelineResponse> {
  const res = await fetch(`${API_BASE}/sites/${encodeURIComponent(siteId)}/timeline`);
  return handleResponse<SiteTimelineResponse>(res);
}

export async function fetchSiteDetections(siteId: string): Promise<SiteDetectionsResponse> {
  const res = await fetch(`${API_BASE}/sites/${encodeURIComponent(siteId)}/detections`);
  return handleResponse<SiteDetectionsResponse>(res);
}

export async function fetchSiteEvidence(siteId: string, radiusM: number = 3000): Promise<SiteEvidenceResponse> {
  const res = await fetch(`${API_BASE}/sites/${encodeURIComponent(siteId)}/evidence?radius_m=${radiusM}`);
  return handleResponse<SiteEvidenceResponse>(res);
}

export async function fetchSiteImagery(siteId: string): Promise<ImageryCacheSummary[]> {
  const res = await fetch(`${API_BASE}/sites/${encodeURIComponent(siteId)}/imagery`);
  return handleResponse<ImageryCacheSummary[]>(res);
}

export async function fetchAlerts(
  severity?: string,
  status: string = 'ACTIVE',
  limit: number = 100
): Promise<AlertFeedResponse> {
  const params = new URLSearchParams();
  if (severity) params.set('severity', severity);
  if (status) params.set('status', status);
  params.set('limit', String(limit));

  const res = await fetch(`${API_BASE}/alerts?${params.toString()}`);
  return handleResponse<AlertFeedResponse>(res);
}

export async function acknowledgeAlert(
  alertId: string,
  acknowledgedBy: string = 'analyst_operator'
): Promise<AlertAckResponse> {
  const res = await fetch(`${API_BASE}/alerts/${encodeURIComponent(alertId)}/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ acknowledged_by: acknowledgedBy })
  });
  return handleResponse<AlertAckResponse>(res);
}

export async function fetchReplaySnapshot(
  dateStr: string,
  bbox?: [number, number, number, number],
  limit: number = 3000
): Promise<ReplaySnapshotResponse> {
  const params = new URLSearchParams();
  params.set('date', dateStr);
  if (bbox) {
    params.set('bbox', bbox.map(b => b.toFixed(5)).join(','));
  }
  params.set('limit', String(limit));

  const res = await fetch(`${API_BASE}/replay?${params.toString()}`);
  return handleResponse<ReplaySnapshotResponse>(res);
}

export function subscribeToAlertStream(
  onAlert: (alert: AlertItem) => void,
  onConnected?: () => void,
  onError?: (err: any) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/stream/alerts?poll_interval=4.0`);

  eventSource.addEventListener('connected', () => {
    if (onConnected) onConnected();
  });

  eventSource.addEventListener('alert', (event) => {
    try {
      const data = JSON.parse(event.data);
      onAlert(data);
    } catch (e) {
      console.error('Failed to parse SSE alert:', e);
    }
  });

  eventSource.onerror = (e) => {
    if (onError) onError(e);
  };

  // Return unsubscribe function
  return () => {
    eventSource.close();
  };
}
