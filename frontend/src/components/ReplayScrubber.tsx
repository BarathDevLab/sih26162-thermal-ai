import { useState, useEffect } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Calendar
} from 'lucide-react';

interface ReplayScrubberProps {
  currentDate: string; // YYYY-MM-DD
  onDateChange: (date: string) => void;
  activeCount: number;
}

export const ReplayScrubber: React.FC<ReplayScrubberProps> = ({
  currentDate,
  onDateChange,
  activeCount
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  const startDate = new Date('2025-01-01').getTime();
  const endDate = new Date('2026-09-04').getTime();
  const currTime = new Date(currentDate).getTime();

  // Playback timer effect
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      const nextTime = new Date(currentDate).getTime() + 24 * 3600 * 1000;
      if (nextTime > endDate) {
        setIsPlaying(false);
      } else {
        const nextDateStr = new Date(nextTime).toISOString().split('T')[0];
        onDateChange(nextDateStr);
      }
    }, 1500 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, currentDate, playbackSpeed, endDate, onDateChange]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const timestamp = parseInt(e.target.value, 10);
    const dateStr = new Date(timestamp).toISOString().split('T')[0];
    onDateChange(dateStr);
  };

  const stepDate = (days: number) => {
    const nextTime = new Date(currentDate).getTime() + days * 24 * 3600 * 1000;
    if (nextTime >= startDate && nextTime <= endDate) {
      onDateChange(new Date(nextTime).toISOString().split('T')[0]);
    }
  };

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 w-[600px] max-w-[calc(100vw-340px)] bg-[#070a12]/95 border border-amber-500/40 rounded-lg p-3 shadow-2xl backdrop-blur select-none">
      {/* Top Telemetry Header */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/10 text-xs">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-4 h-4 text-amber-400" />
          <span className="font-bold text-slate-100 font-mono">
            HISTORICAL REPLAY MODE
          </span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono border border-amber-500/30">
            ZERO FUTURE LEAKAGE
          </span>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px]">
          <Calendar className="w-3 h-3 text-slate-400" />
          <span className="text-amber-300 font-bold text-sm">{currentDate}</span>
          <span className="text-slate-500">&middot;</span>
          <span className="text-slate-300">{activeCount.toLocaleString()} sites</span>
        </div>
      </div>

      {/* Scrubbing Slider */}
      <div className="space-y-1.5">
        <input
          type="range"
          min={startDate}
          max={endDate}
          step={24 * 3600 * 1000}
          value={currTime}
          onChange={handleSliderChange}
          className="w-full accent-amber-500 bg-slate-800 h-1.5 rounded cursor-pointer"
        />

        <div className="flex justify-between text-[9px] font-mono text-slate-500">
          <span>2025-01-01</span>
          <span>2025-06-01</span>
          <span>2026-01-01</span>
          <span>2026-09-04</span>
        </div>
      </div>

      {/* Playback Controls */}
      <div className="flex items-center justify-between pt-2 mt-1 border-t border-white/5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => stepDate(-1)}
            className="p-1 rounded bg-[#0c1424] hover:bg-[#121c32] text-slate-300 border border-white/10"
            title="Step backward 1 day"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="px-3 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-xs border border-amber-500/40 flex items-center gap-1.5 transition-all"
          >
            {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
          </button>

          <button
            onClick={() => stepDate(1)}
            className="p-1 rounded bg-[#0c1424] hover:bg-[#121c32] text-slate-300 border border-white/10"
            title="Step forward 1 day"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Speed Selector */}
        <div className="flex items-center gap-1 text-[10px] font-mono">
          <span className="text-slate-500 mr-1">SPEED:</span>
          {[1, 2, 5].map((s) => (
            <button
              key={s}
              onClick={() => setPlaybackSpeed(s)}
              className={`px-1.5 py-0.5 rounded border ${
                playbackSpeed === s
                  ? 'bg-amber-500/30 text-amber-300 border-amber-500/50 font-bold'
                  : 'bg-slate-900 text-slate-400 border-white/5 hover:text-slate-200'
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
