import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Globe, Satellite, Radio } from 'lucide-react';
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
  const sitesRequestId = useRef(0);
  const sitesAbortController = useRef<AbortController | null>(null);
  const sitesCache = useRef<Map<string, SiteGeoJSONFeatureCollection>>(new Map());
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

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#02040a] text-slate-100 select-none font-sans">
      {/* Full-bleed map canvas covers the entire screen */}
      <div className="absolute inset-0">
        <ErrorBoundary fallbackTitle="Tactical Map Rendering Error">
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
          />
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
            site={selectedSite?.site_id === selectedSiteId ? selectedSite : null}
            asOfDate={mode === 'REPLAY' ? replayDate : undefined}
            onRefreshSite={refreshSelectedSite}
            onClose={() => setSelectedSiteId(null)}
          />
        </div>
      )}
    </div>
  );
}
