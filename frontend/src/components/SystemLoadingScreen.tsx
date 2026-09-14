import {
  Cpu,
  Database,
  MapPinned,
  RadioTower,
  Radar,
  Satellite,
  ShieldCheck
} from 'lucide-react';
import type { StartupCatchupStatus } from '../types/api';

interface SystemLoadingScreenProps {
  visible: boolean;
  mapReady: boolean;
  backendReady: boolean;
  sitesReady: boolean;
  error?: string | null;
  catchup?: StartupCatchupStatus | null;
}

export function SystemLoadingScreen({
  visible,
  mapReady,
  backendReady,
  sitesReady,
  error,
  catchup
}: SystemLoadingScreenProps) {
  if (!visible) return null;

  const missionActive = Boolean(
    catchup?.running || catchup?.status === 'COMPLETED'
  );
  const completed = [mapReady, backendReady, sitesReady].filter(Boolean).length;
  const bootProgress = error ? 100 : Math.max(8, Math.round((completed / 3) * 100));
  const progress = missionActive
    ? Math.max(1, Math.min(100, catchup?.progress_percent ?? 1))
    : bootProgress;
  const bootStages = [
    { label: 'MAP ENGINE', ready: mapReady, icon: MapPinned },
    { label: 'RUNTIME LINK', ready: backendReady, icon: Database },
    { label: 'SITE CLUSTERS', ready: sitesReady, icon: Radar }
  ];
  const missionStages = [
    { label: 'FIRMS SYNC', readyAt: 70, activeFrom: 1, icon: Satellite },
    { label: 'MODEL B STATE', readyAt: 78, activeFrom: 70, icon: Database },
    { label: 'MODEL A/C STACK', readyAt: 95, activeFrom: 78, icon: Cpu },
    { label: 'LIVE AUTH', readyAt: 100, activeFrom: 95, icon: RadioTower }
  ];
  const dateRange = catchup?.target_date
    ? `${catchup.source_date ?? '2026-01-01'} → ${catchup.target_date}`
    : 'CALCULATING';
  const windowRange = catchup?.current_window_start
    ? `${catchup.current_window_start} → ${catchup.current_window_end ?? catchup.current_window_start}`
    : 'AWAITING WINDOW';

  return (
    <div className="system-loading-screen" role="status" aria-live="polite">
      <div className="system-loading-grid" />
      <div className="system-loading-scanline" />
      <section className="system-loading-panel">
        <div className="system-loading-emblem">
          <ShieldCheck size={28} strokeWidth={1.5} />
        </div>
        <p className="system-loading-kicker">
          {missionActive ? 'MISSION UPDATE // OPERATION CURRENT STACK' : 'SIH26162 // THERMAL AI'}
        </p>
        <h1>
          {missionActive
            ? 'SYNCHRONIZING OPERATIONAL INTELLIGENCE'
            : error
              ? 'INTERFACE ONLINE'
              : 'INITIALIZING COMMAND CENTER'}
        </h1>
        <p className="system-loading-copy">
          {missionActive
            ? catchup?.detail
            : error
            ? 'The map interface is available, but the latest site viewport could not be synchronized.'
            : 'Establishing runtime telemetry and building the first spatial cluster index.'}
        </p>

        <div className="system-loading-progress" aria-label={`${progress}% initialized`}>
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="system-loading-progress-labels">
          <span>{missionActive ? (catchup?.phase ?? 'MISSION_SYNC').replaceAll('_', ' ') : 'BOOT SEQUENCE'}</span>
          <strong>{progress}%</strong>
        </div>

        {missionActive ? (
          <>
            <div className="system-loading-mission-grid">
              <div><span>DATA PERIOD</span><b>{dateRange}</b></div>
              <div><span>ACTIVE WINDOW</span><b>{windowRange}</b></div>
              <div>
                <span>FIRMS WINDOWS</span>
                <b>{catchup?.completed_windows ?? 0}/{catchup?.total_windows ?? 0}</b>
              </div>
              <div>
                <span>A/C SITES</span>
                <b>{catchup?.processed_sites ?? 0}/{catchup?.total_sites ?? 0}</b>
              </div>
              <div><span>DB RECORDS</span><b>{(catchup?.records_processed ?? 0).toLocaleString()}</b></div>
              <div><span>MISSION STATE</span><b>{catchup?.status ?? 'RUNNING'}</b></div>
            </div>
            <div className="system-loading-stages system-loading-mission-stages">
              {missionStages.map(({ label, readyAt, activeFrom, icon: Icon }) => {
                const ready = progress >= readyAt;
                const active = !ready && progress >= activeFrom;
                return (
                  <div className={ready ? 'is-ready' : active ? 'is-active' : ''} key={label}>
                    <Icon size={14} />
                    <span>{label}</span>
                    <b>{ready ? 'SECURED' : active ? 'EXECUTING' : 'QUEUED'}</b>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="system-loading-stages">
            {bootStages.map(({ label, ready, icon: Icon }) => (
              <div className={ready ? 'is-ready' : ''} key={label}>
                <Icon size={14} />
                <span>{label}</span>
                <b>{ready ? 'READY' : 'SYNC'}</b>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
