import React from 'react';
import type { FailureType, HealthStatus, IncidentSeverity, IncidentStatus, ResourceState } from '../../api/types';

export const StateBadge: React.FC<{ state: ResourceState | string }> = ({ state }) => {
  const styles: Record<string, string> = {
    HEALTHY: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    WARNING: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    FAILURE_DETECTED: 'bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse',
    RECOVERY_INITIATED: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40',
    RECOVERY_IN_PROGRESS: 'bg-blue-500/15 text-blue-400 border-blue-500/40 animate-pulse',
    RECOVERED: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
    RECOVERY_FAILED: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
    MANUAL_INTERVENTION_REQUIRED: 'bg-purple-500/20 text-purple-300 border-purple-500/50 animate-bounce',
  };

  const currentStyle = styles[state] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${currentStyle}`}>
      <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current opacity-80" />
      {state}
    </span>
  );
};

export const HealthBadge: React.FC<{ health: HealthStatus | string }> = ({ health }) => {
  const styles: Record<string, string> = {
    HEALTHY: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    DEGRADED: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    CRITICAL: 'bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse',
  };

  const currentStyle = styles[health] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${currentStyle}`}>
      {health}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: IncidentStatus | string }> = ({ status }) => {
  const styles: Record<string, string> = {
    OPEN: 'bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse',
    RECOVERING: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40 animate-pulse',
    RESOLVED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    ESCALATED: 'bg-purple-500/20 text-purple-300 border-purple-500/50',
  };

  const currentStyle = styles[status] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold border ${currentStyle}`}>
      {status}
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: IncidentSeverity | string }> = ({ severity }) => {
  const styles: Record<string, string> = {
    LOW: 'bg-slate-800 text-slate-300 border-slate-700',
    MEDIUM: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    HIGH: 'bg-amber-500/15 text-amber-400 border-amber-500/40',
    CRITICAL: 'bg-rose-500/20 text-rose-300 border-rose-500/50 font-bold',
  };

  const currentStyle = styles[severity] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${currentStyle}`}>
      {severity}
    </span>
  );
};

export const FailureTypeBadge: React.FC<{ failureType: FailureType | string }> = ({ failureType }) => {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
      {failureType}
    </span>
  );
};
