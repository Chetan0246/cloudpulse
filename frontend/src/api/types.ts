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
  resource_id: string;
  failure_type: FailureType;
  severity: IncidentSeverity;
  status: IncidentStatus;
  detected_at: string; // ISO8601
  resolved_at: string | null;
}

export interface Incident extends IncidentSummary {
  state_at_detection: ResourceState;
  state_at_resolution: ResourceState | null;
  recovery_initiated_at: string | null;
  recovery_attempts: number;
  recovery_notes: string[];
  notification_sent: boolean;
}

export interface InjectRequest {
  resource_id: string;
  failure_type: FailureType;
}

export interface SimulateResponse {
  message: string;
  resource: Resource;
}
