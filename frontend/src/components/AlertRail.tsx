import React, { useState, useEffect } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Crosshair,
  Check,
  Radio
} from 'lucide-react';
import type { AlertItem } from '../types/api';
import { acknowledgeAlert } from '../services/api';

interface AlertRailProps {
  alerts: AlertItem[];
  onJumpToSite: (siteId: string, lat?: number, lon?: number) => void;
  onAlertAcknowledged: (alertId: string) => void;
  hasSelectedSite?: boolean;
  onClose?: () => void;
}

export const AlertRail: React.FC<AlertRailProps> = ({
  alerts,
  onJumpToSite,
  onAlertAcknowledged,
  hasSelectedSite = false
}) => {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [ackingId, setAckingId] = useState<string | null>(null);

  // Auto-collapse AlertRail into compact pill when site drawer opens to prevent blocking the map
  useEffect(() => {
    if (hasSelectedSite) {
      setCollapsed(true);
    }
  }, [hasSelectedSite]);

  const handleAck = async (alertId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setAckingId(alertId);
    try {
      await acknowledgeAlert(alertId, 'analyst_operator');
      onAlertAcknowledged(alertId);
    } catch (err) {
      console.error('Failed to ack alert:', err);
    } finally {
      setAckingId(null);
    }
  };

  const criticalCount = alerts.filter(a => a.alert_level === 'CRITICAL').length;

  // Responsive docking: If site drawer is open on the right (460px + 16px = 476px), dock adjacent to it with 10px clearance
  const positionClass = hasSelectedSite
    ? 'top-14 right-[485px]'
    : 'top-14 right-4';

  // Compact floating pill when collapsed
  if (collapsed) {
    return (
      <div
        className={`absolute ${positionClass} z-20 transition-all duration-300 pointer-events-auto select-none`}
      >
        <button
          onClick={() => setCollapsed(false)}
          type="button"
          className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-sky-400/35 bg-[#070e1e]/90 backdrop-blur-md shadow-[0_4px_20px_rgba(0,0,0,0.65)] font-mono text-xs cursor-pointer hover:bg-[#16385c]/80 hover:border-sky-400/60 transition-all group"
        >
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_#f43f5e] animate-pulse" />
            <span className="font-bold text-white tracking-wider">RADAR</span>
          </div>

          <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
            {criticalCount > 0 ? `${criticalCount} CRIT` : `${alerts.length} ALERTS`}
          </span>

          <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-white transition-colors" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`absolute ${positionClass} z-20 w-[370px] max-w-[calc(100vw-32px)] transition-all duration-300 select-none pointer-events-auto`}
    >
      <div className="rounded-2xl border border-sky-400/30 bg-[#070e1e]/90 backdrop-blur-md shadow-[0_12px_36px_rgba(0,0,0,0.75)] overflow-hidden font-mono">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-sky-400/20 bg-sky-950/25">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shadow-[0_0_8px_rgba(244,63,94,0.3)]">
              <Radio className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
            </div>
            <span className="text-xs font-bold tracking-widest text-white uppercase">
              INCIDENT RADAR
            </span>
            <span className={`text-[9.5px] px-2 py-0.5 rounded-full font-bold border ${
              criticalCount > 0
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-[0_0_8px_rgba(244,63,94,0.25)]'
                : 'bg-sky-500/20 text-sky-300 border-sky-400/30'
            }`}>
              {criticalCount > 0 ? `${criticalCount} CRITICAL` : `${alerts.length} ACTIVE`}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setCollapsed(true)}
              aria-label="Collapse Radar"
              title="Minimize"
              type="button"
              className="w-6 h-6 rounded-md flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            >
              <ChevronUp className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Alert Feed List */}
        <div className="max-h-[350px] overflow-y-auto p-2.5 space-y-2">
          {alerts.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs">
              No active operational anomalies detected.
            </div>
          ) : (
            alerts.slice(0, 20).map((alert) => {
              const isCritical = alert.alert_level === 'CRITICAL';
              return (
                <div
                  key={alert.alert_id}
                  onClick={() => onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined)}
                  className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isCritical
                      ? 'border-rose-500/40 bg-rose-950/25 hover:border-rose-500/80 hover:bg-rose-950/40 shadow-[0_0_15px_rgba(244,63,94,0.15)]'
                      : 'border-white/10 bg-white/[0.03] hover:border-sky-400/40 hover:bg-[#16385c]/40'
                  }`}
                >
                  {/* Top Site & Severity Row */}
                  <div className="flex items-center justify-between text-[10px] mb-1.5">
                    <div className="flex items-center gap-1.5 overflow-hidden">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        isCritical ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e] animate-pulse' : 'bg-amber-400'
                      }`} />
                      <span className="font-bold text-[#89E5FC] truncate max-w-[200px]" title={alert.site_id}>
                        {alert.site_id}
                      </span>
                    </div>

                    <span className={`px-2 py-0.5 rounded-full font-bold tracking-wider text-[9px] border shrink-0 ${
                      isCritical
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}>
                      {alert.alert_level}
                    </span>
                  </div>

                  {/* Headline */}
                  <div className="text-xs font-sans text-slate-200 line-clamp-2 leading-relaxed mb-2 font-normal">
                    {alert.headline}
                  </div>

                  {/* Footer Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-white/10 text-[10px]">
                    <span className="text-slate-400">
                      DAY: <strong className="text-slate-300 font-semibold">{alert.site_day}</strong>
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined);
                        }}
                        type="button"
                        className="px-2.5 py-1 rounded-full bg-[#16385c]/70 hover:bg-[#16385c] text-[#89E5FC] hover:text-white border border-sky-400/40 flex items-center gap-1 font-semibold transition-all shadow-[0_0_10px_rgba(56,189,248,0.2)] active:scale-95 cursor-pointer"
                        title="Locate site on map"
                      >
                        <Crosshair className="w-3 h-3" />
                        <span>Locate</span>
                      </button>

                      <button
                        onClick={(e) => handleAck(alert.alert_id, e)}
                        disabled={ackingId === alert.alert_id}
                        type="button"
                        className="px-2.5 py-1 rounded-full bg-white/5 hover:bg-emerald-500/20 text-slate-400 hover:text-emerald-300 border border-white/10 hover:border-emerald-500/40 flex items-center gap-1 transition-all disabled:opacity-50 active:scale-95 cursor-pointer"
                        title="Acknowledge alert"
                      >
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>{ackingId === alert.alert_id ? '...' : 'Ack'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
