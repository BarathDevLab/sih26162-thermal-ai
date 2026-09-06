import {
  SlidersHorizontal,
  Factory,
  Trees,
  HelpCircle,
  Clock,
  Zap,
  Flame,
  Building2,
  Wheat,
  Layers,
  Box
} from 'lucide-react';
import type { FilterState } from '../types/api';

interface SidebarFiltersProps {
  filters: FilterState;
  onChange: (f: FilterState) => void;
  siteCount: number;
}

export const SidebarFilters: React.FC<SidebarFiltersProps> = ({
  filters,
  onChange,
  siteCount
}) => {
  const toggleArrayItem = (key: 'aClasses' | 'bStates' | 'cStatuses' | 'alertSeverities', val: string) => {
    const arr = filters[key];
    const next = arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val];
    onChange({ ...filters, [key]: next });
  };

  const toggleEvidence = (layer: keyof FilterState['evidenceLayers']) => {
    onChange({
      ...filters,
      evidenceLayers: {
        ...filters.evidenceLayers,
        [layer]: !filters.evidenceLayers[layer]
      }
    });
  };

  return (
    <aside className="w-72 bg-[#070a12] border-r border-white/10 flex flex-col h-full select-none z-20 shrink-0 text-xs overflow-y-auto">
      {/* Panel Header */}
      <div className="p-3 border-b border-white/10 flex items-center justify-between bg-[#0b1120]">
        <div className="flex items-center gap-2 font-semibold text-slate-200">
          <SlidersHorizontal className="w-3.5 h-3.5 text-cyan-400" />
          <span>LAYER & FILTER MATRIX</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
          {siteCount.toLocaleString()} sites
        </span>
      </div>

      <div className="p-3 space-y-4">
        {/* 1. Model A: Source Identity */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Factory className="w-3.5 h-3.5 text-amber-400" />
              Model A: Identity
            </span>
          </div>
          <div className="space-y-1">
            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.aClasses.includes('INDUSTRIAL')}
                  onChange={() => toggleArrayItem('aClasses', 'INDUSTRIAL')}
                  className="rounded bg-slate-800 border-slate-600 text-amber-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200 font-medium">INDUSTRIAL</span>
              </div>
              <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 shadow-[0_0_6px_#f59e0b]" />
            </label>

            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.aClasses.includes('NONINDUSTRIAL')}
                  onChange={() => toggleArrayItem('aClasses', 'NONINDUSTRIAL')}
                  className="rounded bg-slate-800 border-slate-600 text-emerald-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200 font-medium">NON-INDUSTRIAL</span>
              </div>
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 shadow-[0_0_6px_#10b981]" />
            </label>

            <label
              className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5"
              title="Review queue: Missing or ambiguous ground-truth. Never treated as Non-Industrial."
            >
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.aClasses.includes('UNKNOWN')}
                  onChange={() => toggleArrayItem('aClasses', 'UNKNOWN')}
                  className="rounded bg-slate-800 border-slate-600 text-indigo-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-indigo-200 font-medium flex items-center gap-1">
                  UNKNOWN <HelpCircle className="w-3 h-3 text-indigo-400" />
                </span>
              </div>
              <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 shadow-[0_0_6px_#818cf8]" />
            </label>
          </div>
        </div>

        {/* 2. Model B: Temporal State */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              Model B: Temporal State
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1">
            {[
              { id: 'PERSISTENT', label: 'Persistent', color: 'bg-cyan-500' },
              { id: 'REACTIVATED', label: 'Reactivated', color: 'bg-purple-500' },
              { id: 'INTERMITTENT', label: 'Intermittent', color: 'bg-sky-400' },
              { id: 'NEW', label: 'New Source', color: 'bg-teal-400' },
              { id: 'DORMANT', label: 'Dormant', color: 'bg-slate-500' }
            ].map(b => (
              <button
                key={b.id}
                onClick={() => toggleArrayItem('bStates', b.id)}
                className={`p-1.5 rounded text-left border flex items-center justify-between transition-colors ${
                  filters.bStates.includes(b.id)
                    ? 'bg-[#121c32] border-cyan-500/40 text-slate-100 font-medium'
                    : 'bg-[#0a0f1c] border-white/5 text-slate-400 hover:text-slate-300'
                }`}
              >
                <span>{b.label}</span>
                <span className={`w-2 h-2 rounded-full ${b.color}`} />
              </button>
            ))}
          </div>
        </div>

        {/* 3. Model C: Anomaly Severity */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-orange-400" />
              Model C: Anomaly Status
            </span>
          </div>
          <div className="space-y-1">
            {[
              { id: 'CRITICAL', label: 'CRITICAL (≥0.99)', color: 'bg-red-500 text-red-300' },
              { id: 'ANOMALOUS', label: 'ANOMALOUS (≥0.95)', color: 'bg-orange-500 text-orange-300' },
              { id: 'ELEVATED', label: 'ELEVATED (≥0.90)', color: 'bg-amber-500 text-amber-300' },
              { id: 'NORMAL', label: 'NORMAL OPERATION', color: 'bg-emerald-500 text-emerald-300' },
              { id: 'INSUFFICIENT_HISTORY', label: 'COLD START (<5 days)', color: 'bg-slate-500 text-slate-300' }
            ].map(c => (
              <label
                key={c.id}
                className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5"
              >
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={filters.cStatuses.includes(c.id)}
                    onChange={() => toggleArrayItem('cStatuses', c.id)}
                    className="rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 w-3.5 h-3.5"
                  />
                  <span className="text-slate-200">{c.label}</span>
                </div>
                <span className={`w-2.5 h-2.5 rounded-full ${c.color.split(' ')[0]}`} />
              </label>
            ))}
          </div>
        </div>

        {/* 4. 3D Geospatial Controls */}
        <div className="p-2.5 rounded bg-[#0c1424] border border-cyan-500/20">
          <span className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5 mb-2">
            <Box className="w-3.5 h-3.5 text-cyan-400" />
            3D Elevation Controls
          </span>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-slate-300">3D FRP Spike Height</span>
              <span className="font-mono text-cyan-300">{filters.spikeHeightScale}x</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="0.5"
              value={filters.spikeHeightScale}
              onChange={(e) => onChange({ ...filters, spikeHeightScale: parseFloat(e.target.value) })}
              className="w-full accent-cyan-400 bg-slate-800 h-1 rounded"
            />

            <label className="flex items-center justify-between cursor-pointer pt-1">
              <span className="text-[11px] text-slate-300">3D Digital Terrain (DEM)</span>
              <input
                type="checkbox"
                checked={filters.terrain3D}
                onChange={() => onChange({ ...filters, terrain3D: !filters.terrain3D })}
                className="rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 w-3.5 h-3.5"
              />
            </label>
          </div>
        </div>

        {/* 5. Evidence & Overlay Layers */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-blue-400" />
              Corroborating Evidence
            </span>
          </div>
          <div className="space-y-1">
            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.evidenceLayers.gem}
                  onChange={() => toggleEvidence('gem')}
                  className="rounded bg-slate-800 border-slate-600 text-blue-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200">GEM Power Plants (962)</span>
              </div>
              <Building2 className="w-3.5 h-3.5 text-blue-400" />
            </label>

            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.evidenceLayers.gfmr}
                  onChange={() => toggleEvidence('gfmr')}
                  className="rounded bg-slate-800 border-slate-600 text-amber-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200">World Bank Flaring (174)</span>
              </div>
              <Flame className="w-3.5 h-3.5 text-amber-400" />
            </label>

            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.evidenceLayers.icar}
                  onChange={() => toggleEvidence('icar')}
                  className="rounded bg-slate-800 border-slate-600 text-orange-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200">ICAR Crop Burns (5,158)</span>
              </div>
              <Wheat className="w-3.5 h-3.5 text-orange-400" />
            </label>

            <label className="flex items-center justify-between p-1.5 rounded bg-[#0e1628] hover:bg-[#142038] cursor-pointer border border-white/5">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.evidenceLayers.fsi}
                  onChange={() => toggleEvidence('fsi')}
                  className="rounded bg-slate-800 border-slate-600 text-red-500 focus:ring-0 w-3.5 h-3.5"
                />
                <span className="text-slate-200">FSI Wildfire Perimeters</span>
              </div>
              <Trees className="w-3.5 h-3.5 text-red-400" />
            </label>
          </div>
        </div>
      </div>
    </aside>
  );
};
