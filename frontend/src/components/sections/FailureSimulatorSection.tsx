import React, { useState, useEffect } from 'react';
import type { FailureType, IncidentSeverity, ResourceSummary } from '../../api/types';
import { simulateApi } from '../../api/simulate';
import { Panel } from '../common/Card';
import { StateBadge, SeverityBadge } from '../common/Badge';

interface ScenarioMeta {
  code: string;
  name: string;
  type: FailureType;
  description: string;
  metric: string;
  alarmThreshold: string;
  recoveryStrategy: string;
  defaultSeverity: IncidentSeverity;
}

const SCENARIOS: ScenarioMeta[] = [
  {
    code: 'FS-01',
    name: 'High CPU Utilization',
    type: 'HIGH_CPU',
    description:
      'Simulates heavy application processing or runaway compute tasks pushing CPU to 95%.',
    metric: 'CPUUtilization (VirtualComputeEngine)',
    alarmThreshold: 'CPU > 85% for 2 consecutive periods (60s)',
    recoveryStrategy: 'SCALE_OUT — Scale instance capacity and normalize thread pool',
    defaultSeverity: 'HIGH',
  },
  {
    code: 'FS-02',
    name: 'Service Health Degradation',
    type: 'SERVICE_FAILURE',
    description:
      'Simulates internal worker crash or memory leak resulting in unhealthy service state.',
    metric: 'ServiceHealth (HealthStatus)',
    alarmThreshold: 'ServiceHealth == 0 (UNHEALTHY / CRITICAL)',
    recoveryStrategy: 'SERVICE_RESTART — Graceful process restart and health check verify',
    defaultSeverity: 'HIGH',
  },
  {
    code: 'FS-03',
    name: 'Storage Volume Exhaustion',
    type: 'STORAGE_EXHAUSTION',
    description:
      'Simulates rapid log growth or uncleaned temp caches filling disk volume to 92%.',
    metric: 'StorageUtilization (EBS/Disk)',
    alarmThreshold: 'Disk Usage > 85% capacity threshold',
    recoveryStrategy: 'STORAGE_CLEANUP — Purge transient logs and reclaim storage blocks',
    defaultSeverity: 'MEDIUM',
  },
  {
    code: 'FS-04',
    name: 'Network Latency Spike',
    type: 'NETWORK_LATENCY',
    description:
      'Simulates routing degradation or packet drops driving latency to 250ms.',
    metric: 'NetworkLatency (VPC RTT)',
    alarmThreshold: 'Network Latency > 100ms sustained for 60s',
    recoveryStrategy: 'NETWORK_REROUTE — Flush routing table and switch to standby transit path',
    defaultSeverity: 'MEDIUM',
  },
  {
    code: 'FS-05',
    name: 'Unrecoverable Service Downtime',
    type: 'SERVICE_DOWNTIME',
    description:
      'Simulates catastrophic cluster downtime triggering failover protocol.',
    metric: 'Availability & Heartbeat Timeout',
    alarmThreshold: 'Zero response across 3 health probes',
    recoveryStrategy: 'FAILOVER — Promote standby node and redirect traffic via DNS',
    defaultSeverity: 'CRITICAL',
  },
];

export type LifecycleStage = 'HEALTHY' | 'FAILURE' | 'DETECTION' | 'RECOVERY' | 'RECOVERED';

interface FailureSimulatorSectionProps {
  resources: ResourceSummary[];
  selectedResourceId?: string;
  onInjectFailure: (
    resourceId: string,
    failureType: FailureType,
    severity: IncidentSeverity
  ) => Promise<any>;
  onResetResource: (resourceId: string) => Promise<void>;
  onInspectIncident?: (incidentId: string) => void;
}

