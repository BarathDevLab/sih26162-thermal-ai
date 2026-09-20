import { lazy, Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Globe, Satellite, Radio } from 'lucide-react';
import { Header } from './components/Header';
import { SidebarFilters } from './components/SidebarFilters';
import { SiteDrawer } from './components/SiteDrawer';
import { AlertRail } from './components/AlertRail';
import { ReplayScrubber } from './components/ReplayScrubber';
import { ErrorBoundary } from './components/ErrorBoundary';
import { SystemLoadingScreen } from './components/SystemLoadingScreen';
import type {
  SystemStats,
  HealthCheck,
  SiteGeoJSONFeatureCollection,
  SiteDetail,
  AlertItem,
  FilterState,
  LiveRuntimeStatus
} from './types/api';
import {
  fetchHealth,
  fetchStats,
  fetchSitesInBBox,
  fetchSiteDetail,
  fetchAlerts,
  fetchLiveStatus,
  fetchReplaySnapshot,
  subscribeToAlertStream,
  subscribeToStartupRuntime
} from './services/api';

const MapContainer = lazy(() => import('./components/MapContainer').then(module => ({
  default: module.MapContainer
})));

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

const VIEWPORT_REQUEST_DEBOUNCE_MS = 45;
const VIEWPORT_CACHE_SIZE = 8;
const VIEWPORT_CACHE_FEATURE_BUDGET = 40_000;

interface ViewportCacheEntry {
  data: SiteGeoJSONFeatureCollection;
  bbox: [number, number, number, number];
  limit: number;
  mode: 'LIVE' | 'REPLAY';
  replayDate: string;
  cachedAt: number;
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
  return [mode, mode === 'REPLAY' ? replayDate : '', limit, ...bbox.map(value => value.toFixed(2))].join('|');
}

function expandBBox(
  bbox: [number, number, number, number],
  paddingRatio = 0.18
): [number, number, number, number] {
  const longitudePadding = Math.abs(bbox[2] - bbox[0]) * paddingRatio;
  const latitudePadding = Math.abs(bbox[3] - bbox[1]) * paddingRatio;
  return [
    Math.max(-180, bbox[0] - longitudePadding),
    Math.max(-90, bbox[1] - latitudePadding),
    Math.min(180, bbox[2] + longitudePadding),
    Math.min(90, bbox[3] + latitudePadding)
  ];
}

function bboxContains(
  outer: [number, number, number, number],
  inner: [number, number, number, number]
): boolean {
  return outer[0] <= inner[0]
    && outer[1] <= inner[1]
    && outer[2] >= inner[2]
    && outer[3] >= inner[3];
}

