import React, { useState } from 'react';
import type { ReliabilityMetric } from '../../api/types';
import { Panel, MetricCard } from '../common/Card';
import { LinearGauge } from '../common/Gauge';
import { EmptyState } from '../common/StateViews';

interface ReliabilityMetricsSectionProps {
  metrics: ReliabilityMetric[];
  selectedWindow: 'DAILY' | 'WEEKLY' | 'CUMULATIVE';
  onChangeWindow: (window: 'DAILY' | 'WEEKLY' | 'CUMULATIVE') => void;
}

export const ReliabilityMetricsSection: React.FC<ReliabilityMetricsSectionProps> = ({
  metrics,
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
    mttrValues.length > 0
      ? (mttrValues.reduce((sum, v) => sum + v, 0) / mttrValues.length).toFixed(1)
      : '0.0';

  // Mean MTBF
  const mtbfValues = filteredMetrics
    .map((m) => m.mtbf_seconds)
    .filter((v): v is number => typeof v === 'number');
  const avgMtbf =
    mtbfValues.length > 0
      ? (mtbfValues.reduce((sum, v) => sum + v, 0) / mtbfValues.length).toFixed(0)
      : '86400';

  const recoverySuccessRate =
    totalIncidents > 0
      ? Math.round((resolvedIncidents / Math.max(1, resolvedIncidents + failedRecoveries)) * 100)
      : 100;

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

      {/* SRE KPI Cards */}
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
          title="Mean Time Between Failures (MTBF)"
          value={`${avgMtbf}s`}
          subtext="Stability interval"
          status="purple"
          icon="⏳"
        />
        <MetricCard
          title="Self-Healing Success Rate"
          value={`${recoverySuccessRate}%`}
          subtext={`${resolvedIncidents} resolved / ${totalIncidents} total`}
          status="amber"
          icon="🎯"
        />
      </div>

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
              <div className="space-y-4">
                {Object.entries(failureTypeCounts).map(([type, count]) => {
                  const percentage =
                    totalIncidents > 0 ? (count / totalIncidents) * 100 : 0;

                  return (
                    <div key={type} className="space-y-1">
                      <div className="flex justify-between text-xs font-mono">
                        <span className="text-slate-300 font-medium">{type}</span>
                        <span className="text-cyan-400 font-semibold">
                          {count} ({percentage.toFixed(0)}%)
                        </span>
                      </div>
                      <LinearGauge
                        label=""
                        value={percentage}
                        showValue={false}
                        warnThreshold={50}
                        critThreshold={75}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
};
