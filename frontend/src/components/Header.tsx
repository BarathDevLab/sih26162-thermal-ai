import {
  Flame,
  Activity,
  Layers,
  Radio,
  Eye,
  Box,
  RotateCcw
} from 'lucide-react';
import type { SystemStats, HealthCheck } from '../types/api';

interface HeaderProps {
  stats: SystemStats | null;
  health: HealthCheck | null;
  mode: 'LIVE' | 'REPLAY';
  onModeChange: (m: 'LIVE' | 'REPLAY') => void;
  is3D: boolean;
  onToggle3D: () => void;
  sseConnected: boolean;
  activeAlertCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  health,
  mode,
  onModeChange,
  is3D,
  onToggle3D,
  sseConnected,
  activeAlertCount
}) => {
  const modelVersion = health?.active_models?.['model_a'] || '2026-09-04-r1';

  return (
    <header className="h-14 bg-[#070a12] border-b border-white/10 px-4 flex items-center justify-between select-none z-30 relative shrink-0">
      {/* Brand & Mission Identifier */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-gradient-to-br from-amber-500/20 to-orange-600/30 border border-amber-500/40 flex items-center justify-center shadow-[0_0_12px_rgba(245,158,11,0.25)]">
          <Flame className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-wider text-slate-100 uppercase">
              SIH26162 OSIRIS
            </h1>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-mono border border-amber-500/30">
              THERMAL AI
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-mono tracking-tight">
            Industrial Thermal Intelligence Platform
          </p>
        </div>
      </div>

      {/* Center Telemetry Readouts */}
      <div className="hidden lg:flex items-center gap-4 bg-[#0c1322] border border-white/5 py-1 px-3 rounded-md">
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[11px] text-slate-400">Total Sites:</span>
          <span className="text-xs font-mono font-bold text-slate-200">
            {stats?.total_sites ? stats.total_sites.toLocaleString() : '79,365'}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-slate-400">30d Active:</span>
          <span className="text-xs font-mono font-bold text-emerald-400">
            {stats?.active_sites_30d ? stats.active_sites_30d.toLocaleString() : '9,010'}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-red-400" />
          <span className="text-[11px] text-slate-400">Active Alerts:</span>
          <span className="text-xs font-mono font-bold text-red-400">
            {activeAlertCount}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400">Stack:</span>
          <span className="text-[11px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {modelVersion}
          </span>
        </div>
      </div>

      {/* Right Controls: 2D/3D, Mode, SSE Pulse */}
      <div className="flex items-center gap-2.5">
        {/* 2D / 3D Geospatial Toggle */}
        <button
          onClick={onToggle3D}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-all ${
            is3D
              ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.3)]'
              : 'bg-[#111a2e] border-white/10 text-slate-300 hover:border-white/20'
          }`}
          title="Toggle 2D Tactical View vs 3D Perspective with FRP Spikes"
        >
          <Box className="w-3.5 h-3.5" />
          <span>{is3D ? '3D PERSPECTIVE' : '2D MAP'}</span>
        </button>

        {/* Operating Mode Switcher */}
        <div className="flex bg-[#0c1322] p-0.5 rounded border border-white/10">
          <button
            onClick={() => onModeChange('LIVE')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold tracking-wide transition-colors ${
              mode === 'LIVE'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Eye className="w-3 h-3" />
            <span>LIVE</span>
          </button>
          <button
            onClick={() => onModeChange('REPLAY')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold tracking-wide transition-colors ${
              mode === 'REPLAY'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <RotateCcw className="w-3 h-3" />
            <span>REPLAY</span>
          </button>
        </div>

        {/* Real-Time SSE Stream Heartbeat Indicator */}
        <div
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#0c1322] border border-white/10"
          title={sseConnected ? 'Connected to live SSE alert stream' : 'Reconnecting to stream...'}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              sseConnected
                ? 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse'
                : 'bg-amber-400'
            }`}
          />
          <span className="text-[10px] font-mono text-slate-300">
            {sseConnected ? 'ONLINE' : 'CONNECTING'}
          </span>
        </div>
      </div>
    </header>
  );
};
