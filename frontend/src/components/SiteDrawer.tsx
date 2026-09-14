import React, { useState, useEffect } from 'react';
import {
  X,
  Satellite,
  ExternalLink,
  Sparkles,
  ShieldCheck,
  Hexagon,
  Clock,
  Activity
} from 'lucide-react';
import {
  DecisionEngineIcon
} from './Icons';
import type {
  SiteDetail,
  SiteTimelineResponse,
  SiteEvidenceResponse,
  SiteDetectionsResponse,
  ImageryCacheSummary,
  SiteReviewHistoryResponse
} from '../types/api';
import {
  fetchSiteTimeline,
  fetchSiteEvidence,
  fetchSiteDetections,
  fetchSiteImagery,
  fetchSiteReviews
} from '../services/api';
import { AnalystReviewPanel } from './AnalystReviewPanel';

interface SiteDrawerProps {
  site: SiteDetail | null;
  asOfDate?: string;
  onRefreshSite: (siteId: string, asOfDate?: string) => Promise<SiteDetail>;
  onClose: () => void;
}

type TabType = 'OVERVIEW' | 'TIMELINE' | 'EVIDENCE' | 'SATELLITE' | 'RAW_FIRMS' | 'REVIEW';

const PRITHVI_STATUS_POLL_MS = 4_000;
const PRITHVI_STATUS_POLL_LIMIT_MS = 10 * 60_000;

