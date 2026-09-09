/**
 * TypeScript types mirroring the backend Pydantic models.
 * Keep in sync with backend/app/models/*.py
 */

export type ResourceType = 'VM' | 'API' | 'DB' | 'STORAGE';

export type ResourceState =
  | 'HEALTHY'
  | 'WARNING'
  | 'FAILURE_DETECTED'
  | 'RECOVERY_INITIATED'
  | 'RECOVERY_IN_PROGRESS'
  | 'RECOVERED'
  | 'RECOVERY_FAILED'
  | 'MANUAL_INTERVENTION_REQUIRED';

export type HealthStatus = 'HEALTHY' | 'DEGRADED' | 'CRITICAL';

export type FailureType =
  | 'HIGH_CPU'
  | 'SERVICE_FAILURE'
  | 'STORAGE_EXHAUSTION'
  | 'NETWORK_LATENCY'
  | 'SERVICE_DOWNTIME';

export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type IncidentStatus = 'OPEN' | 'RECOVERING' | 'RESOLVED' | 'ESCALATED';

export interface ResourceSummary {
  resource_id: string;
  resource_type: ResourceType;
  current_state: ResourceState;
  health_status: HealthStatus;
  active_failure_type: FailureType | null;
  last_heartbeat: string; // ISO8601
  cpu_utilization?: number;
  memory_utilization?: number;
  storage_utilization?: number;
  network_latency_ms?: number;
}

export interface Resource extends ResourceSummary {
  cpu_utilization: number;
  memory_utilization: number;
  storage_utilization: number;
  network_latency_ms: number;
  updated_at: string; // ISO8601
}

export interface IncidentSummary {
  incident_id: string;
  incidentId?: string;
  resource_id: string;
  resourceId?: string;
  failure_type: FailureType;
  failureType?: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  created_at?: string;
  createdAt?: string;
  detected_at: string; // ISO8601
  detectedAt?: string;
  recovery_started_at?: string | null;
  recoveryStartedAt?: string | null;
  recovered_at?: string | null;
  recoveredAt?: string | null;
  resolved_at: string | null;
  escalated_at?: string | null;
  duration_seconds?: number | null;
  recovery_action?: string | null;
  recoveryAction?: string | null;
  recovery_result?: string | null;
  recoveryResult?: string | null;
  notification_status?: string;
  notificationStatus?: string;
  notification_sent?: boolean;
  retry_count?: number;
  retryCount?: number;
  recovery_attempts?: number;
  error_message?: string | null;
  errorMessage?: string | null;
}

export interface Incident extends IncidentSummary {
  state_at_detection: ResourceState;
  state_at_resolution: ResourceState | null;
  recovery_initiated_at: string | null;
  recovery_attempts: number;
  recovery_actions?: Array<{
    action_id: string;
    action_type: string;
    status: string;
    started_at: string;
    completed_at?: string | null;
    outcome_message: string;
    error_detail?: string | null;
  }>;
  recovery_notes: string[];
  notification_sent: boolean;
  notified_transitions?: string[];
}

export interface InjectRequest {
  resource_id: string;
  failure_type: FailureType;
}

export interface SimulateResponse {
  message: string;
  resource: Resource;
}

export interface ReliabilityMetric {
  resource_id: string;
  window_key: string;
  window_type: 'DAILY' | 'WEEKLY' | 'CUMULATIVE';
  window_start: string;
  window_end: string;
  total_incidents: number;
  resolved_incidents: number;
  failed_recoveries: number;
  mttr_seconds: number | null;
  mtbf_seconds: number | null;
  availability_pct: number | null;
  failure_type_counts: Record<string, number>;
}

