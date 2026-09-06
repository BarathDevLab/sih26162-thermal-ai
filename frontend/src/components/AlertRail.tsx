import { useState } from 'react';
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
    <div className="absolute bottom-4 left-76 z-20 w-96 max-w-[calc(100vw-340px)] shadow-2xl transition-all">
      {/* Header Bar */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        className="bg-[#0b1120] border border-white/15 px-3 py-2 rounded-t flex items-center justify-between cursor-pointer hover:bg-[#111a2e]"
      >
        <div className="flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-red-400 animate-pulse" />
          <span className="font-bold text-slate-100 text-xs tracking-wide">
            OPERATIONAL ALERT STREAM
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 border border-red-500/30">
            {criticalCount} CRITICAL
          </span>
        </div>

        <button className="text-slate-400 hover:text-slate-200">
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
              return (
                <div
                  key={alert.alert_id}
                  onClick={() => onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined)}
                  className={`p-2.5 rounded border transition-all cursor-pointer ${
                    isCritical
                      ? 'bg-red-950/20 border-red-500/40 hover:border-red-500/80'
                      : 'bg-[#0c1424] border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between font-mono text-[10px] mb-1">
                    <span className="font-bold text-cyan-300">
                      {alert.site_id}
                    </span>
                    <span className={`px-1.5 py-0.2 rounded font-semibold border ${
                      isCritical
                        ? 'bg-red-500/20 text-red-300 border-red-500/40'
                        : 'bg-orange-500/20 text-orange-300 border-orange-500/40'
                    }`}>
                      {alert.alert_level}
                    </span>
                  </div>

                  <div className="text-[11px] font-medium text-slate-200 line-clamp-2 mb-1.5 leading-snug">
                    {alert.headline}
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-white/5 font-mono text-[9px]">
                    <span className="text-slate-400">
                      {alert.site_day}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onJumpToSite(alert.site_id, alert.latitude ?? undefined, alert.longitude ?? undefined);
                        }}
                        className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 border border-cyan-500/30 flex items-center gap-1"
                        title="Focus site on map"
                      >
                        <Crosshair className="w-2.5 h-2.5" />
                        <span>Locate</span>
                      </button>

                      <button
                        onClick={(e) => handleAck(alert.alert_id, e)}
                        disabled={ackingId === alert.alert_id}
                        className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-600 flex items-center gap-1 disabled:opacity-50"
                        title="Acknowledge alert"
                      >
                        <Check className="w-2.5 h-2.5" />
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
