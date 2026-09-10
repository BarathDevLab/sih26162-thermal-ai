import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Header } from './components/Header';
import { SidebarFilters } from './components/SidebarFilters';
import { MapContainer } from './components/MapContainer';
import { SiteDrawer } from './components/SiteDrawer';
import { AlertRail } from './components/AlertRail';
import { ReplayScrubber } from './components/ReplayScrubber';
import { ErrorBoundary } from './components/ErrorBoundary';
import type {
  SystemStats,
  HealthCheck,
  SiteGeoJSONFeatureCollection,
  SiteDetail,
  AlertItem,
  FilterState
} from './types/api';
import {
  fetchHealth,
  fetchStats,
  fetchSitesInBBox,
  fetchSiteDetail,
  fetchAlerts,
  fetchReplaySnapshot,
  subscribeToAlertStream
} from './services/api';

const DEFAULT_FILTERS: FilterState = {
  aClasses: ['INDUSTRIAL', 'NONINDUSTRIAL', 'UNKNOWN', 'UNAVAILABLE'],
  bStates: ['PERSISTENT', 'REACTIVATED', 'INTERMITTENT', 'NEW', 'DORMANT', 'UNAVAILABLE'],
  cStatuses: ['CRITICAL', 'ANOMALOUS', 'ELEVATED', 'NORMAL', 'INSUFFICIENT_HISTORY', 'NO_RECENT_EVENT', 'UNAVAILABLE'],
  alertSeverities: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
  evidenceLayers: {
    gem: true,
    gfmr: true,
    icar: false,
    fsi: false
  },
  firmsHotspots: false,
  mode3D: false,
  terrain3D: false,
  spikeHeightScale: 2.0
};

const VIEWPORT_REQUEST_DEBOUNCE_MS = 90;
const VIEWPORT_ZOOM_OUT_DEBOUNCE_MS = 0;
const VIEWPORT_CACHE_SIZE = 24;
const VIEWPORT_CACHE_FRESH_MS = 30_000;

interface ViewportCacheEntry {
  data: SiteGeoJSONFeatureCollection;
  fetchedAt: number;
}

function canEnterLiveMode(health: HealthCheck | null, stats: SystemStats | null): boolean {
  if (!health) return stats?.data_mode === 'LIVE';
  if (health.database !== 'connected') return false;
  return (
    health.status === 'READY' ||
    health.status === 'DEGRADED_PRITHVI_UNAVAILABLE' ||
    stats?.data_mode === 'LIVE'
  );
}

function viewportLimit(bbox: [number, number, number, number]): number {
  const longitudeSpan = Math.abs(bbox[2] - bbox[0]);
  const latitudeSpan = Math.abs(bbox[3] - bbox[1]);
  if (longitudeSpan <= 4 && latitudeSpan <= 4) return 10000;
  if (longitudeSpan <= 12 && latitudeSpan <= 12) return 6000;
  return 3000;
}

function viewportCacheKey(
  mode: 'LIVE' | 'REPLAY',
  replayDate: string,
  bbox: [number, number, number, number],
  limit: number
): string {
  const span = Math.max(Math.abs(bbox[2] - bbox[0]), Math.abs(bbox[3] - bbox[1]));
  const precision = span >= 20 ? 2 : span >= 8 ? 3 : 4;
  return [mode, mode === 'REPLAY' ? replayDate : '', limit, ...bbox.map(value => value.toFixed(precision))].join('|');
}

function viewportArea(bbox: [number, number, number, number]): number {
  return Math.abs((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]));
}

