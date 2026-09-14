import React, { useState, useRef, useEffect } from 'react';
import { Bell, Settings, Layers, Radio, Satellite, Volume2, VolumeX, X } from 'lucide-react';
import type { HealthCheck } from '../types/api';

interface HeaderProps {
  health: HealthCheck | null;
  mode: 'LIVE' | 'REPLAY';
  onModeChange: (m: 'LIVE' | 'REPLAY') => void;
  is3D: boolean;
  onToggle3D: () => void;
  basemapMode: 'SATELLITE' | 'DARK';
  onBasemapChange: (m: 'SATELLITE' | 'DARK') => void;
  show3DColumns: boolean;
  onToggle3DColumns: () => void;
  showSatellites?: boolean;
  onToggleSatellites?: () => void;
  showSwaths?: boolean;
  onToggleSwaths?: () => void;
  showHeatBloom?: boolean;
  onToggleHeatBloom?: () => void;
  sseConnected: boolean;
  activeAlertCount: number | null;
  siteCount?: number;
  activeRate?: string;
  industrialCount?: number;
  alertCount?: number;
  sidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  alertsOpen?: boolean;
  onToggleAlerts?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  mode,
  onModeChange,
  is3D,
  onToggle3D,
  basemapMode,
  onBasemapChange,
  show3DColumns,
  onToggle3DColumns,
  showSatellites = true,
  onToggleSatellites,
  showSwaths = true,
  onToggleSwaths,
  showHeatBloom = true,
  onToggleHeatBloom,
  sseConnected,
  activeAlertCount,
  siteCount = 42,
  activeRate = '99.98%',
  industrialCount = 1408,
  alertCount = 3,
  alertsOpen = true,
  onToggleAlerts
}) => {
  const [settingsOpen, setSettingsOpen] = useState<boolean>(false);
  const [audioTelemetry, setAudioTelemetry] = useState<boolean>(true);
  const settingsRef = useRef<HTMLDivElement>(null);

  const liveAvailable = health?.status === 'READY' || health?.status === 'DEGRADED_PRITHVI_UNAVAILABLE';

  // Close settings popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    };
    if (settingsOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [settingsOpen]);

  return (
    <header
      className="w-full flex items-center justify-between pointer-events-none select-none px-4 py-2.5 z-30 relative"
      data-purpose="tactical-stitch-header"
    >
      {/* ── Left: Sidebar Toggle + SIH26162 and Tagline in unified tactical glass capsule ── */}
      <div className="flex items-center gap-2.5 p-1 px-2.5 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md font-mono shadow-[0_4px_15px_rgba(0,0,0,0.5)] pointer-events-auto shrink-0">
        {/* Mission Brand Insignia Emblem */}
        <div className="flex items-center justify-center w-7 h-7 rounded-full border border-sky-400/40 bg-[#16385c]/60 text-[#89E5FC] shadow-[0_0_10px_rgba(56,189,248,0.3)] shrink-0">
          <Satellite className="w-3.5 h-3.5 text-[#89E5FC]" />
        </div>

        <div className="flex flex-col select-none pr-1.5">
          <h1 className="text-xs font-black tracking-widest text-[#89E5FC] font-mono leading-tight">
            SIH26162
          </h1>
          <p className="text-[8px] tracking-widest text-[#64748B] font-mono uppercase font-semibold">
            AEROSPACE STRATEGIC TELEMETRY
          </p>
        </div>
      </div>

      {/* ── Center Cluster: Stats Capsule (Wide Screens) + View Switcher ── */}
      <div className="flex items-center gap-3 pointer-events-auto shrink-0">
        {/* Stats Capsule (Stitch Spec) */}
        <div className="hidden 2xl:flex items-center gap-2.5 px-3 py-1 rounded-full border border-sky-400/25 bg-[#070e1e]/85 backdrop-blur-md font-mono text-[10px] text-slate-400 shadow-[0_4px_15px_rgba(0,0,0,0.5)]">
          <span>SITES: <strong className="text-white font-bold">{siteCount}</strong></span>
          <span className="text-slate-600">·</span>
          <span>30D ACTIVE: <strong className="text-white font-bold">{activeRate}</strong></span>
          <span className="text-slate-600">·</span>
          <span>INDUSTRIAL: <strong className="text-white font-bold">{industrialCount.toLocaleString()}</strong></span>
          <span className="text-slate-600">·</span>
          <span className="flex items-center gap-1.5">
            <span>ALERTS:</span>
            <span className="px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[9px] font-bold">
              {alertCount} CRIT
            </span>
          </span>
        </div>

        {/* Projection Mode Capsule: [ 3D Globe | 2D Plane ] */}
        <div className="flex items-center gap-1 p-1 px-1.5 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md font-mono text-xs shadow-[0_4px_15px_rgba(0,0,0,0.5)]">
          <button
            onClick={() => {
              if (!is3D) onToggle3D();
            }}
            type="button"
            className={`px-3 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              is3D
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {is3D && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            )}
            <span>3D Globe</span>
          </button>

          <button
            onClick={() => {
              if (is3D) onToggle3D();
            }}
            type="button"
            className={`px-3 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              !is3D
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {!is3D && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            )}
            <span>2D Plane</span>
          </button>
        </div>

        {/* Basemap & Plumes Capsule: [ Satellite View | Black Canvas ] | [ 3D Plumes ] */}
        <div className="flex items-center gap-1.5 p-1 px-1.5 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md font-mono text-xs shadow-[0_4px_15px_rgba(0,0,0,0.5)]">
          <button
            onClick={() => onBasemapChange('SATELLITE')}
            type="button"
            className={`px-3 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              basemapMode === 'SATELLITE'
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {basemapMode === 'SATELLITE' && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            )}
            <span>Satellite View</span>
          </button>

          <button
            onClick={() => onBasemapChange('DARK')}
            type="button"
            className={`px-3 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              basemapMode === 'DARK'
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {basemapMode === 'DARK' && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            )}
            <span>Black Canvas</span>
          </button>

          {/* 3D Volumetric Plumes - only shown in 3D globe mode */}
          {is3D && (
            <>
              <span className="w-px h-3.5 bg-sky-400/30 mx-0.5" />
              <button
                onClick={onToggle3DColumns}
                type="button"
                className={`px-3 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
                  show3DColumns
                    ? 'text-[#89E5FC] bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {show3DColumns && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
                )}
                <span>3D Plumes</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Right Controls: LIVE / REPLAY + Bell + Settings ── */}
      <div className="flex items-center gap-2 pointer-events-auto shrink-0">
        {/* Mode Capsule: LIVE vs REPLAY */}
        <div className="flex items-center gap-1 p-1 px-1.5 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md font-mono text-xs shadow-[0_4px_15px_rgba(0,0,0,0.5)]">
          <button
            onClick={() => onModeChange('LIVE')}
            disabled={!liveAvailable}
            type="button"
            className={`px-3.5 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              mode === 'LIVE'
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : !liveAvailable
                ? 'text-[#475569] cursor-not-allowed'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {mode === 'LIVE' && (
              <span className={`w-1.5 h-1.5 rounded-full ${sseConnected ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-[#89E5FC] shadow-[0_0_6px_#89E5FC]'} animate-cyan-breathe`} />
            )}
            LIVE
          </button>
          <button
            onClick={() => onModeChange('REPLAY')}
            type="button"
            className={`px-3.5 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
              mode === 'REPLAY'
                ? 'text-white bg-[#16385c]/90 border border-sky-400/60 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {mode === 'REPLAY' && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] shadow-[0_0_6px_#89E5FC] animate-cyan-breathe" />
            )}
            REPLAY
          </button>
        </div>

        {/* Notifications Bell */}
        <button
          type="button"
          onClick={onToggleAlerts}
          aria-label="Notifications"
          title="Incident Alerts"
          className={`w-8 h-8 rounded-full border bg-[#070e1e]/85 backdrop-blur-md flex items-center justify-center transition-all cursor-pointer relative shadow-[0_4px_15px_rgba(0,0,0,0.5)] ${
            alertsOpen
              ? 'text-[#89E5FC] border-sky-400/70 bg-[#16385c]/90 shadow-[0_0_12px_rgba(56,189,248,0.35)]'
              : 'text-slate-300 hover:text-white border-sky-400/25 hover:border-sky-400/50 hover:bg-[#16385c]/50'
          }`}
        >
          <Bell className="w-3.5 h-3.5" />
          {(activeAlertCount ?? 0) > 0 && (
            <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_6px_#f43f5e] animate-pulse" />
          )}
        </button>

        {/* Settings Icon & Dropdown Popover */}
        <div className="relative" ref={settingsRef}>
          <button
            type="button"
            onClick={() => setSettingsOpen(!settingsOpen)}
            aria-label="System Settings"
            className={`w-8 h-8 rounded-full border bg-[#070e1e]/85 backdrop-blur-md flex items-center justify-center transition-all cursor-pointer shadow-[0_4px_15px_rgba(0,0,0,0.5)] ${
              settingsOpen
                ? 'text-[#89E5FC] border-sky-400/70 bg-[#16385c]/90 shadow-[0_0_12px_rgba(56,189,248,0.35)]'
                : 'text-slate-300 hover:text-white border-sky-400/25 hover:border-sky-400/50 hover:bg-[#16385c]/50'
            }`}
          >
            <Settings className={`w-3.5 h-3.5 transition-transform duration-300 ${settingsOpen ? 'rotate-90 text-[#89E5FC]' : ''}`} />
          </button>

          {/* Tactical Quick Settings Popover */}
          {settingsOpen && (
            <div className="absolute right-0 top-10 w-64 rounded-xl drawer-glass p-3 shadow-[0_12px_35px_rgba(0,0,0,0.9)] border border-sky-400/30 z-50 animate-in fade-in zoom-in-95 duration-150 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/10">
                <span className="text-[10px] font-bold text-sky-400 tracking-wider uppercase">
                  TACTICAL SETTINGS
                </span>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(false)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex flex-col gap-2.5">
                {/* Satellite Orbits Toggle */}
                {onToggleSatellites && (
                  <label className="flex items-center justify-between cursor-pointer group">
                    <span className="flex items-center gap-1.5 text-slate-300 group-hover:text-white">
                      <Satellite className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Satellite Orbits</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={showSatellites}
                      onChange={onToggleSatellites}
                      className="accent-sky-400 cursor-pointer"
                    />
                  </label>
                )}

                {/* Sensor Swaths Toggle */}
                {onToggleSwaths && (
                  <label className="flex items-center justify-between cursor-pointer group">
                    <span className="flex items-center gap-1.5 text-slate-300 group-hover:text-white">
                      <Radio className="w-3.5 h-3.5 text-amber-400" />
                      <span>Sensor Swaths</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={showSwaths}
                      onChange={onToggleSwaths}
                      className="accent-sky-400 cursor-pointer"
                    />
                  </label>
                )}

                {/* Heat Bloom Toggle */}
                {onToggleHeatBloom && (
                  <label className="flex items-center justify-between cursor-pointer group">
                    <span className="flex items-center gap-1.5 text-slate-300 group-hover:text-white">
                      <Layers className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Heat Bloom</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={showHeatBloom}
                      onChange={onToggleHeatBloom}
                      className="accent-sky-400 cursor-pointer"
                    />
                  </label>
                )}

                {/* Audio Telemetry Toggle */}
                <label className="flex items-center justify-between cursor-pointer group pt-1 border-t border-white/5">
                  <span className="flex items-center gap-1.5 text-slate-300 group-hover:text-white">
                    {audioTelemetry ? (
                      <Volume2 className="w-3.5 h-3.5 text-sky-400" />
                    ) : (
                      <VolumeX className="w-3.5 h-3.5 text-slate-500" />
                    )}
                    <span>Audio Chimes</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={audioTelemetry}
                    onChange={() => setAudioTelemetry(!audioTelemetry)}
                    className="accent-sky-400 cursor-pointer"
                  />
                </label>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
