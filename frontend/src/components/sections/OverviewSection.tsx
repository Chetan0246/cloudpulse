import React from 'react';
import type { IncidentSummary, ResourceSummary, FleetReliabilityOverview } from '../../api/types';
import { MetricCard, Panel } from '../common/Card';
import { SeverityBadge, StatusBadge, FailureTypeBadge } from '../common/Badge';
import { EmptyState } from '../common/StateViews';
import { SegmentedHealthBar } from '../common/Charts';

interface OverviewSectionProps {
  resources: ResourceSummary[];
  incidents: IncidentSummary[];
  overview?: FleetReliabilityOverview | null;
  onSelectIncident: (incidentId: string) => void;
  onNavigateTab: (tabId: any) => void;
  onSimulateForResource?: (resourceId: string) => void;
}

export const OverviewSection: React.FC<OverviewSectionProps> = ({
  resources,
  incidents,
  overview,
  onSelectIncident,
  onNavigateTab,
  onSimulateForResource,
}) => {
  // Counts by resource health/state (derived from backend overview or fallback to resources)
  const healthyCount = overview?.health_distribution
    ? overview.health_distribution.healthy_count
    : resources.filter(
        (r) => r.current_state === 'HEALTHY' || r.current_state === 'RECOVERED'
      ).length;
  const warningCount = overview?.health_distribution
    ? overview.health_distribution.warning_count
    : resources.filter((r) => r.current_state === 'WARNING').length;
  const failedCount = overview?.health_distribution
    ? overview.health_distribution.failed_count
    : resources.filter(
        (r) =>
          r.current_state === 'FAILURE_DETECTED' ||
          r.current_state === 'RECOVERY_FAILED' ||
          r.current_state === 'MANUAL_INTERVENTION_REQUIRED'
      ).length;
  const recoveringCount = overview?.health_distribution
    ? overview.health_distribution.recovering_count
    : resources.filter(
        (r) =>
          r.current_state === 'RECOVERY_INITIATED' ||
          r.current_state === 'RECOVERY_IN_PROGRESS'
      ).length;

  // Incident metrics
  const activeIncidents = incidents.filter(
    (i) => i.status === 'OPEN' || i.status === 'RECOVERING'
  );
  const resolvedIncidents = incidents.filter((i) => i.status === 'RESOLVED');
  const totalFinished = incidents.filter(
    (i) => i.status === 'RESOLVED' || i.status === 'ESCALATED'
  );

  const recoverySuccessRate =
    overview != null
      ? Math.round(overview.recovery_success_rate_pct)
      : totalFinished.length > 0
        ? Math.round((resolvedIncidents.length / totalFinished.length) * 100)
        : 100;

  // Calculate MTTR (average duration of resolved incidents)
  const resolvedDurations = resolvedIncidents
    .map((i) => i.duration_seconds)
    .filter((d): d is number => typeof d === 'number' && d > 0);

  const avgRecoveryTime =
    overview?.mttr_seconds != null
      ? overview.mttr_seconds.toFixed(1)
      : resolvedDurations.length > 0
        ? (resolvedDurations.reduce((a, b) => a + b, 0) / resolvedDurations.length).toFixed(1)
        : '0.0';

  // Recent 5 incidents
  const recentIncidents = incidents.slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Alert Banner if Active Incidents exist */}
      {activeIncidents.length > 0 ? (
        <div className="bg-gradient-to-r from-rose-950/40 via-amber-950/20 to-slate-900 border border-rose-500/40 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center space-x-3">
            <span className="text-2xl animate-pulse">🚨</span>
            <div>
              <h4 className="text-sm font-semibold text-rose-300 font-mono">
                ACTIVE INCIDENT DETECTED — {activeIncidents.length} IN FLIGHT
              </h4>
              <p className="text-xs text-slate-300 mt-0.5">
                CloudPulse autonomous self-healing engine is monitoring / recovering affected resources.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('incidents')}
            className="px-3 py-1.5 bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/50 rounded-lg text-xs font-mono font-semibold transition-colors"
          >
            Inspect Incidents →
          </button>
        </div>
      ) : (
        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-3 px-4 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center space-x-2 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold">All Simulated Systems Nominal</span>
            <span className="text-slate-500">— CloudWatch alarms steady, zero open alerts.</span>
          </div>
          <button
            onClick={() => onNavigateTab('simulator')}
            className="text-xs text-indigo-400 hover:text-indigo-300 underline font-mono"
          >
            Launch Failure Simulator →
          </button>
        </div>
      )}

      {/* Prominent SRE Demo & Quick Simulate Workflow */}
      <div className="bg-slate-900/90 border border-indigo-500/40 rounded-xl p-4 shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-xl">⚡</span>
              <h3 className="text-sm font-bold text-slate-100 font-mono tracking-wide uppercase">
                Chaos Engineering Quick-Trigger Workflow
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                DEMO PIPELINE
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Inject a fault to watch the real-time SRE transition: <strong className="text-emerald-400">HEALTHY</strong> → <strong className="text-amber-400">FAILURE</strong> → <strong className="text-rose-400">DETECTED</strong> → <strong className="text-cyan-400">RECOVERING</strong> → <strong className="text-emerald-400">RECOVERED</strong>.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {resources.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mr-1">
                <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">Presets:</span>
                {resources.slice(0, 3).map((r) => (
                  <button
                    key={r.resource_id}
                    onClick={() => {
                      if (onSimulateForResource) onSimulateForResource(r.resource_id);
                      else onNavigateTab('simulator');
                    }}
                    title={`Simulate fault injection on ${r.resource_id}`}
                    className="px-2 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[11px] font-mono transition-colors"
                  >
                    ⚡ {r.resource_id}
                  </button>
                ))}
              </div>
            )}
            <button
              onClick={() => onNavigateTab('simulator')}
              className="px-3 py-1.5 bg-gradient-to-r from-rose-600 via-amber-600 to-rose-600 hover:from-rose-500 hover:via-amber-500 hover:to-rose-500 text-white font-bold text-xs font-mono rounded-lg shadow-md shadow-rose-950/50 border border-rose-400/50 flex items-center space-x-1.5 transition-all transform hover:scale-105 active:scale-95 cursor-pointer"
            >
              <span>⚡</span>
              <span>Launch Simulator</span>
            </button>
          </div>
        </div>

        {/* 5-Stage Visual Transition Stepper Ribbon */}
        <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
          <div className="flex items-center space-x-2 flex-1 overflow-x-auto py-1">
            <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 font-semibold">1. HEALTHY</span>
            <span className="text-slate-600">↓</span>
            <span className="px-2 py-0.5 rounded bg-amber-950/40 text-amber-400 border border-amber-800/40 font-semibold">2. FAILURE</span>
            <span className="text-slate-600">↓</span>
            <span className="px-2 py-0.5 rounded bg-rose-950/40 text-rose-400 border border-rose-800/40 font-semibold">3. DETECTED</span>
            <span className="text-slate-600">↓</span>
            <span className="px-2 py-0.5 rounded bg-cyan-950/40 text-cyan-400 border border-cyan-800/40 font-semibold">4. RECOVERING</span>
            <span className="text-slate-600">↓</span>
            <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 font-semibold">5. RECOVERED</span>
          </div>
          <button
            onClick={() => onNavigateTab('simulator')}
            className="text-[11px] text-indigo-400 hover:text-indigo-300 underline font-mono ml-auto"
          >
            Configure Failure Scenarios →
          </button>
        </div>
      </div>

      {/* Fleet Health Distribution Visual Bar */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-lg">
        <SegmentedHealthBar
          total={resources.length}
          healthy={healthyCount}
          warning={warningCount}
          failed={failedCount}
          recovering={recoveringCount}
        />
      </div>

      {/* KPI Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Healthy Resources"
          value={healthyCount}
          subtext={`of ${resources.length} total resources`}
          status="emerald"
          icon="✅"
          onClick={() => onNavigateTab('resources')}
        />
        <MetricCard
          title="Warning Resources"
          value={warningCount}
          subtext="Metrics approaching threshold"
          status={warningCount > 0 ? 'amber' : 'slate'}
          icon="⚠️"
          onClick={() => onNavigateTab('resources')}
        />
        <MetricCard
          title="Failed Resources"
          value={failedCount}
          subtext="Alarms triggered / degraded"
          status={failedCount > 0 ? 'rose' : 'slate'}
          icon="💥"
          onClick={() => onNavigateTab('resources')}
        />
        <MetricCard
          title="Recovering Resources"
          value={recoveringCount}
          subtext="Self-healing in progress"
          status={recoveringCount > 0 ? 'cyan' : 'slate'}
          icon="🔄"
          onClick={() => onNavigateTab('resources')}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Active Incidents"
          value={activeIncidents.length}
          subtext="Requiring or undergoing recovery"
          status={activeIncidents.length > 0 ? 'rose' : 'emerald'}
          icon="🚨"
          onClick={() => onNavigateTab('incidents')}
        />
        <MetricCard
          title="Recovery Success Rate"
          value={`${recoverySuccessRate}%`}
          subtext={`${resolvedIncidents.length} resolved of ${totalFinished.length || 0} finished`}
          status="cyan"
          icon="🎯"
          onClick={() => onNavigateTab('recovery')}
        />
        <MetricCard
          title="Avg Recovery Time (MTTR)"
          value={`${avgRecoveryTime}s`}
          subtext="From alarm trigger to nominal state"
          status="purple"
          icon="⏱️"
          onClick={() => onNavigateTab('metrics')}
        />
      </div>

      {/* Recent Incidents Table */}
      <Panel
        title="Recent Incidents"
        subtitle="Latest 5 simulated telemetry faults and automated recovery responses"
        action={
          <button
            onClick={() => onNavigateTab('incidents')}
            className="text-xs font-mono text-indigo-400 hover:text-indigo-300"
          >
            View All ({incidents.length}) →
          </button>
        }
      >
        {recentIncidents.length === 0 ? (
          <EmptyState
            title="No Incidents Recorded"
            description="All virtual systems are nominal. Inject a fault using the Failure Simulator to test self-healing."
            icon="🛡️"
            actionText="Inject First Failure"
            onAction={() => onNavigateTab('simulator')}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Incident ID</th>
                  <th className="py-2.5 px-3">Resource</th>
                  <th className="py-2.5 px-3">Failure Type</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Detected At</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {recentIncidents.map((incident) => {
                  const incId = incident.incident_id || incident.incidentId || '';
                  const resId = incident.resource_id || incident.resourceId || '';
                  const fType = incident.failure_type || incident.failureType || 'UNKNOWN';
                  const detected = incident.detected_at || incident.detectedAt || '';

                  return (
                    <tr
                      key={incId}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      onClick={() => onSelectIncident(incId)}
                    >
                      <td className="py-3 px-3 font-semibold text-cyan-400">
                        {incId.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3 text-slate-200">{resId}</td>
                      <td className="py-3 px-3">
                        <FailureTypeBadge failureType={fType} />
                      </td>
                      <td className="py-3 px-3">
                        <SeverityBadge severity={incident.severity} />
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={incident.status} />
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {detected ? new Date(detected).toLocaleTimeString() : 'N/A'}
                      </td>
                      <td className="py-3 px-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectIncident(incId);
                          }}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded text-[11px] transition-colors"
                        >
                          Details →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};
