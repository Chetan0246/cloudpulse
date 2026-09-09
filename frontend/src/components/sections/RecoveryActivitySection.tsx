import React, { useState } from 'react';
import type { IncidentSummary } from '../../api/types';
import { Panel, MetricCard } from '../common/Card';
import { EmptyState } from '../common/StateViews';

interface RecoveryActivitySectionProps {
  incidents: IncidentSummary[];
  onSelectIncident: (id: string) => void;
}

export const RecoveryActivitySection: React.FC<RecoveryActivitySectionProps> = ({
  incidents,
  onSelectIncident,
}) => {
  const [strategyFilter, setStrategyFilter] = useState<string>('ALL');

  // Aggregate actions from incidents
  const actionsList = incidents
    .filter((inc) => inc.recovery_action || inc.recoveryAction)
    .map((inc) => ({
      incidentId: inc.incident_id || inc.incidentId || '',
      resourceId: inc.resource_id || inc.resourceId || '',
      failureType: inc.failure_type || inc.failureType || '',
      action: inc.recovery_action || inc.recoveryAction || 'UNKNOWN',
      result: inc.recovery_result || inc.recoveryResult || inc.status,
      timestamp: inc.recovery_started_at || inc.recoveryStartedAt || inc.detected_at || inc.detectedAt,
      duration: inc.duration_seconds,
      retries: inc.retry_count ?? inc.retryCount ?? inc.recovery_attempts ?? 1,
    }));

  const totalActions = actionsList.length;
  const successfulActions = actionsList.filter(
    (a) => a.result === 'SUCCEEDED' || a.result === 'RESOLVED'
  ).length;
  const failedActions = actionsList.filter(
    (a) => a.result === 'FAILED' || a.result === 'ESCALATED'
  ).length;

  const validDurations = actionsList
    .map((a) => a.duration)
    .filter((d): d is number => typeof d === 'number' && d > 0);

  const avgDuration =
    validDurations.length > 0
      ? (validDurations.reduce((a, b) => a + b, 0) / validDurations.length).toFixed(1)
      : '0.0';

  // Strategy count breakdown
  const strategyCounts: Record<string, number> = {
    SCALE_OUT: 0,
    SERVICE_RESTART: 0,
    STORAGE_CLEANUP: 0,
    NETWORK_REROUTE: 0,
    FAILOVER: 0,
  };

  actionsList.forEach((act) => {
    const key = act.action.toUpperCase();
    if (key in strategyCounts) {
      strategyCounts[key]++;
    }
  });

  const filteredActions = actionsList.filter((a) => {
    if (strategyFilter === 'ALL') return true;
    return a.action.toUpperCase() === strategyFilter;
  });

  const strategiesMeta = [
    {
      type: 'SCALE_OUT',
      name: 'Dynamic Scaling',
      desc: 'Adds compute threads / memory pools to absorb load spikes.',
      color: 'border-cyan-500/30 text-cyan-400 bg-cyan-950/20',
      icon: '📈',
    },
    {
      type: 'SERVICE_RESTART',
      name: 'Process Restart',
      desc: 'Gracefully restarts worker daemons and flushes hung threads.',
      color: 'border-emerald-500/30 text-emerald-400 bg-emerald-950/20',
      icon: '🔄',
    },
    {
      type: 'STORAGE_CLEANUP',
      name: 'Disk Reclamation',
      desc: 'Truncates rotated logs, flushes temporary cache partitions.',
      color: 'border-amber-500/30 text-amber-400 bg-amber-950/20',
      icon: '🧹',
    },
    {
      type: 'NETWORK_REROUTE',
      name: 'Path Reroute',
      desc: 'Flushes route cache, switches VPC transit peering to backup path.',
      color: 'border-blue-500/30 text-blue-400 bg-blue-950/20',
      icon: '🔀',
    },
    {
      type: 'FAILOVER',
      name: 'Cluster Failover',
      desc: 'Promotes standby replica and updates DNS endpoints.',
      color: 'border-purple-500/30 text-purple-400 bg-purple-950/20',
      icon: '🛡️',
    },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Actions"
          value={totalActions}
          subtext="Self-healing routines dispatched"
          status="slate"
          icon="⚡"
        />
        <MetricCard
          title="Succeeded"
          value={successfulActions}
          subtext="Restored to nominal state"
          status="emerald"
          icon="✅"
        />
        <MetricCard
          title="Escalated / Failed"
          value={failedActions}
          subtext="Exceeded max retry threshold"
          status={failedActions > 0 ? 'rose' : 'slate'}
          icon="⚠️"
        />
        <MetricCard
          title="Avg Remediation Time"
          value={`${avgDuration}s`}
          subtext="Mean Lambda execution latency"
          status="cyan"
          icon="⏱️"
        />
      </div>

      {/* Recovery Strategy Breakdown Cards */}
      <div>
        <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Self-Healing Strategy Distribution
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {strategiesMeta.map((s) => {
            const count = strategyCounts[s.type] || 0;
            const isSelected = strategyFilter === s.type;

            return (
              <button
                key={s.type}
                onClick={() => setStrategyFilter(isSelected ? 'ALL' : s.type)}
                className={`p-3 rounded-xl border text-left transition-all font-mono ${
                  isSelected
                    ? 'ring-2 ring-indigo-500 border-indigo-500 bg-indigo-950/40'
                    : `border-slate-800 bg-slate-900/80 hover:border-slate-700`
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-base">{s.icon}</span>
                  <span className="text-lg font-bold text-slate-100">{count}</span>
                </div>
                <div className="text-xs font-semibold text-slate-200">{s.name}</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">{s.type}</div>
                <p className="text-[10px] text-slate-400 mt-2 line-clamp-2">{s.desc}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Audit Log Stream */}
      <Panel
        title={`Recovery Audit Stream (${filteredActions.length})`}
        subtitle="Chronological log of self-healing operations triggered by CloudWatch alarms"
        action={
          strategyFilter !== 'ALL' ? (
            <button
              onClick={() => setStrategyFilter('ALL')}
              className="text-xs font-mono text-indigo-400 hover:text-indigo-300"
            >
              Clear Filter ({strategyFilter})
            </button>
          ) : undefined
        }
      >
        {filteredActions.length === 0 ? (
          <EmptyState
            title="No Recovery Activity Recorded"
            description="When simulated alarms trigger, automated self-healing actions will appear here in real-time."
            icon="🛠️"
          />
        ) : (
          <div className="space-y-3">
            {filteredActions.map((act, index) => (
              <div
                key={act.incidentId + index}
                onClick={() => onSelectIncident(act.incidentId)}
                className="bg-slate-950/80 border border-slate-850 hover:border-slate-750 rounded-lg p-3 text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-cyan-400 font-bold">{act.resourceId}</span>
                    <span className="text-slate-500">•</span>
                    <span className="text-slate-200 font-semibold">{act.action}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        act.result === 'SUCCEEDED' || act.result === 'RESOLVED'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                      }`}
                    >
                      {act.result}
                    </span>
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Triggered by <span className="text-slate-300">{act.failureType}</span> anomaly
                    • Retries: {act.retries}
                  </div>
                </div>

                <div className="text-slate-400 text-[11px] sm:text-right flex sm:flex-col justify-between items-end">
                  <div className="text-indigo-300 font-semibold">
                    {act.duration ? `${act.duration.toFixed(1)}s execution` : 'In flight'}
                  </div>
                  <div className="text-slate-500">
                    {act.timestamp ? new Date(act.timestamp).toLocaleTimeString() : 'N/A'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
};