export default function App() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [mode, setMode] = useState<'LIVE' | 'REPLAY'>('REPLAY');
  const [replayDate, setReplayDate] = useState<string>('2025-06-01');
  const [is3D, setIs3D] = useState<boolean>(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  const [currentBBox, setCurrentBBox] = useState<[number, number, number, number] | undefined>(undefined);
  const [sitesData, setSitesData] = useState<SiteGeoJSONFeatureCollection | null>(null);
  const [sitesLoading, setSitesLoading] = useState<boolean>(false);
  const [sitesError, setSitesError] = useState<string | null>(null);
  const sitesRequestId = useRef(0);
  const sitesAbortController = useRef<AbortController | null>(null);
  const sitesCache = useRef<Map<string, ViewportCacheEntry>>(new Map());
  const previousViewportBBox = useRef<[number, number, number, number] | undefined>(undefined);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState<SiteDetail | null>(null);
  const selectedSiteRequestId = useRef(0);

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [focusedCoordinates, setFocusedCoordinates] = useState<[number, number] | null>(null);
  const liveAvailable = canEnterLiveMode(health, stats);

  const loadedModelACounts = useMemo(() => {
    const counts = {
      INDUSTRIAL: 0,
      NONINDUSTRIAL: 0,
      UNKNOWN: 0,
      UNAVAILABLE: 0
    };
    for (const feature of sitesData?.features ?? []) {
      counts[feature.properties.a_class] += 1;
    }
    return counts;
  }, [sitesData]);

  // 1. Initial Health, Stats, and Alerts Load
  useEffect(() => {
    const initTelemetry = async () => {
      const [healthResult, statsResult, alertsResult] = await Promise.allSettled([
        fetchHealth(),
        fetchStats(),
        fetchAlerts()
      ]);

      const nextHealth = healthResult.status === 'fulfilled' ? healthResult.value : null;
      const nextStats = statsResult.status === 'fulfilled' ? statsResult.value : null;
      if (nextHealth) setHealth(nextHealth);
      if (nextStats) setStats(nextStats);
      if (alertsResult.status === 'fulfilled') setAlerts(alertsResult.value.alerts);

      if (healthResult.status === 'rejected') console.error('Health bootstrap failed:', healthResult.reason);
      if (statsResult.status === 'rejected') console.error('Statistics bootstrap failed:', statsResult.reason);
      if (alertsResult.status === 'rejected') console.error('Alert bootstrap failed:', alertsResult.reason);

      const nextLiveAvailable = canEnterLiveMode(nextHealth, nextStats);
      setMode(nextLiveAvailable ? 'LIVE' : 'REPLAY');
      if (!nextLiveAvailable && nextStats?.latest_firms_date) {
        setReplayDate(nextStats.latest_firms_date);
      }
    };

    initTelemetry();
  }, []);

  // A stale backend catches up in the background. Poll readiness so the UI
  // enables Live automatically when the new common snapshot is published.
  useEffect(() => {
    if (liveAvailable) return;

    const interval = window.setInterval(async () => {
      const [healthResult, statsResult] = await Promise.allSettled([fetchHealth(), fetchStats()]);
      const nextHealth = healthResult.status === 'fulfilled' ? healthResult.value : health;
      const nextStats = statsResult.status === 'fulfilled' ? statsResult.value : stats;
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
      if (statsResult.status === 'fulfilled') setStats(statsResult.value);
      if (canEnterLiveMode(nextHealth, nextStats)) {
        setMode('LIVE');
      }
    }, 10_000);

    return () => window.clearInterval(interval);
  }, [health, stats, liveAvailable]);

  // 2. Real-Time Alert Stream Subscription
  useEffect(() => {
    if (mode !== 'LIVE') return;

    const unsubscribe = subscribeToAlertStream(
      (newAlert) => {
        setAlerts((prev) => {
          // Avoid duplicate alerts
          if (prev.some(a => a.alert_id === newAlert.alert_id)) {
            return prev.map(a => a.alert_id === newAlert.alert_id ? newAlert : a);
          }
          return [newAlert, ...prev];
        });
      },
      () => setSseConnected(true),
      () => setSseConnected(false)
    );

    return () => {
      unsubscribe();
      setSseConnected(false);
    };
  }, [mode]);

  // 3. Load Sites based on BBox and Operating Mode
  const loadSites = useCallback(async () => {
    if (!currentBBox) return;

    const requestId = ++sitesRequestId.current;
    const limit = viewportLimit(currentBBox);
    const cacheKey = viewportCacheKey(mode, replayDate, currentBBox, limit);
    const cached = sitesCache.current.get(cacheKey);
    sitesAbortController.current?.abort();
    sitesAbortController.current = null;
    if (cached) {
      sitesCache.current.delete(cacheKey);
      sitesCache.current.set(cacheKey, cached);
      setSitesData(cached.data);
      setSitesError(null);
      const isFresh = mode === 'REPLAY' || Date.now() - cached.fetchedAt < VIEWPORT_CACHE_FRESH_MS;
      if (isFresh) {
        setSitesLoading(false);
        return;
      }
    }

    const controller = new AbortController();
    sitesAbortController.current = controller;
    setSitesLoading(true);
    setSitesError(null);
    try {
      let data: SiteGeoJSONFeatureCollection;
      if (mode === 'LIVE') {
        data = await fetchSitesInBBox(currentBBox, { limit }, controller.signal);
      } else {
        const replayData = await fetchReplaySnapshot(replayDate, currentBBox, limit, controller.signal);
        data = {
          type: 'FeatureCollection',
          features: replayData.features,
          total_count: replayData.active_sites_count,
          returned_count: replayData.returned_sites_count,
          truncated: replayData.truncated
        };
      }

      if (requestId === sitesRequestId.current) {
        sitesCache.current.set(cacheKey, { data, fetchedAt: Date.now() });
        while (sitesCache.current.size > VIEWPORT_CACHE_SIZE) {
          const oldestKey = sitesCache.current.keys().next().value;
          if (oldestKey === undefined) break;
          sitesCache.current.delete(oldestKey);
        }
        setSitesData(data);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Error fetching sites:', err);
      if (requestId === sitesRequestId.current) {
        setSitesError(err instanceof Error ? err.message : 'Unable to load sites');
      }
    } finally {
      if (requestId === sitesRequestId.current) {
        setSitesLoading(false);
        if (sitesAbortController.current === controller) {
          sitesAbortController.current = null;
        }
      }
    }
  }, [currentBBox, mode, replayDate]);

  useEffect(() => {
    if (!currentBBox) return;
    const previous = previousViewportBBox.current;
    const isZoomingOut = previous !== undefined && viewportArea(currentBBox) > viewportArea(previous) * 1.08;
    previousViewportBBox.current = currentBBox;
    const delay = isZoomingOut ? VIEWPORT_ZOOM_OUT_DEBOUNCE_MS : VIEWPORT_REQUEST_DEBOUNCE_MS;
    const task = window.setTimeout(() => void loadSites(), delay);
    return () => {
      window.clearTimeout(task);
      sitesAbortController.current?.abort();
    };
  }, [currentBBox, loadSites]);

  const refreshSelectedSite = useCallback(async (siteId: string, asOfDate?: string) => {
    const requestId = ++selectedSiteRequestId.current;
    const detail = await fetchSiteDetail(siteId, asOfDate);
    if (requestId !== selectedSiteRequestId.current) {
      return detail;
    }

    setSelectedSite(detail);

    // A completed live Prithvi rescue must be reflected on the selected marker too.
    // Replay snapshots remain immutable and are never patched with a current result.
    const modelA = detail.model_a;
    if (asOfDate === undefined && modelA) {
      setSitesData((previous) => {
        if (!previous) return previous;
        let changed = false;
        const features = previous.features.map((feature) => {
          if (feature.properties.site_id !== siteId) return feature;
          if (
            feature.properties.a_class === modelA.class_name &&
            feature.properties.a_prob === modelA.core_probability
          ) {
            return feature;
          }
          changed = true;
          return {
            ...feature,
            properties: {
              ...feature.properties,
              a_class: modelA.class_name,
              a_prob: modelA.core_probability
            }
          };
        });
        return changed ? { ...previous, features } : previous;
      });
    }

    return detail;
  }, []);

  // 4. Load Detailed Site Intelligence when a site is selected
  useEffect(() => {
    let active = true;

    if (!selectedSiteId) {
      return;
    }

    const cutoff = mode === 'REPLAY' ? replayDate : undefined;
    queueMicrotask(() => {
      if (!active) return;
      refreshSelectedSite(selectedSiteId, cutoff).catch((err) => {
        if (active) console.error(`Failed to fetch site ${selectedSiteId}:`, err);
      });
    });

    return () => {
      active = false;
      selectedSiteRequestId.current += 1;
    };
  }, [selectedSiteId, mode, replayDate, refreshSelectedSite]);

  // Jump to site action from alert feed
  const handleJumpToSite = (siteId: string, lat?: number, lon?: number) => {
    setSelectedSiteId(siteId);
    if (lat !== undefined && lon !== undefined) {
      setFocusedCoordinates([lon, lat]);
    }
  };

  const handleAlertAcked = (alertId: string) => {
    setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
  };

  return (
    <div className="app-shell flex flex-col w-screen h-screen overflow-hidden text-slate-100 select-none">
      {/* Top Telemetry Header */}
      <Header
        stats={stats}
        health={health}
        liveAvailable={liveAvailable}
        mode={mode}
        onModeChange={(m) => {
          setMode(m);
          setSelectedSiteId(null);
        }}
        is3D={is3D}
        onToggle3D={() => setIs3D(!is3D)}
        sseConnected={sseConnected}
        activeAlertCount={mode === 'LIVE' ? alerts.length : null}
      />

      {/* Main Workspace Cockpit */}
      <div className="command-workspace flex flex-1 w-full overflow-hidden relative">
        {/* Left Layer & Filter Rail */}
        <SidebarFilters
          filters={filters}
          onChange={setFilters}
          loadedSiteCount={sitesData?.returned_count ?? sitesData?.features.length ?? 0}
          totalSiteCount={sitesData?.total_count ?? 0}
          modelACounts={loadedModelACounts}
          isLoading={sitesLoading}
        />

        {/* Center Interactive Map Viewport */}
        <div className="map-workspace flex-1 h-full relative min-w-0">
          <ErrorBoundary fallbackTitle="Map rendering error">
            <MapContainer
              sitesData={sitesData}
              selectedSiteId={selectedSiteId}
              onSelectSite={(id) => setSelectedSiteId(id)}
              onBoundsChange={(bbox) => setCurrentBBox(bbox)}
              filters={filters}
              is3D={is3D}
              focusedCoordinates={focusedCoordinates}
              isLoading={sitesLoading}
            />
          </ErrorBoundary>

          {/* Floating Operational Alert Feed (LIVE Mode) */}
          {mode === 'LIVE' && (
            <AlertRail
              alerts={alerts}
              onJumpToSite={handleJumpToSite}
              onAlertAcknowledged={handleAlertAcked}
            />
          )}

          {/* Bottom Historical Replay Scrubber (REPLAY Mode) */}
          {mode === 'REPLAY' && (
            <ReplayScrubber
              currentDate={replayDate}
              endDate={stats?.latest_firms_date || undefined}
              onDateChange={setReplayDate}
              activeCount={sitesData?.total_count || 0}
              isLoading={sitesLoading}
              error={sitesError}
            />
          )}
        </div>

        {/* Right Site Intelligence Drawer */}
        {selectedSiteId && (
          <SiteDrawer
            site={selectedSite?.site_id === selectedSiteId ? selectedSite : null}
            asOfDate={mode === 'REPLAY' ? replayDate : undefined}
            onRefreshSite={refreshSelectedSite}
            onClose={() => setSelectedSiteId(null)}
          />
        )}
      </div>
    </div>
  );
}
