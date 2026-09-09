import React from 'react';
import type { FailureType, HealthStatus, IncidentSeverity, IncidentStatus, ResourceState } from '../../api/types';

export const StateBadge: React.FC<{ state: ResourceState | string }> = ({ state }) => {
  const styles: Record<string, { cls: string; icon: string }> = {
    HEALTHY: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', icon: '●' },
    WARNING: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', icon: '⚠️' },
    FAILURE_DETECTED: { cls: 'bg-rose-500/20 text-rose-400 border-rose-500/50 animate-pulse shadow-sm shadow-rose-500/20', icon: '💥' },
    RECOVERY_INITIATED: { cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40', icon: '⚙️' },
    RECOVERY_IN_PROGRESS: { cls: 'bg-blue-500/20 text-blue-300 border-blue-500/50 animate-pulse shadow-sm shadow-blue-500/20', icon: '🔄' },
    RECOVERED: { cls: 'bg-teal-500/15 text-teal-400 border-teal-500/40', icon: '✅' },
    RECOVERY_FAILED: { cls: 'bg-rose-500/25 text-rose-300 border-rose-500/60 font-bold', icon: '❌' },
    MANUAL_INTERVENTION_REQUIRED: { cls: 'bg-purple-500/25 text-purple-300 border-purple-500/60 animate-bounce font-bold', icon: '🚨' },
  };

  const theme = styles[state] || { cls: 'bg-slate-800 text-slate-300 border-slate-700', icon: '•' };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${theme.cls}`}>
      <span className="mr-1 text-[10px]">{theme.icon}</span>
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
  const styles: Record<string, { cls: string; icon: string }> = {
    OPEN: { cls: 'bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse', icon: '🚨' },
    RECOVERING: { cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40 animate-pulse', icon: '🔄' },
    RESOLVED: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', icon: '✓' },
    ESCALATED: { cls: 'bg-purple-500/20 text-purple-300 border-purple-500/50', icon: '⚠️' },
  };

  const theme = styles[status] || { cls: 'bg-slate-800 text-slate-300 border-slate-700', icon: '•' };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold border ${theme.cls}`}>
      <span className="mr-1 text-[10px]">{theme.icon}</span>
      {status}
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: IncidentSeverity | string }> = ({ severity }) => {
  const styles: Record<string, { cls: string; dot: string }> = {
    LOW: { cls: 'bg-slate-800 text-slate-300 border-slate-700', dot: 'bg-slate-400' },
    MEDIUM: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/30', dot: 'bg-blue-400' },
    HIGH: { cls: 'bg-amber-500/15 text-amber-400 border-amber-500/40 font-semibold', dot: 'bg-amber-400' },
    CRITICAL: { cls: 'bg-rose-500/20 text-rose-300 border-rose-500/50 font-bold shadow-sm shadow-rose-500/20', dot: 'bg-rose-400 animate-pulse' },
  };

  const theme = styles[severity] || { cls: 'bg-slate-800 text-slate-300 border-slate-700', dot: 'bg-slate-400' };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${theme.cls}`}>
      <span className={`w-1.5 h-1.5 mr-1.5 rounded-full ${theme.dot}`} />
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
