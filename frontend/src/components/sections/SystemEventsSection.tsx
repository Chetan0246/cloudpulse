import React, { useState } from 'react';
import type { IncidentSummary, ResourceSummary } from '../../api/types';
import { Panel } from '../common/Card';
import { EmptyState } from '../common/StateViews';

interface SystemEventsSectionProps {
  incidents: IncidentSummary[];
  resources: ResourceSummary[];
  onSelectIncident: (id: string) => void;
}

interface SystemEvent {
  id: string;
  type: 'FAILURE' | 'RECOVERY' | 'RESOLUTION' | 'ALERT';
  timestamp: string;
  resourceId: string;
  incidentId: string;
  title: string;
  description: string;
  severity?: string;
}

export const SystemEventsSection: React.FC<SystemEventsSectionProps> = ({
  incidents,
  resources,
  onSelectIncident,
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [resourceFilter, setResourceFilter] = useState<string>('ALL');

  // Derive granular events from incidents
  const events: SystemEvent[] = [];

  incidents.forEach((inc) => {
    const incId = inc.incident_id || inc.incidentId || '';
    const resId = inc.resource_id || inc.resourceId || 'N/A';
    const fType = inc.failure_type || inc.failureType || 'UNKNOWN';

    // 1. Failure detection event
    const detectedAt = inc.detected_at || inc.detectedAt;
    if (detectedAt) {
      events.push({
        id: `${incId}-det`,
        type: 'FAILURE',
        timestamp: detectedAt,
        resourceId: resId,
        incidentId: incId,
        title: `Anomaly Detected: ${fType}`,
        description: `CloudWatch alarm breached threshold on resource ${resId}. Failure state recorded as FAILURE_DETECTED.`,
        severity: inc.severity,
      });
    }

    // 2. Recovery start event
    const recoveryStartedAt =
      inc.recovery_started_at || inc.recoveryStartedAt;
    if (recoveryStartedAt) {
      events.push({
        id: `${incId}-rec`,
        type: 'RECOVERY',
        timestamp: recoveryStartedAt,
        resourceId: resId,
        incidentId: incId,
        title: `Recovery Lambda Triggered: ${inc.recovery_action || inc.recoveryAction || 'Self-Healing'}`,
        description: `EventBridge routed alarm state change to Recovery Lambda. Automated remediation initiated.`,
        severity: inc.severity,
      });
    }

    // 3. Resolution / Escalation event
    const resolvedAt =
      inc.recovered_at || inc.recoveredAt || inc.resolved_at;
    if (resolvedAt) {
      const isEscalated = inc.status === 'ESCALATED';
      events.push({
        id: `${incId}-res`,
        type: isEscalated ? 'FAILURE' : 'RESOLUTION',
        timestamp: resolvedAt,
        resourceId: resId,
        incidentId: incId,
        title: isEscalated
          ? `Incident Escalated: Max Retries Exceeded`
          : `Incident Resolved: ${resId} Recovered`,
        description: isEscalated
          ? `Automatic recovery failed after multiple attempts. Flagged for MANUAL_INTERVENTION_REQUIRED.`
          : `Metrics normalized to nominal range. Resource state transitioned to RECOVERED (${inc.duration_seconds?.toFixed(1) || 0}s duration).`,
        severity: inc.severity,
      });
    }

    // 4. Notification event
    if (inc.notification_status || inc.notification_sent) {
      events.push({
        id: `${incId}-notif`,
        type: 'ALERT',
        timestamp: resolvedAt || recoveryStartedAt || detectedAt || new Date().toISOString(),
        resourceId: resId,
        incidentId: incId,
        title: `SNS Alert Dispatched`,
        description: `Lifecycle notification published to Amazon SNS topic for incident ${incId.slice(0, 8)}.`,
      });
    }
  });

  // Sort newest first
  events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  // Filter
  const filteredEvents = events.filter((e) => {
    if (filterType !== 'ALL' && e.type !== filterType) return false;
    if (resourceFilter !== 'ALL' && e.resourceId !== resourceFilter) return false;
    return true;
  });

  const getEventBadge = (type: SystemEvent['type']) => {
    switch (type) {
      case 'FAILURE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">
            FAULT DETECTED
          </span>
        );
      case 'RECOVERY':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
            SELF-HEALING
          </span>
        );
      case 'RESOLUTION':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            RESOLVED
          </span>
        );
      case 'ALERT':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
            SNS ALERT
          </span>
        );
    }
  };

  const getEventIcon = (type: SystemEvent['type']) => {
    switch (type) {
      case 'FAILURE':
        return '💥';
      case 'RECOVERY':
        return '⚡';
      case 'RESOLUTION':
        return '✅';
      case 'ALERT':
        return '📬';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Filter Controls */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
            <span>📜</span>
            <span>Real-Time System Observability Event Stream</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized stream of anomaly breaches, EventBridge routing, Lambda actions, and alerts.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          {/* Event Category Filter */}
          <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {['ALL', 'FAILURE', 'RECOVERY', 'RESOLUTION', 'ALERT'].map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  filterType === t
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Resource Filter */}
          <select
            value={resourceFilter}
            onChange={(e) => setResourceFilter(e.target.value)}
            className="bg-slate-950 text-slate-300 px-2.5 py-1.5 rounded-lg border border-slate-800 focus:outline-none"
          >
            <option value="ALL">ALL RESOURCES</option>
            {resources.map((r) => (
              <option key={r.resource_id} value={r.resource_id}>
                {r.resource_id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stream Panel */}
      <Panel
        title={`Live Event Stream (${filteredEvents.length} events)`}
        subtitle="Chronological audit sequence matching CloudWatch alarm & EventBridge lifecycle"
      >
        {filteredEvents.length === 0 ? (
          <EmptyState
            title="No Events Found"
            description="Trigger a simulated fault to watch the live event stream generate telemetry entries."
            icon="📜"
          />
        ) : (
          <div className="relative border-l-2 border-slate-800 ml-4 pl-4 space-y-6 my-2">
            {filteredEvents.map((evt) => {
              return (
                <div
                  key={evt.id}
                  onClick={() => onSelectIncident(evt.incidentId)}
                  className="relative group cursor-pointer"
                >
                  {/* Timeline dot */}
                  <div className="absolute -left-[25px] top-1 w-4 h-4 rounded-full bg-slate-900 border-2 border-indigo-500 flex items-center justify-center text-[8px] group-hover:scale-125 transition-transform" />

                  <div className="bg-slate-950/70 border border-slate-850 group-hover:border-slate-750 p-3.5 rounded-xl transition-colors space-y-1.5 font-mono text-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm">{getEventIcon(evt.type)}</span>
                        <span className="font-bold text-slate-200">{evt.title}</span>
                        {getEventBadge(evt.type)}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {new Date(evt.timestamp).toLocaleTimeString()} • {new Date(evt.timestamp).toLocaleDateString()}
                      </div>
                    </div>

                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      {evt.description}
                    </p>

                    <div className="flex items-center space-x-3 text-[10px] text-slate-400 pt-1 border-t border-slate-900">
                      <span>
                        Resource: <span className="text-cyan-400 font-semibold">{evt.resourceId}</span>
                      </span>
                      <span>•</span>
                      <span>
                        Incident: <span className="text-slate-300">{evt.incidentId.slice(0, 8)}...</span>
                      </span>
                      <span className="ml-auto text-indigo-400 group-hover:underline">
                        Inspect Incident →
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
};
