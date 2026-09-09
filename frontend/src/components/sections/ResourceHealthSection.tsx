import React, { useState } from 'react';
import type { ResourceSummary } from '../../api/types';
import { Panel, StatBox } from '../common/Card';
import { HealthBadge, StateBadge } from '../common/Badge';
import { LinearGauge, LatencyGauge } from '../common/Gauge';
import { EmptyState } from '../common/StateViews';

interface ResourceHealthSectionProps {
  resources: ResourceSummary[];
  onResetResource: (resourceId: string) => Promise<void>;
  onSimulateForResource: (resourceId: string) => void;
}

export const ResourceHealthSection: React.FC<ResourceHealthSectionProps> = ({
  resources,
  onResetResource,
  onSimulateForResource,
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  const handleReset = async (resourceId: string) => {
    try {
      setResettingId(resourceId);
      await onResetResource(resourceId);
    } finally {
      setResettingId(null);
    }
  };

  const filteredResources = resources.filter((r) => {
    if (filterType === 'ALL') return true;
    return r.resource_type === filterType;
  });

  const formatHeartbeat = (isoString?: string) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diffSec < 5) return 'Just now (< 5s ago)';
    if (diffSec < 60) return `${diffSec}s ago`;
    return date.toLocaleTimeString();
  };

  return (
    <div className="space-y-6">
      {/* Header controls & filter */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
            <span>🖥️</span>
            <span>Virtual Cloud Infrastructure Fleet</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time simulated telemetry for compute, storage, API gateways, and database clusters.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs font-mono">
          {/* Type filter */}
          <div className="flex items-center space-x-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-500 mr-1">Type:</span>
            {['ALL', 'VM', 'API', 'DB', 'STORAGE'].map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                  filterType === type
                    ? 'bg-indigo-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {type}
              </button>
            ))}
          </div>

          {/* View toggle */}
          <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setViewMode('grid')}
              title="Grid View"
              className={`p-1 rounded ${viewMode === 'grid' ? 'bg-slate-800 text-cyan-400' : 'text-slate-500'}`}
            >
              ⊞
            </button>
            <button
              onClick={() => setViewMode('table')}
              title="Table View"
              className={`p-1 rounded ${viewMode === 'table' ? 'bg-slate-800 text-cyan-400' : 'text-slate-500'}`}
            >
              ☰
            </button>
          </div>
        </div>
      </div>

      {/* Fleet Telemetry Quick Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
        <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Total Nodes</span>
          <span className="text-slate-200 font-bold text-sm">{resources.length}</span>
        </div>
        <div className="bg-emerald-950/20 border border-emerald-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Nominal</span>
          <span className="text-emerald-400 font-bold text-sm">
            {resources.filter((r) => r.current_state === 'HEALTHY' || r.current_state === 'RECOVERED').length}
          </span>
        </div>
        <div className="bg-amber-950/20 border border-amber-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Warning</span>
          <span className="text-amber-400 font-bold text-sm">
            {resources.filter((r) => r.current_state === 'WARNING').length}
          </span>
        </div>
        <div className="bg-rose-950/20 border border-rose-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Anomalous / Self-Healing</span>
          <span className="text-rose-400 font-bold text-sm">
            {resources.filter((r) => r.current_state !== 'HEALTHY' && r.current_state !== 'RECOVERED' && r.current_state !== 'WARNING').length}
          </span>
        </div>
      </div>

      {filteredResources.length === 0 ? (
        <EmptyState
          title="No Resources Found"
          description={`No simulated resources matching filter "${filterType}".`}
          icon="🖥️"
        />
      ) : viewMode === 'grid' ? (
        /* Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-5">
          {filteredResources.map((resource) => {
            const isDegraded =
              resource.current_state !== 'HEALTHY' && resource.current_state !== 'RECOVERED';
            const isResetting = resettingId === resource.resource_id;

            return (
              <Panel
                key={resource.resource_id}
                className={`transition-all ${
                  isDegraded
                    ? 'border-rose-500/40 bg-rose-950/10'
                    : 'border-slate-800/80'
                }`}
                title={resource.resource_id}
                badge={<StateBadge state={resource.current_state} />}
                action={<HealthBadge health={resource.health_status} />}
                subtitle={`Type: ${resource.resource_type} • Heartbeat: ${formatHeartbeat(
                  resource.last_heartbeat
                )}`}
              >
                {/* Active failure notice */}
                {resource.active_failure_type && (
                  <div className="mb-4 bg-rose-950/40 border border-rose-500/40 rounded-lg p-2.5 text-xs font-mono text-rose-300 flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span>⚡</span>
                      <span>Fault Active: {resource.active_failure_type}</span>
                    </div>
                    <span className="text-[10px] text-rose-400 underline">Self-healing</span>
                  </div>
                )}

                {/* Telemetry Gauges */}
                <div className="space-y-3 my-4 bg-slate-950/60 p-3.5 rounded-lg border border-slate-850">
                  <LinearGauge
                    label="CPU Utilization"
                    value={resource.cpu_utilization ?? 0}
                    unit="%"
                    warnThreshold={70}
                    critThreshold={85}
                  />
                  <LinearGauge
                    label="Memory Utilization"
                    value={resource.memory_utilization ?? 0}
                    unit="%"
                    warnThreshold={75}
                    critThreshold={90}
                  />
                  <LinearGauge
                    label="Storage Utilization"
                    value={resource.storage_utilization ?? 0}
                    unit="%"
                    warnThreshold={75}
                    critThreshold={90}
                  />
                  <LatencyGauge
                    latencyMs={resource.network_latency_ms ?? 0}
                    warnThreshold={60}
                    critThreshold={120}
                  />
                </div>

                {/* Quick telemetry metrics */}
                <div className="grid grid-cols-2 gap-2 text-xs font-mono mb-4">
                  <StatBox
                    label="Heartbeat"
                    value={formatHeartbeat(resource.last_heartbeat)}
                  />
                  <StatBox
                    label="Active Fault"
                    value={resource.active_failure_type || 'None'}
                    highlight={!!resource.active_failure_type}
                  />
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-800/60">
                  <button
                    onClick={() => onSimulateForResource(resource.resource_id)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono transition-colors flex items-center space-x-1"
                  >
                    <span>⚡</span>
                    <span>Inject Fault</span>
                  </button>

                  <button
                    onClick={() => handleReset(resource.resource_id)}
                    disabled={isResetting}
                    className="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 border border-indigo-500/40 rounded-lg text-xs font-mono font-medium transition-colors disabled:opacity-50 flex items-center space-x-1"
                  >
                    <span>{isResetting ? '🔄' : '✨'}</span>
                    <span>{isResetting ? 'Resetting...' : 'Reset to Healthy'}</span>
                  </button>
                </div>
              </Panel>
            );
          })}
        </div>
      ) : (
        /* Table View */
        <Panel title="Infrastructure Telemetry Grid">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Resource ID</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">State</th>
                  <th className="py-2.5 px-3">Health</th>
                  <th className="py-2.5 px-3">CPU</th>
                  <th className="py-2.5 px-3">Memory</th>
                  <th className="py-2.5 px-3">Storage</th>
                  <th className="py-2.5 px-3">Latency</th>
                  <th className="py-2.5 px-3">Last Heartbeat</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredResources.map((resource) => (
                  <tr key={resource.resource_id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-3 font-semibold text-cyan-400">
                      {resource.resource_id}
                    </td>
                    <td className="py-3 px-3 text-slate-300">{resource.resource_type}</td>
                    <td className="py-3 px-3">
                      <StateBadge state={resource.current_state} />
                    </td>
                    <td className="py-3 px-3">
                      <HealthBadge health={resource.health_status} />
                    </td>
                    <td className="py-3 px-3 text-slate-200">
                      {(resource.cpu_utilization ?? 0).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-slate-200">
                      {(resource.memory_utilization ?? 0).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-slate-200">
                      {(resource.storage_utilization ?? 0).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-slate-200">
                      {(resource.network_latency_ms ?? 0).toFixed(1)}ms
                    </td>
                    <td className="py-3 px-3 text-slate-400">
                      {formatHeartbeat(resource.last_heartbeat)}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={() => onSimulateForResource(resource.resource_id)}
                        className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded text-[11px]"
                      >
                        Inject
                      </button>
                      <button
                        onClick={() => handleReset(resource.resource_id)}
                        disabled={resettingId === resource.resource_id}
                        className="px-2 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 rounded text-[11px]"
                      >
                        Reset
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
};
