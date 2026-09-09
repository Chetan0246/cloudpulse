import React, { useState } from 'react';
import type { IncidentSummary, ResourceSummary } from '../../api/types';
import { Panel } from '../common/Card';

interface ArchitectureViewSectionProps {
  resources: ResourceSummary[];
  incidents: IncidentSummary[];
}

interface NodeDetail {
  id: string;
  name: string;
  category: string;
  icon: string;
  status: string;
  role: string;
  technicalSpecs: { [key: string]: string };
  responsibilities: string[];
}

export const ArchitectureViewSection: React.FC<ArchitectureViewSectionProps> = ({
  resources,
  incidents,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>('lambda');

  const activeIncidents = incidents.filter(
    (i) => i.status === 'OPEN' || i.status === 'RECOVERING'
  );
  const isAlarmFiring = activeIncidents.length > 0;
  const isLambdaActive = incidents.some((i) => i.status === 'RECOVERING');

  const nodes: NodeDetail[] = [
    {
      id: 'resource',
      name: 'Virtual Infrastructure Fleet',
      category: 'Simulated Environment',
      icon: '🖥️',
      status: `${resources.length} active resources`,
      role: 'Simulates heterogeneous cloud infrastructure (EC2, ECS, Aurora DB, S3 Storage) with live metric telemetry.',
      technicalSpecs: {
        'Fleet Size': `${resources.length} virtual resources`,
        'Resource Types': 'VM, API, DB, STORAGE',
        'Telemetry Loop': 'Continuous background emission (CPU, Latency, Storage, Health)',
        'Fault Types Supported': 'FS-01 to FS-05',
      },
      responsibilities: [
        'Maintains deterministic in-memory resource health and metric states',
        'Responds to chaos injection scenarios with metric deviations',
        'Accepts state resets and recovery mutations from the Lambda engine',
      ],
    },
    {
      id: 'cloudwatch-metric',
      name: 'CloudWatch Custom Metrics',
      category: 'Observability Layer',
      icon: '📊',
      status: 'Namespace: CloudPulse/SimulatedFleet',
      role: 'Receives and aggregates custom high-resolution telemetry emitted by simulated workloads.',
      technicalSpecs: {
        Namespace: 'CloudPulse/SimulatedFleet',
        Dimensions: 'ResourceId, ResourceType, Environment',
        Resolution: 'Standard (60s) / High-resolution (10s)',
        UnitTypes: 'Percent, Milliseconds, Count',
      },
      responsibilities: [
        'Collects CPUUtilization, StorageUtilization, NetworkLatency, and ServiceHealth',
        'Buffers historical telemetry datapoints for anomaly trend analysis',
        'Provides real-time metric streams to CloudWatch Alarm evaluators',
      ],
    },
    {
      id: 'alarm',
      name: 'CloudWatch Alarms',
      category: 'Detection Mechanism',
      icon: '🔔',
      status: isAlarmFiring ? 'TRIGGERED (ALARM)' : 'NOMINAL (OK)',
      role: 'Monitors custom metrics against strict SRE thresholds to deterministically detect infrastructure failure.',
      technicalSpecs: {
        'Evaluation Periods': '2 consecutive evaluation intervals (avoid flap)',
        'CPU Threshold': 'CPUUtilization > 85.0%',
        'Latency Threshold': 'NetworkLatency > 100.0ms',
        'Storage Threshold': 'StorageUtilization > 85.0%',
        'Service Threshold': 'ServiceHealth == 0 (CRITICAL)',
      },
      responsibilities: [
        'Evaluates rolling telemetry windows against threshold boundaries',
        'Transitions state from OK → ALARM upon sustained fault detection',
        'Publishes state change events to Amazon EventBridge default event bus',
      ],
    },
    {
      id: 'eventbridge',
      name: 'Amazon EventBridge',
      category: 'Event Routing Bus',
      icon: '⚡',
      status: 'Active Event Bus',
      role: 'Decouples monitoring detection from remediation execution via pattern-based rule dispatching.',
      technicalSpecs: {
        EventBus: 'default',
        SourcePattern: 'aws.cloudwatch',
        DetailType: 'CloudWatch Alarm State Change',
        Target: 'Recovery Lambda Function (ARN targeted)',
        DeadLetterQueue: 'Optional SQS fallback for unrouted events',
      },
      responsibilities: [
        'Filters alarm events matching CloudPulse naming convention',
        'Parses resource ID and failure type tokens from alarm metadata',
        'Invokes Recovery Lambda asynchronously with full alarm context',
      ],
    },
    {
      id: 'lambda',
      name: 'Self-Healing Recovery Lambda',
      category: 'Remediation Engine',
      icon: '🛠️',
      status: isLambdaActive ? 'EXECUTING STRATEGY' : 'IDLE / LISTENING',
      role: 'Serverless orchestrator executing automated recovery strategies without human intervention.',
      technicalSpecs: {
        Runtime: 'Python 3.12 (AWS Lambda)',
        Idempotency: 'Pre-read state guard protects against duplicate triggers',
        'Max Retries': '3 recovery attempts before escalating to MANUAL',
        Strategies: 'SCALE_OUT, SERVICE_RESTART, STORAGE_CLEANUP, NETWORK_REROUTE, FAILOVER',
      },
      responsibilities: [
        'Dispatches tailored recovery strategy based on detected failure scenario',
        'Mutates virtual resource state from FAILURE_DETECTED → RECOVERED',
        'Records recovery execution duration and updates incident repository in DynamoDB',
      ],
    },
    {
      id: 'dynamo-sns',
      name: 'DynamoDB & SNS Alerts',
      category: 'State Persistence & Alerting',
      icon: '📬',
      status: 'Synchronized',
      role: 'Persists 14-field incident lifecycle records and broadcasts SRE notifications via Amazon SNS.',
      technicalSpecs: {
        StateTable: 'cloudpulse-incidents (DynamoDB)',
        NotificationTopic: 'cloudpulse-incident-notifications (SNS)',
        DeliveryChannels: 'Email, PagerDuty, Slack Webhook',
        NotifiedTransitions: '4 key transitions (Detection, Start, Success, Failure)',
      },
      responsibilities: [
        'Maintains immutable audit trail of incident start, attempts, and resolution',
        'Suppresses duplicate notifications using state transition hashing',
        'Delivers human-readable remediation notifications to on-call engineers',
      ],
    },
  ];

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || nodes[4];

  return (
    <div className="space-y-6">
      {/* Introduction Banner */}
      <div className="bg-slate-900/80 p-5 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono flex items-center space-x-2">
            <span>🗺️</span>
            <span>Closed-Loop Self-Healing Architecture Map</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Interactive visualization of the end-to-end event-driven loop. Click any node in the
            circuit to view technical specifications, trigger conditions, and component responsibilities.
          </p>
        </div>

        <div className="flex items-center space-x-2 font-mono text-xs">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-emerald-400 font-semibold">Circuit Active</span>
        </div>
      </div>

      {/* Interactive Topology Graph */}
      <div className="bg-slate-950 p-6 rounded-xl border border-slate-850 overflow-x-auto">
        <div className="min-w-[850px] flex items-center justify-between relative py-6">
          {/* Connecting Line */}
          <div className="absolute top-1/2 left-8 right-8 h-1 bg-slate-800 -translate-y-1/2 z-0" />
          {/* Pulsing data flow beam */}
          <div
            className={`absolute top-1/2 left-8 right-8 h-1 -translate-y-1/2 z-0 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-60 ${
              isAlarmFiring ? 'animate-pulse' : ''
            }`}
          />

          {nodes.map((node, index) => {
            const isSelected = selectedNodeId === node.id;
            let nodeGlow = 'border-slate-750 bg-slate-900';
            if (isSelected) {
              nodeGlow = 'border-indigo-500 bg-indigo-950/70 ring-2 ring-indigo-500';
            } else if (node.id === 'alarm' && isAlarmFiring) {
              nodeGlow = 'border-rose-500 bg-rose-950/60 ring-2 ring-rose-500 animate-pulse';
            } else if (node.id === 'lambda' && isLambdaActive) {
              nodeGlow = 'border-cyan-500 bg-cyan-950/60 ring-2 ring-cyan-500 animate-pulse';
            }

            return (
              <div key={node.id} className="relative z-10 flex flex-col items-center">
                <button
                  onClick={() => setSelectedNodeId(node.id)}
                  className={`w-16 h-16 rounded-2xl border-2 flex items-center justify-center text-2xl shadow-xl transition-all transform hover:scale-105 ${nodeGlow}`}
                >
                  <span>{node.icon}</span>
                </button>

                <div className="text-center mt-3 max-w-[120px]">
                  <div className="text-[11px] font-mono font-bold text-slate-200 truncate">
                    {node.name}
                  </div>
                  <div className="text-[9px] font-mono text-slate-500 uppercase mt-0.5">
                    Step {index + 1}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Feedback loop return arrow */}
        <div className="mt-4 pt-3 border-t border-slate-900 flex items-center justify-center space-x-2 text-xs font-mono text-cyan-400/80">
          <span>↺ Automated Feedback Loop: Recovery Lambda mutates Resource State back to Nominal</span>
        </div>
      </div>

      {/* Selected Node Deep Dive Specs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <Panel
            title={selectedNode.name}
            subtitle={selectedNode.category}
            badge={
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                {selectedNode.status}
              </span>
            }
          >
            <p className="text-xs text-slate-300 font-mono mb-4 leading-relaxed bg-slate-950/70 p-3 rounded-lg border border-slate-850">
              {selectedNode.role}
            </p>

            <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
              Primary Responsibilities
            </h4>
            <ul className="space-y-1.5 mb-5 text-xs font-mono text-slate-300">
              {selectedNode.responsibilities.map((r, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>

            <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
              Technical Configuration & Contracts
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              {Object.entries(selectedNode.technicalSpecs).map(([key, value]) => (
                <div key={key} className="bg-slate-950 p-2.5 rounded-lg border border-slate-850">
                  <div className="text-[10px] text-slate-500 uppercase">{key}</div>
                  <div className="text-cyan-400 font-semibold mt-0.5 truncate">{value}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Live Closed-Loop Status Panel */}
        <div>
          <Panel title="Circuit Operational Status" subtitle="Live state across all nodes">
            <div className="space-y-3 text-xs font-mono">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 flex items-center justify-between">
                <span className="text-slate-400">Resources Monitored:</span>
                <span className="text-slate-100 font-bold">{resources.length} Nodes</span>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 flex items-center justify-between">
                <span className="text-slate-400">Alarms Triggered:</span>
                <span
                  className={`font-bold ${
                    isAlarmFiring ? 'text-rose-400 animate-pulse' : 'text-emerald-400'
                  }`}
                >
                  {activeIncidents.length} Alarms Active
                </span>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 flex items-center justify-between">
                <span className="text-slate-400">Recovery Lambda:</span>
                <span className={`font-bold ${isLambdaActive ? 'text-cyan-400' : 'text-slate-300'}`}>
                  {isLambdaActive ? 'Processing Event' : 'Standby / Ready'}
                </span>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 flex items-center justify-between">
                <span className="text-slate-400">SNS Alert Channel:</span>
                <span className="text-emerald-400 font-bold">Enabled (EMAIL/TOPIC)</span>
              </div>

              <div className="mt-4 p-3 rounded-lg bg-indigo-950/20 border border-indigo-800/40 text-[11px] text-indigo-300 leading-relaxed">
                ℹ️ The entire cycle executes deterministically under 10 seconds without human intervention.
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
};
