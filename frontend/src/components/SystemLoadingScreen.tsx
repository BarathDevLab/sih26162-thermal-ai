import type { CSSProperties } from 'react';
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
}

const HOTSPOTS = [
  [29, 52, 'orange'], [33, 47, 'orange'], [38, 58, 'cyan'],
  [43, 42, 'cyan'], [49, 49, 'cyan'], [54, 43, 'orange'],
  [59, 51, 'cyan'], [63, 45, 'cyan'], [67, 55, 'orange'],
  [72, 48, 'cyan'], [76, 57, 'cyan'], [81, 43, 'orange']
] as const;

export function SystemLoadingScreen({
  visible,
  mapReady,
  backendReady,
  sitesReady,
  error,
  catchup
}: SystemLoadingScreenProps) {
  if (!visible) return null;

  const missionActive = Boolean(catchup?.running || catchup?.status === 'COMPLETED');
  const completed = [mapReady, backendReady, sitesReady].filter(Boolean).length;
  const bootProgress = error ? 100 : Math.max(8, Math.round((completed / 3) * 100));
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
          : 'RESOLVING SITE CLUSTERS';
  const detail = missionActive
    ? catchup?.detail
    : error
      ? 'Map interface available; the latest site viewport could not be synchronized.'
      : 'Building the operational picture from local runtime intelligence.';
  const target = catchup?.target_date ?? 'DETECTING';
  const currentWindow = catchup?.current_window_start
    ? `${catchup.current_window_start} / ${catchup.current_window_end ?? catchup.current_window_start}`
    : missionActive ? 'AWAITING FIRMS WINDOW' : 'INITIAL BOOT';
  const stages = missionActive
    ? [
        { label: 'FIRMS INGEST', readyAt: 70, activeFrom: 1, icon: Satellite },
        { label: 'MODEL B STATE', readyAt: 78, activeFrom: 70, icon: Database },
        { label: 'A/C MATERIALIZE', readyAt: 95, activeFrom: 78, icon: Cpu },
        { label: 'LIVE AUTHORITY', readyAt: 100, activeFrom: 95, icon: RadioTower }
      ]
    : [
        { label: 'MAP ENGINE', ready: mapReady, icon: MapPinned },
        { label: 'RUNTIME LINK', ready: backendReady, icon: Database },
        { label: 'SITE CLUSTERS', ready: sitesReady, icon: Radar }
      ];
  const progressStyle = {
    '--mission-progress': `${progress * 3.6}deg`
  } as CSSProperties;

  return (
    <div className="system-loading-screen" role="status" aria-live="polite">
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
          <span>FIRMS WINDOWS <b>{catchup?.completed_windows ?? 0}/{catchup?.total_windows ?? 0}</b></span>
          <span>DB RECORDS <b>{(catchup?.records_processed ?? 0).toLocaleString()}</b></span>
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
            <span>ANALYZED</span>
          </div>
        </div>
      </main>

      <aside className="mission-stage-rail" aria-label="Startup stages">
        {stages.map((stage) => {
          const ready = 'ready' in stage ? stage.ready : progress >= stage.readyAt;
          const active = 'activeFrom' in stage && !ready && progress >= stage.activeFrom;
          const Icon = stage.icon;
          return (
            <div className={ready ? 'is-ready' : active ? 'is-active' : ''} key={stage.label}>
              <Icon size={13} />
              <span>{stage.label}</span>
              <b>{ready ? 'SECURED' : active ? 'EXECUTING' : 'QUEUED'}</b>
            </div>
          );
        })}
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
          <small>{currentWindow}</small>
        </div>
        <div className="mission-loader-counters">
          <span>A/C SITES <b>{catchup?.processed_sites ?? 0}/{catchup?.total_sites ?? 0}</b></span>
          <span>MISSION <b>{catchup?.status ?? (error ? 'DEGRADED' : 'BOOTING')}</b></span>
        </div>
      </section>
    </div>
  );
}
