import { useState, useEffect } from 'react';
import {
  X,
  Layers,
  Satellite,
  Table,
  ExternalLink,
  MapPin,
  Eye,
  Sparkles,
  ShieldCheck
} from 'lucide-react';
import {
  ModelAIcon,
  ModelBIcon,
  ModelCIcon,
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

export const SiteDrawer: React.FC<SiteDrawerProps> = ({ site, asOfDate, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabType>('OVERVIEW');
  const [timelineData, setTimelineData] = useState<SiteTimelineResponse | null>(null);
  const [evidenceData, setEvidenceData] = useState<SiteEvidenceResponse | null>(null);
  const [detectionsData, setDetectionsData] = useState<SiteDetectionsResponse | null>(null);
  const [imageryData, setImageryData] = useState<ImageryCacheSummary[]>([]);
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
      fetchSiteImagery(siteId, asOfDate)
    ]).then(([timeline, evidence, detections, imagery]) => {
      if (!active) return;
      if (timeline.status === 'fulfilled') setTimelineData(timeline.value);
      if (evidence.status === 'fulfilled') setEvidenceData(evidence.value);
      if (detections.status === 'fulfilled') setDetectionsData(detections.value);
      if (imagery.status === 'fulfilled') setImageryData(imagery.value);
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [siteId, asOfDate]);

  if (!site) return null;

  const activePrithviProb = site.model_a?.prithvi_probability ?? (imageryData[0]?.prithvi_probability ?? null);
  const activePrithviStatus = site.model_a?.prithvi_status ?? imageryData[0]?.status ?? 'UNAVAILABLE';
  const activePrithviValue = activePrithviProb !== null
    ? `${(activePrithviProb * 100).toFixed(1)}%`
    : activePrithviStatus === 'PENDING' ? 'PENDING' : 'N/A';

  return (
    <aside className="w-[460px] bg-[#070a12]/95 border-l border-white/10 flex flex-col h-full z-20 shrink-0 text-xs overflow-hidden select-none backdrop-blur tactical-glass shadow-2xl">
      {/* Header Bar */}
      <div className="p-3.5 border-b border-white/10 bg-[#090e1a] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-cyan-300">
              {site.site_id}
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-slate-900 text-cyan-300 font-mono border border-cyan-500/30">
              <ResolverIcon className="w-3 h-3 text-cyan-400" />
              750m RESOLVER
            </span>
            {loading && (
              <span className="text-[10px] font-mono text-cyan-400 animate-pulse">
                SYNCING...
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-1">
            <MapPin className="w-3 h-3 text-slate-500" />
            <span>{site.latitude.toFixed(4)}°N, {site.longitude.toFixed(4)}°E</span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-200 transition-colors"
          title="Close Drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-white/10 bg-[#080d18] px-2 pt-1 gap-1">
        {[
          { id: 'OVERVIEW', label: 'Overview', icon: ModelAIcon },
          { id: 'TIMELINE', label: 'Timeline', icon: ModelBIcon },
          { id: 'EVIDENCE', label: 'Evidence', icon: Layers },
          { id: 'SATELLITE', label: 'Satellite', icon: Satellite },
          { id: 'RAW_FIRMS', label: 'Detections', icon: Table }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-1.5 px-3 py-2 border-b-2 text-[11px] font-medium transition-all ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-white/5 shadow-[0_1px_8px_rgba(6,182,212,0.2)]'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'OVERVIEW' && (
          <div className="space-y-4">
            {/* Active Alert Banner if Present */}
            {site.active_alert && (
              <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/50 space-y-1.5 shadow-[0_0_16px_rgba(239,68,68,0.2)] tactical-glass">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 flex items-center gap-1.5 font-mono">
                    <DecisionEngineIcon className="w-3.5 h-3.5 text-red-400" />
                    {site.active_alert.alert_level} INCIDENT
                  </span>
                  <span className="font-mono text-[10px] text-red-300/80">
                    {site.active_alert.alert_type}
                  </span>
                </div>
                <div className="font-semibold text-slate-100 text-[12px] leading-snug">
                  {site.active_alert.headline}
                </div>
                {site.active_alert.reason_codes && site.active_alert.reason_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {site.active_alert.reason_codes.map((code) => (
                      <span key={code} className="text-[9px] font-mono px-1.5 py-0.5 bg-slate-900/80 rounded text-slate-300 border border-white/10">
                        {code}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Model A Intelligence Card */}
            <div className="p-3 rounded-lg bg-[#0b1120] border border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <ModelAIcon className="w-4 h-4 text-amber-400" />
                  Model A: Source Identity
                </span>
                <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
                  site.model_a?.class_name === 'INDUSTRIAL'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : site.model_a?.class_name === 'NONINDUSTRIAL'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                }`}>
                  {site.model_a?.class_name || 'UNAVAILABLE'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] pt-1.5 border-t border-white/5 font-mono">
                <div>
                  <span className="text-slate-400 text-[10px]">A-Core Probability:</span>
                  <div className="font-bold text-slate-100 mt-0.5 text-xs">
                    {site.model_a?.core_probability !== null && site.model_a?.core_probability !== undefined
                      ? `${(site.model_a.core_probability * 100).toFixed(1)}%`
                      : 'N/A'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px]">Prithvi Visual Score:</span>
                  <div className="font-bold text-cyan-300 mt-0.5 text-xs flex items-center gap-1.5">
                    <span>{activePrithviValue}</span>
                    <span className={`text-[8.5px] px-1 py-0.5 rounded font-mono font-normal border ${
                      activePrithviStatus === 'RESCUED' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' :
                      activePrithviStatus === 'CONFIRMED' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' :
                      activePrithviStatus === 'EVALUATED' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' :
                      'bg-slate-500/20 text-slate-400 border-slate-500/40'
                    }`}>
                      {activePrithviStatus}
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setActiveTab('SATELLITE')}
                className="w-full mt-1.5 py-1.5 px-2 rounded bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono flex items-center justify-center gap-1.5 transition-colors"
              >
                <Eye className="w-3 h-3 text-cyan-400" />
                <span>Inspect HLS / Prithvi Evidence ➔</span>
              </button>
            </div>

            {/* Model B Intelligence Card */}
            <div className="p-3 rounded-lg bg-[#0b1120] border border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <ModelBIcon className="w-4 h-4 text-cyan-400" />
                  Model B: Recurrence Engine
                </span>
                <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  {site.model_b?.state || 'UNAVAILABLE'}
                </span>
              </div>
              <div className="text-[10.5px] text-slate-300 leading-relaxed font-mono">
                {site.model_b?.reason || 'Model B state is unavailable for this cutoff.'}
              </div>
              {site.model_b?.active_days_windows && (
                <div className="grid grid-cols-4 gap-1.5 pt-1.5 border-t border-white/5 font-mono text-[10px] text-center">
                  <div className="p-1.5 rounded bg-slate-900/80 border border-white/5">
                    <span className="text-slate-500 block text-[9px]">30d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['30'] ?? 0}d</span>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900/80 border border-white/5">
                    <span className="text-slate-500 block text-[9px]">90d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['90'] ?? 0}d</span>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900/80 border border-white/5">
                    <span className="text-slate-500 block text-[9px]">180d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['180'] ?? 0}d</span>
                  </div>
                  <div className="p-1.5 rounded bg-slate-900/80 border border-white/5">
                    <span className="text-slate-500 block text-[9px]">365d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['365'] ?? 0}d</span>
                  </div>
                </div>
              )}
            </div>

            {/* Model C Intelligence Card */}
            <div className="p-3 rounded-lg bg-[#0b1120] border border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <ModelCIcon className="w-4 h-4 text-orange-400" />
                  Model C: Anomaly Engine
                </span>
                <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
                  site.model_c?.operational_status === 'CRITICAL'
                    ? 'bg-red-500/20 text-red-300 border-red-500/40'
                    : site.model_c?.operational_status === 'ANOMALOUS'
                    ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                    : site.model_c?.operational_status === 'ELEVATED'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : site.model_c?.operational_status === 'NORMAL'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-slate-500/20 text-slate-300 border-slate-500/40'
                }`}>
                  {site.model_c?.operational_status || 'UNAVAILABLE'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div>
                  <span className="text-slate-400">Anomaly Score:</span>
                  <div className="font-bold text-orange-300 mt-0.5">
                    {site.model_c?.c_score !== null && site.model_c?.c_score !== undefined
                      ? (site.model_c.c_score * 100).toFixed(1) + '%'
                      : 'N/A'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">P99 Evidence Count:</span>
                  <div className="font-bold text-slate-200 mt-0.5">
                    {site.model_c ? `${site.model_c.evidence_99} metrics` : 'N/A'}
                  </div>
                </div>
              </div>
              {site.model_c?.drivers && site.model_c.drivers.length > 0 && (
                <div className="pt-2 border-t border-white/5">
                  <span className="text-[10px] text-slate-400 block mb-1">Anomaly Drivers:</span>
                  <div className="flex flex-wrap gap-1 font-mono text-[9px]">
                    {site.model_c.drivers.map((d) => (
                      <span key={d} className="px-1.5 py-0.5 rounded bg-orange-950/40 text-orange-300 border border-orange-500/30">
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Land Cover & WorldCover Composition */}
            {site.land_cover && (
              <div className="p-3 rounded bg-[#0b1120] border border-white/5 space-y-1.5">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                  WorldCover 10m Composition
                </span>
                <div className="grid grid-cols-2 gap-2 font-mono text-[10px]">
                  {Object.entries(site.land_cover).map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-white/5 pb-0.5">
                      <span className="text-slate-400">{k}:</span>
                      <span className="text-slate-200">{v ? `${(v * 100).toFixed(1)}%` : '0%'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: TIMELINE CHART */}
        {activeTab === 'TIMELINE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 text-xs">
                DAILY THERMAL HISTORY ({timelineData?.total_active_days || 0} active days)
              </span>
              <span className="text-[10px] font-mono text-cyan-400">
                {timelineData?.first_date} &rarr; {timelineData?.last_date}
              </span>
            </div>

            {timelineData && timelineData.history.length > 0 ? (
              <div className="space-y-2">
                {/* SVG Visual Timeline Bar Chart */}
                <div className="p-3 bg-[#0c1424] rounded border border-white/10 space-y-1">
                  <span className="text-[10px] font-mono text-slate-400 block mb-1">
                    MAX FRP (MW) SEQUENCE
                  </span>
                  <div className="h-28 flex items-end gap-1 overflow-x-auto pt-2 pb-1">
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
                            className={`w-3 rounded-t transition-all ${
                              isAnomalous
                                ? 'bg-red-500 shadow-[0_0_6px_#ef4444]'
                                : 'bg-cyan-500 hover:bg-cyan-400'
                            }`}
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Tabular chronological log */}
                <div className="border border-white/10 rounded overflow-hidden">
                  <table className="w-full text-left font-mono text-[10px]">
                    <thead className="bg-[#0b1120] text-slate-400 border-b border-white/10">
                      <tr>
                        <th className="p-1.5">Date</th>
                        <th className="p-1.5">Detections</th>
                        <th className="p-1.5">Max FRP</th>
                        <th className="p-1.5">C Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {timelineData.history.slice(-15).reverse().map((pt, i) => (
                        <tr key={i} className="hover:bg-white/5">
                          <td className="p-1.5 text-slate-300">{pt.acq_date}</td>
                          <td className="p-1.5 text-cyan-300 font-bold">{pt.detections}</td>
                          <td className="p-1.5 text-amber-300">{pt.max_frp.toFixed(1)} MW</td>
                          <td className="p-1.5">
                            <span className={`px-1 rounded ${
                              pt.c_status === 'CRITICAL' ? 'bg-red-500/20 text-red-300' :
                              pt.c_status === 'ANOMALOUS' ? 'bg-orange-500/20 text-orange-300' :
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
            ) : (
              <div className="p-8 text-center text-slate-500 font-mono">
                No recorded thermal activity history for this site.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: EVIDENCE */}
        {activeTab === 'EVIDENCE' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 text-xs">
                CORROBORATING GIS EVIDENCE ({evidenceData?.total_evidence_count || 0})
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                Radius: {evidenceData?.search_radius_m || 5000}m
              </span>
            </div>

            {evidenceData && evidenceData.evidence.length > 0 ? (
              <div className="space-y-2">
                {evidenceData.evidence.map((ev) => (
                  <div key={ev.evidence_id} className="p-2.5 rounded bg-[#0b1120] border border-white/10 space-y-1">
                    <div className="flex items-center justify-between font-mono">
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
                        {ev.source_name}
                      </span>
                      <span className="text-cyan-300 font-bold">
                        {ev.distance_m}m away
                      </span>
                    </div>
                    <div className="font-semibold text-slate-200 text-xs mt-1">
                      {ev.facility_name}
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center justify-between font-mono">
                      <span>Type: {ev.facility_type}</span>
                      <span>Quality: {ev.coordinate_quality}</span>
                    </div>
                    {ev.source_url && (
                      <a
                        href={ev.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[10px] text-cyan-400 hover:underline pt-1"
                      >
                        Source Registry <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 font-mono">
                No overlapping external facility evidence found within 5 km.
                <div className="text-[10px] text-slate-600 mt-1">
                  (Absence of evidence does not imply negative evidence).
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-white/10">
              <span className="font-bold text-slate-200 text-xs">
                TIME-BOUND EVENT EVIDENCE ({evidenceData?.total_event_evidence_count || 0})
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                ±{evidenceData?.temporal_window_days || 7}d from {evidenceData?.as_of_date || 'cutoff'}
              </span>
            </div>
            {evidenceData && evidenceData.event_evidence.length > 0 ? (
              <div className="space-y-2">
                {evidenceData.event_evidence.map((ev) => (
                  <div key={ev.evidence_id} className="p-2.5 rounded bg-[#0b1120] border border-amber-500/20 space-y-1">
                    <div className="flex items-center justify-between font-mono">
                      <span className="text-[10px] px-1.5 rounded bg-amber-500/20 text-amber-300">
                        {ev.source_name}
                      </span>
                      <span className="text-cyan-300 font-bold">{ev.distance_m}m away</span>
                    </div>
                    <div className="font-semibold text-slate-200 text-xs">{ev.evidence_type}</div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      Event: {ev.event_start ? ev.event_start.slice(0, 10) : 'unknown date'}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-slate-500 font-mono text-[10px]">
                No time-matched ICAR/FSI event evidence near this site.
              </div>
            )}
          </div>
        )}

        {/* TAB 4: SATELLITE IMAGERY */}
        {activeTab === 'SATELLITE' && (
          <div className="space-y-3 font-mono">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                <Satellite className="w-3.5 h-3.5 text-cyan-400" />
                HLS / PRITHVI EVIDENCE
              </span>
              <span className="text-[10px] text-cyan-300 font-bold px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30">
                6×224×224 HLS
              </span>
            </div>

            {imageryData.length > 0 ? (
              <div className="space-y-3">
                {imageryData.map((img) => (
                  <div key={img.cache_id} className="p-3 rounded-lg bg-[#0b1120] border border-white/10 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-300 font-bold">{img.product || 'HLS'}</span>
                      <span className={`text-[9px] px-2 py-0.5 rounded border ${
                        img.status === 'AVAILABLE'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : img.status === 'PENDING'
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                          : 'bg-slate-500/20 text-slate-300 border-slate-500/40'
                      }`}>
                        {img.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[10px]">
                      <div className="p-2 rounded bg-black/30 border border-white/5">
                        <div className="text-slate-500">Acquisition</div>
                        <div className="text-slate-200 mt-0.5">{img.acquisition_date}</div>
                      </div>
                      <div className="p-2 rounded bg-black/30 border border-white/5">
                        <div className="text-slate-500">Cloud / invalid</div>
                        <div className="text-slate-200 mt-0.5">
                          {img.cloud_fraction !== null ? `${(img.cloud_fraction * 100).toFixed(1)}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-black/30 border border-white/5">
                        <div className="text-slate-500">Six-band patch</div>
                        <div className="text-slate-200 mt-0.5">{img.patch_uri ? 'CACHED' : 'UNAVAILABLE'}</div>
                      </div>
                      <div className="p-2 rounded bg-black/30 border border-white/5">
                        <div className="text-slate-500">1024-d embedding</div>
                        <div className="text-slate-200 mt-0.5">{img.embedding_uri ? 'CACHED' : 'UNAVAILABLE'}</div>
                      </div>
                    </div>

                    <div className="p-3 rounded bg-black/20 border border-white/5 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5 uppercase">
                          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                          Prithvi-EO-2.0 (300M)
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {img.model_revision || 'MODEL UNAVAILABLE'}
                        </span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px]">
                          <span className="text-slate-400">Industrial probability</span>
                          <span className="text-cyan-300 font-bold text-xs">
                            {img.prithvi_probability !== null ? `${(img.prithvi_probability * 100).toFixed(1)}%` : 'N/A'}
                          </span>
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden border border-white/5">
                          <div
                            className="h-full bg-gradient-to-r from-cyan-500 via-sky-400 to-amber-400 transition-all duration-700"
                            style={{ width: `${(img.prithvi_probability ?? 0) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {img.failure_reason && (
                      <div className="p-2 rounded bg-rose-950/20 border border-rose-500/20 text-[10px] text-rose-200 leading-relaxed">
                        {img.failure_reason}
                      </div>
                    )}

                    <div className="p-2.5 rounded bg-cyan-950/20 border border-cyan-500/30 text-[10px] space-y-1">
                      <div className="flex items-center gap-1.5 text-cyan-300 font-bold">
                        <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                        <span>GUARDED DECISION PROVENANCE</span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">
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
              <div className="p-8 text-center text-slate-500">
                <Satellite className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <div>No cached HLS / Prithvi evidence is available.</div>
                <div className="mt-2 text-[10px] text-slate-600">
                  Eligible retrieval runs asynchronously; unavailable evidence remains null.
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: RAW FIRMS DETECTIONS */}
        {activeTab === 'RAW_FIRMS' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-200 text-xs">
                RAW HOTSPOT LOG ({detectionsData?.count || 0})
              </span>
            </div>

            {detectionsData && detectionsData.detections.length > 0 ? (
              <div className="border border-white/10 rounded overflow-hidden">
                <table className="w-full text-left font-mono text-[9px]">
                  <thead className="bg-[#0b1120] text-slate-400 border-b border-white/10">
                    <tr>
                      <th className="p-1.5">Acq Date</th>
                      <th className="p-1.5">Time</th>
                      <th className="p-1.5">Sensor</th>
                      <th className="p-1.5">FRP</th>
                      <th className="p-1.5">Conf</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {detectionsData.detections.map((d) => (
                      <tr key={d.detection_id} className="hover:bg-white/5">
                        <td className="p-1.5 text-slate-300">{d.acq_date}</td>
                        <td className="p-1.5 text-slate-400">{d.acq_time}</td>
                        <td className="p-1.5 text-slate-400">{d.source_sensor}</td>
                        <td className="p-1.5 text-amber-300 font-bold">{d.frp.toFixed(1)} MW</td>
                        <td className="p-1.5 text-slate-400">{d.confidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 font-mono">
                No individual hotspot detections loaded for this site.
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
