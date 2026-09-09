import React, { useEffect, useState } from 'react';
import type { Incident, IncidentSummary } from '../../api/types';
import { incidentsApi } from '../../api/incidents';
import { Panel, StatBox } from '../common/Card';
import { StatusBadge, SeverityBadge, FailureTypeBadge, StateBadge } from '../common/Badge';
import { LoadingState, ErrorState, EmptyState } from '../common/StateViews';

interface IncidentDetailSectionProps {
  selectedIncidentId?: string;
  allIncidents: IncidentSummary[];
  onSelectIncident: (id: string) => void;
  onNavigateTab: (tab: any) => void;
}

export const IncidentDetailSection: React.FC<IncidentDetailSectionProps> = ({
  selectedIncidentId,
  allIncidents,
  onSelectIncident,
  onNavigateTab,
}) => {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active incident ID fallback
  const activeId = selectedIncidentId || allIncidents[0]?.incident_id || allIncidents[0]?.incidentId;

  useEffect(() => {
    if (!activeId) {
      setIncident(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    incidentsApi
      .get(activeId)
      .then((data) => {
        if (isMounted) setIncident(data);
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err.response?.data?.detail || err.message || 'Failed to fetch incident details'
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [activeId]);

  if (!activeId || (allIncidents.length === 0 && !incident)) {
    return (
      <div className="space-y-6">
        <EmptyState
          title="No Incident Selected"
          description="Select an incident from the Active Incidents section or trigger a failure in the simulator."
          icon="🔍"
          actionText="View Active Incidents"
          onAction={() => onNavigateTab('incidents')}
        />
      </div>
    );
  }

  if (loading && !incident) {
    return <LoadingState message="Fetching comprehensive incident lifecycle..." />;
  }

  if (error && !incident) {
    return (
      <ErrorState
        title="Could Not Load Incident"
        message={error}
        onRetry={() => {
          if (activeId) onSelectIncident(activeId);
        }}
      />
    );
  }

  if (!incident) {
    return (
      <EmptyState
        title="Incident Not Found"
        description={`No incident record found for ID "${activeId}".`}
        icon="❓"
      />
    );
  }

  // 14 Lifecycle Fields extraction
  const incidentId = incident.incident_id || incident.incidentId || activeId;
  const resourceId = incident.resource_id || incident.resourceId || 'N/A';
  const failureType = incident.failure_type || incident.failureType || 'UNKNOWN';
  const severity = incident.severity || 'MEDIUM';
  const status = incident.status || 'OPEN';

  const createdAt = incident.created_at || incident.createdAt || incident.detected_at || incident.detectedAt;
  const detectedAt = incident.detected_at || incident.detectedAt;
  const recoveryStartedAt =
    incident.recovery_started_at ||
    incident.recoveryStartedAt ||
    incident.recovery_initiated_at;
  const recoveredAt =
    incident.recovered_at || incident.recoveredAt || incident.resolved_at;

  const recoveryAction =
    incident.recovery_action ||
    incident.recoveryAction ||
    (incident.recovery_actions && incident.recovery_actions[0]?.action_type) ||
    'None';
  const recoveryResult =
    incident.recovery_result ||
    incident.recoveryResult ||
    (incident.recovery_actions && incident.recovery_actions[0]?.status) ||
    'In Progress';
  const notificationStatus =
    incident.notification_status ||
    incident.notificationStatus ||
    (incident.notification_sent ? 'DELIVERED (SNS)' : 'PENDING');
  const retryCount =
    incident.retry_count ??
    incident.retryCount ??
    incident.recovery_attempts ??
    (incident.recovery_actions ? incident.recovery_actions.length : 0);
  const errorMessage = incident.error_message || incident.errorMessage || null;

  const formatDate = (iso?: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
  };

  const calculateDuration = () => {
    if (incident.duration_seconds && incident.duration_seconds > 0) {
      return `${incident.duration_seconds.toFixed(1)}s`;
    }
    if (detectedAt && recoveredAt) {
      const ms = new Date(recoveredAt).getTime() - new Date(detectedAt).getTime();
      return `${(ms / 1000).toFixed(1)}s`;
    }
    return 'In progress / Not yet resolved';
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Selector */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => onNavigateTab('incidents')}
              className="text-xs font-mono text-indigo-400 hover:text-indigo-300 mr-2"
            >
              ← Back to List
            </button>
            <h2 className="text-base font-bold text-slate-100 font-mono">
              Incident Details
            </h2>
            <StatusBadge status={status} />
            <SeverityBadge severity={severity} />
          </div>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Tracking ID: <span className="text-cyan-400 font-semibold">{incidentId}</span>
          </p>
        </div>

        {/* Dropdown to switch incident quickly */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          <label className="text-slate-400">Switch Incident:</label>
          <select
            value={incidentId}
            onChange={(e) => onSelectIncident(e.target.value)}
            className="bg-slate-950 text-slate-300 px-3 py-1.5 rounded-lg border border-slate-800 focus:outline-none focus:border-indigo-500 max-w-xs truncate"
          >
            {allIncidents.map((inc) => {
              const id = inc.incident_id || inc.incidentId || '';
              const res = inc.resource_id || inc.resourceId;
              const f = inc.failure_type || inc.failureType;
              return (
                <option key={id} value={id}>
                  {id.slice(0, 8)}... — {res} ({f})
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Error Callout if applicable */}
      {errorMessage && (
        <div className="bg-rose-950/40 border border-rose-500/50 rounded-xl p-4 text-xs font-mono text-rose-300">
          <div className="font-bold mb-1 flex items-center space-x-2">
            <span>⚠️</span>
            <span>Recorded Exception Detail:</span>
          </div>
          <p className="bg-slate-950/70 p-2.5 rounded border border-rose-900/50 mt-1">
            {errorMessage}
          </p>
        </div>
      )}

      {/* Visual Step Timeline */}
      <Panel title="Incident Lifecycle Stepper" subtitle="Automated recovery state progression and milestone timeline">
        <div className="relative flex flex-col md:flex-row items-center justify-between py-4 gap-4 md:gap-0 border-b border-slate-800/80 mb-4">
          {[
            {
              step: '1. Detected',
              time: formatDate(detectedAt),
              done: !!detectedAt,
              active: status === 'OPEN',
            },
            {
              step: '2. Recovery Initiated',
              time: formatDate(recoveryStartedAt),
              done: !!recoveryStartedAt,
              active: status === 'RECOVERING',
            },
            {
              step: '3. Action Executed',
              time: recoveryAction !== 'None' ? recoveryAction : 'Pending',
              done: (incident.recovery_actions?.length ?? 0) > 0,
              active: status === 'RECOVERING',
            },
            {
              step: '4. Resolution / Final State',
              time: status === 'RESOLVED' ? formatDate(recoveredAt) : status,
              done: status === 'RESOLVED' || status === 'ESCALATED',
              active: status === 'RESOLVED' || status === 'ESCALATED',
            },
          ].map((s, idx) => (
            <div key={s.step} className="flex-1 flex flex-col items-center text-center px-2">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center font-mono font-bold text-xs border mb-2 transition-all ${
                  s.done
                    ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500 shadow-sm shadow-emerald-500/20'
                    : s.active
                    ? 'bg-cyan-600/30 text-cyan-300 border-cyan-400 animate-pulse ring-2 ring-cyan-500/30'
                    : 'bg-slate-900 text-slate-600 border-slate-800'
                }`}
              >
                {s.done ? '✓' : idx + 1}
              </div>
              <div className="text-xs font-mono font-semibold text-slate-200">{s.step}</div>
              <div className="text-[11px] font-mono text-slate-400 mt-0.5">{s.time}</div>
            </div>
          ))}
        </div>

        {/* Chronological Incident Event Timeline */}
        <div className="space-y-3 pt-2">
          <h4 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider mb-3">
            Chronological Incident Timeline:
          </h4>
          <div className="relative pl-6 border-l-2 border-slate-800 space-y-4 font-mono text-xs">
            {/* 1. Created */}
            <div className="relative">
              <span className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-amber-500 border-2 border-slate-900 ring-2 ring-amber-500/30" />
              <div className="flex items-center justify-between">
                <span className="font-bold text-amber-400">1. Workload Anomaly Created</span>
                <span className="text-[11px] text-slate-500">{formatDate(createdAt)}</span>
              </div>
              <p className="text-slate-400 text-[11px] mt-0.5">
                Fault condition injected into {resourceId}. Target threshold breached.
              </p>
            </div>

            {/* 2. Detected */}
            <div className="relative">
              <span className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-rose-500 border-2 border-slate-900 ring-2 ring-rose-500/30 animate-pulse" />
              <div className="flex items-center justify-between">
                <span className="font-bold text-rose-400">2. CloudWatch Alarm Detected</span>
                <span className="text-[11px] text-slate-500">{formatDate(detectedAt)}</span>
              </div>
              <p className="text-slate-400 text-[11px] mt-0.5">
                Metric alarm state changed to ALARM. Incident opened with severity {severity}.
              </p>
            </div>

            {/* 3. Recovery Initiated */}
            {recoveryStartedAt && (
              <div className="relative">
                <span className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-cyan-500 border-2 border-slate-900 ring-2 ring-cyan-500/30" />
                <div className="flex items-center justify-between">
                  <span className="font-bold text-cyan-400">3. EventBridge Routed to Recovery Lambda</span>
                  <span className="text-[11px] text-slate-500">{formatDate(recoveryStartedAt)}</span>
                </div>
                <p className="text-slate-400 text-[11px] mt-0.5">
                  Recovery Lambda invoked with correlation context. Dispatched strategy: {recoveryAction}.
                </p>
              </div>
            )}

            {/* 4. Resolved */}
            {recoveredAt && (
              <div className="relative">
                <span className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-slate-900 ring-2 ring-emerald-500/30" />
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-400">4. Recovery Verified & Resolved</span>
                  <span className="text-[11px] text-slate-500">{formatDate(recoveredAt)}</span>
                </div>
                <p className="text-slate-400 text-[11px] mt-0.5">
                  Remediation verified nominal. Total MTTR: {calculateDuration()}. Notification status: {notificationStatus}.
                </p>
              </div>
            )}
          </div>
        </div>
      </Panel>

      {/* 14 Lifecycle Fields Display */}
      <Panel
        title="14 Incident Lifecycle Fields"
        subtitle="Canonical SRE state contract conforming to CloudPulse incident schema"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
          <StatBox label="1. Incident ID" value={incidentId.slice(0, 18) + '...'} />
          <StatBox label="2. Resource ID" value={resourceId} highlight />
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
            <div className="text-[11px] text-slate-400 uppercase">3. Failure Type</div>
            <div className="mt-1">
              <FailureTypeBadge failureType={failureType} />
            </div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
            <div className="text-[11px] text-slate-400 uppercase">4. Severity</div>
            <div className="mt-1">
              <SeverityBadge severity={severity} />
            </div>
          </div>

          <StatBox label="5. Created At" value={formatDate(createdAt)} />
          <StatBox label="6. Detected At" value={formatDate(detectedAt)} />
          <StatBox label="7. Recovery Started At" value={formatDate(recoveryStartedAt)} />
          <StatBox label="8. Recovered At" value={formatDate(recoveredAt)} />

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
            <div className="text-[11px] text-slate-400 uppercase">9. Status</div>
            <div className="mt-1">
              <StatusBadge status={status} />
            </div>
          </div>
          <StatBox label="10. Recovery Action" value={recoveryAction} highlight />
          <StatBox label="11. Recovery Result" value={recoveryResult} />
          <StatBox label="12. Notification Status" value={notificationStatus} />

          <StatBox label="13. Retry Count" value={retryCount} />
          <StatBox
            label="14. Error Message"
            value={errorMessage ? 'Yes (See banner)' : 'None'}
            highlight={!!errorMessage}
          />
          <StatBox label="Total Duration" value={calculateDuration()} />
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
            <div className="text-[11px] text-slate-400 uppercase">State at Detection</div>
            <div className="mt-1">
              <StateBadge state={incident.state_at_detection || 'FAILURE_DETECTED'} />
            </div>
          </div>
        </div>
      </Panel>

      {/* Recovery Actions Audit Log */}
      <Panel
        title="Executed Recovery Actions"
        subtitle="Step-by-step remediation commands dispatched by the self-healing engine"
      >
        {(!incident.recovery_actions || incident.recovery_actions.length === 0) ? (
          <EmptyState
            title="No Recovery Actions Executed Yet"
            description="Autonomous recovery is either pending execution or the incident was resolved manually."
            icon="🛠️"
          />
        ) : (
          <div className="space-y-3">
            {incident.recovery_actions.map((act, index) => (
              <div
                key={act.action_id || index}
                className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-200">
                      #{index + 1} {act.action_type}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        act.status === 'SUCCEEDED'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                      }`}
                    >
                      {act.status}
                    </span>
                  </div>
                  <p className="text-slate-400">{act.outcome_message}</p>
                  {act.error_detail && (
                    <p className="text-rose-400 text-[11px]">{act.error_detail}</p>
                  )}
                </div>
                <div className="text-slate-500 text-[11px] sm:text-right">
                  <div>Started: {formatDate(act.started_at)}</div>
                  <div>Completed: {formatDate(act.completed_at)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Notifications & Audit Notes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Panel title="SNS Dispatch Status">
          <div className="space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between p-2 bg-slate-950 rounded border border-slate-850">
              <span className="text-slate-400">SNS Alert Delivered:</span>
              <span className="text-emerald-400 font-semibold">
                {incident.notification_sent ? 'YES (Topic Dispatched)' : 'NO'}
              </span>
            </div>
            <div className="p-2 bg-slate-950 rounded border border-slate-850">
              <div className="text-[10px] text-slate-400 uppercase mb-1">Notified Transitions</div>
              <div className="flex flex-wrap gap-1">
                {incident.notified_transitions && incident.notified_transitions.length > 0 ? (
                  incident.notified_transitions.map((t) => (
                    <span
                      key={t}
                      className="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 text-[10px]"
                    >
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-500 text-[11px]">No transitions logged</span>
                )}
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="Recovery Notes">
          <div className="space-y-2 text-xs font-mono">
            {incident.recovery_notes && incident.recovery_notes.length > 0 ? (
              <ul className="list-disc list-inside text-slate-300 space-y-1">
                {incident.recovery_notes.map((note, idx) => (
                  <li key={idx} className="bg-slate-950 p-2 rounded border border-slate-850">
                    {note}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-slate-500 italic p-3 text-center">
                No custom engineer recovery notes recorded.
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
};
