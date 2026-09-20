import { useEffect, useState, type CSSProperties } from 'react';
import {
  Cpu,
  Database,
  MapPinned,
  RadioTower,
  Radar,
  Satellite
} from 'lucide-react';
import type { StartupCatchupStatus } from '../types/api';

interface SystemLoadingScreenProps {
  visible: boolean;
  mapReady: boolean;
  backendReady: boolean;
  sitesReady: boolean;
  error?: string | null;
  catchup?: StartupCatchupStatus | null;
  connectionAttempt?: number;
  connectionDetail?: string;
  retryDelayMs?: number | null;
}

const HOTSPOTS = [
  [29, 52, 'orange'], [33, 47, 'orange'], [38, 58, 'cyan'],
  [43, 42, 'cyan'], [49, 49, 'cyan'], [54, 43, 'orange'],
  [59, 51, 'cyan'], [63, 45, 'cyan'], [67, 55, 'orange'],
  [72, 48, 'cyan'], [76, 57, 'cyan'], [81, 43, 'orange']
] as const;

const BACKEND_STAGES = [
  { phase: 'ACQUIRING_LOCK', label: 'DATABASE LOCK', icon: Database },
  { phase: 'VERIFYING_ARTIFACTS', label: 'ARTIFACT INTEGRITY', icon: Cpu },
  { phase: 'PLANNING_WINDOWS', label: 'FIRMS WINDOW PLAN', icon: Satellite },
  { phase: 'SYNCING_FIRMS', label: 'FIRMS INGESTION', icon: Satellite },
  { phase: 'REFRESHING_MODEL_B', label: 'MODEL B TEMPORAL STATE', icon: Database },
  { phase: 'HYDRATING_WORLDCOVER', label: 'WORLDCOVER CONTEXT', icon: MapPinned },
  { phase: 'MATERIALIZING_MODELS', label: 'MODEL A/C MATERIALIZE', icon: Cpu },
  { phase: 'VERIFYING_COVERAGE', label: 'COVERAGE AUDIT', icon: Radar },
  { phase: 'PUBLISHING_SNAPSHOT', label: 'SNAPSHOT PUBLISH', icon: Database },
  { phase: 'ACTIVATING_LIVE', label: 'LIVE AUTHORIZATION', icon: RadioTower }
] as const;

const EXIT_TRANSITION_MS = 900;

