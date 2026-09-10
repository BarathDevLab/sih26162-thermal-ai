import React, { useState, useEffect } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Calendar,
  Loader2,
  FastForward,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface ReplayScrubberProps {
  currentDate: string; // YYYY-MM-DD
  endDate?: string;
  onDateChange: (date: string) => void;
  activeCount: number;
  isLoading?: boolean;
  error?: string | null;
}

export const ReplayScrubber: React.FC<ReplayScrubberProps> = ({
  currentDate,
  endDate: configuredEndDate,
  onDateChange,
  activeCount,
  isLoading = false,
  error = null
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [minimized, setMinimized] = useState<boolean>(false);

  const startDate = new Date('2025-01-01').getTime();
  const endDateLabel = configuredEndDate || new Date().toISOString().slice(0, 10);
  const endDate = new Date(endDateLabel).getTime();
  const currTime = new Date(currentDate).getTime();

  const progressPercent = Math.min(
    100,
    Math.max(0, ((currTime - startDate) / Math.max(1, endDate - startDate)) * 100)
  );

  useEffect(() => {
    if (!isPlaying || isLoading || error) return;
    const interval = setInterval(() => {
      const nextTime = new Date(currentDate).getTime() + 24 * 3600 * 1000;
      if (nextTime > endDate) {
        setIsPlaying(false);
      } else {
        onDateChange(new Date(nextTime).toISOString().split('T')[0]);
      }
    }, 1500 / playbackSpeed);
    return () => clearInterval(interval);
  }, [isPlaying, isLoading, error, currentDate, playbackSpeed, endDate, onDateChange]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const timestamp = parseInt(e.target.value, 10);
    onDateChange(new Date(timestamp).toISOString().split('T')[0]);
  };

  const stepDate = (days: number) => {
    const next = Math.max(startDate, Math.min(endDate, new Date(currentDate).getTime() + days * 86400000));
    onDateChange(new Date(next).toISOString().split('T')[0]);
  };

  const jumpToDate = (target: number) => {
    onDateChange(new Date(Math.max(startDate, Math.min(endDate, target))).toISOString().split('T')[0]);
  };

  /* ─── Shared button base classes ─── */
  const btnBase =
    'px-2 py-1 rounded-md text-[10px] font-mono font-medium border transition-all cursor-pointer flex items-center gap-0.5 ' +
    'bg-black/20 border-white/[0.08] text-[#64748B] hover:text-[#89E5FC] hover:border-[#89E5FC]/25';

  /* ─── Compact Mini Bar when Minimized ─── */
  if (minimized) {
    return (
      <div
        className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 px-4 py-1.5 rounded-full border border-sky-400/35 bg-[#070e1e]/90 backdrop-blur-md shadow-[0_8px_25px_rgba(0,0,0,0.7)] font-mono text-xs select-none pointer-events-auto"
        data-purpose="c4isr-replay-minibar"
      >
        <div className="flex items-center gap-2 pr-2 border-r border-sky-400/25">
          <RotateCcw className={`w-3.5 h-3.5 text-[#89E5FC] ${isPlaying ? 'animate-spin' : ''}`} />
          <span className="text-[11px] font-bold text-white tracking-widest uppercase">
            REPLAY
          </span>
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 border border-sky-400/30 font-semibold">
            {currentDate}
          </span>
        </div>

        {/* Quick Play/Pause Mini Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsPlaying(!isPlaying);
          }}
          type="button"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#16385c]/80 hover:bg-[#16385c] text-[#89E5FC] hover:text-white border border-sky-400/40 text-[10px] font-bold cursor-pointer transition-all active:scale-95 shadow-[0_0_8px_rgba(56,189,248,0.2)]"
          title={isPlaying ? 'Pause Replay' : 'Play Replay'}
        >
          {isPlaying ? <Pause className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
          <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
        </button>

        {/* Site Count */}
        <div className="flex items-center gap-1 text-[11px]">
          <span className="font-bold text-[#89E5FC]">{activeCount.toLocaleString()}</span>
          <span className="text-[9px] text-[#64748B]">SITES</span>
        </div>

        {isLoading && (
          <Loader2 className="w-3.5 h-3.5 text-[#89E5FC] animate-spin" />
        )}

        <div className="pl-1 border-l border-sky-400/25">
          {/* Maximize / Expand button */}
          <button
            onClick={() => setMinimized(false)}
            type="button"
            className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-slate-300 hover:text-white hover:bg-white/10 transition-all cursor-pointer text-[10px] font-semibold"
            title="Expand Full Replay Scrubber"
          >
            <ChevronUp className="w-3.5 h-3.5 text-sky-400" />
            <span>EXPAND</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 w-[640px] max-w-[calc(100vw-360px)] hud-glass-panel rounded-2xl p-4 select-none"
      data-purpose="c4isr-replay-scrubber"
    >
      {/* ── Top row: label + meta ── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <RotateCcw className="w-3.5 h-3.5 text-[#89E5FC]" />
          <span className="text-[11px] font-mono font-semibold tracking-widest text-white uppercase">
            CHRONO REPLAY
          </span>
          <span className="chip">FRAME LOCK</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Date pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-sky-400/20 bg-[#070e1e]/60">
            <Calendar className="w-3 h-3 text-[#89E5FC]" />
            <span className="text-[11px] font-mono font-semibold text-white tracking-wider">{currentDate}</span>
          </div>

          {/* Site count */}
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-sky-400/20 bg-[#070e1e]/60">
            <span className="text-[11px] font-mono font-bold text-[#89E5FC]">{activeCount.toLocaleString()}</span>
            <span className="text-[9px] font-mono text-[#64748B]">SITES</span>
          </div>

          {isLoading && (
            <Loader2 className="w-3.5 h-3.5 text-[#89E5FC] animate-spin" />
          )}

          {/* Minimize to Mini Bar Button */}
          <button
            onClick={() => setMinimized(true)}
            aria-label="Minimize Replay Bar"
            title="Minimize to Mini Bar"
            type="button"
            className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-sky-400/30 bg-[#16385c]/50 hover:bg-[#16385c] hover:border-sky-400/60 text-[#89E5FC] hover:text-white transition-all cursor-pointer shadow-sm active:scale-95"
          >
            <ChevronDown className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-[10px] font-mono font-medium tracking-wide">MINIMIZE</span>
          </button>
        </div>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-[rgba(244,63,94,0.08)] border border-[rgba(244,63,94,0.20)] text-[10px] font-mono text-[#fda4af] flex items-center justify-between">
          <span>Frame unavailable: {error}</span>
          <button
            onClick={() => stepDate(-1)}
            className="underline hover:text-white transition-colors cursor-pointer ml-3"
          >
            Step back 1d
          </button>
        </div>
      )}

      {/* ── Slider track ── */}
      <div className="relative flex items-center mb-1">
        {/* Filled progress behind track */}
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-[4px] rounded-full pointer-events-none"
          style={{
            width: `${progressPercent}%`,
            background: 'linear-gradient(to right, rgba(104,137,247,0.6), #89E5FC)',
            boxShadow: '0 0 6px rgba(137,229,252,0.5)'
          }}
        />
        <input
          type="range"
          min={startDate}
          max={endDate}
          step={86400000}
          value={currTime}
          onChange={handleSliderChange}
          className="tactical-slider w-full z-10"
          aria-label="Historical Replay Date Slider"
        />
      </div>

      {/* Epoch labels */}
      <div className="flex justify-between text-[9px] font-mono text-[#475569] tracking-wider mb-3">
        <button onClick={() => jumpToDate(startDate)} className="hover:text-[#89E5FC] transition-colors cursor-pointer">
          2025-01-01
        </button>
        <span className="text-[#89E5FC]/70">{progressPercent.toFixed(1)}% EPOCH</span>
        <button onClick={() => jumpToDate(endDate)} className="hover:text-[#89E5FC] transition-colors cursor-pointer">
          {endDateLabel}
        </button>
      </div>

      {/* ── Controls row ── */}
      <div className="flex items-center justify-between">
        {/* Step buttons */}
        <div className="flex items-center gap-1">
          <button onClick={() => stepDate(-7)} className={btnBase} title="−7 days">
            <ChevronsLeft className="w-3 h-3" /><span>7D</span>
          </button>
          <button onClick={() => stepDate(-1)} className={btnBase} title="−1 day">
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          {/* Play / Pause */}
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            disabled={Boolean(error)}
            className={`px-4 py-1.5 rounded-lg text-[11px] font-mono font-semibold border flex items-center gap-2 transition-all cursor-pointer active:scale-95 ${
              isPlaying
                ? 'bg-[#89E5FC]/10 border-[#89E5FC]/30 text-[#89E5FC]'
                : 'bg-black/25 border-white/[0.10] text-white hover:border-[#89E5FC]/30 hover:text-[#89E5FC]'
            }`}
          >
            {isPlaying ? (
              <><Pause className="w-3.5 h-3.5" /><span>PAUSE</span></>
            ) : (
              <><Play className="w-3.5 h-3.5" /><span>PLAY</span></>
            )}
          </button>

          <button onClick={() => stepDate(1)} className={btnBase} title="+1 day">
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => stepDate(7)} className={btnBase} title="+7 days">
            <span>7D</span><ChevronsRight className="w-3 h-3" />
          </button>
        </div>

        {/* Speed selector */}
        <div className="flex items-center gap-2">
          <FastForward className="w-3 h-3 text-[#64748B]" />
          <div className="flex items-center p-0.5 rounded-lg hud-card">
            {[1, 2, 5].map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                className={`px-2.5 py-0.5 rounded-md text-[10px] font-mono font-semibold transition-all cursor-pointer ${
                  playbackSpeed === s
                    ? 'bg-[#89E5FC]/15 text-[#89E5FC] border border-[#89E5FC]/25'
                    : 'text-[#64748B] hover:text-[#94A3B8]'
                }`}
              >
                {s}×
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
