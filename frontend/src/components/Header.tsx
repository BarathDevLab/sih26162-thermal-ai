import {
  Activity,
  BellRing,
  Box,
  Database,
  Eye,
  Layers3,
  Radio,
  RotateCcw
} from 'lucide-react';
import { HeliosLogo } from './Icons';
import type { SystemStats, HealthCheck } from '../types/api';

interface HeaderProps {
  stats: SystemStats | null;
  health: HealthCheck | null;
  liveAvailable: boolean;
  mode: 'LIVE' | 'REPLAY';
  onModeChange: (m: 'LIVE' | 'REPLAY') => void;
  is3D: boolean;
  onToggle3D: () => void;
  sseConnected: boolean;
  activeAlertCount: number | null;
}

function telemetryValue(value: number | undefined): string {
  return value === undefined ? '—' : value.toLocaleString();
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  health,
  liveAvailable,
  mode,
  onModeChange,
  is3D,
  onToggle3D,
  sseConnected,
  activeAlertCount
}) => {
  const modelVersion = health?.active_models?.A_CORE || 'UNAVAILABLE';
  const healthTone = liveAvailable ? 'emerald' : health ? 'amber' : 'slate';

  return (
    <header className="command-header">
      <div className="command-brand">
        <div className="brand-mark" aria-hidden="true">
          <HeliosLogo className="w-7 h-7" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="brand-title">HELIOS</h1>
            <span className="brand-divider" />
            <span className="brand-code">SIH26162</span>
          </div>
          <p className="brand-subtitle">INDUSTRIAL THERMAL INTELLIGENCE</p>
        </div>
      </div>

      <div className="header-telemetry" aria-label="System telemetry">
        <div className="telemetry-cell">
          <Layers3 className="telemetry-icon text-cyan-300" />
          <span className="telemetry-label">MONITORED SITES</span>
          <strong>{telemetryValue(stats?.total_sites)}</strong>
        </div>
        <div className="telemetry-cell">
          <Activity className="telemetry-icon text-emerald-300" />
          <span className="telemetry-label">ACTIVE / 30D</span>
          <strong className="text-emerald-300">{telemetryValue(stats?.active_sites_30d)}</strong>
        </div>
        <div className="telemetry-cell">
          <span className="status-pip bg-amber-400 shadow-[0_0_8px_#f59e0b]" />
          <span className="telemetry-label">INDUSTRIAL</span>
          <strong className="text-amber-300">{telemetryValue(stats?.model_a_counts.INDUSTRIAL)}</strong>
        </div>
        <div className="telemetry-cell">
          <BellRing className={`telemetry-icon ${activeAlertCount ? 'text-rose-400' : 'text-slate-500'}`} />
          <span className="telemetry-label">OPEN ALERTS</span>
          <strong className={activeAlertCount ? 'text-rose-300' : ''}>
            {activeAlertCount === null ? '—' : activeAlertCount}
          </strong>
        </div>
        <div className="telemetry-cell telemetry-stack">
          <Database className="telemetry-icon text-slate-500" />
          <span className="telemetry-label">A-CORE</span>
          <strong title={modelVersion}>{modelVersion}</strong>
        </div>
      </div>

      <div className="header-actions">
        <button
          onClick={onToggle3D}
          className={`hud-button ${is3D ? 'hud-button-active' : ''}`}
          title="Toggle globe perspective and FRP elevation"
        >
          <Box className="w-3.5 h-3.5" />
          <span>{is3D ? '3D' : '2D'}</span>
        </button>

        <div className="mode-switch" aria-label="Operating mode">
          <button
            onClick={() => onModeChange('LIVE')}
            disabled={!liveAvailable}
            title={liveAvailable ? 'Show the current operational snapshot' : `Live mode blocked: ${health?.status || 'READINESS UNKNOWN'}`}
            className={mode === 'LIVE' ? 'mode-live-active' : ''}
          >
            <Eye className="w-3 h-3" />
            LIVE
          </button>
          <button
            onClick={() => onModeChange('REPLAY')}
            className={mode === 'REPLAY' ? 'mode-replay-active' : ''}
          >
            <RotateCcw className="w-3 h-3" />
            REPLAY
          </button>
        </div>

        <div
          className={`connection-state connection-${healthTone}`}
          title={mode === 'REPLAY' ? 'Historical replay mode' : liveAvailable ? (sseConnected ? 'Connected to the live alert stream' : 'Reconnecting to alert stream') : `Live mode blocked: ${health?.status || 'READINESS UNKNOWN'}`}
        >
          <Radio className="w-3.5 h-3.5" />
          <span>
            {mode === 'REPLAY' ? 'HISTORICAL' : !liveAvailable ? 'NOT READY' : sseConnected ? 'STREAM ONLINE' : 'CONNECTING'}
          </span>
        </div>
      </div>
    </header>
  );
};
