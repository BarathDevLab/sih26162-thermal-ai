import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Crosshair,
  Check
} from 'lucide-react';
import { DecisionEngineIcon } from './Icons';
import type { AlertItem } from '../types/api';
import { acknowledgeAlert } from '../services/api';

interface AlertRailProps {
  alerts: AlertItem[];
  onJumpToSite: (siteId: string, lat?: number, lon?: number) => void;
  onAlertAcknowledged: (alertId: string) => void;
}

const severityStyles: Record<string, { dot: string; badge: string }> = {
  CRITICAL: {
    dot: 'bg-red-500 shadow-[0_0_8px_#ef4444] animate-pulse',
    badge: 'bg-red-500/20 text-red-300 border-red-500/40'
  },
  HIGH: {
    dot: 'bg-orange-400 shadow-[0_0_7px_rgba(251,146,60,0.7)]',
    badge: 'bg-orange-500/20 text-orange-300 border-orange-500/40'
  },
  MEDIUM: {
    dot: 'bg-amber-400',
    badge: 'bg-amber-500/15 text-amber-200 border-amber-500/35'
  },
  LOW: {
    dot: 'bg-cyan-500',
    badge: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
  }
};

function compactSiteId(siteId: string): string {
  const promotedPrefix = 'INDIA_PROMOTED_';
  if (siteId.startsWith(promotedPrefix)) {
    return `NEW SITE · ${siteId.slice(-10).toUpperCase()}`;
  }
  if (siteId.length > 30) return `${siteId.slice(0, 18)}…${siteId.slice(-8)}`;
  return siteId;
}

export const AlertRail: React.FC<AlertRailProps> = ({
  alerts,
  onJumpToSite,
  onAlertAcknowledged
}) => {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [ackingId, setAckingId] = useState<string | null>(null);

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

  return (
    <div className="alert-console absolute bottom-4 right-4 z-20 w-[390px] max-w-[calc(100vw-360px)] shadow-2xl transition-all select-none">
      {/* Header Bar */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        className="bg-[#090e1a]/95 border border-white/15 px-3.5 py-2.5 rounded-t-lg flex items-center justify-between cursor-pointer hover:bg-[#111a2e] tactical-glass"
      >
        <div className="flex items-center gap-2.5">
          <DecisionEngineIcon className="w-4 h-4 text-red-400 drop-shadow-[0_0_6px_rgba(239,68,68,0.5)]" />
          <span className="font-bold text-slate-100 text-xs tracking-wider font-mono uppercase">
            PRIORITY ALERTS
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-semibold">
            {alerts.length} ACTIVE
          </span>
          {criticalCount > 0 && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 font-semibold">
              {criticalCount} CRITICAL
            </span>
          )}
        </div>

        <button className="text-slate-400 hover:text-slate-200 transition-colors">
          {collapsed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Alert Feed Body */}
      {!collapsed && (
        <div className="bg-[#070a12]/95 border-x border-b border-white/15 max-h-72 overflow-y-auto p-2 space-y-2 rounded-b backdrop-blur">
          {alerts.length === 0 ? (
            <div className="p-4 text-center text-slate-500 text-xs font-mono">
              No active unacknowledged operational alerts.
            </div>
          ) : (
            alerts.slice(0, 20).map((alert) => {
              const isCritical = alert.alert_level === 'CRITICAL';
              const severity = severityStyles[alert.alert_level] ?? severityStyles.LOW;
              return (
                <div
                  key={alert.alert_id}
                  onClick={() => onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined)}
                  className={`alert-card p-2.5 rounded-lg border transition-all cursor-pointer ${
                    isCritical
                      ? 'bg-red-950/25 border-red-500/40 hover:border-red-500/80 shadow-[0_0_12px_rgba(239,68,68,0.15)]'
                      : 'bg-[#0c1424] border-white/10 hover:border-white/25 hover:bg-[#101b30]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 font-mono text-[10px] mb-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`w-2 h-2 shrink-0 rounded-full ${severity.dot}`} />
                      <span className="font-bold text-cyan-300 truncate" title={alert.site_id}>
                        {compactSiteId(alert.site_id)}
                      </span>
                    </div>
                    <span className={`shrink-0 px-2 py-0.5 rounded font-bold tracking-wider text-[9px] border ${severity.badge}`}>
                      {alert.alert_level}
                    </span>
                  </div>

                  <div className="text-[11.5px] font-medium text-slate-100 line-clamp-2 mb-2 leading-snug">
                    {alert.headline}
                  </div>

                  <div className="flex items-center justify-between pt-1.5 border-t border-white/10 font-mono text-[9.5px]">
                    <span className="text-slate-400 flex items-center gap-1">
                      <span className="text-slate-500">Day:</span>
                      <span className="text-slate-300 font-semibold">{alert.site_day}</span>
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined);
                        }}
                        className="px-2.5 py-1 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40 flex items-center gap-1 font-semibold transition-all hover:shadow-[0_0_8px_rgba(6,182,212,0.3)]"
                        title="Focus site on map"
                      >
                        <Crosshair className="w-3 h-3" />
                        <span>Locate</span>
                      </button>

                      <button
                        onClick={(e) => handleAck(alert.alert_id, e)}
                        disabled={ackingId === alert.alert_id}
                        className="px-2.5 py-1 rounded bg-slate-800/80 text-slate-300 hover:bg-slate-700 border border-white/10 flex items-center gap-1 transition-colors disabled:opacity-50"
                        title="Acknowledge alert"
                      >
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>{ackingId === alert.alert_id ? 'Acking...' : 'Ack'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
