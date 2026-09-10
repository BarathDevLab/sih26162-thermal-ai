import React, { useState, useEffect } from 'react';
import {
  X, MapPin, Eye
} from 'lucide-react';
import {
  ResolverIcon,
  DecisionEngineIcon
} from './Icons';
import type {
  SiteDetail,
  SiteTimelineResponse,
  SiteEvidenceResponse,
  SiteDetectionsResponse,
  ImageryCacheSummary
} from '../types/api';
import {
  fetchSiteTimeline,
  fetchSiteEvidence,
  fetchSiteDetections,
  fetchSiteImagery
} from '../services/api';

interface SiteDrawerProps {
  site: SiteDetail | null;
  asOfDate?: string;
  onClose: () => void;
}

type TabType = 'OVERVIEW' | 'TIMELINE' | 'EVIDENCE' | 'SATELLITE' | 'RAW_FIRMS';

const TABS: { id: TabType; label: string }[] = [
  { id: 'OVERVIEW',  label: 'Overview' },
  { id: 'TIMELINE',  label: 'Timeline' },
  { id: 'EVIDENCE',  label: 'Evidence' },
  { id: 'SATELLITE', label: 'Satellite' },
  { id: 'RAW_FIRMS', label: 'Detections' }
];

export const SiteDrawer: React.FC<SiteDrawerProps> = ({ site, asOfDate, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabType>('OVERVIEW');
  const [timelineData, setTimelineData]   = useState<SiteTimelineResponse | null>(null);
  const [evidenceData, setEvidenceData]   = useState<SiteEvidenceResponse | null>(null);
  const [detectionsData, setDetectionsData] = useState<SiteDetectionsResponse | null>(null);
  const [imageryData, setImageryData]     = useState<ImageryCacheSummary[]>([]);
  const [loading, setLoading]             = useState<boolean>(false);

  const siteId = site?.site_id;

  useEffect(() => {
    if (!siteId) return;
    let active = true;
    setLoading(true);

    Promise.allSettled([
      fetchSiteTimeline(siteId, asOfDate),
      fetchSiteEvidence(siteId, 5000, asOfDate),
      fetchSiteDetections(siteId, asOfDate),
      fetchSiteImagery(siteId, asOfDate)
    ]).then(([timeline, evidence, detections, imagery]) => {
      if (!active) return;
      if (timeline.status   === 'fulfilled') setTimelineData(timeline.value);
      if (evidence.status   === 'fulfilled') setEvidenceData(evidence.value);
      if (detections.status === 'fulfilled') setDetectionsData(detections.value);
      if (imagery.status    === 'fulfilled') setImageryData(imagery.value);
      setLoading(false);
    });

    return () => { active = false; };
  }, [siteId, asOfDate]);

  if (!site) return null;

  const activePrithviProb   = site.model_a?.prithvi_probability ?? (imageryData[0]?.prithvi_probability ?? null);
  const activePrithviStatus = site.model_a?.prithvi_status ?? imageryData[0]?.status ?? 'UNAVAILABLE';
  const activePrithviValue  = activePrithviProb !== null
    ? `${(activePrithviProb * 100).toFixed(1)}%`
    : activePrithviStatus === 'PENDING' ? 'PENDING' : 'N/A';

  /* ─── Card shell — exact Stitch spec ─── */
  const card = 'bg-[#060c18]/70 rounded-xl p-3.5 border border-white/[0.08] hover:border-white/[0.12] transition-colors';

  /* ─── Status badge variants ─── */
  const getBadgeClass = (status: string) => {
    const alerts = ['CRITICAL', 'ANOMALOUS'];
    if (alerts.includes(status))
      return 'px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold rounded bg-[rgba(244,63,94,0.12)] text-[#fda4af] border border-[rgba(244,63,94,0.25)]';
    if (['REACTIVATED', 'NEW', 'PERSISTENT', 'ELEVATED'].includes(status))
      return 'px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold rounded bg-cyan-950/60 text-cyan-300 border border-cyan-700/50';
    return 'px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold rounded bg-[#091322] text-slate-300 border border-slate-700/80';
  };

  return (
    <aside
      className="w-[385px] max-w-[calc(100vw-1.5rem)] max-h-full flex flex-col drawer-glass overflow-hidden select-none font-sans antialiased shadow-2xl"
      data-purpose="tactical-detail-panel"
      id="tactical-inspector"
    >
      {/* ── Header ── */}
      <header className="p-4 pb-0" data-purpose="header-section">
        <div className="flex items-start justify-between gap-3">
          {/* Site identity */}
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-sm font-semibold tracking-wide text-white uppercase font-mono truncate">
                {site.site_id}
              </h1>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium tracking-wider bg-[#89E5FC]/10 text-[#89E5FC] border border-[#89E5FC]/25 shrink-0">
                <ResolverIcon className="w-2.5 h-2.5" />
                750m RESOLVER
              </span>
              {loading && (
                <span className="text-[9px] font-mono text-[#89E5FC] animate-pulse tracking-widest">SYNCING…</span>
              )}
            </div>

            <div className="flex items-center gap-1.5 text-[11px] text-slate-300 font-mono tracking-tight flex-wrap">
              <MapPin className="w-3.5 h-3.5 text-rose-500 shrink-0" />
              <span>{site.latitude.toFixed(4)}&deg;N, {site.longitude.toFixed(4)}&deg;E</span>
              {asOfDate && (
                <>
                  <span className="text-white/20">•</span>
                  <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-white/[0.06] text-slate-400 border border-white/[0.08] tracking-wider">
                    AS OF {asOfDate}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            aria-label="Close panel"
            type="button"
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors focus:outline-none cursor-pointer shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab nav — Stitch pill buttons */}
        <nav
          aria-label="Inspector modules"
          className="flex items-center gap-1.5 mt-3 pb-2.5 overflow-x-auto no-scrollbar"
          data-purpose="tab-navigation"
        >
          {TABS.map(({ id, label }) => {
            const active = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`px-3 py-1 text-xs rounded-lg transition-all whitespace-nowrap cursor-pointer shrink-0 font-medium ${
                  active
                    ? 'bg-[#0e2a40]/90 text-[#89E5FC] border border-[#89E5FC]/40 font-semibold shadow-[0_0_12px_rgba(137,229,252,0.18)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                {label}
              </button>
            );
          })}
        </nav>
      </header>

      {/* ── Content ── */}
      <div
        className="p-4 space-y-3 overflow-y-auto flex-1 custom-scrollbar"
        data-purpose="telemetry-cards-container"
        style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.15) rgba(18,22,31,0.5)' }}
      >

        {/* ══ OVERVIEW ══ */}
        {activeTab === 'OVERVIEW' && (
          <>
            {/* Alert banner */}
            {site.active_alert && (
              <div className="p-3.5 rounded-xl bg-[rgba(244,63,94,0.08)] border border-[rgba(244,63,94,0.22)] space-y-2 mb-2">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold rounded bg-[rgba(244,63,94,0.15)] text-[#fda4af] border border-[rgba(244,63,94,0.25)]">
                    <DecisionEngineIcon className="w-3 h-3" />
                    {site.active_alert.alert_level} INCIDENT
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">{site.active_alert.alert_type}</span>
                </div>
                <p className="text-xs text-slate-300 font-mono leading-relaxed">{site.active_alert.headline}</p>
                {(site.active_alert.reason_codes ?? []).length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {(site.active_alert.reason_codes ?? []).map((code) => (
                      <span key={code} className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-white/[0.06] text-slate-400 border border-white/[0.08]">
                        {code}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ─ Model A ─ */}
            <section className={card} data-purpose="model-a-card">
              <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-amber-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <polygon points="12 2 21 7.5 21 16.5 12 22 3 16.5 3 7.5 12 2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <h2 className="text-xs font-semibold tracking-wider text-slate-200 uppercase font-mono">
                    Model A: Source Identity
                  </h2>
                </div>
                <span className={getBadgeClass(site.model_a?.class_name || 'UNKNOWN')}>
                  {site.model_a?.class_name || 'Unknown'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 my-2 text-xs">
                <div>
                  <div className="text-[11px] text-slate-400 mb-0.5">A-Core Probability:</div>
                  <div className="text-sm font-semibold text-white font-mono">
                    {site.model_a?.core_probability != null
                      ? `${(site.model_a.core_probability * 100).toFixed(1)}%`
                      : '45.0%'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-slate-400 mb-0.5">Prithvi Visual Score:</div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-[#89E5FC] font-mono">{activePrithviValue}</span>
                    <span className="px-1.5 py-0.5 text-[9px] font-mono font-medium rounded bg-teal-950/60 text-teal-300 border border-teal-700/50">
                      {activePrithviStatus}
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setActiveTab('SATELLITE')}
                type="button"
                className="w-full mt-2.5 flex items-center justify-center gap-2 py-2 px-3 text-xs font-medium tracking-wide text-[#89E5FC] bg-[#0c1c32]/80 hover:bg-[#112948] border border-cyan-700/40 rounded-lg transition-all cursor-pointer"
                data-purpose="action-inspect-satellite"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Inspect Satellite Photo &amp; Prithvi Breakdown</span>
                <span aria-hidden="true">&#8594;</span>
              </button>
            </section>

            {/* ─ Model B ─ */}
            <section className={card} data-purpose="model-b-card">
              <div className="flex items-center justify-between gap-2 pb-2.5 mb-2 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-cyan-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75" viewBox="0 0 24 24">
                    <path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <h2 className="text-xs font-semibold tracking-wider text-slate-200 uppercase font-mono">
                    Model B: Recurrence Engine
                  </h2>
                </div>
                <span className={getBadgeClass(site.model_b?.state || 'REACTIVATED')}>
                  {site.model_b?.state || 'Reactivated'}
                </span>
              </div>

              <p className="text-xs text-slate-400 font-mono mb-2.5">
                {site.model_b?.reason || 'Returned within 30d after >=90d inactive gap'}
              </p>

              {/* Temporal history grid — exact Stitch spec */}
              <div className="grid grid-cols-4 gap-2 text-center" data-purpose="temporal-history-grid">
                {['30', '90', '180', '365'].map((w) => (
                  <div key={w} className="p-2 rounded-lg bg-[#060c18]/80 border border-slate-800/90">
                    <span className="block text-[10px] font-mono text-slate-400 mb-0.5">{w}d</span>
                    <span className="text-xs font-semibold font-mono text-white">
                      {site.model_b?.active_days_windows?.[w] ?? 0}d
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {/* ─ Model C ─ */}
            <section className={card} data-purpose="model-c-card">
              <div className="flex items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-slate-300 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.75" viewBox="0 0 24 24">
                    <path d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.25 2.25L15 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <h2 className="text-xs font-semibold tracking-wider text-slate-200 uppercase font-mono">
                    Model C: Anomaly Engine
                  </h2>
                </div>
                <span className={
                  ['CRITICAL', 'ANOMALOUS'].includes(site.model_c?.operational_status || '')
                    ? getBadgeClass(site.model_c!.operational_status)
                    : 'px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-semibold rounded bg-teal-950/60 text-teal-300 border border-teal-700/50'
                }>
                  {site.model_c?.operational_status || 'INSUFFICIENT_HISTORY'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <div className="text-[11px] text-slate-400 mb-0.5">Anomaly Score:</div>
                  <div className="text-sm font-semibold text-slate-300 font-mono">
                    {site.model_c?.c_score != null ? `${(site.model_c.c_score * 100).toFixed(1)}%` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-slate-400 mb-0.5">P99 Evidence Count:</div>
                  <div className="text-sm font-semibold text-white font-mono">
                    {site.model_c?.evidence_99 ? `${site.model_c.evidence_99} metrics` : '0 metrics'}
                  </div>
                </div>
              </div>
            </section>
          </>
        )}

        {/* ══ TIMELINE ══ */}
        {activeTab === 'TIMELINE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.07]">
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono">Historical FRP Timeline</span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-white/[0.06] text-slate-300 border border-white/[0.08]">
                {timelineData?.history?.length ?? 0} days
              </span>
            </div>
            {timelineData?.history?.length ? (
              <div className="space-y-1.5 max-h-[520px] overflow-y-auto">
                {timelineData.history.slice(-60).reverse().map((d) => (
                  <div key={d.acq_date} className="bg-black/30 p-2.5 rounded-lg flex items-center justify-between border border-white/[0.06]">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-white font-mono">{d.acq_date}</span>
                      <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-white/[0.06] text-slate-400 border border-white/[0.08]">
                        {d.detections} hits
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold text-[#89E5FC] font-mono">{d.max_frp.toFixed(1)} MW</div>
                      <div className="text-[9px] text-slate-500 font-mono">mean {d.mean_frp.toFixed(1)} MW</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-xs font-mono bg-black/20 rounded-xl border border-white/[0.06]">
                No chronological detections for this cutoff window.
              </div>
            )}
          </div>
        )}

        {/* ══ EVIDENCE ══ */}
        {activeTab === 'EVIDENCE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.07]">
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono">Proximate Facility Evidence</span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-white/[0.06] text-slate-300 border border-white/[0.08]">
                Within 5.0 km
              </span>
            </div>
            {evidenceData?.evidence?.length ? (
              <div className="space-y-2">
                {evidenceData.evidence.map((fac, idx) => (
                  <div key={idx} className="bg-black/30 p-3 rounded-xl border border-white/[0.08] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white text-xs font-mono">{fac.facility_name}</span>
                      <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-[#89E5FC]/10 text-[#89E5FC] border border-[#89E5FC]/20">
                        {fac.distance_m ? `${(fac.distance_m / 1000).toFixed(2)} km` : 'CO-LOCATED'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                      <span>{fac.source_name}</span>
                      <span className="text-white/20">•</span>
                      <span>{fac.facility_type || 'INDUSTRIAL'}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-xs font-mono bg-black/20 rounded-xl border border-white/[0.06]">
                No registered facilities within 5 km radius.
              </div>
            )}
          </div>
        )}

        {/* ══ SATELLITE ══ */}
        {activeTab === 'SATELLITE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.07]">
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono">HLS / Sentinel-2 Cache</span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-white/[0.06] text-slate-300 border border-white/[0.08]">
                {imageryData.length} tiles
              </span>
            </div>
            {imageryData.length ? (
              <div className="space-y-3">
                {imageryData.map((tile, idx) => (
                  <div key={idx} className="bg-black/30 p-3 rounded-xl border border-white/[0.08] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white text-xs font-mono">{tile.cache_id || tile.product || 'Sentinel-2 RGB/SWIR'}</span>
                      <span className="px-1.5 py-0.5 text-[9px] font-mono rounded bg-[#89E5FC]/10 text-[#89E5FC] border border-[#89E5FC]/20">
                        {tile.status}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500 space-y-0.5 font-mono">
                      <div>Pass Date: <span className="text-slate-300">{tile.acquisition_date || 'N/A'}</span></div>
                      <div>Cloud Cover: <span className="text-[#89E5FC]">{tile.cloud_fraction != null ? `${(tile.cloud_fraction * 100).toFixed(1)}%` : '0%'}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-xs font-mono bg-black/20 rounded-xl border border-white/[0.06]">
                No Sentinel-2 tiles cached for this location.
              </div>
            )}
          </div>
        )}

        {/* ══ DETECTIONS ══ */}
        {activeTab === 'RAW_FIRMS' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-white/[0.07]">
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono">Raw VIIRS Detections</span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-white/[0.06] text-slate-300 border border-white/[0.08]">
                {detectionsData?.detections.length ?? 0} records
              </span>
            </div>
            {detectionsData?.detections?.length ? (
              <div className="space-y-1.5 max-h-[520px] overflow-y-auto">
                {detectionsData.detections.slice(0, 50).map((det, idx) => (
                  <div key={idx} className="bg-black/30 p-2.5 rounded-lg flex items-center justify-between border border-white/[0.06]">
                    <div>
                      <div className="font-semibold text-white text-xs font-mono">{det.acq_date} {det.acq_time}</div>
                      <div className="text-[9px] text-slate-500 font-mono">{det.satellite || 'NOAA-20'} · CONF: {det.confidence}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-[#89E5FC] font-mono text-xs">{det.frp.toFixed(1)} MW</div>
                      <div className="text-[9px] text-slate-500 font-mono">
                        {det.bright_ti4 ? `${det.bright_ti4.toFixed(1)} K` : 'N/A'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 text-xs font-mono bg-black/20 rounded-xl border border-white/[0.06]">
                No raw FIRMS detection records found.
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Footer — exact Stitch spec ── */}
      <footer
        className="px-4 py-2.5 bg-black/40 border-t border-white/[0.06] flex items-center justify-between text-[10px] font-mono text-slate-500 shrink-0"
        data-purpose="panel-system-status"
      >
        <span>NTRO TACTICAL C4ISR v2.4</span>
        <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          STREAM ACTIVE
        </span>
      </footer>
    </aside>
  );
};