export const SiteDrawer: React.FC<SiteDrawerProps> = ({ site, asOfDate, onRefreshSite, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabType>('OVERVIEW');
  const [timelineData, setTimelineData] = useState<SiteTimelineResponse | null>(null);
  const [evidenceData, setEvidenceData] = useState<SiteEvidenceResponse | null>(null);
  const [detectionsData, setDetectionsData] = useState<SiteDetectionsResponse | null>(null);
  const [imageryData, setImageryData] = useState<ImageryCacheSummary[]>([]);
  const [reviewHistory, setReviewHistory] = useState<SiteReviewHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const siteId = site?.site_id;

  useEffect(() => {
    if (!siteId) return;

    let active = true;
    queueMicrotask(() => {
      if (active) setLoading(true);
    });

    Promise.allSettled([
      fetchSiteTimeline(siteId, asOfDate),
      fetchSiteEvidence(siteId, 5000, asOfDate),
      fetchSiteDetections(siteId, asOfDate),
      fetchSiteImagery(siteId, asOfDate),
      asOfDate === undefined && site?.model_a?.class_name === 'UNKNOWN'
        ? fetchSiteReviews(siteId)
        : Promise.resolve(null)
    ]).then(async ([timeline, evidence, detections, imagery, reviews]) => {
      if (!active) return;
      if (timeline.status === 'fulfilled') setTimelineData(timeline.value);
      if (evidence.status === 'fulfilled') setEvidenceData(evidence.value);
      if (detections.status === 'fulfilled') setDetectionsData(detections.value);
      if (imagery.status === 'fulfilled') setImageryData(imagery.value);
      if (reviews.status === 'fulfilled') setReviewHistory(reviews.value);
      setLoading(false);

      if (asOfDate === undefined) {
        try {
          await onRefreshSite(siteId);
        } catch (error) {
          console.error(`Failed to refresh Model A status for ${siteId}:`, error);
        }
      }
    });

    return () => {
      active = false;
    };
  }, [siteId, site?.model_a?.class_name, asOfDate, onRefreshSite]);

  const prithviStatus = site?.model_a?.prithvi_status;

  useEffect(() => {
    if (!siteId || asOfDate !== undefined || prithviStatus !== 'PENDING') return;

    let active = true;
    let timer: number | undefined;
    const deadline = Date.now() + PRITHVI_STATUS_POLL_LIMIT_MS;

    const poll = async () => {
      const [imagery, detail] = await Promise.allSettled([
        fetchSiteImagery(siteId),
        onRefreshSite(siteId)
      ]);
      if (!active) return;

      if (imagery.status === 'fulfilled') setImageryData(imagery.value);
      if (detail.status === 'fulfilled' && detail.value.model_a?.prithvi_status === 'PENDING' && Date.now() < deadline) {
        timer = window.setTimeout(poll, PRITHVI_STATUS_POLL_MS);
      }
    };

    timer = window.setTimeout(poll, 1_500);
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [siteId, asOfDate, prithviStatus, onRefreshSite]);

  if (!site) return null;

  const availableImagery = imageryData.find((item) => item.prithvi_probability !== null);
  const activePrithviProb = site.model_a?.prithvi_probability ?? availableImagery?.prithvi_probability ?? null;
  const activePrithviStatus = site.model_a?.prithvi_status === 'PENDING'
    ? 'PENDING'
    : activePrithviProb !== null
    ? 'AVAILABLE'
    : site.model_a?.prithvi_status ?? imageryData[0]?.status ?? 'UNAVAILABLE';
  const activePrithviValue = activePrithviProb !== null
    ? `${(activePrithviProb * 100).toFixed(1)}%`
    : activePrithviStatus === 'PENDING' ? 'PENDING' : 'N/A';
  const prithviRescued = site.model_a?.decision === 'INDUSTRIAL_PRITHVI_RESCUE';
  const prithviPending = activePrithviStatus === 'PENDING';

  return (
    <aside className="w-[420px] max-w-[calc(100vw-32px)] flex flex-col h-full z-20 shrink-0 text-xs overflow-hidden select-none bg-[#070d19]/95 backdrop-blur-xl rounded-2xl border border-sky-500/20 shadow-[0_20px_60px_rgba(0,0,0,0.85)] font-mono">
      {/* ── Fixed Header Bar ── */}
      <div className="p-4 border-b border-sky-500/15 bg-[#070e1a]/80 backdrop-blur-md flex items-start justify-between gap-3 shrink-0">
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono text-sm font-bold text-white tracking-wide truncate max-w-[210px]" title={site.site_id}>
              {site.site_id}
            </span>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-sky-950/60 text-cyan-300 border border-sky-500/40 shrink-0">
              750m RESOLVER
            </span>
            {loading && (
              <span className="text-[9px] text-cyan-400 animate-pulse font-mono shrink-0">
                SYNCING
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
            <span className="text-rose-400 text-sm leading-none">📍</span>
            <span>{site.latitude.toFixed(4)}°N, {site.longitude.toFixed(4)}°E</span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-6 h-6 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors flex items-center justify-center cursor-pointer shrink-0 mt-0.5"
          title="Close Drawer"
          type="button"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Minimal Tactical Pill Tabs ── */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-sky-500/15 bg-[#050a14]/60 shrink-0 overflow-x-auto no-scrollbar font-mono text-xs">
        {[
          { id: 'OVERVIEW', label: 'Overview' },
          { id: 'TIMELINE', label: 'Timeline' },
          { id: 'EVIDENCE', label: 'Evidence' },
          { id: 'SATELLITE', label: 'Satellite' },
          { id: 'RAW_FIRMS', label: 'Detections' },
          ...(asOfDate === undefined && site.model_a?.class_name === 'UNKNOWN'
            ? [{ id: 'REVIEW', label: 'Review' }]
            : [])
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              type="button"
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all cursor-pointer shrink-0 ${
                isActive
                  ? 'text-white bg-[#0c1c2e] border border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.25)] font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab Content Area ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">

        {/* ══ TAB 1: OVERVIEW ══ */}
        {activeTab === 'OVERVIEW' && (
          <div className="space-y-3">
            {/* Active Alert Banner if Present */}
            {site.active_alert && (
              <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-500/40 space-y-1.5 shadow-[0_0_14px_rgba(244,63,94,0.15)]">
                <div className="flex items-center justify-between">
                  <span className="chip chip-alert text-[8.5px] flex items-center gap-1 font-bold">
                    <DecisionEngineIcon className="w-3 h-3 text-rose-400" />
                    {site.active_alert.alert_level} PRIORITY
                  </span>
                  <span className="text-[9px] text-rose-300/80 font-mono">
                    {site.active_alert.alert_type}
                  </span>
                </div>
                <div className="font-semibold text-slate-100 text-[11.5px] leading-snug">
                  {site.active_alert.headline}
                </div>
                {site.active_alert.reason_codes && site.active_alert.reason_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    {site.active_alert.reason_codes.map((code) => (
                      <span key={code} className="text-[8.5px] px-1.5 py-0.5 rounded bg-black/50 text-slate-300 border border-white/10 font-mono">
                        {code}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Model A Intelligence Card */}
            <div className="p-3.5 rounded-xl bg-[#08101d]/90 border border-sky-500/20 space-y-3 shadow-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2 font-mono">
                  <Hexagon className="w-4 h-4 text-amber-400 stroke-[1.75]" />
                  MODEL A: SOURCE IDENTITY
                </span>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  site.model_a?.class_name === 'INDUSTRIAL'
                    ? 'bg-amber-950/40 text-amber-300 border-amber-500/40'
                    : site.model_a?.class_name === 'NONINDUSTRIAL'
                    ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40'
                    : 'bg-sky-950/40 text-slate-300 border-sky-500/30'
                }`}>
                  {site.model_a?.class_name || 'UNKNOWN'}
                </span>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">A-Core Probability:</span>
                  <span className="font-bold text-white">
                    {site.model_a?.core_probability !== null && site.model_a?.core_probability !== undefined
                      ? `${(site.model_a.core_probability * 100).toFixed(1)}%`
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Prithvi Visual Score:</span>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">
                      {activePrithviValue}
                    </span>
                    <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                      activePrithviStatus === 'AVAILABLE' || activePrithviStatus === 'EVALUATED'
                        ? 'bg-sky-950/60 text-cyan-300 border-sky-400/40'
                        : activePrithviStatus === 'PENDING'
                        ? 'bg-amber-950/60 text-amber-300 border-amber-400/40 animate-pulse'
                        : 'bg-slate-900/60 text-slate-400 border-slate-700/40'
                    }`}>
                      {activePrithviStatus}
                    </span>
                  </div>
                </div>
              </div>

              {prithviPending && (
                <div className="prithvi-progress-row" role="status" aria-live="polite">
                  <span className="prithvi-progress-orbit" aria-hidden="true" />
                  <span className="text-[9.5px]">
                    VISUAL EVALUATION QUEUED
                    <small>Retrieving genuine HLS evidence; card refreshes automatically.</small>
                  </span>
                </div>
              )}
              {prithviRescued && (
                <div className="prithvi-rescue-row" role="status" aria-live="polite">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-[10px] text-amber-300 font-bold">UNKNOWN → INDUSTRIAL · PRITHVI RESCUE VERIFIED</span>
                </div>
              )}

              <button
                onClick={() => setActiveTab('SATELLITE')}
                type="button"
                className="w-full py-2 px-3 rounded-lg bg-[#0b1b2d] hover:bg-[#102742] border border-sky-500/30 text-sky-200 text-xs font-mono font-medium text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-0.5 shadow-sm"
              >
                <span>Inspect Satellite Photo &amp; Prithvi Breakdown</span>
                <span className="text-sm leading-none">➔</span>
              </button>
            </div>

            {/* Model B Intelligence Card */}
            <div className="p-3.5 rounded-xl bg-[#08101d]/90 border border-sky-500/20 space-y-2.5 shadow-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2 font-mono">
                  <Clock className="w-4 h-4 text-cyan-400 stroke-[1.75]" />
                  MODEL B: RECURRENCE ENGINE
                </span>
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-sky-950/40 text-cyan-300 border border-sky-500/30">
                  {site.model_b?.state || 'REACTIVATED'}
                </span>
              </div>

              <div className="text-xs text-slate-300 leading-relaxed font-mono">
                {site.model_b?.reason || 'Calculated deterministically based on observation windows.'}
              </div>

              <div className="grid grid-cols-4 gap-2 pt-1 font-mono">
                {[
                  { label: '30d', key: '30' },
                  { label: '90d', key: '90' },
                  { label: '180d', key: '180' },
                  { label: '365d', key: '365' }
                ].map(({ label, key }) => {
                  const val = site.model_b?.active_days_windows
                    ? (site.model_b.active_days_windows[label] ?? site.model_b.active_days_windows[key] ?? 0)
                    : 0;
                  return (
                    <div key={label} className="py-2.5 px-2 rounded-lg bg-[#050c17] border border-sky-500/20 text-center flex flex-col items-center justify-center">
                      <span className="text-[10px] text-slate-400 font-mono">{label}</span>
                      <span className="text-xs font-bold text-white font-mono mt-0.5">{val}d</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Model C Intelligence Card */}
            <div className="p-3.5 rounded-xl bg-[#08101d]/90 border border-sky-500/20 space-y-3 shadow-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2 font-mono">
                  <Activity className="w-4 h-4 text-rose-400 stroke-[1.75]" />
                  MODEL C: ANOMALY ENGINE
                </span>
                <span className={`text-[9.5px] font-mono font-bold px-2 py-0.5 rounded border ${
                  site.model_c?.operational_status === 'CRITICAL'
                    ? 'bg-rose-950/40 text-rose-300 border-rose-500/40'
                    : site.model_c?.operational_status === 'ANOMALOUS'
                    ? 'bg-orange-950/40 text-orange-300 border-orange-500/40'
                    : site.model_c?.operational_status === 'NORMAL'
                    ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40'
                    : 'bg-emerald-950/40 text-emerald-400 border-emerald-500/40'
                }`}>
                  {site.model_c?.operational_status || 'INSUFFICIENT_HISTORY'}
                </span>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Anomaly Score:</span>
                  <span className="font-bold text-amber-400">
                    {site.model_c?.c_score !== null && site.model_c?.c_score !== undefined
                      ? (site.model_c.c_score * 100).toFixed(1) + '%'
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">P99 Evidence Count:</span>
                  <span className="font-bold text-white">
                    {site.model_c?.evidence_99 ?? 0} metrics
                  </span>
                </div>
              </div>

              {site.model_c?.drivers && site.model_c.drivers.length > 0 && (
                <div className="pt-2 border-t border-white/[0.06]">
                  <span className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Anomaly Drivers:</span>
                  <div className="flex flex-wrap gap-1 font-mono text-[9.5px]">
                    {site.model_c.drivers.map((d) => (
                      <span key={d} className="px-2 py-0.5 rounded bg-sky-950/40 text-cyan-300 border border-sky-500/30">
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* WorldCover 10m Composition */}
            {site.land_cover && (
              <div className="p-3.5 rounded-xl bg-[#08101d]/90 border border-sky-500/20 space-y-2 shadow-md">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block font-mono">
                  WorldCover 10m Composition
                </span>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[10px] font-mono">
                  {Object.entries(site.land_cover).map(([k, v]) => (
                    <div key={k} className="flex justify-between p-1.5 rounded bg-[#050c17] border border-sky-500/15">
                      <span className="text-slate-400">{k}:</span>
                      <span className="text-slate-200 font-semibold">{v ? `${(v * 100).toFixed(1)}%` : '0%'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══ TAB 2: TIMELINE ══ */}
        {activeTab === 'TIMELINE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 text-[11px] uppercase tracking-wider">
                DAILY THERMAL HISTORY ({timelineData?.total_active_days || 0} active days)
              </span>
              <span className="text-[9.5px] text-[#89E5FC] font-semibold">
                {timelineData?.first_date} → {timelineData?.last_date}
              </span>
            </div>

            {timelineData && timelineData.history.length > 0 ? (
              <div className="space-y-2.5">
                {/* SVG Visual Timeline Bar Chart */}
                <div className="p-3 rounded-xl bg-black/25 border border-white/[0.07] space-y-1.5">
                  <span className="text-[9px] text-[#64748B] block uppercase tracking-wider">
                    MAX FRP (MW) SEQUENCE
                  </span>
                  <div className="h-28 flex items-end gap-1 overflow-x-auto pt-2 pb-1 custom-scrollbar">
                    {timelineData.history.map((pt, idx) => {
                      const maxPossibleFRP = Math.max(...timelineData.history.map(h => h.max_frp || 1), 10);
                      const barHeight = Math.max(4, Math.round((pt.max_frp / maxPossibleFRP) * 80));
                      const isAnomalous = pt.c_status === 'CRITICAL' || pt.c_status === 'ANOMALOUS';

                      return (
                        <div
                          key={idx}
                          className="flex flex-col items-center group relative cursor-pointer"
                          title={`${pt.acq_date}: Max FRP ${pt.max_frp} MW, ${pt.detections} detections, Status: ${pt.c_status || 'UNAVAILABLE'}`}
                        >
                          <div
                            style={{ height: `${barHeight}px` }}
                            className={`w-2.5 rounded-t transition-all ${
                              isAnomalous
                                ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e]'
                                : 'bg-[#89E5FC] hover:bg-white'
                            }`}
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Tabular chronological log */}
                <div className="rounded-xl border border-white/[0.07] overflow-hidden bg-black/20">
                  <table className="w-full text-left text-[9.5px]">
                    <thead className="bg-black/40 text-[#64748B] border-b border-white/[0.07]">
                      <tr>
                        <th className="p-2">Date</th>
                        <th className="p-2">Detections</th>
                        <th className="p-2">Max FRP</th>
                        <th className="p-2">C Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {timelineData.history.slice(-15).reverse().map((pt, i) => (
                        <tr key={i} className="hover:bg-white/[0.04] transition-colors">
                          <td className="p-2 text-slate-300">{pt.acq_date}</td>
                          <td className="p-2 text-[#89E5FC] font-bold">{pt.detections}</td>
                          <td className="p-2 text-amber-300 font-bold">{pt.max_frp.toFixed(1)} MW</td>
                          <td className="p-2">
                            <span className={`px-1.5 py-0.5 rounded text-[8.5px] ${
                              pt.c_status === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' :
                              pt.c_status === 'ANOMALOUS' ? 'bg-orange-500/20 text-orange-300 border border-orange-500/30' :
                              'text-slate-400'
                            }`}>
                              {pt.c_status || 'UNAVAILABLE'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : prithviPending ? (
              <div className="prithvi-empty-progress" role="status" aria-live="polite">
                <span className="prithvi-progress-orbit" aria-hidden="true" />
                <div className="text-cyan-200 font-bold tracking-wider">HLS / PRITHVI EVALUATION IN PROGRESS</div>
                <div className="mt-2 text-[10px] text-slate-500">
                  Server-side retrieval and inference are asynchronous. Results will appear here automatically.
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-[#64748B] bg-black/20 rounded-xl border border-white/[0.06]">
                No recorded thermal activity history for this site.
              </div>
            )}
          </div>
        )}

        {/* ══ TAB 3: EVIDENCE ══ */}
        {activeTab === 'EVIDENCE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 text-[11px] uppercase tracking-wider">
                CORROBORATING GIS EVIDENCE ({evidenceData?.total_evidence_count || 0})
              </span>
              <span className="text-[9.5px] text-[#64748B]">
                Radius: {evidenceData?.search_radius_m || 5000}m
              </span>
            </div>

            {evidenceData && evidenceData.evidence.length > 0 ? (
              <div className="space-y-2">
                {evidenceData.evidence.map((ev) => (
                  <div key={ev.evidence_id} className="p-2.5 rounded-xl bg-black/25 border border-white/[0.07] space-y-1 hover:border-white/[0.12] transition-all">
                    <div className="flex items-center justify-between">
                      <span className="chip chip-cyan text-[8.5px]">
                        {ev.source_name}
                      </span>
                      <span className="text-[#89E5FC] font-bold text-[10px]">
                        {ev.distance_m}m away
                      </span>
                    </div>
                    <div className="font-semibold text-white text-[11px] mt-1">
                      {ev.facility_name}
                    </div>
                    <div className="text-[9.5px] text-[#64748B] flex items-center justify-between">
                      <span>Type: {ev.facility_type}</span>
                      <span>Quality: {ev.coordinate_quality}</span>
                    </div>
                    {ev.source_url && (
                      <a
                        href={ev.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[9.5px] text-[#89E5FC] hover:underline pt-0.5"
                      >
                        Source Registry <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-[#64748B] bg-black/20 rounded-xl border border-white/[0.06]">
                No overlapping external facility evidence found within 5 km.
              </div>
            )}
          </div>
        )}

        {/* ══ TAB 4: SATELLITE IMAGERY ══ */}
        {activeTab === 'SATELLITE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-white/[0.07] pb-2">
              <span className="font-semibold text-white text-[11px] flex items-center gap-1.5 uppercase tracking-wider">
                <Satellite className="w-3.5 h-3.5 text-[#89E5FC]" />
                HLS / PRITHVI EVIDENCE
              </span>
              <span className="chip chip-cyan text-[8.5px]">
                6×224×224 HLS
              </span>
            </div>

            {imageryData.length > 0 ? (
              <div className="space-y-3">
                {imageryData.map((img) => (
                  <div key={img.cache_id} className="hud-card rounded-xl p-3 space-y-2.5 bg-black/25 border border-white/[0.07]">
                    <div className="flex items-center justify-between">
                      <span className="text-[#89E5FC] font-bold text-[11px]">{img.product || 'HLS'}</span>
                      <span className="chip text-[8.5px]">
                        {img.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[9.5px]">
                      <div className="p-2 rounded-lg bg-black/30 border border-white/[0.04]">
                        <span className="text-[#64748B] block">Acquisition</span>
                        <span className="text-slate-200 mt-0.5 font-semibold">{img.acquisition_date}</span>
                      </div>
                      <div className="p-2 rounded-lg bg-black/30 border border-white/[0.04]">
                        <span className="text-[#64748B] block">Cloud / Invalid</span>
                        <span className="text-slate-200 mt-0.5 font-semibold">
                          {img.cloud_fraction !== null ? `${(img.cloud_fraction * 100).toFixed(1)}%` : 'N/A'}
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-black/20 border border-white/[0.05] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-white flex items-center gap-1.5 uppercase">
                          <Sparkles className="w-3 h-3 text-[#89E5FC]" />
                          Prithvi-EO-2.0 (300M)
                        </span>
                        <span className="text-[9px] text-[#64748B]">
                          {img.model_revision || 'MODEL UNAVAILABLE'}
                        </span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-[9.5px]">
                          <span className="text-[#64748B]">Industrial Probability</span>
                          <span className="text-[#89E5FC] font-bold">
                            {img.prithvi_probability !== null ? `${(img.prithvi_probability * 100).toFixed(1)}%` : 'N/A'}
                          </span>
                        </div>
                        <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden border border-white/[0.06]">
                          <div
                            className="h-full bg-gradient-to-r from-cyan-500 via-sky-400 to-amber-400 transition-all duration-700"
                            style={{ width: `${(img.prithvi_probability ?? 0) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="p-2 rounded-lg bg-sky-950/20 border border-sky-400/20 text-[9.5px] space-y-1">
                      <div className="flex items-center gap-1 text-[#89E5FC] font-semibold">
                        <ShieldCheck className="w-3 h-3 text-[#89E5FC]" />
                        <span>GUARDED DECISION PROVENANCE</span>
                      </div>
                      <p className="text-slate-300 leading-relaxed text-[9px]">
                        {img.prithvi_probability === null || site.model_a?.core_probability === null || site.model_a?.core_probability === undefined
                          ? 'No Prithvi probability is available. No visual inference has been fabricated, and the A-Core decision remains unchanged.'
                          : site.model_a.core_probability >= 0.885
                          ? `A-Core is positive (${(site.model_a.core_probability * 100).toFixed(1)}%). Prithvi evidence cannot veto it.`
                          : site.model_a.core_probability >= 0.405 && img.prithvi_probability >= 0.965
                          ? `A-Core was uncertain and genuine Prithvi evidence met the 96.5% positive-rescue threshold.`
                          : 'The positive-rescue threshold was not met; the site remains UNKNOWN under the frozen policy.'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-[#64748B] bg-black/20 rounded-xl border border-white/[0.06]">
                <Satellite className="w-6 h-6 text-slate-600 mx-auto mb-2" />
                <div>No cached HLS / Prithvi evidence is available.</div>
              </div>
            )}
          </div>
        )}

        {/* ══ TAB 5: RAW FIRMS DETECTIONS ══ */}
        {activeTab === 'RAW_FIRMS' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 text-[11px] uppercase tracking-wider">
                RAW HOTSPOT LOG ({detectionsData?.count || 0})
              </span>
            </div>

            {detectionsData && detectionsData.detections.length > 0 ? (
              <div className="rounded-xl border border-white/[0.07] overflow-hidden bg-black/20">
                <table className="w-full text-left text-[9px]">
                  <thead className="bg-black/40 text-[#64748B] border-b border-white/[0.07]">
                    <tr>
                      <th className="p-2">Acq Date</th>
                      <th className="p-2">Time</th>
                      <th className="p-2">Sensor</th>
                      <th className="p-2">FRP</th>
                      <th className="p-2">Conf</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {detectionsData.detections.map((d) => (
                      <tr key={d.detection_id} className="hover:bg-white/[0.04] transition-colors">
                        <td className="p-2 text-slate-300">{d.acq_date}</td>
                        <td className="p-2 text-[#64748B]">{d.acq_time}</td>
                        <td className="p-2 text-[#64748B]">{d.source_sensor}</td>
                        <td className="p-2 text-amber-300 font-bold">{d.frp.toFixed(1)} MW</td>
                        <td className="p-2 text-[#64748B]">{d.confidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-[#64748B] bg-black/20 rounded-xl border border-white/[0.06]">
                No individual hotspot detections loaded for this site.
              </div>
            )}
          </div>
        )}

        {activeTab === 'REVIEW' && asOfDate === undefined && site.model_a?.class_name === 'UNKNOWN' && (
          <AnalystReviewPanel
            key={site.site_id}
            site={site}
            evidence={evidenceData}
            imagery={imageryData}
            detections={detectionsData}
            history={reviewHistory}
            onHistoryChange={setReviewHistory}
          />
        )}
      </div>

      {/* ── Tactical Footer Status Bar ── */}
      <div className="p-3.5 border-t border-sky-500/15 bg-[#050a14]/90 flex items-center justify-between text-[10px] font-mono shrink-0">
        <span className="text-slate-500 font-mono tracking-wider font-semibold">NTRO TACTICAL C4ISR v2.4</span>
        <div className="flex items-center gap-2 text-emerald-400 font-mono font-bold tracking-wider">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse inline-block" />
          <span>STREAM ACTIVE</span>
        </div>
      </div>
    </aside>
  );
};