export default function App() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [mode, setMode] = useState<'LIVE' | 'REPLAY'>('REPLAY');
  const [replayDate, setReplayDate] = useState<string>('2025-06-01');
  const [is3D, setIs3D] = useState<boolean>(false);
  const [basemapMode, setBasemapMode] = useState<'SATELLITE' | 'DARK'>('SATELLITE');
  const [show3DColumns, setShow3DColumns] = useState<boolean>(true);
  const [showSatellites, setShowSatellites] = useState<boolean>(true);
  const [showSwaths, setShowSwaths] = useState<boolean>(true);
  const [showHeatBloom, setShowHeatBloom] = useState<boolean>(true);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [alertsOpen, setAlertsOpen] = useState<boolean>(true);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  const [currentBBox, setCurrentBBox] = useState<[number, number, number, number] | undefined>(undefined);
  const [sitesData, setSitesData] = useState<SiteGeoJSONFeatureCollection | null>(null);
  const [sitesLoading, setSitesLoading] = useState<boolean>(false);
  const [sitesError, setSitesError] = useState<string | null>(null);
  const [bootstrapSettled, setBootstrapSettled] = useState<boolean>(false);
  const [telemetryReady, setTelemetryReady] = useState<boolean>(false);
  const [startupAttempt, setStartupAttempt] = useState<number>(0);
  const [startupConnectionDetail, setStartupConnectionDetail] = useState<string>(
    'Waiting for the local backend to accept operational traffic.'
  );
  const [startupRetryDelayMs, setStartupRetryDelayMs] = useState<number | null>(null);
  const [liveRuntime, setLiveRuntime] = useState<LiveRuntimeStatus | null>(null);
  const [mapReady, setMapReady] = useState<boolean>(false);
  const [initialSitesRendered, setInitialSitesRendered] = useState<boolean>(false);
  const [interfaceActivated, setInterfaceActivated] = useState<boolean>(false);
  const sitesRequestId = useRef(0);
  const sitesAbortController = useRef<AbortController | null>(null);
  const initialSiteRetryAttempt = useRef(0);
  const sitesCache = useRef<Map<string, ViewportCacheEntry>>(new Map());
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState<SiteDetail | null>(null);
  const selectedSiteRequestId = useRef(0);

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

  const startupRuntimeBlocking = Boolean(liveRuntime?.startup_catchup.running) || Boolean(
    health?.status === 'STALE_BACKFILL'
    && liveRuntime?.startup_catchup.status === 'COMPLETED'
  );

  // 1. Initial runtime handshake. Uvicorn may still be completing its lifespan
  // startup while Vite is already serving the shell, so a proxy 502 is a
  // transient "not ready" signal rather than a completed bootstrap.
  useEffect(() => {
    let active = true;
    let retryTimer: number | null = null;
    let attempt = 0;

    const initTelemetry = async () => {
      attempt += 1;
      if (!active) return;
      setStartupAttempt(attempt);
      setStartupRetryDelayMs(null);
      setStartupConnectionDetail(
        attempt === 1
          ? 'Contacting the local backend and waiting for application startup.'
          : `Re-establishing the local backend link (attempt ${attempt}).`
      );

      try {
        // While Uvicorn is still offline, probe only the lightweight health
        // endpoint. The remaining API calls start after the socket is live so
        // one retry produces one expected proxy refusal instead of four.
        const h = await fetchHealth();
        if (!active) return;
        setStartupConnectionDetail('Backend socket established. Loading runtime telemetry.');
        const runtime = await fetchLiveStatus();
        if (!active) return;
        const catchupRunning = runtime.startup_catchup.running;
        let s: SystemStats | null = null;
        let initialAlerts: AlertItem[] = [];
        if (!catchupRunning) {
          const [nextStats, alertResponse] = await Promise.all([fetchStats(), fetchAlerts()]);
          if (!active) return;
          s = nextStats;
          initialAlerts = alertResponse.alerts;
        }
        setHealth(h);
        if (s) setStats(s);
        setAlerts(initialAlerts);
        setLiveRuntime(runtime);
        setTelemetryReady(true);
        setBootstrapSettled(true);
        setSitesError(null);
        setStartupConnectionDetail('Backend runtime established. Loading the operational picture.');
        const liveReady = h.status === 'READY' || h.status === 'DEGRADED_PRITHVI_UNAVAILABLE';
        setMode(liveReady ? 'LIVE' : 'REPLAY');
        if (!liveReady && s?.latest_firms_date) {
          setReplayDate(s.latest_firms_date);
        }
      } catch (err) {
        if (!active) return;
        setTelemetryReady(false);
        setBootstrapSettled(false);
        const retryDelay = Math.min(5_000, 500 * (2 ** Math.min(attempt - 1, 4)));
        setStartupRetryDelayMs(retryDelay);
        setStartupConnectionDetail(
          `Backend startup has not completed (attempt ${attempt}). Retrying in ${(retryDelay / 1_000).toFixed(1)}s.`
        );
        console.info('Backend runtime is not ready; bootstrap will retry:', err);
        retryTimer = window.setTimeout(() => void initTelemetry(), retryDelay);
      }
    };

    void initTelemetry();

    return () => {
      active = false;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
    };
  }, []);

  // A stale backend catches up in the background. One SSE connection carries
  // progress, activity, timing, and readiness until the stack becomes live.
  const readinessStatus = health?.status;
  useEffect(() => {
    const liveReady = readinessStatus === 'READY' || readinessStatus === 'DEGRADED_PRITHVI_UNAVAILABLE';
    if (!readinessStatus || liveReady) return;

    let active = true;
    let finalizing = false;
    let unsubscribe = () => {};

    const finalizeLiveActivation = async () => {
      try {
        const [nextHealth, nextStats, nextAlerts] = await Promise.all([
          fetchHealth(),
          fetchStats(),
          fetchAlerts()
        ]);
        if (!active) return;
        setHealth(nextHealth);
        setStats(nextStats);
        setAlerts(nextAlerts.alerts);
        setMode('LIVE');
      } catch (err) {
        finalizing = false;
        console.error('Final live activation refresh failed:', err);
      }
    };

    unsubscribe = subscribeToStartupRuntime(
      (update) => {
        if (!active) return;
        setLiveRuntime((current) => current ? {
          ...current,
          startup_catchup: update.startup_catchup,
          runtime_readiness: update.runtime_readiness
        } : current);
        const readiness = update.runtime_readiness;
        setHealth((current) => current ? { ...current, status: readiness.status } : current);

        const nextLiveReady = readiness.can_start_live
          || readiness.status === 'READY'
          || readiness.status === 'DEGRADED_PRITHVI_UNAVAILABLE';
        if (nextLiveReady && !finalizing) {
          finalizing = true;
          setMode('LIVE');
          unsubscribe();
          void finalizeLiveActivation();
          return;
        }

        const catchup = update.startup_catchup;
        if (
          ['FAILED', 'COMPLETED_NOT_READY', 'SKIPPED_ALREADY_RUNNING'].includes(catchup.status)
          || (catchup.status === 'IDLE' && !catchup.running)
        ) {
          unsubscribe();
        }
      },
      (connected) => setStartupConnectionDetail(
        connected
          ? 'Receiving live backend startup telemetry.'
          : 'Startup telemetry link interrupted; reconnecting automatically.'
      )
    );

    return () => {
      active = false;
      unsubscribe();
    };
  }, [readinessStatus]);

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
    if (!currentBBox || !telemetryReady || !bootstrapSettled || startupRuntimeBlocking) return;

    const requestId = ++sitesRequestId.current;
    const limit = viewportLimit(currentBBox);
    sitesAbortController.current?.abort();
    sitesAbortController.current = null;

    const cachedMatch = Array.from(sitesCache.current.entries()).find(([, entry]) => (
      entry.mode === mode
      && entry.replayDate === (mode === 'REPLAY' ? replayDate : '')
      && entry.limit >= limit
      && bboxContains(entry.bbox, currentBBox)
    ));
    if (cachedMatch) {
      const [cachedKey, cachedEntry] = cachedMatch;
      sitesCache.current.delete(cachedKey);
      sitesCache.current.set(cachedKey, cachedEntry);
      setSitesData(cachedEntry.data);
      setSitesError(null);

      const freshnessMs = mode === 'LIVE' ? 30_000 : 5 * 60_000;
      if (Date.now() - cachedEntry.cachedAt < freshnessMs) {
        setSitesLoading(false);
        return;
      }
    }

    const requestBBox = expandBBox(currentBBox);
    const cacheKey = viewportCacheKey(mode, replayDate, requestBBox, limit);
    const controller = new AbortController();
    sitesAbortController.current = controller;
    setSitesLoading(true);
    setSitesError(null);
    try {
      let data: SiteGeoJSONFeatureCollection;
      if (mode === 'LIVE') {
        data = await fetchSitesInBBox(requestBBox, { limit }, controller.signal);
      } else {
        const replayData = await fetchReplaySnapshot(replayDate, requestBBox, limit, controller.signal);
        data = {
          type: 'FeatureCollection',
          features: replayData.features,
          total_count: replayData.active_sites_count,
          returned_count: replayData.returned_sites_count,
          truncated: replayData.truncated
        };
      }

      if (requestId === sitesRequestId.current) {
        sitesCache.current.set(cacheKey, {
          data,
          bbox: requestBBox,
          limit,
          mode,
          replayDate: mode === 'REPLAY' ? replayDate : '',
          cachedAt: Date.now()
        });
        let cachedFeatureCount = Array.from(sitesCache.current.values()).reduce(
          (sum, entry) => sum + entry.data.features.length,
          0
        );
        while (
          sitesCache.current.size > VIEWPORT_CACHE_SIZE
          || cachedFeatureCount > VIEWPORT_CACHE_FEATURE_BUDGET
        ) {
          const oldestKey = sitesCache.current.keys().next().value;
          if (oldestKey === undefined) break;
          cachedFeatureCount -= sitesCache.current.get(oldestKey)?.data.features.length ?? 0;
          sitesCache.current.delete(oldestKey);
        }
        initialSiteRetryAttempt.current = 0;
        setSitesData(data);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Error fetching sites:', err);
      if (requestId === sitesRequestId.current && !cachedMatch) {
        if (!initialSitesRendered) initialSiteRetryAttempt.current += 1;
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
  }, [
    bootstrapSettled,
    currentBBox,
    initialSitesRendered,
    mode,
    replayDate,
    startupRuntimeBlocking,
    telemetryReady
  ]);

  useEffect(() => {
    if (!currentBBox || !telemetryReady || !bootstrapSettled || startupRuntimeBlocking) return;
    const task = window.setTimeout(() => void loadSites(), VIEWPORT_REQUEST_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(task);
      sitesAbortController.current?.abort();
    };
  }, [bootstrapSettled, currentBBox, loadSites, startupRuntimeBlocking, telemetryReady]);

  // The first viewport is part of startup. Keep retrying it behind the mission
  // screen instead of revealing a half-initialized interface after one error.
  useEffect(() => {
    if (
      !currentBBox
      || !telemetryReady
      || !bootstrapSettled
      || startupRuntimeBlocking
      || initialSitesRendered
      || !sitesError
    ) return;

    const retryDelay = Math.min(
      5_000,
      750 * (2 ** Math.min(initialSiteRetryAttempt.current - 1, 3))
    );
    const task = window.setTimeout(() => void loadSites(), retryDelay);
    return () => window.clearTimeout(task);
  }, [
    bootstrapSettled,
    currentBBox,
    initialSitesRendered,
    loadSites,
    sitesError,
    startupRuntimeBlocking,
    telemetryReady
  ]);

  const refreshSelectedSite = useCallback(async (siteId: string, asOfDate?: string) => {
    const requestId = ++selectedSiteRequestId.current;
    const detail = await fetchSiteDetail(siteId, asOfDate);
    if (requestId !== selectedSiteRequestId.current) {
      return detail;
    }
    setSelectedSite(detail);
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

  const startupPrerequisitesReady = telemetryReady
    && bootstrapSettled
    && mapReady
    && initialSitesRendered
    && !sitesError
    && !startupRuntimeBlocking;

  // Startup is a one-way handoff. Once activated, ordinary runtime errors are
  // handled inside the command center and never resurrect the boot overlay.
  useEffect(() => {
    if (interfaceActivated || !startupPrerequisitesReady) return;
    const confirmation = window.setTimeout(() => setInterfaceActivated(true), 350);
    return () => window.clearTimeout(confirmation);
  }, [interfaceActivated, startupPrerequisitesReady]);

  return (
    <div
      className={`command-center-root relative w-screen h-screen overflow-hidden bg-[#02040a] text-slate-100 select-none font-sans ${interfaceActivated ? 'is-activated' : 'is-booting'}`}
      aria-busy={!interfaceActivated}
    >
      {/* Full-bleed map canvas covers the entire screen */}
      <div className="absolute inset-0">
        <ErrorBoundary fallbackTitle="Tactical Map Rendering Error">
          <Suspense fallback={null}>
            <MapContainer
              sitesData={sitesData}
              selectedSiteId={selectedSiteId}
              onSelectSite={(id) => setSelectedSiteId(id)}
              onBoundsChange={(bbox) => setCurrentBBox(bbox)}
              filters={filters}
              is3D={is3D}
              basemapMode={basemapMode}
              show3DColumns={show3DColumns}
              showSatellites={showSatellites}
              showSwaths={showSwaths}
              showHeatBloom={showHeatBloom}
              focusedCoordinates={focusedCoordinates}
              isLoading={sitesLoading}
              onMapReady={() => setMapReady(true)}
              onSitesRendered={() => setInitialSitesRendered(true)}
            />
          </Suspense>
        </ErrorBoundary>
      </div>

      {/* Floating Tactical Header Bar (Stitch Spec — Transparent, SIH26162, Controls, Live/Replay) */}
      <Header
        health={health}
        mode={mode}
        onModeChange={(m) => {
          setMode(m);
          setSelectedSiteId(null);
        }}
        is3D={is3D}
        onToggle3D={() => setIs3D(!is3D)}
        basemapMode={basemapMode}
        onBasemapChange={(m) => setBasemapMode(m)}
        show3DColumns={show3DColumns}
        onToggle3DColumns={() => setShow3DColumns(!show3DColumns)}
        showSatellites={showSatellites}
        onToggleSatellites={() => setShowSatellites(!showSatellites)}
        showSwaths={showSwaths}
        onToggleSwaths={() => setShowSwaths(!showSwaths)}
        showHeatBloom={showHeatBloom}
        onToggleHeatBloom={() => setShowHeatBloom(!showHeatBloom)}
        sseConnected={sseConnected}
        activeAlertCount={mode === 'LIVE' ? alerts.length : null}
        siteCount={sitesData?.returned_count ?? sitesData?.features.length ?? (stats?.total_sites ?? 42)}
        activeRate={stats?.active_sites_30d ? `${((stats.active_sites_30d / Math.max(1, stats.total_sites)) * 100).toFixed(2)}%` : '99.98%'}
        industrialCount={loadedModelACounts.INDUSTRIAL || (stats?.model_a_counts['INDUSTRIAL'] ?? 1408)}
        alertCount={alerts.length > 0 ? alerts.length : 3}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        alertsOpen={alertsOpen}
        onToggleAlerts={() => setAlertsOpen(!alertsOpen)}
      />

      {/* Centered Floating Orbit View Sub-Bar (Stitch C4ISR Spec) */}
      <div className="absolute top-14 left-1/2 -translate-x-1/2 z-20 pointer-events-auto hidden sm:flex items-center gap-2 px-3.5 py-1 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md font-mono text-xs shadow-[0_4px_20px_rgba(0,0,0,0.65)]">
        <div className="flex items-center space-x-1.5 pr-2 border-r border-sky-400/30">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-300 shadow-[0_0_8px_#38bdf8] animate-pulse" />
          <span className="text-[9px] font-bold tracking-widest text-slate-300 uppercase">ORBIT VIEW</span>
        </div>

        <div className="flex items-center space-x-1 p-0.5">
          {/* 1. All Active */}
          <button
            onClick={() => {
              setShowSatellites(true);
              setShowSwaths(true);
              setShowHeatBloom(true);
            }}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] transition-all cursor-pointer ${
              showSatellites && showSwaths
                ? 'font-semibold text-white bg-[#16385c]/90 border border-sky-400/60 shadow-[0_0_10px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Globe className="w-3 h-3 text-sky-300" />
            <span>All Active</span>
          </button>

          {/* 2. Satellites */}
          <button
            onClick={() => {
              if (showSatellites && !showSwaths) {
                setShowSatellites(false);
              } else {
                setShowSatellites(true);
                setShowSwaths(false);
              }
            }}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] transition-all cursor-pointer ${
              showSatellites && !showSwaths
                ? 'font-semibold text-white bg-[#16385c]/90 border border-sky-400/60 shadow-[0_0_10px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Satellite className="w-3 h-3 text-sky-300" />
            <span>Satellites</span>
          </button>

          {/* 3. Swaths */}
          <button
            onClick={() => {
              if (!showSatellites && showSwaths) {
                setShowSwaths(false);
              } else {
                setShowSatellites(false);
                setShowSwaths(true);
              }
            }}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] transition-all cursor-pointer ${
              !showSatellites && showSwaths
                ? 'font-semibold text-white bg-[#16385c]/90 border border-sky-400/60 shadow-[0_0_10px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Radio className="w-3 h-3 text-sky-300" />
            <span>Swaths</span>
          </button>

          {/* 4. Clean Earth */}
          <button
            onClick={() => {
              setShowSatellites(false);
              setShowSwaths(false);
              setShowHeatBloom(false);
            }}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] transition-all cursor-pointer ${
              !showSatellites && !showSwaths
                ? 'font-semibold text-white bg-[#16385c]/90 border border-sky-400/60 shadow-[0_0_10px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <span>Clean Earth</span>
          </button>
        </div>
      </div>

      {/* Floating Left Filter Rail */}
      <SidebarFilters
        filters={filters}
        onChange={setFilters}
        loadedSiteCount={sitesData?.returned_count ?? sitesData?.features.length ?? 0}
        totalSiteCount={sitesData?.total_count ?? 0}
        modelACounts={loadedModelACounts}
        isLoading={sitesLoading}
        isOpen={sidebarOpen}
        onToggleOpen={() => setSidebarOpen(prev => !prev)}
      />

      {/* Floating Alert Feed (LIVE) */}
      {mode === 'LIVE' && alertsOpen && (
        <AlertRail
          alerts={alerts}
          onJumpToSite={handleJumpToSite}
          onAlertAcknowledged={handleAlertAcked}
          hasSelectedSite={Boolean(selectedSiteId)}
          onClose={() => setAlertsOpen(false)}
        />
      )}

      {/* Live Feed pill (LIVE) */}
      {mode === 'LIVE' && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 hidden md:flex items-center gap-3 px-4 py-1.5 rounded-full hud-glass-pill text-[11px] font-mono">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            <span className="text-white font-semibold tracking-wider font-mono">LIVE FEED</span>
          </div>
          <span className="w-px h-3 bg-white/10" />
          <span className="text-[#64748B] font-mono">NOAA-20 / VIIRS NRT</span>
          {alerts.length > 0 && (
            <>
              <span className="w-px h-3 bg-white/10" />
              <span className="chip chip-alert">{alerts.length} ACTIVE</span>
            </>
          )}
        </div>
      )}

      {/* Replay Scrubber (REPLAY) */}
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

      {/* Right Tactical Inspector — floating glass card overlay */}
      {selectedSiteId && (
        <div className="absolute top-14 right-4 bottom-4 z-30 flex flex-col justify-start pointer-events-auto">
          <SiteDrawer
            key={selectedSiteId}
            site={selectedSite?.site_id === selectedSiteId ? selectedSite : null}
            asOfDate={mode === 'REPLAY' ? replayDate : undefined}
            onRefreshSite={refreshSelectedSite}
            onClose={() => setSelectedSiteId(null)}
          />
        </div>
      )}

      <SystemLoadingScreen
        visible={!interfaceActivated}
        mapReady={mapReady}
        backendReady={telemetryReady}
        sitesReady={initialSitesRendered}
        error={telemetryReady ? sitesError : null}
        catchup={liveRuntime?.startup_catchup ?? null}
        connectionAttempt={startupAttempt}
        connectionDetail={startupConnectionDetail}
        retryDelayMs={startupRetryDelayMs}
      />
    </div>
  );
}
