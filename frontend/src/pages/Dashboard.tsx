import React, { useEffect, useState, useCallback, useRef } from 'react';
import type {
  IncidentSummary,
  ResourceSummary,
  ReliabilityMetric,
  FailureType,
  IncidentSeverity,
  FleetReliabilityOverview,
} from '../api/types';
import { healthApi } from '../api/health';
import { resourcesApi } from '../api/resources';
import { incidentsApi } from '../api/incidents';
import { metricsApi } from '../api/metrics';
import { simulateApi } from '../api/simulate';

import { Header } from '../components/navigation/Header';
import { TabNav, SectionTabId } from '../components/navigation/TabNav';
import { LoadingState, ErrorState } from '../components/common/StateViews';

import { OverviewSection } from '../components/sections/OverviewSection';
import { ResourceHealthSection } from '../components/sections/ResourceHealthSection';
import { FailureSimulatorSection } from '../components/sections/FailureSimulatorSection';
import { ActiveIncidentsSection } from '../components/sections/ActiveIncidentsSection';
import { IncidentDetailSection } from '../components/sections/IncidentDetailSection';
import { RecoveryActivitySection } from '../components/sections/RecoveryActivitySection';
import { ReliabilityMetricsSection } from '../components/sections/ReliabilityMetricsSection';
import { ArchitectureViewSection } from '../components/sections/ArchitectureViewSection';
import { SystemEventsSection } from '../components/sections/SystemEventsSection';

// Low-cost student deployment refresh strategy intervals
const IDLE_POLL_INTERVAL_MS = 10_000; // 10s when all resources are healthy
const ACTIVE_POLL_INTERVAL_MS = 3_000; // 3s when incidents or self-healing are in-flight

