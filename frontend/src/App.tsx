import { useState, useEffect, useCallback } from 'react';
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
  aClasses: ['INDUSTRIAL', 'NONINDUSTRIAL', 'UNKNOWN'],
  bStates: ['PERSISTENT', 'REACTIVATED', 'INTERMITTENT', 'NEW', 'DORMANT'],
  cStatuses: ['CRITICAL', 'ANOMALOUS', 'ELEVATED', 'NORMAL', 'INSUFFICIENT_HISTORY'],
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

export default function App() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [mode, setMode] = useState<'LIVE' | 'REPLAY'>('LIVE');
  const [replayDate, setReplayDate] = useState<string>('2025-06-01');
  const [is3D, setIs3D] = useState<boolean>(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  const [currentBBox, setCurrentBBox] = useState<[number, number, number, number] | undefined>(undefined);
  const [sitesData, setSitesData] = useState<SiteGeoJSONFeatureCollection | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState<SiteDetail | null>(null);

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [focusedCoordinates, setFocusedCoordinates] = useState<[number, number] | null>(null);

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
      } catch (err) {
        console.error('Telemetry bootstrap failed:', err);
      }
    };

    initTelemetry();
  }, []);

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
    try {
      if (mode === 'LIVE') {
        const data = await fetchSitesInBBox(currentBBox, { limit: 3000 });
        setSitesData(data);
      } else {
        const replayData = await fetchReplaySnapshot(replayDate, currentBBox, 3000);
        setSitesData({
          type: 'FeatureCollection',
          features: replayData.features,
          total_count: replayData.active_sites_count
        });
      }
    } catch (err) {
      console.error('Error fetching sites:', err);
    }
  }, [currentBBox, mode, replayDate]);

  useEffect(() => {
    loadSites();
  }, [loadSites]);

  // 4. Load Detailed Site Intelligence when a site is selected
  useEffect(() => {
    let active = true;

    if (!selectedSiteId) {
      setSelectedSite(null);
      return;
    }

    fetchSiteDetail(selectedSiteId)
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
  }, [selectedSiteId]);

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
        stats={stats}
        health={health}
        mode={mode}
        onModeChange={(m) => {
          setMode(m);
          setSelectedSiteId(null);
        }}
        is3D={is3D}
        onToggle3D={() => setIs3D(!is3D)}
        sseConnected={sseConnected}
        activeAlertCount={alerts.length}
      />

      {/* Main Workspace Cockpit */}
      <div className="flex flex-1 w-full h-[calc(100vh-3.5rem)] overflow-hidden relative">
        {/* Left Layer & Filter Rail */}
        <SidebarFilters
          filters={filters}
          onChange={setFilters}
          siteCount={sitesData?.total_count || 0}
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
              onDateChange={setReplayDate}
              activeCount={sitesData?.total_count || 0}
            />
          )}
        </div>

        {/* Right Site Intelligence Drawer */}
        {selectedSiteId && (
          <SiteDrawer
            site={selectedSite}
            onClose={() => setSelectedSiteId(null)}
          />
        )}
      </div>
    </div>
  );
}
