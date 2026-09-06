import { useState } from 'react';
import {
  SlidersHorizontal,
  Trees,
  HelpCircle,
  Flame,
  Building2,
  Wheat,
  Layers,
  Box,
  ChevronDown,
  ChevronRight,
  Info
} from 'lucide-react';
import {
  ModelAIcon,
  ModelBIcon,
  ModelCIcon,
  ResolverIcon
} from './Icons';
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
  const [openSections, setOpenSections] = useState({
    modelA: true,
    modelB: true,
    modelC: true,
    elevation3D: true,
    evidence: true
  });

  const toggleSection = (key: keyof typeof openSections) => {
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

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
    <aside className="w-80 bg-[#070a12]/95 border-r border-white/10 flex flex-col h-full select-none z-20 shrink-0 text-xs overflow-y-auto backdrop-blur tactical-glass">
      {/* Panel Header */}
      <div className="p-3.5 border-b border-white/10 flex items-center justify-between bg-[#090e1a]">
        <div className="flex items-center gap-2.5 font-bold text-slate-100 tracking-wider">
          <div className="w-6 h-6 rounded bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <SlidersHorizontal className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-wider">LAYER MATRIX</span>
        </div>
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900/90 border border-white/10">
          <ResolverIcon className="w-3 h-3 text-cyan-400" />
          <span className="text-[10px] font-mono text-cyan-300 font-semibold">
            {siteCount.toLocaleString()}
          </span>
          <span className="text-[9px] font-mono text-slate-400">SITES</span>
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* 1. Model A: Source Identity */}
        <div className="rounded-lg bg-[#0b1120]/80 border border-white/10 overflow-hidden">
          <button
            onClick={() => toggleSection('modelA')}
            className="w-full px-3 py-2 bg-[#0d1424] hover:bg-[#111c33] border-b border-white/5 flex items-center justify-between text-left transition-colors"
          >
            <div className="flex items-center gap-2">
              <ModelAIcon className="w-4 h-4 text-amber-400" />
              <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wide font-mono">
                Model A: Identity
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                {filters.aClasses.length}/3
              </span>
              {openSections.modelA ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            </div>
          </button>

          {openSections.modelA && (
            <div className="p-2 space-y-1.5">
              {/* INDUSTRIAL */}
              <div
                onClick={() => toggleArrayItem('aClasses', 'INDUSTRIAL')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.aClasses.includes('INDUSTRIAL')
                    ? 'bg-amber-500/15 border-amber-500/50 shadow-[0_0_10px_rgba(245,158,11,0.15)] text-amber-200'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                    filters.aClasses.includes('INDUSTRIAL') ? 'bg-amber-500 border-amber-400' : 'bg-slate-900 border-slate-700'
                  }`}>
                    {filters.aClasses.includes('INDUSTRIAL') && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                  </div>
                  <div>
                    <div className="font-mono font-bold text-[11px] tracking-wide text-slate-100">
                      INDUSTRIAL
                    </div>
                    <div className="text-[9.5px] text-slate-400 font-mono">
                      Persistent combustion emitter
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-[0_0_8px_#f59e0b]" />
                </div>
              </div>

              {/* NON-INDUSTRIAL */}
              <div
                onClick={() => toggleArrayItem('aClasses', 'NONINDUSTRIAL')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.aClasses.includes('NONINDUSTRIAL')
                    ? 'bg-emerald-500/15 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.15)] text-emerald-200'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                    filters.aClasses.includes('NONINDUSTRIAL') ? 'bg-emerald-500 border-emerald-400' : 'bg-slate-900 border-slate-700'
                  }`}>
                    {filters.aClasses.includes('NONINDUSTRIAL') && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                  </div>
                  <div>
                    <div className="font-mono font-bold text-[11px] tracking-wide text-slate-100">
                      NON-INDUSTRIAL
                    </div>
                    <div className="text-[9.5px] text-slate-400 font-mono">
                      Wildfire, stubble, biomass
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#10b981]" />
                </div>
              </div>

              {/* UNKNOWN */}
              <div
                onClick={() => toggleArrayItem('aClasses', 'UNKNOWN')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.aClasses.includes('UNKNOWN')
                    ? 'bg-indigo-500/15 border-indigo-500/50 shadow-[0_0_10px_rgba(129,140,248,0.15)] text-indigo-200'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                    filters.aClasses.includes('UNKNOWN') ? 'bg-indigo-500 border-indigo-400' : 'bg-slate-900 border-slate-700'
                  }`}>
                    {filters.aClasses.includes('UNKNOWN') && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                  </div>
                  <div>
                    <div className="font-mono font-bold text-[11px] tracking-wide text-indigo-200 flex items-center gap-1">
                      UNKNOWN
                      <HelpCircle className="w-3 h-3 text-indigo-400" />
                    </div>
                    <div className="text-[9.5px] text-indigo-300/70 font-mono">
                      Review queue &bull; Never coerced
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 shadow-[0_0_8px_#818cf8]" />
                </div>
              </div>

              {/* Unambiguous Rule Note */}
              <div className="mt-1 px-2 py-1.5 rounded bg-indigo-950/30 border border-indigo-500/20 text-[9.5px] text-indigo-300/80 font-mono flex items-start gap-1.5 leading-relaxed">
                <Info className="w-3 h-3 text-indigo-400 shrink-0 mt-0.5" />
                <span>Frozen policy: UNKNOWN preserves ambiguity for expert review and is never suppressed.</span>
              </div>
            </div>
          )}
        </div>

        {/* 2. Model B: Temporal State */}
        <div className="rounded-lg bg-[#0b1120]/80 border border-white/10 overflow-hidden">
          <button
            onClick={() => toggleSection('modelB')}
            className="w-full px-3 py-2 bg-[#0d1424] hover:bg-[#111c33] border-b border-white/5 flex items-center justify-between text-left transition-colors"
          >
            <div className="flex items-center gap-2">
              <ModelBIcon className="w-4 h-4 text-cyan-400" />
              <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wide font-mono">
                Model B: Recurrence
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                {filters.bStates.length}/5
              </span>
              {openSections.modelB ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            </div>
          </button>

          {openSections.modelB && (
            <div className="p-2 space-y-1">
              {[
                { id: 'PERSISTENT', label: 'PERSISTENT', desc: 'Frequent multi-window burns', color: 'bg-cyan-400' },
                { id: 'REACTIVATED', label: 'REACTIVATED', desc: 'Re-emerged post >180d dormant', color: 'bg-purple-400' },
                { id: 'INTERMITTENT', label: 'INTERMITTENT', desc: 'Sporadic operating schedule', color: 'bg-sky-400' },
                { id: 'NEW', label: 'NEW SOURCE', desc: 'First detected ≤90d window', color: 'bg-teal-400' },
                { id: 'DORMANT', label: 'DORMANT', desc: 'Inactive past 90+ days', color: 'bg-slate-500' }
              ].map(b => {
                const isActive = filters.bStates.includes(b.id);
                return (
                  <button
                    key={b.id}
                    onClick={() => toggleArrayItem('bStates', b.id)}
                    className={`w-full p-2 rounded text-left border flex items-center justify-between transition-all ${
                      isActive
                        ? 'bg-[#131f38] border-cyan-500/40 text-slate-100 shadow-[0_0_8px_rgba(6,182,212,0.12)]'
                        : 'bg-[#080d18] border-white/5 text-slate-400 hover:text-slate-200 hover:border-white/15'
                    }`}
                  >
                    <div>
                      <div className="font-mono text-[10.5px] font-bold tracking-wide">
                        {b.label}
                      </div>
                      <div className="text-[9px] text-slate-400 font-mono">
                        {b.desc}
                      </div>
                    </div>
                    <span className={`w-2 h-2 rounded-full ${b.color} ${isActive ? 'shadow-[0_0_6px_currentColor]' : 'opacity-40'}`} />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 3. Model C: Anomaly Severity Status */}
        <div className="rounded-lg bg-[#0b1120]/80 border border-white/10 overflow-hidden">
          <button
            onClick={() => toggleSection('modelC')}
            className="w-full px-3 py-2 bg-[#0d1424] hover:bg-[#111c33] border-b border-white/5 flex items-center justify-between text-left transition-colors"
          >
            <div className="flex items-center gap-2">
              <ModelCIcon className="w-4 h-4 text-orange-400" />
              <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wide font-mono">
                Model C: Anomaly
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-orange-500/15 text-orange-300 border border-orange-500/30">
                {filters.cStatuses.length}/5
              </span>
              {openSections.modelC ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            </div>
          </button>

          {openSections.modelC && (
            <div className="p-2 space-y-1.5">
              {[
                { id: 'CRITICAL', label: 'CRITICAL', score: 'P ≥ 0.99', desc: 'Emergency combustion surge', color: 'bg-red-500 border-red-400/40 text-red-300', dot: 'bg-red-400 shadow-[0_0_8px_#f87171]' },
                { id: 'ANOMALOUS', label: 'ANOMALOUS', score: 'P ≥ 0.95', desc: 'High thermal intensity deviation', color: 'bg-orange-500/20 border-orange-400/40 text-orange-300', dot: 'bg-orange-400 shadow-[0_0_6px_#fb923c]' },
                { id: 'ELEVATED', label: 'ELEVATED', score: 'P ≥ 0.90', desc: 'Noticeable baseline departure', color: 'bg-amber-500/20 border-amber-400/40 text-amber-300', dot: 'bg-amber-400' },
                { id: 'NORMAL', label: 'NORMAL', score: 'P < 0.90', desc: 'Expected operational radiance', color: 'bg-emerald-500/20 border-emerald-400/40 text-emerald-300', dot: 'bg-emerald-400' },
                { id: 'INSUFFICIENT_HISTORY', label: 'COLD START', score: '<5 active days', desc: 'Statistical baseline building', color: 'bg-slate-700/40 border-slate-600/40 text-slate-300', dot: 'bg-slate-400' }
              ].map(c => {
                const isActive = filters.cStatuses.includes(c.id);
                return (
                  <div
                    key={c.id}
                    onClick={() => toggleArrayItem('cStatuses', c.id)}
                    className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                      isActive
                        ? 'bg-[#131f38] border-orange-500/40 text-slate-100 shadow-[0_0_8px_rgba(249,115,22,0.15)]'
                        : 'bg-[#080d18] border-white/5 text-slate-400 hover:text-slate-200 hover:border-white/15'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                        isActive ? 'bg-orange-500 border-orange-400' : 'bg-slate-900 border-slate-700'
                      }`}>
                        {isActive && <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />}
                      </div>
                      <div>
                        <div className="font-mono text-[10.5px] font-bold flex items-center gap-2">
                          <span className="text-slate-100">{c.label}</span>
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-900 border border-white/10 text-slate-400">
                            {c.score}
                          </span>
                        </div>
                        <div className="text-[9px] text-slate-400 font-mono">
                          {c.desc}
                        </div>
                      </div>
                    </div>
                    <span className={`w-2 h-2 rounded-full ${c.dot}`} />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 4. 3D Geospatial & Terrain Controls */}
        <div className="rounded-lg bg-[#0b1120]/80 border border-white/10 overflow-hidden">
          <button
            onClick={() => toggleSection('elevation3D')}
            className="w-full px-3 py-2 bg-[#0d1424] hover:bg-[#111c33] border-b border-white/5 flex items-center justify-between text-left transition-colors"
          >
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-cyan-400" />
              <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wide font-mono">
                3D Volumetric Extrusion
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                {filters.spikeHeightScale}x
              </span>
              {openSections.elevation3D ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            </div>
          </button>

          {openSections.elevation3D && (
            <div className="p-3 space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1.5 font-mono text-[10.5px]">
                  <span className="text-slate-300">FRP Spike Altitude Scale:</span>
                  <span className="text-cyan-400 font-bold">{filters.spikeHeightScale}x</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="0.5"
                  value={filters.spikeHeightScale}
                  onChange={(e) => onChange({ ...filters, spikeHeightScale: parseFloat(e.target.value) })}
                  className="w-full accent-cyan-400 bg-slate-800 h-1.5 rounded cursor-pointer"
                />
                <div className="flex justify-between text-[8.5px] font-mono text-slate-500 mt-1">
                  <span>1.0x (Flat)</span>
                  <span>3.0x</span>
                  <span>5.0x (Mega Spikes)</span>
                </div>
              </div>

              <div
                onClick={() => onChange({ ...filters, terrain3D: !filters.terrain3D })}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.terrain3D
                    ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-200'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div>
                  <div className="font-mono text-[10.5px] font-bold text-slate-100">
                    3D Digital Elevation (DEM)
                  </div>
                  <div className="text-[9px] text-slate-400 font-mono">
                    Terrain topography shading
                  </div>
                </div>
                <div className={`w-8 h-4 rounded-full transition-colors relative ${
                  filters.terrain3D ? 'bg-cyan-500' : 'bg-slate-800'
                }`}>
                  <div className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${
                    filters.terrain3D ? 'right-0.5' : 'left-0.5'
                  }`} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 5. Corroborating Ground-Truth Registries */}
        <div className="rounded-lg bg-[#0b1120]/80 border border-white/10 overflow-hidden">
          <button
            onClick={() => toggleSection('evidence')}
            className="w-full px-3 py-2 bg-[#0d1424] hover:bg-[#111c33] border-b border-white/5 flex items-center justify-between text-left transition-colors"
          >
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-400" />
              <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wide font-mono">
                Evidence Registries
              </span>
            </div>
            {openSections.evidence ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
          </button>

          {openSections.evidence && (
            <div className="p-2 space-y-1.5">
              {/* GEM Power Plants */}
              <div
                onClick={() => toggleEvidence('gem')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.evidenceLayers.gem
                    ? 'bg-blue-500/15 border-blue-500/40 text-blue-200 shadow-[0_0_8px_rgba(59,130,246,0.15)]'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Building2 className="w-3.5 h-3.5 text-blue-400" />
                  <div>
                    <div className="font-mono text-[10.5px] font-bold text-slate-100">
                      GEM Thermal Power
                    </div>
                    <div className="text-[9px] text-slate-400 font-mono">
                      Global Energy Monitor
                    </div>
                  </div>
                </div>
                <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  962 units
                </span>
              </div>

              {/* World Bank Flaring (GFMR) */}
              <div
                onClick={() => toggleEvidence('gfmr')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.evidenceLayers.gfmr
                    ? 'bg-amber-500/15 border-amber-500/40 text-amber-200 shadow-[0_0_8px_rgba(245,158,11,0.15)]'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Flame className="w-3.5 h-3.5 text-amber-400" />
                  <div>
                    <div className="font-mono text-[10.5px] font-bold text-slate-100">
                      World Bank GFMR
                    </div>
                    <div className="text-[9px] text-slate-400 font-mono">
                      Gas Flaring Reduction
                    </div>
                  </div>
                </div>
                <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  174 flares
                </span>
              </div>

              {/* ICAR Stubble */}
              <div
                onClick={() => toggleEvidence('icar')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.evidenceLayers.icar
                    ? 'bg-orange-500/15 border-orange-500/40 text-orange-200 shadow-[0_0_8px_rgba(249,115,22,0.15)]'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Wheat className="w-3.5 h-3.5 text-orange-400" />
                  <div>
                    <div className="font-mono text-[10.5px] font-bold text-slate-100">
                      ICAR Crop Burns
                    </div>
                    <div className="text-[9px] text-slate-400 font-mono">
                      Stubble burn registry
                    </div>
                  </div>
                </div>
                <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-orange-500/20 text-orange-300 border border-orange-500/30">
                  5,158 pts
                </span>
              </div>

              {/* FSI Forest Fires */}
              <div
                onClick={() => toggleEvidence('fsi')}
                className={`p-2 rounded flex items-center justify-between cursor-pointer border transition-all ${
                  filters.evidenceLayers.fsi
                    ? 'bg-red-500/15 border-red-500/40 text-red-200 shadow-[0_0_8px_rgba(239,68,68,0.15)]'
                    : 'bg-[#080d18] border-white/5 text-slate-400 hover:border-white/15'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Trees className="w-3.5 h-3.5 text-red-400" />
                  <div>
                    <div className="font-mono text-[10.5px] font-bold text-slate-100">
                      FSI Wildfires
                    </div>
                    <div className="text-[9px] text-slate-400 font-mono">
                      Forest Survey of India
                    </div>
                  </div>
                </div>
                <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 border border-red-500/30">
                  Active
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
