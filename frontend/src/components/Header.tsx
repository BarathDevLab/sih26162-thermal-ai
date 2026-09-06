import {
  Activity,
  Layers,
  Radio,
  Eye,
  Box,
  RotateCcw
} from 'lucide-react';
import { HeliosLogo } from './Icons';
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
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500/20 via-orange-500/25 to-red-600/30 border border-amber-500/40 flex items-center justify-center shadow-[0_0_16px_rgba(245,158,11,0.25)] relative overflow-hidden group">
          <HeliosLogo className="w-6 h-6 text-amber-400 relative z-10 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
          <div className="absolute inset-0 bg-amber-400/10 animate-ping-slow pointer-events-none" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-white/10" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-black tracking-widest text-slate-100 uppercase font-mono">
              SIH26162 <span className="text-amber-400">HELIOS</span>
            </h1>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 font-mono border border-amber-500/30 font-bold tracking-wider">
              THERMAL AI
            </span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 font-mono border border-cyan-500/30 tracking-wider">
              OSIRIS COCKPIT
            </span>
          </div>
          <p className="text-[10.5px] text-slate-400 font-mono tracking-tight flex items-center gap-1.5">
            <span>Orbital Infrared Early-Warning Command Center</span>
            <span className="text-slate-600">&bull;</span>
            <span className="text-emerald-400">VIIRS NOAA-20/21</span>
          </p>
        </div>
      </div>

      {/* Center Telemetry Readouts */}
      <div className="hidden lg:flex items-center gap-4 bg-[#090e1a]/90 border border-white/10 py-1.5 px-3.5 rounded-lg tactical-glass shadow-lg">
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[11px] text-slate-400 font-mono">Sites:</span>
          <span className="text-xs font-mono font-bold text-white">
            {stats?.total_sites ? stats.total_sites.toLocaleString() : '79,365'}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-slate-400 font-mono">30d Active:</span>
          <span className="text-xs font-mono font-bold text-emerald-400">
            {stats?.active_sites_30d ? stats.active_sites_30d.toLocaleString() : '9,010'}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#f59e0b]" />
          <span className="text-[11px] text-slate-400 font-mono">Industrial:</span>
          <span className="text-xs font-mono font-bold text-amber-400">
            {stats?.model_a_counts?.['INDUSTRIAL'] ? stats.model_a_counts['INDUSTRIAL'].toLocaleString() : '808'}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-red-400 animate-pulse" />
          <span className="text-[11px] text-slate-400 font-mono">Active Alerts:</span>
          <span className="text-xs font-mono font-bold text-red-400">
            {activeAlertCount}
          </span>
        </div>

        <div className="h-3 w-px bg-white/10" />

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400 font-mono">Stack:</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-bold">
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
