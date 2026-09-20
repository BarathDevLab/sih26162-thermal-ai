import { useEffect, useState } from 'react';
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

const BACKEND_STAGES = [
  { phase: 'ACQUIRING_LOCK', label: 'DATABASE LOCK', icon: 'ph-database' },
  { phase: 'VERIFYING_ARTIFACTS', label: 'ARTIFACT INTEGRITY', icon: 'ph-cpu' },
  { phase: 'PLANNING_WINDOWS', label: 'FIRMS WINDOW PLAN', icon: 'ph-satellite' },
  { phase: 'SYNCING_FIRMS', label: 'FIRMS INGESTION', icon: 'ph-satellite' },
  { phase: 'REFRESHING_MODEL_B', label: 'MODEL B TEMPORAL STATE', icon: 'ph-database' },
  { phase: 'HYDRATING_WORLDCOVER', label: 'WORLDCOVER CONTEXT', icon: 'ph-map-pin' },
  { phase: 'MATERIALIZING_MODELS', label: 'MODEL A/C MATERIALIZE', icon: 'ph-cpu' },
  { phase: 'VERIFYING_COVERAGE', label: 'COVERAGE AUDIT', icon: 'ph-radar' },
  { phase: 'PUBLISHING_SNAPSHOT', label: 'SNAPSHOT PUBLISH', icon: 'ph-database' },
  { phase: 'ACTIVATING_LIVE', label: 'LIVE AUTHORIZATION', icon: 'ph-radio-tower' }
] as const;

