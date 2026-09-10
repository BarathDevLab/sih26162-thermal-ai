import React, { useState } from 'react';
import { SlidersHorizontal, Layers, ChevronDown, Zap, ChevronLeft, ChevronRight } from 'lucide-react';
import { ModelAIcon, ModelBIcon, ModelCIcon } from './Icons';
import type { FilterState } from '../types/api';

interface SidebarFiltersProps {
  filters: FilterState;
  onChange: (f: FilterState) => void;
  loadedSiteCount: number;
  totalSiteCount: number;
  modelACounts: Record<'INDUSTRIAL' | 'NONINDUSTRIAL' | 'UNKNOWN' | 'UNAVAILABLE', number>;
  isLoading: boolean;
  isOpen?: boolean;
  onToggleOpen?: () => void;
}

export const SidebarFilters: React.FC<SidebarFiltersProps> = ({
  filters,
  onChange,
  loadedSiteCount,
  totalSiteCount,
  modelACounts,
  isLoading,
  isOpen = true,
  onToggleOpen
}) => {
  const [openSections, setOpenSections] = useState({
    extrusion: false,
    evidence: false,
    modelA: true,
    modelB: true,
    modelC: true
  });

  const toggleSection = (key: keyof typeof openSections) =>
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  const toggleArrayItem = (key: 'aClasses' | 'bStates' | 'cStatuses' | 'alertSeverities', val: string) => {
    const arr = filters[key];
    onChange({ ...filters, [key]: arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val] });
  };

  const toggleEvidence = (layer: keyof FilterState['evidenceLayers']) =>
    onChange({ ...filters, evidenceLayers: { ...filters.evidenceLayers, [layer]: !filters.evidenceLayers[layer] } });

  // If collapsed: show compact tactical floating trigger pill
  if (!isOpen) {
    return (
      <aside
        className="absolute top-14 left-4 z-20 font-mono text-xs select-none pointer-events-auto"
        data-purpose="telemetry-sidebar-collapsed"
      >
        <button
          onClick={onToggleOpen}
          type="button"
          className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-sky-400/30 bg-[#070e1e]/90 backdrop-blur-md text-[#89E5FC] hover:text-white hover:border-sky-400/60 shadow-[0_4px_16px_rgba(0,0,0,0.6)] transition-all cursor-pointer group active:scale-95"
          title="Expand Model Intel Panel"
        >
          <SlidersHorizontal className="w-3.5 h-3.5 text-[#89E5FC] group-hover:rotate-45 transition-transform" />
          <span className="font-semibold text-[10px] tracking-wider uppercase text-slate-200 group-hover:text-white">MODEL INTEL</span>
          <span className="px-1.5 py-0.5 rounded-full bg-sky-500/20 text-[#89E5FC] border border-sky-400/30 text-[9px] font-bold">
            {loadedSiteCount.toLocaleString()}
          </span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
        </button>
      </aside>
    );
  }

  /* ─── Mini toggle switch ─── */
  const Toggle = ({ checked, onClick }: { checked: boolean; onClick: () => void }) => (
    <button
      type="button"
      onClick={onClick}
      className={`w-7 h-3.5 rounded-full border p-0.5 flex items-center transition-all cursor-pointer shrink-0 ${checked ? 'bg-[#89E5FC]/20 border-[#89E5FC]/40 justify-end' : 'bg-black/40 border-white/[0.12] justify-start'
        }`}
    >
      <div className={`w-2.5 h-2.5 rounded-full transition-colors ${checked ? 'bg-[#89E5FC] shadow-[0_0_6px_#89E5FC]' : 'bg-[#475569]'}`} />
    </button>
  );

  /* ─── Section header ─── */
  const SectionHeader = ({ icon, label, children, open }: { icon: React.ReactNode; label: string; children?: React.ReactNode; open: boolean }) => (
    <div className="flex items-center justify-between pb-1 border-b border-white/[0.06]">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[10px] text-[#94A3B8] font-semibold tracking-wider uppercase">{label}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {children}
        <ChevronDown className={`w-3.5 h-3.5 text-[#475569] transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </div>
    </div>
  );

  const allExpanded = Object.values(openSections).every(Boolean);

  return (
    <aside
      className="absolute top-14 left-4 z-20 font-mono text-xs select-none pointer-events-auto"
      data-purpose="telemetry-left-sidebar"
    >
      <div className="w-72 max-h-[calc(100vh-140px)] flex flex-col hud-glass-panel rounded-2xl overflow-hidden border border-sky-400/25 shadow-[0_12px_40px_rgba(0,0,0,0.8)]">

        {/* Fixed Pinned Header */}
        <div className="p-3.5 border-b border-white/[0.08] bg-[#0c1220]/75 backdrop-blur-md shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-3.5 h-3.5 text-[#89E5FC]" />
              <span className="font-semibold tracking-wider text-[11px] text-white uppercase">MODEL INTEL</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-full hud-card text-[10px]">
                <span className="text-[#89E5FC] font-bold">{loadedSiteCount.toLocaleString()}</span>
                <span className="text-[#475569]">/</span>
                <span className="text-[#64748B]">{totalSiteCount.toLocaleString()}</span>
                {isLoading && <span className="w-1.5 h-1.5 rounded-full bg-[#89E5FC] animate-ping ml-0.5" />}
              </div>
              {onToggleOpen && (
                <button
                  onClick={onToggleOpen}
                  type="button"
                  title="Minimize Model Intel"
                  className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between mt-1 pt-1 border-t border-white/[0.04]">
            <p className="text-[8px] tracking-widest text-[#64748B] uppercase">TAXONOMY & UNCERTAINTY</p>
            <button
              onClick={() => {
                setOpenSections({
                  extrusion: !allExpanded,
                  evidence: !allExpanded,
                  modelA: !allExpanded,
                  modelB: !allExpanded,
                  modelC: !allExpanded
                });
              }}
              className="text-[8.5px] text-sky-400/80 hover:text-sky-300 tracking-wider uppercase transition-colors cursor-pointer font-medium"
            >
              {allExpanded ? 'COLLAPSE ALL' : 'EXPAND ALL'}
            </button>
          </div>
        </div>

        {/* Scrollable Content Body with Guaranteed Padding */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5 pb-6 custom-scrollbar">

          {/* ── Section 1: 3D Extrusion ── */}
          <div className="hud-card rounded-xl p-2.5 space-y-0">
            <button onClick={() => toggleSection('extrusion')} className="w-full cursor-pointer text-left">
              <SectionHeader
                icon={<Zap className="w-3.5 h-3.5 text-[#89E5FC]" />}
                label="3D EXTRUSION"
                open={openSections.extrusion}
              >
                <span className="chip chip-cyan">{filters.spikeHeightScale.toFixed(1)}×</span>
              </SectionHeader>
            </button>

            {openSections.extrusion && (
              <div className="space-y-2.5 pt-2.5">
                <div>
                  <div className="flex justify-between text-[10px] text-[#64748B] mb-1">
                    <span>FRP Spike Scale</span>
                    <span className="text-white font-semibold font-mono">{filters.spikeHeightScale.toFixed(1)}×</span>
                  </div>
                  <input
                    type="range"
                    min={1.0} max={5.0} step={0.5}
                    value={filters.spikeHeightScale}
                    onChange={(e) => onChange({ ...filters, spikeHeightScale: parseFloat(e.target.value) })}
                    className="tactical-slider w-full"
                  />
                  <div className="flex justify-between text-[8px] text-[#475569] mt-0.5">
                    <span>1.0× Flat</span><span>5.0× Spikes</span>
                  </div>
                </div>

                <div
                  className={`pt-2 border-t border-white/[0.06] flex items-center justify-between p-1.5 rounded-lg transition-all ${
                    filters.mode3D ? 'bg-black/25 border border-white/[0.12]' : 'bg-transparent border border-transparent'
                  }`}
                >
                  <div>
                    <span
                      className={`block text-[10px] font-semibold transition-all ${
                        filters.mode3D
                          ? 'text-[#89E5FC] drop-shadow-[0_0_8px_rgba(137,229,252,0.6)]'
                          : 'text-[#64748B]'
                      }`}
                    >
                      3D Volumetric Mode
                    </span>
                    <span className="block text-[8px] text-[#475569]">Render FRP columns</span>
                  </div>
                  <Toggle checked={filters.mode3D} onClick={() => onChange({ ...filters, mode3D: !filters.mode3D })} />
                </div>
              </div>
            )}
          </div>

          {/* ── Section 2: Evidence Registries ── */}
          <div className="hud-card rounded-xl p-2.5">
            <button onClick={() => toggleSection('evidence')} className="w-full cursor-pointer text-left">
              <SectionHeader
                icon={<Layers className="w-3.5 h-3.5 text-[#89E5FC]" />}
                label="EVIDENCE REGISTRIES"
                open={openSections.evidence}
              >
                <span className="chip">{Object.values(filters.evidenceLayers).filter(Boolean).length} ACTIVE</span>
              </SectionHeader>
            </button>

            {openSections.evidence && (
              <div className="space-y-1.5 pt-2">
                {[
                  { key: 'gem' as const, label: 'GEM Thermal Plants' },
                  { key: 'gfmr' as const, label: 'World Bank Gas Flaring' },
                  { key: 'icar' as const, label: 'ICAR Crop Burning' },
                  { key: 'fsi' as const, label: 'FSI Forest Perimeters' }
                ].map((ev) => {
                  const active = filters.evidenceLayers[ev.key];
                  return (
                    <div
                      key={ev.key}
                      className={`flex items-center justify-between p-1.5 rounded-lg border transition-all ${
                        active
                          ? 'bg-black/25 border-white/[0.12] hover:border-white/[0.18]'
                          : 'bg-black/20 border-white/[0.06] hover:border-white/[0.10]'
                      }`}
                    >
                      <span
                        className={`text-[10px] font-semibold transition-all ${
                          active
                            ? 'text-[#89E5FC] drop-shadow-[0_0_8px_rgba(137,229,252,0.6)]'
                            : 'text-[#64748B]'
                        }`}
                      >
                        {ev.label}
                      </span>
                      <Toggle checked={active} onClick={() => toggleEvidence(ev.key)} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Section 3: Model A ── */}
          <div className="hud-card rounded-xl p-2.5">
            <button onClick={() => toggleSection('modelA')} className="w-full cursor-pointer text-left">
              <SectionHeader
                icon={<ModelAIcon className="w-3.5 h-3.5 text-[#89E5FC]" />}
                label="MODEL A · IDENTITY"
                open={openSections.modelA}
              />
            </button>

            {openSections.modelA && (
              <div className="space-y-1.5 pt-2">
                {[
                  { id: 'INDUSTRIAL', label: 'INDUSTRIAL', desc: 'Smelter, refinery, brick kiln' },
                  { id: 'NONINDUSTRIAL', label: 'NON-INDUSTRIAL', desc: 'Wildfire, stubble, biomass' },
                  { id: 'UNKNOWN', label: 'UNKNOWN (?)', desc: 'Review queue · Ambiguity' }
                ].map((cls) => {
                  const active = filters.aClasses.includes(cls.id);
                  return (
                    <div
                      key={cls.id}
                      className="flex items-center justify-between p-1.5 rounded-lg bg-black/20 border border-white/[0.06] hover:border-white/[0.12] transition-all"
                    >
                      <div>
                        <div
                          className={`text-[10px] font-semibold transition-all ${
                            active
                              ? 'text-[#89E5FC] drop-shadow-[0_0_8px_rgba(137,229,252,0.6)]'
                              : 'text-[#64748B]'
                          }`}
                        >
                          {cls.label}
                        </div>
                        <div className="text-[8px] text-[#475569]">{cls.desc}</div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="chip">{modelACounts[cls.id as keyof typeof modelACounts] ?? 0}</span>
                        <Toggle checked={active} onClick={() => toggleArrayItem('aClasses', cls.id)} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Section 4: Model B ── */}
          <div className="hud-card rounded-xl p-2.5">
            <button onClick={() => toggleSection('modelB')} className="w-full cursor-pointer text-left">
              <SectionHeader
                icon={<ModelBIcon className="w-3.5 h-3.5 text-[#89E5FC]" />}
                label="MODEL B · RECURRENCE"
                open={openSections.modelB}
              />
            </button>

            {openSections.modelB && (
              <div className="space-y-1.5 pt-2">
                {([
                  { id: 'PERSISTENT', desc: 'Continuous baseline' },
                  { id: 'REACTIVATED', desc: 'Re-ignited dormant source' },
                  { id: 'INTERMITTENT', desc: 'Irregular cadence' },
                  { id: 'NEW', desc: 'First occurrence <30d' },
                  { id: 'DORMANT', desc: 'No signal >90d' }
                ] as { id: string; desc: string }[]).map((state) => {
                  const active = filters.bStates.includes(state.id);
                  return (
                    <div
                      key={state.id}
                      className="flex items-center justify-between p-1.5 rounded-lg bg-black/20 border border-white/[0.06] hover:border-white/[0.12] transition-all"
                    >
                      <div>
                        <div
                          className={`text-[10px] font-semibold transition-all ${
                            active
                              ? 'text-[#89E5FC] drop-shadow-[0_0_8px_rgba(137,229,252,0.6)]'
                              : 'text-[#64748B]'
                          }`}
                        >
                          {state.id}
                        </div>
                        <div className="text-[8px] text-[#475569]">{state.desc}</div>
                      </div>
                      <Toggle checked={active} onClick={() => toggleArrayItem('bStates', state.id)} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Section 5: Model C ── */}
          <div className="hud-card rounded-xl p-2.5">
            <button onClick={() => toggleSection('modelC')} className="w-full cursor-pointer text-left">
              <SectionHeader
                icon={<ModelCIcon className="w-3.5 h-3.5 text-[#89E5FC]" />}
                label="MODEL C · ANOMALY"
                open={openSections.modelC}
              />
            </button>

            {openSections.modelC && (
              <div className="space-y-1.5 pt-2">
                {([
                  { id: 'CRITICAL', label: 'CRITICAL', desc: '≥P99 anomaly score', alert: true },
                  { id: 'ANOMALOUS', label: 'ANOMALOUS', desc: '≥P95 anomaly score', alert: true },
                  { id: 'ELEVATED', label: 'ELEVATED', desc: '≥P90 anomaly score', alert: false },
                  { id: 'NORMAL', label: 'NORMAL', desc: 'Below P90', alert: false },
                  { id: 'INSUFFICIENT_HISTORY', label: 'COLD START', desc: 'History <5 days', alert: false }
                ] as { id: string; label: string; desc: string; alert: boolean }[]).map((c) => {
                  const active = filters.cStatuses.includes(c.id);
                  return (
                    <div
                      key={c.id}
                      className={`flex items-center justify-between p-1.5 rounded-lg border transition-all ${active && c.alert
                          ? 'bg-[rgba(244,63,94,0.06)] border-[rgba(244,63,94,0.18)]'
                          : active
                            ? 'bg-black/25 border-white/[0.12]'
                            : 'bg-black/20 border-white/[0.06]'
                        }`}
                    >
                      <div>
                        <div
                          className={`text-[10px] font-semibold transition-all ${
                            active && c.alert
                              ? 'text-[#fda4af] drop-shadow-[0_0_8px_rgba(244,63,94,0.6)]'
                              : active
                              ? 'text-[#89E5FC] drop-shadow-[0_0_8px_rgba(137,229,252,0.6)]'
                              : 'text-[#64748B]'
                          }`}
                        >
                          {c.label}
                        </div>
                        <div className="text-[8px] text-[#475569]">{c.desc}</div>
                      </div>
                      <Toggle
                        checked={active}
                        onClick={() => toggleArrayItem('cStatuses', c.id)}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
};
