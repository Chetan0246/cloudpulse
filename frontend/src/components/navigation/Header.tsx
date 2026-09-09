import React from 'react';

interface HeaderProps {
  systemStatus: 'NOMINAL' | 'DEGRADED' | 'RECOVERING';
  isPolling: boolean;
  onTogglePolling: () => void;
  onManualRefresh: () => void;
  onSimulateFailure?: () => void;
  lastUpdated: Date | null;
  activeIncidentsCount: number;
  apiConnected?: boolean | null;
  isSyncing?: boolean;
  pollingIntervalMs?: number;
}

export const Header: React.FC<HeaderProps> = ({
  systemStatus,
  isPolling,
  onTogglePolling,
  onManualRefresh,
  onSimulateFailure,
  lastUpdated,
  activeIncidentsCount,
  apiConnected = true,
  isSyncing = false,
  pollingIntervalMs = 10000,
}) => {
  const statusConfig = {
    NOMINAL: {
      text: 'SYSTEM NOMINAL',
      badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      dotClass: 'bg-emerald-400',
    },
    DEGRADED: {
      text: `DEGRADED (${activeIncidentsCount} ACTIVE)`,
      badgeClass: 'bg-rose-500/15 text-rose-400 border-rose-500/40 animate-pulse',
      dotClass: 'bg-rose-400',
    },
    RECOVERING: {
      text: 'SELF-HEALING ACTIVE',
      badgeClass: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40 animate-pulse',
      dotClass: 'bg-cyan-400',
    },
  };

  const currentStatus = statusConfig[systemStatus] || statusConfig.NOMINAL;

  const formatTime = (date: Date | null) => {
    if (!date) return '--:--:--';
    return date.toLocaleTimeString();
  };

  return (
    <header className="bg-slate-900/90 border-b border-slate-800 backdrop-blur sticky top-0 z-30 px-4 sm:px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Brand & System Status */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">⚡</span>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-bold text-slate-100 tracking-tight font-mono">
                  CloudPulse
                </h1>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Control Center
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Autonomous Self-Healing Cloud Reliability Engine
              </p>
            </div>
          </div>

          <div className="h-6 w-px bg-slate-800 mx-2 hidden sm:block" />

          {/* Global Status Pill */}
          <div
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-semibold border ${currentStatus.badgeClass}`}
          >
            <span className={`w-2 h-2 rounded-full mr-2 ${currentStatus.dotClass} animate-ping`} />
            <span>{currentStatus.text}</span>
          </div>

          {/* Backend API Connectivity */}
          {apiConnected !== null && (
            <span
              title={apiConnected ? 'Connected to FastAPI backend' : 'Backend unreachable'}
              className={`hidden lg:inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${
                apiConnected
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/30 animate-pulse'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  apiConnected ? 'bg-emerald-400' : 'bg-rose-400'
                }`}
              />
              {apiConnected ? 'API ONLINE' : 'API OFFLINE'}
            </span>
          )}
        </div>

        {/* Live Polling & Controls */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div className="flex items-center space-x-2 bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800">
            <span
              className={`w-2 h-2 rounded-full ${
                isPolling ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
              }`}
            />
            <span className="text-slate-400">
              {isPolling ? `LIVE (${Math.round(pollingIntervalMs / 1000)}s)` : 'PAUSED'}
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">
              Synced: <span className="text-slate-200">{formatTime(lastUpdated)}</span>
            </span>
          </div>

          {onSimulateFailure && (
            <button
              onClick={onSimulateFailure}
              title="Open Chaos Engineering & Failure Simulator"
              className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-rose-600 via-amber-600 to-rose-600 hover:from-rose-500 hover:via-amber-500 hover:to-rose-500 text-white font-bold text-xs font-mono shadow-md shadow-rose-950/50 border border-rose-400/50 flex items-center space-x-1.5 transition-all transform hover:scale-105 active:scale-95 cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-400 focus:ring-offset-2 focus:ring-offset-slate-950"
            >
              <span className="animate-pulse text-sm">⚡</span>
              <span>Simulate Failure</span>
            </button>
          )}

          <button
            onClick={onTogglePolling}
            title={isPolling ? 'Pause real-time updates' : 'Resume real-time updates'}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
          >
            {isPolling ? '⏸ Pause' : '▶ Resume'}
          </button>

          <button
            onClick={onManualRefresh}
            disabled={isSyncing}
            title="Manual Telemetry Sync"
            className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 border border-indigo-500/40 font-semibold transition-colors disabled:opacity-50 flex items-center space-x-1"
          >
            <span className={isSyncing ? 'animate-spin' : ''}>🔄</span>
            <span>{isSyncing ? 'Syncing...' : 'Sync'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