export const Dashboard: React.FC = () => {
  const [resources, setResources] = useState<ResourceSummary[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [metrics, setMetrics] = useState<ReliabilityMetric[]>([]);
  const [metricsOverview, setMetricsOverview] = useState<FleetReliabilityOverview | null>(null);

  const [activeTab, setActiveTab] = useState<SectionTabId>('overview');
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | undefined>();
  const [simulatorResourceId, setSimulatorResourceId] = useState<string | undefined>();
  const [metricsWindow, setMetricsWindow] = useState<'DAILY' | 'WEEKLY' | 'CUMULATIVE'>('DAILY');

  const [initialLoading, setInitialLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const isFetchingRef = useRef(false);

  // Active in-flight detection
  const hasActiveIncidents = incidents.some(
    (i) => i.status === 'OPEN' || i.status === 'RECOVERING'
  );
  const hasDegradedResources = resources.some(
    (r) =>
      r.current_state === 'FAILURE_DETECTED' ||
      r.current_state === 'RECOVERY_INITIATED' ||
      r.current_state === 'RECOVERY_IN_PROGRESS'
  );
  const isSystemActive = hasActiveIncidents || hasDegradedResources;
  const currentIntervalMs = isSystemActive ? ACTIVE_POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;

  // Consolidated fetch function connecting real APIs
  const fetchAllTelemetry = useCallback(async (isManual = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    if (isManual) setIsSyncing(true);

    try {
      setFetchError(null);

      // Verify health probe alongside resources, incidents, metrics snapshots, and fleet SRE overview
      const [healthRes, resList, incList, metList, overviewRes] = await Promise.all([
        healthApi.check().catch(() => null),
        resourcesApi.list().catch(() => [] as ResourceSummary[]),
        incidentsApi.list({ limit: 100 }).catch(() => [] as IncidentSummary[]),
        metricsApi.list({ window_type: metricsWindow, limit: 50 }).catch(() => [] as ReliabilityMetric[]),
        metricsApi.getOverview(metricsWindow).catch(() => null),
      ]);

      setApiConnected(healthRes?.status === 'ok' || resList.length > 0);
      setResources(resList);
      setIncidents(incList);
      setMetrics(metList);
      setMetricsOverview(overviewRes);
      setLastUpdated(new Date());
    } catch (err: any) {
      console.error('[Telemetry Sync Error]', err);
      setApiConnected(false);
      setFetchError(
        err.response?.data?.detail || err.message || 'Failed to connect to CloudPulse API'
      );
    } finally {
      isFetchingRef.current = false;
      setInitialLoading(false);
      if (isManual) setIsSyncing(false);
    }
  }, [metricsWindow]);

  // Page Visibility API + Adaptive Polling Loop
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let isCancelled = false;

    // Initial fetch
    fetchAllTelemetry();

    const scheduleNextPoll = () => {
      if (!isPolling || document.visibilityState === 'hidden') {
        return;
      }
      timeoutId = setTimeout(async () => {
        if (!isCancelled && isPolling && document.visibilityState === 'visible') {
          await fetchAllTelemetry();
          scheduleNextPoll();
        }
      }, currentIntervalMs);
    };

    scheduleNextPoll();

    // Handle tab visibility change (suspend polling when tab is hidden to conserve resources)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isPolling) {
        fetchAllTelemetry();
        scheduleNextPoll();
      } else if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isCancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchAllTelemetry, isPolling, currentIntervalMs]);

  // Global system status calculation
  const activeIncidents = incidents.filter(
    (i) => i.status === 'OPEN' || i.status === 'RECOVERING'
  );
  const isRecovering = incidents.some((i) => i.status === 'RECOVERING') ||
    resources.some((r) => r.current_state === 'RECOVERY_IN_PROGRESS' || r.current_state === 'RECOVERY_INITIATED');

  let systemStatus: 'NOMINAL' | 'DEGRADED' | 'RECOVERING' = 'NOMINAL';
  if (isRecovering) {
    systemStatus = 'RECOVERING';
  } else if (activeIncidents.length > 0 || hasDegradedResources) {
    systemStatus = 'DEGRADED';
  }

  // Safe Optimistic Handlers
  const handleResetResource = async (resourceId: string) => {
    // 1. Safe optimistic update: immediately mark resource healthy in UI
    setResources((prev) =>
      prev.map((r) =>
        r.resource_id === resourceId
          ? {
              ...r,
              current_state: 'HEALTHY',
              health_status: 'HEALTHY',
              active_failure_type: null,
              cpu_utilization: 25.0,
              memory_utilization: 30.0,
              storage_utilization: 20.0,
              network_latency_ms: 15.0,
            }
          : r
      )
    );

    // 2. Call backend API
    await simulateApi.reset(resourceId);

    // 3. Confirm with fresh server fetch
    await fetchAllTelemetry(true);
  };

  const handleInjectFailure = async (
    resourceId: string,
    failureType: FailureType,
    severity: IncidentSeverity
  ) => {
    // 1. Safe optimistic update: reflect failure state immediately
    setResources((prev) =>
      prev.map((r) =>
        r.resource_id === resourceId
          ? {
              ...r,
              current_state: 'FAILURE_DETECTED',
              health_status: 'CRITICAL',
              active_failure_type: failureType,
            }
          : r
      )
    );

    // 2. Call backend API POST /simulate/failure
    const response = await simulateApi.inject(resourceId, failureType, severity);

    // 3. Confirm with fresh server fetch
    await fetchAllTelemetry(true);
    return response;
  };

  const handleSelectIncident = (incidentId: string) => {
    setSelectedIncidentId(incidentId);
    setActiveTab('incident-detail');
  };

  const handleSimulateForResource = (resourceId: string) => {
    setSimulatorResourceId(resourceId);
    setActiveTab('simulator');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Control Center Header */}
      <Header
        systemStatus={systemStatus}
        isPolling={isPolling}
        onTogglePolling={() => setIsPolling(!isPolling)}
        onManualRefresh={() => fetchAllTelemetry(true)}
        onSimulateFailure={() => setActiveTab('simulator')}
        lastUpdated={lastUpdated}
        activeIncidentsCount={activeIncidents.length}
        apiConnected={apiConnected}
        isSyncing={isSyncing}
        pollingIntervalMs={currentIntervalMs}
      />

      {/* 9-Section Navigation Tab Bar */}
      <TabNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        activeIncidentsCount={activeIncidents.length}
      />

      {/* Main Section Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {initialLoading ? (
          <LoadingState
            message="Connecting to CloudPulse Backend Telemetry API..."
            subtext="Establishing telemetry stream via /health, /resources, /incidents, and /metrics"
            size="lg"
          />
        ) : fetchError && resources.length === 0 ? (
          <ErrorState
            title="Backend Service Unreachable"
            message={`Unable to connect to CloudPulse API: ${fetchError}`}
            onRetry={() => fetchAllTelemetry(true)}
          />
        ) : (
          <div>
            {activeTab === 'overview' && (
              <OverviewSection
                resources={resources}
                incidents={incidents}
                overview={metricsOverview}
                onSelectIncident={handleSelectIncident}
                onNavigateTab={setActiveTab}
                onSimulateForResource={handleSimulateForResource}
              />
            )}

            {activeTab === 'resources' && (
              <ResourceHealthSection
                resources={resources}
                onResetResource={handleResetResource}
                onSimulateForResource={handleSimulateForResource}
              />
            )}

            {activeTab === 'simulator' && (
              <FailureSimulatorSection
                resources={resources}
                selectedResourceId={simulatorResourceId}
                onInjectFailure={handleInjectFailure}
                onResetResource={handleResetResource}
                onInspectIncident={handleSelectIncident}
              />
            )}

            {activeTab === 'incidents' && (
              <ActiveIncidentsSection
                incidents={incidents}
                onSelectIncident={handleSelectIncident}
                onNavigateTab={setActiveTab}
              />
            )}

            {activeTab === 'incident-detail' && (
              <IncidentDetailSection
                selectedIncidentId={selectedIncidentId}
                allIncidents={incidents}
                onSelectIncident={setSelectedIncidentId}
                onNavigateTab={setActiveTab}
              />
            )}

            {activeTab === 'recovery' && (
              <RecoveryActivitySection
                incidents={incidents}
                onSelectIncident={handleSelectIncident}
              />
            )}

            {activeTab === 'metrics' && (
              <ReliabilityMetricsSection
                metrics={metrics}
                overview={metricsOverview}
                selectedWindow={metricsWindow}
                onChangeWindow={setMetricsWindow}
              />
            )}

            {activeTab === 'architecture' && (
              <ArchitectureViewSection
                resources={resources}
                incidents={incidents}
              />
            )}

            {activeTab === 'events' && (
              <SystemEventsSection
                incidents={incidents}
                resources={resources}
                onSelectIncident={handleSelectIncident}
              />
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-6 text-center text-xs font-mono text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>CloudPulse Autonomous Self-Healing Reliability Engine • AWS Serverless</div>
          <div className="text-slate-400">
            Refresh Rate: {Math.round(currentIntervalMs / 1000)}s ({isSystemActive ? 'ACTIVE' : 'IDLE'}) • Connected API: {apiConnected ? 'HEALTHY' : 'OFFLINE'}
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Dashboard;