function formatDuration(seconds: number | null | undefined, fallback = 'CALCULATING') {
  if (seconds === null || seconds === undefined) return fallback;
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}H ${String(minutes).padStart(2, '0')}M`;
  if (minutes > 0) return `${minutes}M ${String(secs).padStart(2, '0')}S`;
  return `${secs}S`;
}

function formatLogTime(timestamp: string) {
  const value = new Date(timestamp);
  if (Number.isNaN(value.getTime())) return '--:--:--';
  return value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

export function SystemLoadingScreen({
  visible,
  mapReady,
  backendReady,
  sitesReady,
  error,
  catchup,
  connectionAttempt = 0,
  connectionDetail,
  retryDelayMs
}: SystemLoadingScreenProps) {
  const [mounted, setMounted] = useState(visible);
  const [mountedAt] = useState(() => Date.now());
  const [clockNow, setClockNow] = useState(() => Date.now());

  useEffect(() => {
    if (visible || !mounted) return;
    const exitTimer = window.setTimeout(() => setMounted(false), EXIT_TRANSITION_MS);
    return () => window.clearTimeout(exitTimer);
  }, [mounted, visible]);

  useEffect(() => {
    if (!mounted) return;
    const clock = window.setInterval(() => setClockNow(Date.now()), 1_000);
    return () => window.clearInterval(clock);
  }, [mounted]);

  if (!mounted) return null;

  const missionActive = Boolean(catchup?.running || catchup?.status === 'COMPLETED');
  const bootProgress = Math.max(
    3,
    (backendReady ? 45 : 0) + (mapReady ? 25 : 0) + (sitesReady ? 30 : 0)
  );
  const progress = missionActive
    ? Math.max(1, Math.min(100, Math.round(catchup?.progress_percent ?? 1)))
    : bootProgress;
  const phase = missionActive
    ? (catchup?.phase ?? 'MISSION_SYNC').replaceAll('_', ' ')
    : error
      ? 'VIEWPORT LINK DEGRADED'
      : !backendReady
        ? 'ESTABLISHING RUNTIME LINK'
        : !mapReady
          ? 'INITIALIZING MAP ENGINE'
          : !sitesReady
            ? 'RESOLVING SITE CLUSTERS'
            : 'OPERATIONAL PICTURE READY';
  const detail = missionActive
    ? catchup?.detail
    : error
      ? 'Initial site synchronization was interrupted. Retrying before interface activation.'
      : !backendReady
        ? connectionDetail ?? 'Waiting for the local backend to accept operational traffic.'
        : sitesReady
          ? 'All startup systems are ready. Transferring control to the command center.'
          : 'Building the operational picture from local runtime intelligence.';
  const target = catchup?.target_date ?? 'DETECTING';
  const currentWindow = catchup?.current_window_start
    ? `${catchup.current_window_start} / ${catchup.current_window_end ?? catchup.current_window_start}`
    : missionActive ? 'AWAITING FIRMS WINDOW' : 'INITIAL BOOT';
  const catchupPhase = catchup?.phase ?? 'ACQUIRING_LOCK';
  const activeBackendStage = catchupPhase === 'LIVE_ACTIVATED'
    ? BACKEND_STAGES.length
    : BACKEND_STAGES.findIndex((stage) => stage.phase === catchupPhase);
  const phaseProgress = Math.max(
    0,
    Math.min(100, Math.round(catchup?.phase_progress_percent ?? 0))
  );
  const stages = missionActive
    ? BACKEND_STAGES.map((stage, index) => {
        const ready = catchup?.status === 'COMPLETED' || index < activeBackendStage;
        const active = catchup?.running && index === activeBackendStage;
        return {
          ...stage,
          ready,
          active,
          progress: ready ? 100 : active ? phaseProgress : 0
        };
      })
    : [
        { label: 'BACKEND RUNTIME', ready: backendReady, active: !backendReady, progress: backendReady ? 100 : 0, icon: Database },
        { label: 'MAP ENGINE', ready: mapReady, active: backendReady && !mapReady, progress: mapReady ? 100 : 0, icon: MapPinned },
        { label: 'SITE CLUSTERS', ready: sitesReady, active: mapReady && backendReady && !sitesReady, progress: sitesReady ? 100 : 0, icon: Radar }
      ];
  const progressStyle = {
    '--mission-progress': `${progress * 3.6}deg`
  } as CSSProperties;
  const activityLog = catchup?.activity_log?.slice(-7) ?? [];
  const localElapsedSeconds = Math.max(0, Math.round((clockNow - mountedAt) / 1_000));
  const elapsed = formatDuration(
    catchup?.started_at ? catchup.elapsed_seconds : localElapsedSeconds,
    '0S'
  );
  const eta = catchup?.running
    ? catchup.estimated_remaining_seconds == null
      ? 'CALCULATING'
      : `~${formatDuration(catchup.estimated_remaining_seconds)}`
    : catchup?.status === 'COMPLETED' ? 'COMPLETE' : 'PENDING';

  return (
    <div
      className={`system-loading-screen${visible ? '' : ' is-exiting'}`}
      role="status"
      aria-live="polite"
    >
      <div className="system-loading-stars" aria-hidden="true" />
      <div className="system-loading-scanline" aria-hidden="true" />
      <div className="system-loading-frame" aria-hidden="true">
        <i /><i /><i /><i />
      </div>

      <header className="mission-loader-heading">
        <div className="mission-loader-title">
          <span>THERMAL EARTH OBSERVATION NETWORK</span>
          <b><Satellite size={15} /> ORBITAL SCAN <em>[ACTIVE]</em></b>
        </div>
        <div className="mission-loader-telemetry">
          <span>TARGET DATE <b>{target}</b></span>
          <span>ELAPSED <b>{elapsed}</b></span>
          <span>ETA <b>{eta}</b></span>
          <span>{missionActive ? 'FIRMS WINDOWS' : 'LINK ATTEMPT'} <b>{missionActive ? `${catchup?.completed_windows ?? 0}/${catchup?.total_windows ?? 0}` : connectionAttempt}</b></span>
          <span>DB INSERTED <b>{(catchup?.records_processed ?? 0).toLocaleString()}</b></span>
        </div>
      </header>

      <main className="mission-earth-stage">
        <div className="mission-data-beam mission-data-beam-orange" aria-hidden="true" />
        <div className="mission-data-beam mission-data-beam-cyan" aria-hidden="true" />
        <svg className="mission-earth" viewBox="0 0 800 800" aria-hidden="true">
          <defs>
            <radialGradient id="earthFill" cx="47%" cy="42%" r="58%">
              <stop offset="0" stopColor="#123140" stopOpacity=".6" />
              <stop offset=".68" stopColor="#06131d" stopOpacity=".88" />
              <stop offset="1" stopColor="#01060b" />
            </radialGradient>
            <filter id="cyanGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <clipPath id="earthClip"><circle cx="400" cy="400" r="325" /></clipPath>
          </defs>
          <circle className="earth-atmosphere earth-atmosphere-wide" cx="400" cy="400" r="342" />
          <circle className="earth-atmosphere" cx="400" cy="400" r="329" />
          <circle className="earth-body" cx="400" cy="400" r="325" fill="url(#earthFill)" />
          <g className="earth-grid" clipPath="url(#earthClip)">
            <ellipse cx="400" cy="400" rx="325" ry="92" />
            <ellipse cx="400" cy="400" rx="325" ry="184" />
            <ellipse cx="400" cy="400" rx="325" ry="270" />
            <ellipse cx="400" cy="400" rx="92" ry="325" />
            <ellipse cx="400" cy="400" rx="184" ry="325" />
            <ellipse cx="400" cy="400" rx="270" ry="325" />
            <path d="M75 400h650M92 292h616M92 508h616" />
          </g>
          <g className="earth-land" clipPath="url(#earthClip)">
            <path d="M138 225l36-50 73-34 69 8 36 28 66 4 23 33-35 26-60 6-37 28-54-12-31 29-46-11-13-32z" />
            <path d="M192 309l56-23 58 17 39 57-15 40 19 50-32 56-25 96-44-33-19-68-36-63-27-72z" />
            <path d="M367 238l35-30 77 5 51-34 113 10 40 46-27 37-75 4-52 27-7 54-40 14-43-39-68-9-31-45z" />
            <path d="M422 340l51-22 56 25 22 48-33 33-33 77-45 62-32-78-31-57 12-53z" />
            <path d="M544 461l37-35 49 18 21 42-35 26-21-26z" />
            <path d="M610 535l59-2 35 42-26 34-62-17-29-31z" />
          </g>
          <g className="earth-orbit earth-orbit-cyan">
            <ellipse cx="400" cy="400" rx="386" ry="190" transform="rotate(-15 400 400)" />
          </g>
          <g className="earth-orbit earth-orbit-orange">
            <ellipse cx="400" cy="400" rx="380" ry="145" transform="rotate(23 400 400)" />
          </g>
        </svg>

        <div className="mission-hotspots" aria-hidden="true">
          {HOTSPOTS.map(([left, top, color], index) => (
            <i
              className={`mission-hotspot mission-hotspot-${color}`}
              key={`${left}-${top}`}
              style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${index * -0.17}s` }}
            />
          ))}
        </div>

        <div className="mission-progress-radar" style={progressStyle}>
          <div className="mission-progress-sweep" />
          <div className="mission-progress-core">
            <strong>{progress}%</strong>
            <span>STACK READY</span>
          </div>
        </div>
      </main>

      <aside className="mission-stage-rail" aria-label="Backend setup stages">
        <h2>{missionActive ? 'BACKEND SETUP SEQUENCE' : 'INTERFACE BOOT SEQUENCE'}</h2>
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          return (
            <div className={stage.ready ? 'is-ready' : stage.active ? 'is-active' : ''} key={stage.label}>
              <span className="mission-stage-index">{String(index + 1).padStart(2, '0')}</span>
              <Icon size={12} />
              <span className="mission-stage-name">{stage.label}</span>
              <b>{stage.ready ? 'COMPLETE' : stage.active ? 'RUNNING' : 'QUEUED'}</b>
              <div className="mission-stage-progress">
                <i style={{ width: `${stage.progress}%` }} />
              </div>
              <em>{stage.progress}%</em>
            </div>
          );
        })}
      </aside>

      <aside className="mission-activity-log" aria-label="Live startup activity">
        <div className="mission-activity-heading">
          <span>MISSION ACTIVITY</span>
          <b>{catchup?.running ? 'LIVE' : backendReady ? 'LINKED' : 'WAITING'}</b>
        </div>
        <div className="mission-activity-timing">
          <span>ELAPSED <b>{elapsed}</b></span>
          <span>EST. REMAINING <b>{eta}</b></span>
          {catchup?.progress_rate_percent_per_minute != null && (
            <span>RATE <b>{catchup.progress_rate_percent_per_minute.toFixed(2)}%/MIN</b></span>
          )}
        </div>
        <div className="mission-activity-events">
          {activityLog.length > 0 ? activityLog.map((event, index) => (
            <div className={`is-${event.level.toLowerCase()}`} key={`${event.timestamp}-${index}`}>
              <time>{formatLogTime(event.timestamp)}</time>
              <span>{event.phase.replaceAll('_', ' ')}</span>
              <p>{event.message}</p>
            </div>
          )) : (
            <div className="is-info">
              <time>--:--:--</time>
              <span>RUNTIME LINK</span>
              <p>{connectionDetail ?? 'Waiting for backend startup telemetry.'}</p>
            </div>
          )}
        </div>
      </aside>

      <section className="mission-loader-footer">
        <div className="mission-loader-legend">
          <b>DATA CHANNELS</b>
          <span><i className="legend-orange" /> FIRMS THERMAL</span>
          <span><i className="legend-cyan" /> INDUSTRIAL INTELLIGENCE</span>
        </div>
        <div className="mission-loader-operation">
          <h1>{phase}</h1>
          <div className="mission-loader-progress" aria-label={`${progress}% initialized`}>
            <span style={{ width: `${progress}%` }} />
          </div>
          <p>{detail}</p>
          <small>
            {catchup?.current_source ? `${catchup.current_source} // ` : ''}
            {!missionActive && !backendReady && retryDelayMs
              ? `LOCAL API // RETRY ${(retryDelayMs / 1_000).toFixed(1)}S`
              : currentWindow}
          </small>
          {missionActive && (
            <div className="mission-loader-live-metrics">
              <span>FETCHED <b>{(catchup?.records_fetched ?? 0).toLocaleString()}</b></span>
              <span>UNIQUE <b>{(catchup?.records_unique ?? 0).toLocaleString()}</b></span>
              <span>INSERTED <b>{(catchup?.records_processed ?? 0).toLocaleString()}</b></span>
              <span>REVISED <b>{(catchup?.records_revised ?? 0).toLocaleString()}</b></span>
            </div>
          )}
        </div>
        <div className="mission-loader-counters">
          {catchup?.phase === 'REFRESHING_MODEL_B' ? (
            <span>MODEL B SITES <b>{catchup.model_b_processed_sites}/{catchup.model_b_total_sites}</b></span>
          ) : catchup?.phase === 'HYDRATING_WORLDCOVER' ? (
            <span>WORLDCOVER SITES <b>{catchup.worldcover_processed_sites}/{catchup.worldcover_total_sites}</b></span>
          ) : (
            <span>A/C SITES <b>{catchup?.processed_sites ?? 0}/{catchup?.total_sites ?? 0}</b></span>
          )}
          {catchup?.worldcover_current_tile && (
            <span>ACTIVE TILE <b>{catchup.worldcover_current_tile}</b></span>
          )}
          <span>PROMOTED / ALERTS <b>{catchup?.promoted_sites ?? 0} / {catchup?.alerts_generated ?? 0}</b></span>
          <span>MISSION <b>{catchup?.status ?? (error ? 'DEGRADED' : 'BOOTING')}</b></span>
        </div>
      </section>
    </div>
  );
}
