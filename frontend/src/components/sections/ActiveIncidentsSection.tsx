import React, { useState } from 'react';
import type { IncidentSummary } from '../../api/types';
import { Panel } from '../common/Card';
import { StatusBadge, SeverityBadge, FailureTypeBadge } from '../common/Badge';
import { EmptyState } from '../common/StateViews';

interface ActiveIncidentsSectionProps {
  incidents: IncidentSummary[];
  onSelectIncident: (incidentId: string) => void;
  onNavigateTab?: (tabId: any) => void;
}

export const ActiveIncidentsSection: React.FC<ActiveIncidentsSectionProps> = ({
  incidents,
  onSelectIncident,
  onNavigateTab,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredIncidents = incidents.filter((incident) => {
    const incId = (incident.incident_id || incident.incidentId || '').toLowerCase();
    const resId = (incident.resource_id || incident.resourceId || '').toLowerCase();
    const fType = incident.failure_type || incident.failureType || '';
    const status = incident.status;
    const severity = incident.severity;

    // Filter by status
    if (statusFilter !== 'ALL' && status !== statusFilter) return false;

    // Filter by severity
    if (severityFilter !== 'ALL' && severity !== severityFilter) return false;

    // Filter by failure type
    if (typeFilter !== 'ALL' && fType !== typeFilter) return false;

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      if (!incId.includes(q) && !resId.includes(q)) {
        return false;
      }
    }

    return true;
  });

  const formatTimestamp = (iso?: string) => {
    if (!iso) return 'N/A';
    const d = new Date(iso);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
  };

  const formatDuration = (seconds?: number | null) => {
    if (typeof seconds !== 'number' || seconds < 0) return 'In Flight';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const rem = (seconds % 60).toFixed(0);
    return `${mins}m ${rem}s`;
  };

  return (
    <div className="space-y-6">
      {/* Filters Control Bar */}
      <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
              <span>🚨</span>
              <span>Incident Lifecycle Telemetry</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Comprehensive audit trail of detected anomalies and autonomous recovery outcomes.
            </p>
          </div>

          {/* Search box */}
          <div className="w-full md:w-64">
            <input
              type="text"
              placeholder="Search Incident / Resource ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-950 text-xs font-mono text-slate-200 rounded-lg border border-slate-800 focus:outline-none focus:border-indigo-500 placeholder-slate-600"
            />
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800/80 text-xs font-mono">
          {/* Status Filter */}
          <div className="flex items-center space-x-1">
            <span className="text-slate-500 mr-1 text-[11px]">Status:</span>
            {['ALL', 'OPEN', 'RECOVERING', 'RESOLVED', 'ESCALATED'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                  statusFilter === st
                    ? 'bg-indigo-600 text-white font-semibold'
                    : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-850'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Severity Filter */}
          <div className="flex items-center space-x-1">
            <span className="text-slate-500 mr-1 text-[11px]">Severity:</span>
            {['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                  severityFilter === sev
                    ? 'bg-indigo-600 text-white font-semibold'
                    : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-850'
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          {/* Failure Type dropdown */}
          <div className="flex items-center space-x-1">
            <span className="text-slate-500 mr-1 text-[11px]">Fault:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-slate-950 text-slate-300 px-2 py-1 rounded text-[11px] border border-slate-800 focus:outline-none"
            >
              <option value="ALL">ALL FAULTS</option>
              <option value="HIGH_CPU">HIGH_CPU</option>
              <option value="SERVICE_FAILURE">SERVICE_FAILURE</option>
              <option value="STORAGE_EXHAUSTION">STORAGE_EXHAUSTION</option>
              <option value="NETWORK_LATENCY">NETWORK_LATENCY</option>
              <option value="SERVICE_DOWNTIME">SERVICE_DOWNTIME</option>
            </select>
          </div>

          {(statusFilter !== 'ALL' ||
            severityFilter !== 'ALL' ||
            typeFilter !== 'ALL' ||
            searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter('ALL');
                setSeverityFilter('ALL');
                setTypeFilter('ALL');
                setSearchQuery('');
              }}
              className="text-[11px] text-rose-400 hover:text-rose-300 underline ml-auto"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Incident Status Metric Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs font-mono">
        <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Total Tracked</span>
          <span className="text-slate-200 font-bold text-sm">{incidents.length}</span>
        </div>
        <div className="bg-rose-950/20 border border-rose-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Open</span>
          <span className="text-rose-400 font-bold text-sm">
            {incidents.filter((i) => i.status === 'OPEN').length}
          </span>
        </div>
        <div className="bg-cyan-950/20 border border-cyan-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Recovering</span>
          <span className="text-cyan-400 font-bold text-sm">
            {incidents.filter((i) => i.status === 'RECOVERING').length}
          </span>
        </div>
        <div className="bg-emerald-950/20 border border-emerald-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Resolved</span>
          <span className="text-emerald-400 font-bold text-sm">
            {incidents.filter((i) => i.status === 'RESOLVED').length}
          </span>
        </div>
        <div className="bg-purple-950/20 border border-purple-800/40 p-3 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Escalated</span>
          <span className="text-purple-400 font-bold text-sm">
            {incidents.filter((i) => i.status === 'ESCALATED').length}
          </span>
        </div>
      </div>

      {/* Incidents List Panel */}
      <Panel
        title={`Incident Records (${filteredIncidents.length})`}
        subtitle="Chronological log of simulated alarm triggers and resolution paths"
      >
        {filteredIncidents.length === 0 ? (
          <EmptyState
            title="No Incidents Match Filters"
            description="Adjust your search criteria or inject a failure scenario to generate incident records."
            icon="📋"
            actionText={incidents.length === 0 && onNavigateTab ? 'Launch Simulator' : undefined}
            onAction={incidents.length === 0 && onNavigateTab ? () => onNavigateTab('simulator') : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Incident ID</th>
                  <th className="py-2.5 px-3">Resource</th>
                  <th className="py-2.5 px-3">Failure Scenario</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Detected At</th>
                  <th className="py-2.5 px-3">Duration</th>
                  <th className="py-2.5 px-3">Recovery Action</th>
                  <th className="py-2.5 px-3 text-right">Lifecycle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredIncidents.map((incident) => {
                  const incId = incident.incident_id || incident.incidentId || '';
                  const resId = incident.resource_id || incident.resourceId || '';
                  const fType = incident.failure_type || incident.failureType || 'UNKNOWN';
                  const detected = incident.detected_at || incident.detectedAt;
                  const action = incident.recovery_action || incident.recoveryAction || 'PENDING';
                  const result = incident.recovery_result || incident.recoveryResult;

                  return (
                    <tr
                      key={incId}
                      onClick={() => onSelectIncident(incId)}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-3 font-semibold text-cyan-400">
                        {incId.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3 text-slate-200 font-bold">{resId}</td>
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
                        {formatTimestamp(detected)}
                      </td>
                      <td className="py-3 px-3 text-slate-300">
                        {formatDuration(incident.duration_seconds)}
                      </td>
                      <td className="py-3 px-3 text-slate-400 max-w-xs truncate">
                        <span className="font-semibold text-slate-300">{action}</span>
                        {result && <span className="text-slate-500 ml-1">({result})</span>}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectIncident(incId);
                          }}
                          className="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 rounded text-[11px] transition-colors"
                        >
                          Inspect →
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
