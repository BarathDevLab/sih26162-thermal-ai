import { useState, useEffect } from 'react';
import {
  X,
  Factory,
  Clock,
  Zap,
  AlertTriangle,
  Layers,
  Satellite,
  Table,
  ExternalLink,
  TrendingUp,
  MapPin
} from 'lucide-react';
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
  onClose: () => void;
}

type TabType = 'OVERVIEW' | 'TIMELINE' | 'EVIDENCE' | 'SATELLITE' | 'RAW_FIRMS';

export const SiteDrawer: React.FC<SiteDrawerProps> = ({ site, onClose }) => {
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
    setLoading(true);

    Promise.allSettled([
      fetchSiteTimeline(siteId),
      fetchSiteEvidence(siteId, 5000),
      fetchSiteDetections(siteId),
      fetchSiteImagery(siteId)
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
  }, [siteId]);

  if (!site) return null;

  return (
    <aside className="w-[450px] bg-[#070a12] border-l border-white/10 flex flex-col h-full z-20 shrink-0 text-xs overflow-hidden select-none">
      {/* Header Bar */}
      <div className="p-3.5 border-b border-white/10 bg-[#0b1120] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-cyan-300">
              {site.site_id}
            </span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono border border-slate-700">
              750m RESOLVER
            </span>
            {loading && (
              <span className="text-[10px] font-mono text-cyan-400 animate-pulse">
                SYNCING...
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-0.5">
            <MapPin className="w-3 h-3 text-slate-500" />
            <span>{site.latitude.toFixed(4)}°N, {site.longitude.toFixed(4)}°E</span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-slate-200 transition-colors"
          title="Close Drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-white/10 bg-[#090d16] px-2 pt-1 gap-1">
        {[
          { id: 'OVERVIEW', label: 'Overview', icon: Factory },
          { id: 'TIMELINE', label: 'Timeline', icon: TrendingUp },
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
              className={`flex items-center gap-1.5 px-2.5 py-2 border-b-2 text-[11px] font-medium transition-all ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-white/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-3 h-3" />
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
              <div className="p-3 rounded bg-red-950/30 border border-red-500/40 space-y-1.5 shadow-[0_0_12px_rgba(239,68,68,0.15)]">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3 text-red-400" />
                    {site.active_alert.alert_level} ALERT
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
                      <span key={code} className="text-[9px] font-mono px-1.5 py-0.5 bg-slate-900/60 rounded text-slate-300 border border-white/10">
                        {code}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Model A Intelligence Card */}
            <div className="p-3 rounded bg-[#0b1120] border border-white/5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Factory className="w-3.5 h-3.5 text-amber-400" />
                  Model A: Source Identity
                </span>
                <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
                  site.model_a?.class_name === 'INDUSTRIAL'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : site.model_a?.class_name === 'NONINDUSTRIAL'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                }`}>
                  {site.model_a?.class_name || 'UNKNOWN'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-white/5 font-mono">
                <div>
                  <span className="text-slate-400">Core Probability:</span>
                  <div className="font-bold text-slate-200 mt-0.5">
                    {site.model_a?.core_probability ? `${(site.model_a.core_probability * 100).toFixed(1)}%` : 'N/A'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Prithvi Rescue:</span>
                  <div className="font-bold text-slate-200 mt-0.5">
                    {site.model_a?.prithvi_status || 'NOT_TRIGGERED'}
                  </div>
                </div>
              </div>
            </div>

            {/* Model B Intelligence Card */}
            <div className="p-3 rounded bg-[#0b1120] border border-white/5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                  Model B: Temporal State
                </span>
                <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  {site.model_b?.state || 'DORMANT'}
                </span>
              </div>
              <div className="text-[11px] text-slate-300 leading-relaxed font-mono">
                {site.model_b?.reason || 'Calculated deterministically based on observation windows.'}
              </div>
              {site.model_b?.active_days_windows && (
                <div className="grid grid-cols-4 gap-1 pt-1 border-t border-white/5 font-mono text-[10px] text-center">
                  <div className="p-1 rounded bg-slate-900/60">
                    <span className="text-slate-500 block">30d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['30d'] ?? 0}d</span>
                  </div>
                  <div className="p-1 rounded bg-slate-900/60">
                    <span className="text-slate-500 block">90d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['90d'] ?? 0}d</span>
                  </div>
                  <div className="p-1 rounded bg-slate-900/60">
                    <span className="text-slate-500 block">180d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['180d'] ?? 0}d</span>
                  </div>
                  <div className="p-1 rounded bg-slate-900/60">
                    <span className="text-slate-500 block">365d</span>
                    <span className="text-cyan-300 font-bold">{site.model_b.active_days_windows['365d'] ?? 0}d</span>
                  </div>
                </div>
              )}
            </div>

            {/* Model C Intelligence Card */}
            <div className="p-3 rounded bg-[#0b1120] border border-white/5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-orange-400" />
                  Model C: Anomaly Engine
                </span>
                <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
                  site.model_c?.operational_status === 'CRITICAL'
                    ? 'bg-red-500/20 text-red-300 border-red-500/40'
                    : site.model_c?.operational_status === 'ANOMALOUS'
                    ? 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                    : site.model_c?.operational_status === 'ELEVATED'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                }`}>
                  {site.model_c?.operational_status || 'NORMAL'}
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
                    {site.model_c?.evidence_99 ?? 0} metrics
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
                          title={`${pt.acq_date}: Max FRP ${pt.max_frp} MW, ${pt.detections} detections, Status: ${pt.c_status || 'NORMAL'}`}
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
                              {pt.c_status || 'NORMAL'}
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
          </div>
        )}

        {/* TAB 4: SATELLITE IMAGERY */}
        {activeTab === 'SATELLITE' && (
          <div className="space-y-3">
            <span className="font-bold text-slate-200 text-xs block">
              HLS SCENES & PRITHVI VISUAL EMBEDDINGS
            </span>

            {imageryData.length > 0 ? (
              <div className="space-y-2">
                {imageryData.map((img) => (
                  <div key={img.cache_id} className="p-3 rounded bg-[#0b1120] border border-white/10 space-y-1.5 font-mono">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-300 font-bold">{img.scene_id}</span>
                      <span className="text-slate-400 text-[10px]">{img.capture_date}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[10px] pt-1 border-t border-white/5">
                      <div>
                        <span className="text-slate-500">Cloud Cover:</span>
                        <span className="text-slate-300 ml-1">{img.cloud_cover !== null ? `${img.cloud_cover}%` : 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Prithvi Score:</span>
                        <span className="text-cyan-300 ml-1 font-bold">
                          {img.prithvi_score !== null ? (img.prithvi_score * 100).toFixed(1) + '%' : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 font-mono">
                No cached HLS satellite scenes for this site coordinates.
                <div className="text-[10px] text-slate-600 mt-1">
                  (A-Core operates independently of optical HLS coverage).
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
