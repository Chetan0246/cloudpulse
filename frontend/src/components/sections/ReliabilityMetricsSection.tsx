import React, { useState } from 'react';
import type { ReliabilityMetric, FleetReliabilityOverview } from '../../api/types';
import { Panel, MetricCard } from '../common/Card';
import { LinearGauge } from '../common/Gauge';
import { EmptyState } from '../common/StateViews';
import { DonutGauge, IncidentBarChart } from '../common/Charts';

interface ReliabilityMetricsSectionProps {
  metrics: ReliabilityMetric[];
  overview?: FleetReliabilityOverview | null;
  selectedWindow: 'DAILY' | 'WEEKLY' | 'CUMULATIVE';
  onChangeWindow: (window: 'DAILY' | 'WEEKLY' | 'CUMULATIVE') => void;
}

export const ReliabilityMetricsSection: React.FC<ReliabilityMetricsSectionProps> = ({
  metrics,
  overview,
  selectedWindow,
  onChangeWindow,
}) => {
  const [selectedResourceId, setSelectedResourceId] = useState<string>('ALL');

  // Filter metrics by resource if selected
  const filteredMetrics = metrics.filter((m) => {
    if (selectedResourceId === 'ALL') return true;
    return m.resource_id === selectedResourceId;
  });

  // Calculate aggregated stats across metrics
  const totalIncidents = filteredMetrics.reduce((sum, m) => sum + (m.total_incidents || 0), 0);
  const resolvedIncidents = filteredMetrics.reduce(
    (sum, m) => sum + (m.resolved_incidents || 0),
    0
  );
  const failedRecoveries = filteredMetrics.reduce(
    (sum, m) => sum + (m.failed_recoveries || 0),
    0
  );

  // Mean availability
  const availabilities = filteredMetrics
    .map((m) => m.availability_pct)
    .filter((a): a is number => typeof a === 'number');
  const avgAvailability =
    availabilities.length > 0
      ? (availabilities.reduce((sum, a) => sum + a, 0) / availabilities.length).toFixed(3)
      : '99.950';

  // Mean MTTR
  const mttrValues = filteredMetrics
    .map((m) => m.mttr_seconds)
    .filter((v): v is number => typeof v === 'number');
  const avgMttr =
    overview?.mttr_seconds != null
      ? overview.mttr_seconds.toFixed(1)
      : mttrValues.length > 0
        ? (mttrValues.reduce((sum, v) => sum + v, 0) / mttrValues.length).toFixed(1)
        : '0.0';

  // Mean MTBF
  const mtbfValues = filteredMetrics
    .map((m) => m.mtbf_seconds)
    .filter((v): v is number => typeof v === 'number');
  const avgMtbf =
    overview?.mtbf_seconds != null
      ? overview.mtbf_seconds.toFixed(0)
      : mtbfValues.length > 0
        ? (mtbfValues.reduce((sum, v) => sum + v, 0) / mtbfValues.length).toFixed(0)
        : '86400';

  const recoverySuccessRate =
    overview != null
      ? overview.recovery_success_rate_pct.toFixed(1)
      : totalIncidents > 0
        ? ((resolvedIncidents / Math.max(1, resolvedIncidents + failedRecoveries)) * 100).toFixed(1)
        : '100.0';

  const recoveryFailureRate =
    overview != null
      ? overview.recovery_failure_rate_pct.toFixed(1)
      : (100 - parseFloat(recoverySuccessRate)).toFixed(1);

  const avgRecoveryTime =
    overview?.avg_recovery_time_seconds != null
      ? overview.avg_recovery_time_seconds.toFixed(1)
      : avgMttr !== '0.0'
        ? avgMttr
        : '0.0';

  const avgDetectionTime =
    overview?.avg_detection_time_seconds != null
      ? overview.avg_detection_time_seconds.toFixed(1)
      : '0.0';

  const incidentCount = overview?.incident_count ?? totalIncidents;
  const incidentFreqHour = overview != null ? overview.incident_frequency_per_hour.toFixed(2) : '0.00';
  const incidentFreqDay = overview != null ? overview.incident_frequency_per_day.toFixed(1) : '0.0';

  // Current resource health distribution
  const healthDist = overview?.health_distribution;

  // Aggregate failure types counts
  const failureTypeCounts: Record<string, number> = {};
  filteredMetrics.forEach((m) => {
    if (m.failure_type_counts) {
      Object.entries(m.failure_type_counts).forEach(([ft, count]) => {
        failureTypeCounts[ft] = (failureTypeCounts[ft] || 0) + count;
      });
    }
  });

  const uniqueResources = Array.from(new Set(metrics.map((m) => m.resource_id)));

  return (
    <div className="space-y-6">
      {/* Window and Resource Filters Header */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
            <span>📈</span>
            <span>Reliability & Service Level Engineering</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Key SRE indicators: Availability, MTTR, MTBF, and Self-Healing Efficacy.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          {/* Resource Filter */}
          {uniqueResources.length > 0 && (
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-500">Resource:</span>
              <select
                value={selectedResourceId}
                onChange={(e) => setSelectedResourceId(e.target.value)}
                className="bg-slate-950 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-800 focus:outline-none"
              >
                <option value="ALL">ALL RESOURCES</option>
                {uniqueResources.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Aggregation Window Selector */}
          <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(['DAILY', 'WEEKLY', 'CUMULATIVE'] as const).map((win) => (
              <button
                key={win}
                onClick={() => onChangeWindow(win)}
                className={`px-3 py-1 rounded text-[11px] font-semibold transition-all ${
                  selectedWindow === win
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {win}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Primary SRE KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Availability (SLO)"
          value={`${avgAvailability}%`}
          subtext="Target: 99.900% uptime"
          status="emerald"
          icon="🛡️"
        />
        <MetricCard
          title="Mean Time To Recovery (MTTR)"
          value={`${avgMttr}s`}
          subtext="Target: < 30s automated"
          status="cyan"
          icon="⏱️"
        />
        <MetricCard
          title="Recovery Success Rate"
          value={`${recoverySuccessRate}%`}
          subtext={`${resolvedIncidents} resolved / ${totalIncidents} total`}
          status="amber"
          icon="🎯"
        />
        <MetricCard
          title="Recovery Failure Rate"
          value={`${recoveryFailureRate}%`}
          subtext="Escalated to manual intervention"
          status={parseFloat(recoveryFailureRate) > 0 ? 'rose' : 'slate'}
          icon="⚡"
        />
      </div>

      {/* Secondary SRE Operational Telemetry */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Incident Count"
          value={incidentCount}
          subtext={`Observed in ${selectedWindow.toLowerCase()} window`}
          status={incidentCount > 0 ? 'amber' : 'slate'}
          icon="📋"
        />
        <MetricCard
          title="Average Recovery Time"
          value={`${avgRecoveryTime}s`}
          subtext="Per-action execution duration"
          status="purple"
          icon="🔧"
        />
        <MetricCard
          title="Average Detection Time"
          value={`${avgDetectionTime}s`}
          subtext="Telemetry breach to alarm"
          status="cyan"
          icon="🔍"
        />
        <MetricCard
          title="Incident Frequency"
          value={`${incidentFreqHour}/hr`}
          subtext={`${incidentFreqDay}/day • MTBF: ${avgMtbf}s`}
          status="slate"
          icon="⏳"
        />
      </div>

      {/* Resource Health Distribution Panel */}
      {healthDist && (
        <Panel
          title="Current Resource Health Distribution"
          subtitle={`Real-time health status across all ${healthDist.total_resources} simulated resources`}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="bg-emerald-950/20 border border-emerald-800/40 p-3 rounded-lg flex items-center justify-between">
                <span className="text-slate-400">HEALTHY</span>
                <span className="text-emerald-400 font-bold text-sm">
                  {healthDist.healthy_count} ({healthDist.healthy_pct.toFixed(0)}%)
                </span>
              </div>
              <div className="bg-amber-950/20 border border-amber-800/40 p-3 rounded-lg flex items-center justify-between">
                <span className="text-slate-400">WARNING</span>
                <span className="text-amber-400 font-bold text-sm">{healthDist.warning_count}</span>
              </div>
              <div className="bg-rose-950/20 border border-rose-800/40 p-3 rounded-lg flex items-center justify-between">
                <span className="text-slate-400">FAILED</span>
                <span className="text-rose-400 font-bold text-sm">{healthDist.failed_count}</span>
              </div>
              <div className="bg-cyan-950/20 border border-cyan-800/40 p-3 rounded-lg flex items-center justify-between">
                <span className="text-slate-400">RECOVERING</span>
                <span className="text-cyan-400 font-bold text-sm">{healthDist.recovering_count}</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-6 bg-slate-950/40 p-4 rounded-xl border border-slate-800">
              <div className="flex-shrink-0">
                <DonutGauge
                  value={healthDist.healthy_pct}
                  label="Fleet Nominal Score"
                  subtext={`${healthDist.healthy_count}/${healthDist.total_resources} Nodes`}
                  size={110}
                  color="emerald"
                />
              </div>
              <div className="flex-1 w-full space-y-3">
                <LinearGauge
                  label="Fleet Health Index"
                  value={healthDist.healthy_pct}
                  showValue={true}
                  unit="%"
                  critThreshold={50}
                  warnThreshold={80}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 text-xs font-mono">
              <div>
                <h4 className="text-slate-400 font-semibold mb-2">By Lifecycle State:</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(healthDist.by_state).map(([st, cnt]) => (
                    <span
                      key={st}
                      className="px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700 text-slate-300"
                    >
                      {st}: <strong className="text-cyan-300">{cnt}</strong>
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="text-slate-400 font-semibold mb-2">By Health Status:</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(healthDist.by_status).map(([st, cnt]) => (
                    <span
                      key={st}
                      className={`px-2.5 py-1 rounded border ${
                        st === 'HEALTHY'
                          ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-300'
                          : st === 'DEGRADED'
                            ? 'bg-amber-950/30 border-amber-700/50 text-amber-300'
                            : 'bg-rose-950/30 border-rose-700/50 text-rose-300'
                      }`}
                    >
                      {st}: <strong>{cnt}</strong>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </Panel>
      )}

      {/* Breakdown Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Per-Resource Reliability Metrics */}
        <div className="lg:col-span-2">
          <Panel
            title="Resource Reliability Breakdown"
            subtitle={`Aggregated for ${selectedWindow} observation window`}
          >
            {filteredMetrics.length === 0 ? (
              <EmptyState
                title="No Metrics Available"
                description={`No metric snapshots computed for window ${selectedWindow}.`}
                icon="📊"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-3">Resource ID</th>
                      <th className="py-2.5 px-3">Availability</th>
                      <th className="py-2.5 px-3">MTTR</th>
                      <th className="py-2.5 px-3">MTBF</th>
                      <th className="py-2.5 px-3">Incidents</th>
                      <th className="py-2.5 px-3">Resolved</th>
                      <th className="py-2.5 px-3">Failed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredMetrics.map((m) => (
                      <tr key={m.resource_id + m.window_key} className="hover:bg-slate-800/30">
                        <td className="py-3 px-3 font-semibold text-cyan-400">
                          {m.resource_id}
                        </td>
                        <td className="py-3 px-3 text-emerald-400 font-semibold">
                          {m.availability_pct !== null ? `${m.availability_pct.toFixed(2)}%` : '100%'}
                        </td>
                        <td className="py-3 px-3 text-slate-200">
                          {m.mttr_seconds !== null ? `${m.mttr_seconds.toFixed(1)}s` : '0.0s'}
                        </td>
                        <td className="py-3 px-3 text-slate-300">
                          {m.mtbf_seconds !== null ? `${m.mtbf_seconds.toFixed(0)}s` : '—'}
                        </td>
                        <td className="py-3 px-3 text-slate-300">{m.total_incidents}</td>
                        <td className="py-3 px-3 text-emerald-400 font-semibold">
                          {m.resolved_incidents}
                        </td>
                        <td className="py-3 px-3 text-rose-400 font-semibold">
                          {m.failed_recoveries}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        {/* Failure Scenario Distribution */}
        <div>
          <Panel
            title="Failure Distribution"
            subtitle="Frequency of fault scenarios encountered"
          >
            {Object.keys(failureTypeCounts).length === 0 ? (
              <div className="text-center py-8 text-xs font-mono text-slate-500">
                No failure events recorded in this window.
              </div>
            ) : (
              <IncidentBarChart data={failureTypeCounts} totalIncidents={totalIncidents} />
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
};