const EXIT_TRANSITION_MS = 900;

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
          label: stage.label,
          ready,
          active,
          progress: ready ? 100 : active ? phaseProgress : 0,
          icon: stage.icon
        };
      })
    : [
        { label: 'BACKEND RUNTIME', ready: backendReady, active: !backendReady, progress: backendReady ? 100 : (connectionAttempt > 0 ? 25 : 0), icon: 'ph-database' },
        { label: 'MAP ENGINE', ready: mapReady, active: backendReady && !mapReady, progress: mapReady ? 100 : 0, icon: 'ph-globe-hemisphere-west' },
        { label: 'SITE CLUSTERS', ready: sitesReady, active: mapReady && backendReady && !sitesReady, progress: sitesReady ? 100 : 0, icon: 'ph-circles-three-plus' },
        { label: 'EPHEMERIS SOLVER', ready: sitesReady, active: false, progress: sitesReady ? 100 : 0, icon: 'ph-sliders-horizontal' },
        { label: 'RF TELEMETRY SOCKET', ready: sitesReady, active: false, progress: sitesReady ? 100 : 0, icon: 'ph-cpu' }
      ];

  const strokeDashoffset = 427.2 - (427.2 * (progress / 100));

  return (
    <div className={`fixed inset-0 z-[1000] h-screen w-screen text-slate-300 font-mono flex flex-col justify-between p-6 lg:p-8 overflow-hidden aerospace-grid selection:bg-cyan-400 selection:text-black bg-[#0e0e11] transition-all duration-700 ${visible ? 'opacity-100' : 'opacity-0 blur-md scale-105 pointer-events-none'}`}>
      <style>{`
        .aerospace-grid {
          background-size: 40px 40px;
          background-image: radial-gradient(circle, rgba(137, 229, 252, 0.12) 1px, transparent 1px);
        }
        .radar-sweep-beam {
          background: conic-gradient(from 0deg, rgba(137, 229, 252, 0.35) 0deg, rgba(137, 229, 252, 0.05) 55deg, transparent 75deg);
          border-radius: 50%;
        }
        .glow-cyan-filter {
          filter: drop-shadow(0 0 10px rgba(137, 229, 252, 0.65));
        }
        .glow-coral-filter {
          filter: drop-shadow(0 0 10px rgba(255, 107, 74, 0.7));
        }
      `}</style>
      
      {/* Reticle Corner Crosshairs & Outer Boundary */}
      <div className="pointer-events-none absolute inset-3 lg:inset-5 border border-cyan-400/10 rounded-sm">
        <div className="absolute -top-1 -left-1 w-3.5 h-3.5 border-t-2 border-l-2 border-[#89e5fc]"></div>
        <div className="absolute -top-1 -right-1 w-3.5 h-3.5 border-t-2 border-r-2 border-[#89e5fc]"></div>
        <div className="absolute -bottom-1 -left-1 w-3.5 h-3.5 border-b-2 border-l-2 border-[#89e5fc]"></div>
        <div className="absolute -bottom-1 -right-1 w-3.5 h-3.5 border-b-2 border-r-2 border-[#89e5fc]"></div>
      </div>
      
      {/* TOP HEADER */}
      <header className="relative z-10 flex flex-wrap justify-between items-start gap-4 px-2 pt-1 pb-3">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2.5">
            <span className="text-[10px] font-mono tracking-widest text-[#89e5fc]/60">SYS.LOC // 45.109.82.01</span>
          </div>
          <div className="flex items-center space-x-3">
            <div className="w-2.5 h-2.5 rounded-full bg-[#89e5fc] shadow-[0_0_12px_#89e5fc] animate-ping"></div>
            <h1 className="text-base md:text-xl font-sans font-semibold tracking-[0.2em] text-white uppercase">
              THERMAL EARTH OBSERVATION NETWORK
            </h1>
          </div>
          <div className="flex items-center space-x-3 text-xs tracking-wider pt-0.5">
            <div className="flex items-center space-x-1.5">
              <i className="ph-bold ph-crosshair-simple text-[#89e5fc] text-sm"></i>
              <span className="text-slate-400 font-mono text-[11px]">ORBITAL SCAN</span>
              <span className="text-[#38bdf8] font-bold text-[11px] tracking-widest ml-1">[{missionActive ? 'ACTIVE' : 'STANDBY'}]</span>
            </div>
            <span className="text-slate-600 font-mono">|</span>
            <span className="text-slate-400 font-mono text-[11px]">TELEMETRY STREAM: <span className="text-[#89e5fc] font-semibold">{error ? 'DEGRADED' : 'STABLE'}</span></span>
          </div>
        </div>
        <div className="text-right text-[11px] font-mono tracking-widest space-y-1 text-slate-400">
          <div className="flex justify-end gap-3">
            <span className="text-slate-500">TARGET DATE</span>
            <span className="text-[#89e5fc] font-bold">{target}</span>
          </div>
          <div className="flex justify-end gap-3">
            <span className="text-slate-500">LINK ATTEMPT</span>
            <span className="text-slate-200">{connectionAttempt}</span>
          </div>
          <div className="flex justify-end gap-3">
            <span className="text-slate-500">DB INSERTED</span>
            <span className="text-slate-200">{(catchup?.records_processed ?? 0).toLocaleString()}</span>
          </div>
          <div className="flex justify-end gap-3">
            <span className="text-slate-500">SYS REF</span>
            <span className="text-[#38bdf8] font-medium">NTRO-SAT-09</span>
          </div>
        </div>
      </header>

      {/* CENTRAL VISUALIZER */}
      <main className="relative z-10 flex-1 flex flex-col lg:flex-row items-center justify-center my-auto py-1">
        <div className="relative w-full max-w-[580px] lg:max-w-[620px] aspect-square flex items-center justify-center">
          <div className="absolute w-[420px] h-[420px] bg-[#38bdf8]/10 rounded-full blur-3xl pointer-events-none"></div>
          <div className="absolute w-56 h-56 bg-[#38bdf8]/5 rounded-full blur-2xl pointer-events-none"></div>
          <div className="absolute inset-2 md:inset-4 rounded-full border border-cyan-400/15 pointer-events-none"></div>
          <div className="absolute inset-8 md:inset-10 rounded-full border border-cyan-400/20 border-dashed animate-[spin_45s_linear_infinite] pointer-events-none"></div>
          <div className="absolute inset-14 md:inset-16 rounded-full border border-cyan-400/10 pointer-events-none"></div>
          
          <svg className="w-[88%] h-[88%] relative z-0" fill="none" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">
            <circle cx="250" cy="250" r="215" stroke="#89e5fc" strokeOpacity="0.3" strokeWidth="1.5"></circle>
            <circle cx="250" cy="250" r="175" stroke="#89e5fc" strokeDasharray="3 3" strokeOpacity="0.2"></circle>
            <ellipse cx="250" cy="250" rx="215" ry="85" stroke="#89e5fc" strokeOpacity="0.22" strokeWidth="1.2"></ellipse>
            <ellipse cx="250" cy="250" rx="215" ry="150" stroke="#89e5fc" strokeDasharray="4 4" strokeOpacity="0.2"></ellipse>
            <ellipse cx="250" cy="250" rx="85" ry="215" stroke="#89e5fc" strokeOpacity="0.22" strokeWidth="1.2"></ellipse>
            <ellipse cx="250" cy="250" rx="150" ry="215" stroke="#89e5fc" strokeDasharray="4 4" strokeOpacity="0.2"></ellipse>
            <line stroke="#89e5fc" strokeDasharray="2 4" strokeOpacity="0.3" x1="35" x2="465" y1="250" y2="250"></line>
            <line stroke="#89e5fc" strokeDasharray="2 4" strokeOpacity="0.3" x1="250" x2="250" y1="35" y2="465"></line>
            
            <g fill="rgba(137, 229, 252, 0.03)" stroke="#89e5fc" strokeDasharray="4 3" strokeOpacity="0.55" strokeWidth="1.4">
              <polygon points="210,130 240,110 280,125 330,120 370,140 380,180 340,210 320,180 290,200 270,180 255,200 250,250 220,270 200,220 180,190 205,160"></polygon>
              <polygon points="120,130 160,120 175,150 150,190 145,230 165,270 170,320 145,340 130,280 115,220 95,180 105,140"></polygon>
              <polygon points="340,280 380,270 410,290 395,330 360,325 335,300"></polygon>
            </g>
            
            <g transform="rotate(-26 250 250)">
              <ellipse cx="250" cy="250" opacity="0.8" rx="245" ry="92" stroke="#89e5fc" strokeDasharray="8 6" strokeWidth="1.5"></ellipse>
              <circle className="glow-cyan-filter animate-ping" cx="495" cy="250" fill="#89e5fc" r="4.5"></circle>
              <circle cx="495" cy="250" fill="#ffffff" r="3"></circle>
              <line opacity="0.75" stroke="#89e5fc" strokeWidth="0.8" x1="495" x2="435" y1="250" y2="220"></line>
              <text fill="#89e5fc" fontFamily="JetBrains Mono" fontSize="9" fontWeight="600" opacity="0.95" x="425" y="215">SAT-C1 [LEO]</text>
            </g>
            
            <g transform="rotate(30 250 250)">
              <ellipse cx="250" cy="250" opacity="0.8" rx="248" ry="96" stroke="#38bdf8" strokeDasharray="10 5" strokeWidth="1.5"></ellipse>
              <circle className="glow-cyan-filter" cx="4" cy="250" fill="#38bdf8" r="4.5"></circle>
              <circle cx="4" cy="250" fill="#ffffff" r="2.5"></circle>
              <line opacity="0.75" stroke="#38bdf8" strokeWidth="0.8" x1="4" x2="65" y1="250" y2="280"></line>
              <text fill="#38bdf8" fontFamily="JetBrains Mono" fontSize="9" fontWeight="600" opacity="0.95" x="35" y="296">FIRMS-IR [LOCK]</text>
            </g>
            
            <circle className="glow-cyan-filter animate-pulse" cx="270" cy="220" fill="#38bdf8" r="3.5"></circle>
            <circle className="glow-cyan-filter" cx="220" cy="180" fill="#89e5fc" r="2.5"></circle>
            <circle cx="150" cy="260" fill="#38bdf8" r="2.5"></circle>
            <circle className="glow-cyan-filter animate-ping" cx="360" cy="170" fill="#38bdf8" r="2.5"></circle>
          </svg>
          
          <div className="absolute inset-[14%] radar-sweep-beam animate-[spin_4.5s_linear_infinite] pointer-events-none opacity-30"></div>
          
          <div className="absolute z-20 flex flex-col items-center justify-center">
            <div className="relative w-36 h-36 md:w-44 md:h-44 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border border-cyan-400/30"></div>
              <div className="absolute inset-2.5 rounded-full border border-slate-700/50 border-dashed"></div>
              
              <svg className="w-full h-full -rotate-90" viewBox="0 0 160 160">
                <circle cx="80" cy="80" fill="transparent" r="68" stroke="#121b24" strokeWidth="7"></circle>
                <circle className="glow-cyan-filter transition-all duration-1000 ease-out" cx="80" cy="80" fill="transparent" r="68" stroke="#38bdf8" strokeDasharray="427.2" strokeDashoffset={strokeDashoffset} strokeLinecap="round" strokeWidth="7"></circle>
              </svg>
              
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center bg-[#0a1018]/90 rounded-full m-3 backdrop-blur-md border border-cyan-400/30 shadow-[0_0_24px_rgba(0,0,0,0.85)]">
                <span className="text-[9px] font-mono tracking-[0.2em] text-[#38bdf8] uppercase mb-0.5 font-medium">{catchup?.running ? 'ACTIVE' : 'INIT'}::{missionActive ? 'STAGE_02' : 'STAGE_01'}</span>
                <span className="text-3xl md:text-4xl font-sans font-extrabold text-white tracking-tight flex items-baseline">
                  {progress}<span className="text-[#38bdf8] text-lg font-bold ml-0.5">%</span>
                </span>
                <span className="text-[9px] md:text-[10px] font-mono tracking-[0.25em] text-[#89e5fc] uppercase mt-0.5 font-medium">{progress === 100 ? 'STACK READY' : 'WORKING'}</span>
                <span className="inline-block w-8 h-[2px] bg-[#38bdf8]/50 mt-1.5 opacity-80"></span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT HUD MODULE */}
        <section aria-label="Interface Boot Sequence" className="w-full lg:w-[380px] mt-6 lg:mt-0 lg:absolute lg:right-8 lg:top-1/2 lg:-translate-y-1/2 z-20">
          <div className="border border-white/10 backdrop-blur-xl rounded-xl p-4 md:p-5 relative overflow-hidden shadow-[0_12px_40px_rgba(0,0,0,0.75)] bg-[#131316]">
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-[#38bdf8]/60"></div>
            
            <div className="flex items-center justify-between pb-3.5 mb-3.5 border-b border-white/10">
              <div className="flex items-center space-x-2.5">
                <div className="w-3.5 h-3.5 rounded border border-[#89e5fc]/60 flex items-center justify-center">
                  <span className="w-1.5 h-1.5 bg-[#89e5fc] rounded-sm"></span>
                </div>
                <h2 className="text-xs md:text-sm font-sans font-bold tracking-[0.2em] text-white uppercase">
                  {missionActive ? 'BACKEND SETUP SEQUENCE' : 'INTERFACE BOOT SEQUENCE'}
                </h2>
              </div>
              <span className="text-[10px] font-mono text-[#38bdf8] tracking-widest font-semibold animate-pulse">REV 4.2</span>
            </div>
            
            <div className="space-y-2.5 font-mono text-[11px] max-h-[300px] overflow-y-auto no-scrollbar">
              {stages.map((stage, index) => {
                const isActive = stage.active;
                const isReady = stage.ready;
                const isPending = !isActive && !isReady;
                const isQueued = isPending && index === stages.findIndex(s => s.active) + 1;
                
                if (isActive) {
                  return (
                    <div key={stage.label} className="p-2.5 rounded-lg bg-[#89e5fc]/[0.05] border border-[#89e5fc]/30 transition hover:border-[#89e5fc]/60">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-500 font-bold">{String(index + 1).padStart(2, '0')}</span>
                          <i className={`ph-fill ${stage.icon} text-[#38bdf8] text-xs`}></i>
                          <span className="font-bold text-slate-100 tracking-wide">{stage.label}</span>
                        </div>
                        <span className="text-[#38bdf8] font-bold text-[10px] tracking-widest flex items-center gap-1">
                          RUNNING <span className="text-slate-300">{stage.progress}%</span>
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-900/90 rounded-full overflow-hidden p-[1px] border border-white/5">
                        <div className="h-full bg-[#38bdf8] rounded-full animate-pulse" style={{ width: `${stage.progress}%` }}></div>
                      </div>
                    </div>
                  );
                } else if (isReady) {
                  return (
                    <div key={stage.label} className="p-2.5 rounded-lg bg-[#89e5fc]/[0.02] border border-[#89e5fc]/20">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-500 font-bold">{String(index + 1).padStart(2, '0')}</span>
                          <i className={`ph-bold ${stage.icon} text-[#89e5fc] text-xs`}></i>
                          <span className="font-medium text-slate-200 tracking-wide">{stage.label}</span>
                        </div>
                        <span className="text-[#89e5fc] font-semibold text-[10px] tracking-widest">
                          COMPLETE <span className="text-slate-400">100%</span>
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-900/90 rounded-full overflow-hidden border border-white/5">
                        <div className="h-full bg-[#89e5fc] rounded-full w-full"></div>
                      </div>
                    </div>
                  );
                } else {
                  return (
                    <div key={stage.label} className={`p-2.5 rounded-lg bg-transparent border border-white/10 ${isQueued ? 'opacity-75' : 'opacity-60'} flex items-center justify-between flex-wrap gap-y-2`}>
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-500 font-bold">{String(index + 1).padStart(2, '0')}</span>
                        <i className={`ph-bold ${stage.icon} text-slate-500 text-xs`}></i>
                        <span className="text-slate-400">{stage.label}</span>
                      </div>
                      <span className="text-slate-500 text-[10px] tracking-widest font-semibold">{isQueued ? 'QUEUED 0%' : 'STANDBY'}</span>
                      {isQueued && (
                        <div className="w-full h-1.5 bg-slate-900/90 rounded-full overflow-hidden border border-white/5">
                          <div className="h-full bg-slate-700 w-0"></div>
                        </div>
                      )}
                    </div>
                  );
                }
              })}
            </div>
            
            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-[10px] text-slate-400 font-mono">
              <span className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${error ? 'bg-red-400 shadow-[0_0_8px_#f87171]' : 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse'}`}></span>
                {error ? 'SYS: ERR' : 'SYS: I/O HEALTHY'}
              </span>
              <span className="tracking-wider text-right max-w-[200px] truncate">{phase}</span>
            </div>
          </div>
        </section>
      </main>
      
      {/* BOTTOM FOOTER */}
      <footer className="relative z-10 grid grid-cols-1 md:grid-cols-3 items-center gap-4 pt-3.5 border-t border-cyan-400/15 text-xs font-mono">
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-[0.18em]">
            DATA CHANNELS
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px]">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-[#38bdf8] rounded-sm shadow-[0_0_6px_#89e5fc]"></span>
              <span className="text-slate-300">FIRMS THERMAL</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-[#89e5fc] rounded-sm shadow-[0_0_6px_#89e5fc]"></span>
              <span className="text-slate-300">INDUSTRIAL INTELLIGENCE</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 border border-cyan-400/40 bg-cyan-400/20 rounded-sm"></span>
              <span className="text-slate-400">RF COMMS</span>
            </div>
          </div>
        </div>
        
        <div className="text-center space-y-1">
          <div className="text-xs md:text-sm font-sans font-bold tracking-[0.2em] text-white uppercase">
            {phase}
          </div>
          <p className="text-[10px] md:text-[11px] text-slate-400 font-mono max-w-md mx-auto">
            {detail}
          </p>
          <div className="pt-0.5">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-[9px] font-mono tracking-widest font-semibold bg-[#89e5fc]/10 text-[#89e5fc] border border-[#89e5fc]/30 uppercase">
              {missionActive ? 'MISSION ACTIVE' : 'INITIAL BOOT'}
            </span>
          </div>
        </div>
        
        <div className="text-left md:text-right text-[11px] space-y-1 text-slate-400">
          <div>
            <span className="text-slate-500">A/C SITES:</span>
            <span className="text-slate-200 font-bold ml-1">{catchup?.processed_sites ?? 0}/{catchup?.total_sites ?? 0}</span>
          </div>
          <div>
            <span className="text-slate-500">PROMOTED / ALERTS:</span>
            <span className="text-slate-200 font-bold ml-1">{catchup?.promoted_sites ?? 0} / {catchup?.alerts_generated ?? 0}</span>
          </div>
          <div>
            <span className="text-slate-500">MISSION:</span>
            <span className={`${error ? 'text-red-400' : 'text-[#38bdf8]'} font-bold tracking-wider ml-1 uppercase`}>
              {catchup?.status ?? (error ? 'DEGRADED' : 'BOOTING')}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