export const FailureSimulatorSection: React.FC<FailureSimulatorSectionProps> = ({
  resources,
  selectedResourceId,
  onInjectFailure,
  onResetResource,
  onInspectIncident,
}) => {
  const [resourceId, setResourceId] = useState<string>(
    selectedResourceId || resources[0]?.resource_id || 'VM-001'
  );
  const [scenarioType, setScenarioType] = useState<FailureType>('HIGH_CPU');
  const [severity, setSeverity] = useState<IncidentSeverity>('HIGH');
  const [autoHeal, setAutoHeal] = useState<boolean>(true);

  const [activeStage, setActiveStage] = useState<LifecycleStage>('HEALTHY');
  const [isInjecting, setIsInjecting] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [lastResult, setLastResult] = useState<any | null>(null);
  const [createdIncidentId, setCreatedIncidentId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [stageTimestamps, setStageTimestamps] = useState<Record<string, string>>({});

  const selectedScenario =
    SCENARIOS.find((s) => s.type === scenarioType) || SCENARIOS[0];
  const targetResource = resources.find((r) => r.resource_id === resourceId);

  // Sync active stage with target resource when idle
  useEffect(() => {
    if (!isInjecting && !isRecovering) {
      if (!targetResource || targetResource.current_state === 'HEALTHY') {
        setActiveStage('HEALTHY');
      } else if (targetResource.current_state === 'FAILURE_DETECTED') {
        setActiveStage('DETECTION');
      } else if (
        targetResource.current_state === 'RECOVERY_INITIATED' ||
        targetResource.current_state === 'RECOVERY_IN_PROGRESS'
      ) {
        setActiveStage('RECOVERY');
      } else if (targetResource.current_state === 'RECOVERED') {
        setActiveStage('RECOVERED');
      }
    }
  }, [targetResource, isInjecting, isRecovering]);

  const recordStageTime = (stage: LifecycleStage) => {
    setStageTimestamps((prev) => ({
      ...prev,
      [stage]: new Date().toLocaleTimeString(),
    }));
  };

  const handleSelectScenario = (scenario: ScenarioMeta) => {
    setScenarioType(scenario.type);
    setSeverity(scenario.defaultSeverity);
  };

  // 5-Stage Lifecycle Execution Flow
  const handleExecuteLifecycle = async () => {
    setErrorMessage(null);
    setLastResult(null);
    setIsInjecting(true);

    try {
      // 1. Healthy baseline confirmed
      recordStageTime('HEALTHY');

      // 2. Failure: Workload fault injected (optimistic transition)
      setActiveStage('FAILURE');
      recordStageTime('FAILURE');

      // Small 400ms pause for visible UI transition
      await new Promise((resolve) => setTimeout(resolve, 400));

      // 3. Detection: Call POST /simulate/failure against backend
      const result = await onInjectFailure(resourceId, scenarioType, severity);
      setLastResult(result);

      const incId =
        result?.incident?.incident_id ||
        result?.incident?.incidentId ||
        result?.incident_id;
      if (incId) setCreatedIncidentId(incId);

      setActiveStage('DETECTION');
      recordStageTime('DETECTION');
      setIsInjecting(false);

      // If Auto-Heal is enabled, automatically execute the self-healing recovery step
      if (autoHeal) {
        // Allow user to see the Detection stage briefly (1200ms)
        await new Promise((resolve) => setTimeout(resolve, 1200));
        await handleTriggerRecovery();
      }
    } catch (err: any) {
      setIsInjecting(false);
      const msg =
        err.response?.data?.detail || err.message || 'Failed to trigger simulated failure';
      setErrorMessage(msg);
      setActiveStage('HEALTHY');
    }
  };

  // Recovery execution: Recovery -> Recovered
  const handleTriggerRecovery = async () => {
    setIsRecovering(true);
    setErrorMessage(null);
    try {
      // 4. Recovery: Engage Self-Healing Engine
      setActiveStage('RECOVERY');
      recordStageTime('RECOVERY');

      // Simulate recovery processing delay (800ms)
      await new Promise((resolve) => setTimeout(resolve, 800));

      // Call backend recover/reset API
      await simulateApi.recover(resourceId);
      await onResetResource(resourceId);

      // 5. Recovered: Success & nominal metrics restored
      setActiveStage('RECOVERED');
      recordStageTime('RECOVERED');
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to execute recovery';
      setErrorMessage(msg);
    } finally {
      setIsRecovering(false);
    }
  };

  const handleReset = async () => {
    setErrorMessage(null);
    setIsResetting(true);
    try {
      await onResetResource(resourceId);
      setActiveStage('HEALTHY');
      setLastResult({
        message: `Resource '${resourceId}' successfully reset to HEALTHY.`,
        resource: { ...targetResource, current_state: 'HEALTHY' },
      });
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to reset resource'
      );
    } finally {
      setIsResetting(false);
    }
  };

  // Lifecycle steps configuration
  const lifecycleSteps: Array<{
    stage: LifecycleStage;
    number: string;
    label: string;
    icon: string;
    detail: string;
  }> = [
    {
      stage: 'HEALTHY',
      number: '1',
      label: 'Healthy',
      icon: '🛡️',
      detail: 'Nominal Baseline — metrics within green threshold',
    },
    {
      stage: 'FAILURE',
      number: '2',
      label: 'Failure',
      icon: '⚡',
      detail: 'Workload Fault — simulated anomaly injected into instance',
    },
    {
      stage: 'DETECTION',
      number: '3',
      label: 'Detection',
      icon: '🔔',
      detail: 'Alarm Triggered — CloudWatch breaches threshold, incident opened',
    },
    {
      stage: 'RECOVERY',
      number: '4',
      label: 'Recovery',
      icon: '🛠️',
      detail: 'Self-Healing — EventBridge routes to Recovery Lambda',
    },
    {
      stage: 'RECOVERED',
      number: '5',
      label: 'Recovered',
      icon: '✅',
      detail: 'SLO Restored — strategy executed, metrics normalized',
    },
  ];

  const getStepStatus = (stepStage: LifecycleStage, index: number) => {
    const stageOrder: LifecycleStage[] = [
      'HEALTHY',
      'FAILURE',
      'DETECTION',
      'RECOVERY',
      'RECOVERED',
    ];
    const currentIndex = stageOrder.indexOf(activeStage);

    if (activeStage === stepStage) return 'active';
    if (currentIndex > index) return 'completed';
    return 'pending';
  };

  return (
    <div className="space-y-6">
      {/* Introduction Card */}
      <div className="bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 border border-indigo-500/30 rounded-xl p-5 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
              <span>⚡</span>
              <span>Chaos Engineering & Fault Injection Simulator</span>
            </h2>
            <p className="text-xs text-slate-300 mt-1 max-w-2xl">
              Simulates the full autonomous reliability lifecycle:
              Healthy → Failure → Detection → Recovery → Recovered.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono text-slate-300">Auto Self-Healing:</span>
            <button
              onClick={() => setAutoHeal(!autoHeal)}
              className={`px-2.5 py-1 rounded text-xs font-mono font-semibold transition-colors border ${
                autoHeal
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              {autoHeal ? 'ON (Auto-Recover)' : 'OFF (Manual Step)'}
            </button>
          </div>
        </div>
      </div>

      {/* 5-Stage Visible Lifecycle Stepper */}
      <Panel
        title="Simulated Reliability Lifecycle"
        subtitle="Real-time progression from baseline health through fault injection and autonomous remediation"
        badge={
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${
              activeStage === 'HEALTHY'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : activeStage === 'FAILURE'
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
                : activeStage === 'DETECTION'
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                : activeStage === 'RECOVERY'
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 animate-pulse'
                : 'bg-teal-500/20 text-teal-300 border-teal-500/40'
            }`}
          >
            STAGE: {activeStage}
          </span>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 py-2">
          {lifecycleSteps.map((step, idx) => {
            const status = getStepStatus(step.stage, idx);
            const isCurrent = status === 'active';
            const isDone = status === 'completed';
            const timestamp = stageTimestamps[step.stage];

            let borderStyle = 'border-slate-800 bg-slate-950/60 text-slate-500';
            if (isCurrent) {
              if (step.stage === 'HEALTHY')
                borderStyle = 'border-emerald-500 bg-emerald-950/30 text-emerald-300 ring-2 ring-emerald-500/30';
              else if (step.stage === 'FAILURE')
                borderStyle = 'border-amber-500 bg-amber-950/30 text-amber-300 ring-2 ring-amber-500/30 animate-pulse';
              else if (step.stage === 'DETECTION')
                borderStyle = 'border-rose-500 bg-rose-950/40 text-rose-300 ring-2 ring-rose-500/40 animate-pulse';
              else if (step.stage === 'RECOVERY')
                borderStyle = 'border-cyan-500 bg-cyan-950/40 text-cyan-300 ring-2 ring-cyan-500/40 animate-pulse';
              else if (step.stage === 'RECOVERED')
                borderStyle = 'border-teal-500 bg-teal-950/40 text-teal-300 ring-2 ring-teal-500/40';
            } else if (isDone) {
              borderStyle = 'border-emerald-500/50 bg-slate-950/90 text-emerald-400';
            }

            return (
              <div
                key={step.stage}
                className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between font-mono ${borderStyle}`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xl">{step.icon}</span>
                    <span className="text-xs font-bold px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                      {isDone ? '✓' : step.number}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-slate-100">{step.label}</div>
                  <p className="text-[10px] text-slate-400 mt-1 leading-snug">{step.detail}</p>
                </div>
                {timestamp && (
                  <div className="text-[10px] text-slate-500 mt-3 pt-2 border-t border-slate-800/80">
                    Time: <span className="text-slate-300">{timestamp}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Manual Recovery Step Action when Auto-Heal is OFF */}
        {!autoHeal && activeStage === 'DETECTION' && (
          <div className="mt-4 p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-500/40 flex items-center justify-between">
            <div className="text-xs font-mono text-cyan-300">
              ⚡ Failure detected! Ready to execute automated self-healing strategy.
            </div>
            <button
              onClick={handleTriggerRecovery}
              disabled={isRecovering}
              className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold rounded-lg transition-colors flex items-center space-x-1"
            >
              <span>{isRecovering ? '🔄' : '🛠️'}</span>
              <span>{isRecovering ? 'Recovering...' : 'Initiate Self-Healing (Lambda)'}</span>
            </button>
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Simulator Form (2 cols) */}
        <div className="lg:col-span-2 space-y-5">
          <Panel title="Configure Failure Scenario">
            {/* Target Resource Picker */}
            <div className="space-y-2 mb-5">
              <label className="text-xs font-mono font-semibold text-slate-300 uppercase">
                1. Select Target Virtual Resource
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {resources.map((res) => {
                  const isSelected = res.resource_id === resourceId;
                  return (
                    <button
                      key={res.resource_id}
                      type="button"
                      onClick={() => setResourceId(res.resource_id)}
                      className={`p-3 rounded-lg border text-left transition-all font-mono ${
                        isSelected
                          ? 'border-indigo-500 bg-indigo-950/30 shadow-md ring-1 ring-indigo-500'
                          : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-100">
                          {res.resource_id}
                        </span>
                        <span className="text-[10px] text-slate-500">{res.resource_type}</span>
                      </div>
                      <StateBadge state={res.current_state} />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Scenario Picker */}
            <div className="space-y-2 mb-5">
              <label className="text-xs font-mono font-semibold text-slate-300 uppercase">
                2. Select Failure Scenario
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SCENARIOS.map((sc) => {
                  const isSelected = sc.type === scenarioType;
                  return (
                    <button
                      key={sc.code}
                      type="button"
                      onClick={() => handleSelectScenario(sc)}
                      className={`p-3 rounded-lg border text-left transition-all font-mono ${
                        isSelected
                          ? 'border-indigo-500 bg-indigo-950/40 ring-1 ring-indigo-500'
                          : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-200">
                          {sc.code}: {sc.name}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2">{sc.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Severity Picker */}
            <div className="space-y-2 mb-6">
              <label className="text-xs font-mono font-semibold text-slate-300 uppercase">
                3. Choose Incident Severity Override
              </label>
              <div className="flex flex-wrap gap-2">
                {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as IncidentSeverity[]).map((sev) => {
                  const isSelected = sev === severity;
                  return (
                    <button
                      key={sev}
                      type="button"
                      onClick={() => setSeverity(sev)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
                        isSelected
                          ? 'border-indigo-500 bg-indigo-600/30 text-white font-bold ring-1 ring-indigo-500'
                          : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <SeverityBadge severity={sev} />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-800/80">
              <button
                onClick={handleReset}
                disabled={isResetting || isInjecting || isRecovering}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono font-medium rounded-lg border border-slate-700 transition-colors disabled:opacity-50 flex items-center space-x-1.5"
              >
                <span>{isResetting ? '🔄' : '✨'}</span>
                <span>{isResetting ? 'Resetting...' : 'Reset Target Resource'}</span>
              </button>

              <button
                onClick={handleExecuteLifecycle}
                disabled={isInjecting || isRecovering || isResetting}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-mono font-bold rounded-lg shadow-lg shadow-rose-600/30 transition-colors disabled:opacity-50 flex items-center space-x-2"
              >
                <span>{isInjecting ? '💥' : '⚡'}</span>
                <span>
                  {isInjecting
                    ? 'Injecting Anomaly...'
                    : isRecovering
                    ? 'Self-Healing Active...'
                    : 'Trigger Failure Scenario'}
                </span>
              </button>
            </div>

            {errorMessage && (
              <div className="mt-4 p-3 bg-rose-950/40 border border-rose-500/50 rounded-lg text-xs font-mono text-rose-300">
                ⚠️ {errorMessage}
              </div>
            )}
          </Panel>
        </div>

        {/* Scenario Details & Execution Output (1 col) */}
        <div className="space-y-5">
          <Panel title="Scenario Architecture Blueprint" subtitle={selectedScenario.code}>
            <div className="space-y-3 text-xs font-mono">
              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-850">
                <div className="text-[10px] text-slate-400 uppercase mb-1">Target CloudWatch Metric</div>
                <div className="text-cyan-400 font-semibold">{selectedScenario.metric}</div>
              </div>

              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-850">
                <div className="text-[10px] text-slate-400 uppercase mb-1">Alarm Trigger Threshold</div>
                <div className="text-amber-400 font-semibold">{selectedScenario.alarmThreshold}</div>
              </div>

              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-850">
                <div className="text-[10px] text-slate-400 uppercase mb-1">Automated Recovery Strategy</div>
                <div className="text-emerald-400 font-semibold">{selectedScenario.recoveryStrategy}</div>
              </div>
            </div>
          </Panel>

          {/* Execution Result Card */}
          {lastResult && (
            <Panel title="Simulator Output" subtitle="Recent API Execution">
              <div className="text-xs font-mono space-y-2">
                <div className="p-2.5 rounded bg-emerald-950/30 border border-emerald-500/30 text-emerald-300 font-medium">
                  ✓ {lastResult.message}
                </div>

                {(createdIncidentId || lastResult.incident) && (
                  <div className="bg-slate-950 p-2.5 rounded border border-slate-850 space-y-1">
                    <div className="text-[10px] text-slate-400">Incident Created:</div>
                    <div className="text-cyan-400 font-bold truncate">
                      {createdIncidentId ||
                        lastResult.incident?.incident_id ||
                        lastResult.incident?.incidentId}
                    </div>
                    {onInspectIncident && (
                      <button
                        onClick={() =>
                          onInspectIncident(
                            createdIncidentId ||
                              lastResult.incident?.incident_id ||
                              lastResult.incident?.incidentId
                          )
                        }
                        className="mt-2 w-full py-1 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 border border-indigo-500/30 rounded text-center text-[11px] font-semibold"
                      >
                        Inspect Incident Lifecycle →
                      </button>
                    )}
                  </div>
                )}

                {lastResult.metrics_emitted && (
                  <div className="bg-slate-950 p-2.5 rounded border border-slate-850">
                    <div className="text-[10px] text-slate-400 mb-1">Metrics Emitted:</div>
                    <pre className="text-[10px] text-slate-300 overflow-x-auto">
                      {JSON.stringify(lastResult.metrics_emitted, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
};
