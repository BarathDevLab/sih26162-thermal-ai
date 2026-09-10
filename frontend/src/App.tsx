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

const VIEWPORT_REQUEST_DEBOUNCE_MS = 180;
const VIEWPORT_CACHE_SIZE = 24;

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
  return [mode, mode === 'REPLAY' ? replayDate : '', limit, ...bbox.map(value => value.toFixed(4))].join('|');
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
  const sitesCache = useRef<Map<string, SiteGeoJSONFeatureCollection>>(new Map());
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState<SiteDetail | null>(null);

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [focusedCoordinates, setFocusedCoordinates] = useState<[number, number] | null>(null);

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
      try {
        const [h, s, a] = await Promise.all([
          fetchHealth(),
          fetchStats(),
          fetchAlerts()
        ]);
        setHealth(h);
        setStats(s);
        setAlerts(a.alerts);
        const liveReady = h.status === 'READY' || h.status === 'DEGRADED_PRITHVI_UNAVAILABLE';
        setMode(liveReady ? 'LIVE' : 'REPLAY');
        if (!liveReady && s.latest_firms_date) {
          setReplayDate(s.latest_firms_date);
        }
      } catch (err) {
        console.error('Telemetry bootstrap failed:', err);
      }
    };

    initTelemetry();
  }, []);

  // A stale backend catches up in the background. Poll readiness so the UI
  // enables Live automatically when the new common snapshot is published.
  useEffect(() => {
    const liveReady = health?.status === 'READY' || health?.status === 'DEGRADED_PRITHVI_UNAVAILABLE';
    if (!health || liveReady) return;

    const interval = window.setInterval(async () => {
      try {
        const nextHealth = await fetchHealth();
        setHealth(nextHealth);
        const nextLiveReady = nextHealth.status === 'READY' || nextHealth.status === 'DEGRADED_PRITHVI_UNAVAILABLE';
        if (nextLiveReady) {
          const nextStats = await fetchStats();
          setStats(nextStats);
          setMode('LIVE');
        }
      } catch (err) {
        console.error('Readiness refresh failed:', err);
      }
    }, 10_000);

    return () => window.clearInterval(interval);
  }, [health]);

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
    if (cached) {
      sitesCache.current.delete(cacheKey);
      sitesCache.current.set(cacheKey, cached);
      setSitesData(cached);
    }

    sitesAbortController.current?.abort();
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
        sitesCache.current.set(cacheKey, data);
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
    const task = window.setTimeout(() => void loadSites(), VIEWPORT_REQUEST_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(task);
      sitesAbortController.current?.abort();
    };
  }, [currentBBox, loadSites]);

  // 4. Load Detailed Site Intelligence when a site is selected
  useEffect(() => {
    let active = true;

    if (!selectedSiteId) {
      return;
    }

    const cutoff = mode === 'REPLAY' ? replayDate : undefined;
    fetchSiteDetail(selectedSiteId, cutoff)
      .then((detail) => {
        if (active) {
          setSelectedSite(detail);
        }
      })
      .catch((err) => {
        console.error(`Failed to fetch site ${selectedSiteId}:`, err);
      });

    return () => {
      active = false;
    };
  }, [selectedSiteId, mode, replayDate]);

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
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-[#070a12] text-slate-100 select-none">
      {/* Top Telemetry Header */}
      <Header
        stats={mode === 'LIVE' ? stats : null}
        health={health}
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
      <div className="flex flex-1 w-full h-[calc(100vh-3.5rem)] overflow-hidden relative">
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
        <div className="flex-1 h-full relative">
          <ErrorBoundary fallbackTitle="Tactical Map Rendering Error">
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
            onClose={() => setSelectedSiteId(null)}
          />
        )}
      </div>
    </div>
  );
}
