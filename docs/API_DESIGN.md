# CloudPulse — REST API Specification & Reference

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** API Design Reference  
**Version:** 1.0  
**Status:** Implemented in FastAPI & Verified  

---

## 1. Overview & General Conventions

The CloudPulse API provides the operational interface between the React SRE dashboard, automation scripts, and the serverless backend.

- **Base URL (Local Development):** `http://localhost:8000`
- **Base URL (AWS Deployed):** `https://{ApiId}.execute-api.ap-south-1.amazonaws.com`
- **Content Negotiation:** All requests and responses use `Content-Type: application/json`.
- **Authentication:** Public (Unauthenticated) by design for student and academic demonstration purposes.
- **CORS Configuration:** Defaults to `http://localhost:5173` (Vite dev server) and the deployed S3 website endpoint; methods restricted to `GET`, `POST`, and `OPTIONS`.
- **Naming Conventions:** Ingress payloads accept both `snake_case` and `camelCase` identifiers (via Pydantic `populate_by_name=True`). Outgoing responses provide snake_case model fields alongside camelCase computed properties for seamless TypeScript consumption.

---

## 2. API Endpoints Catalog

### 2.1 System Health Probes

#### `GET /health`
- **Summary:** Liveness probe verifying that the FastAPI application and runtime are responsive.
- **Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "cloudpulse-api",
  "version": "0.1.0",
  "environment": "dev"
}
```

#### `GET /health/ready`
- **Summary:** Readiness probe checking database connectivity and table accessibility.
- **Response (200 OK):**
```json
{
  "status": "ready",
  "service": "cloudpulse-api",
  "database": "connected"
}
```

---

### 2.2 Virtual Resources API

#### `GET /resources`
- **Summary:** List lightweight summaries for all virtual resources in the fleet.
- **Response (200 OK):**
```json
[
  {
    "resource_id": "VM-001",
    "resource_type": "VM",
    "current_state": "HEALTHY",
    "health_status": "HEALTHY",
    "active_failure_type": null,
    "last_heartbeat": "2026-09-09T14:30:00Z",
    "cpu_utilization": 25.0,
    "memory_utilization": 30.0,
    "storage_utilization": 40.0,
    "network_latency_ms": 10.0
  },
  {
    "resource_id": "API-001",
    "resource_type": "API",
    "current_state": "HEALTHY",
    "health_status": "HEALTHY",
    "active_failure_type": null,
    "last_heartbeat": "2026-09-09T14:30:00Z",
    "cpu_utilization": 30.0,
    "memory_utilization": 35.0,
    "storage_utilization": 20.0,
    "network_latency_ms": 15.0
  }
]
```

#### `GET /resources/{resource_id}`
- **Summary:** Retrieve full state and detailed telemetry for a single resource.
- **Parameters:** `resource_id` (Path, required) — e.g. `VM-001`.
- **Response (200 OK):**
```json
{
  "resource_id": "VM-001",
  "resource_type": "VM",
  "description": "Primary Application Compute Node",
  "current_state": "HEALTHY",
  "health_status": "HEALTHY",
  "active_failure_type": null,
  "cpu_utilization": 25.0,
  "memory_utilization": 30.0,
  "storage_utilization": 40.0,
  "network_latency_ms": 10.0,
  "last_heartbeat": "2026-09-09T14:30:00Z",
  "created_at": "2026-09-08T10:00:00Z",
  "updated_at": "2026-09-09T14:30:00Z"
}
```

---

### 2.3 Incidents API

#### `GET /incidents`
- **Summary:** Query incident records sorted newest first with optional filtering.
- **Query Parameters:**
  - `resource_id` (string, optional): Filter by resource, e.g. `VM-001`.
  - `status` (string, optional): Filter by lifecycle status (`OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`).
  - `failure_type` (string, optional): Filter by failure type.
  - `limit` (integer, optional, default: 50, max: 200).
- **Response (200 OK):**
```json
[
  {
    "incident_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "resource_id": "VM-001",
    "failure_type": "HIGH_CPU",
    "severity": "HIGH",
    "status": "RESOLVED",
    "created_at": "2026-09-09T14:00:00Z",
    "detected_at": "2026-09-09T14:00:00Z",
    "recovery_started_at": "2026-09-09T14:00:02Z",
    "recovered_at": "2026-09-09T14:00:05Z",
    "resolved_at": "2026-09-09T14:00:05Z",
    "duration_seconds": 3.24,
    "recovery_action": "SCALE_OUT",
    "recovery_result": "Simulated scale-out: increased virtual CPU allocation",
    "notification_status": "SENT",
    "retry_count": 0,
    "error_message": null
  }
]
```

#### `GET /incidents/{incident_id}`
- **Summary:** Retrieve complete incident details including embedded remediation action audit log.
- **Parameters:** `incident_id` (Path, required) — UUID v4 format.
- **Response (200 OK):**
```json
{
  "incident_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "resource_id": "VM-001",
  "failure_type": "HIGH_CPU",
  "severity": "HIGH",
  "status": "RESOLVED",
  "state_at_detection": "FAILURE_DETECTED",
  "state_at_resolution": "RECOVERED",
  "created_at": "2026-09-09T14:00:00Z",
  "detected_at": "2026-09-09T14:00:00Z",
  "recovery_started_at": "2026-09-09T14:00:02Z",
  "recovered_at": "2026-09-09T14:00:05Z",
  "resolved_at": "2026-09-09T14:00:05Z",
  "duration_seconds": 3.24,
  "recovery_action": "SCALE_OUT",
  "recovery_result": "Simulated scale-out: increased virtual CPU allocation",
  "recovery_attempts": 1,
  "recovery_actions": [
    {
      "action_id": "c71d2e1b-9a4f-4d9a-9e1e-2c8e3f4b5a6c",
      "action_type": "SCALE_OUT",
      "status": "SUCCEEDED",
      "started_at": "2026-09-09T14:00:02Z",
      "completed_at": "2026-09-09T14:00:05Z",
      "outcome_message": "Simulated scale-out: increased virtual CPU allocation",
      "error_detail": null
    }
  ],
  "notification_status": "SENT",
  "notified_transitions": [
    "FAILURE_DETECTED",
    "RECOVERY_STARTED",
    "RECOVERY_SUCCESSFUL"
  ]
}
```

---

### 2.4 Reliability Metrics API

#### `GET /metrics/overview`
- **Summary:** Return all 8 core SRE reliability indicators computed directly from stored DynamoDB records.
- **Query Parameters:** `window_type` (string, optional, default: `DAILY`).
- **Response (200 OK):**
```json
{
  "incident_count": 14,
  "recovery_success_rate_pct": 92.86,
  "recovery_failure_rate_pct": 7.14,
  "avg_recovery_time_seconds": 3.42,
  "mttr_seconds": 3.42,
  "avg_detection_time_seconds": 1.20,
  "incident_frequency_per_hour": 0.58,
  "incident_frequency_per_day": 14.0,
  "mtbf_seconds": 6171.43,
  "health_distribution": {
    "total_resources": 4,
    "healthy_count": 4,
    "warning_count": 0,
    "failed_count": 0,
    "recovering_count": 0,
    "healthy_pct": 100.0,
    "by_state": {
      "HEALTHY": 4,
      "WARNING": 0,
      "FAILURE_DETECTED": 0,
      "RECOVERED": 0
    },
    "by_status": {
      "HEALTHY": 4,
      "DEGRADED": 0,
      "CRITICAL": 0
    }
  },
  "computed_at": "2026-09-09T14:35:00Z"
}
```

---

### 2.5 Failure Simulation API

#### `POST /simulate/failure`
- **Summary:** Inject a simulated failure scenario onto a target virtual resource.
- **Request Body:**
```json
{
  "resource_id": "VM-001",
  "failure_type": "FS-01",
  "severity": "HIGH"
}
```
*(Note: `failure_type` accepts scenario codes like `"FS-01"` or standard enum keys like `"HIGH_CPU"`).*
- **Response (201 Created):**
```json
{
  "message": "Simulated failure 'FS-01 High CPU Utilization' successfully injected into VM-001",
  "scenario_id": "FS-01",
  "scenario_name": "FS-01 High CPU Utilization",
  "resource": {
    "resource_id": "VM-001",
    "current_state": "FAILURE_DETECTED",
    "health_status": "CRITICAL",
    "active_failure_type": "HIGH_CPU",
    "cpu_utilization": 98.0,
    "memory_utilization": 85.0
  },
  "incident": {
    "incident_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "resource_id": "VM-001",
    "failure_type": "HIGH_CPU",
    "severity": "HIGH",
    "status": "OPEN",
    "detected_at": "2026-09-09T14:40:00Z"
  },
  "metrics_emitted": {
    "CPUUtilization": 98.0,
    "MemoryUtilization": 85.0,
    "StorageUtilization": 40.0,
    "NetworkLatency": 10.0,
    "ServiceHealth": 12.5
  }
}
```

#### `POST /simulate/reset/{resource_id}`
- **Summary:** Manually reset a degraded resource back to nominal operating health.
- **Response (200 OK):**
```json
{
  "message": "Resource VM-001 has been reset to HEALTHY.",
  "resource": {
    "resource_id": "VM-001",
    "current_state": "HEALTHY",
    "health_status": "HEALTHY",
    "cpu_utilization": 25.0,
    "memory_utilization": 30.0,
    "storage_utilization": 40.0,
    "network_latency_ms": 10.0
  },
  "resolved_incidents": [
    "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  ]
}
```

---

## 3. Standardized Error Responses

All errors conform to a standard schema mapped via FastAPI global exception handlers:

```json
{
  "detail": "Descriptive human-readable error message",
  "error_code": "RESOURCE_NOT_FOUND"
}
```

| HTTP Status | Error Code | Trigger Condition |
|---|---|---|
| **404 Not Found** | `RESOURCE_NOT_FOUND` | Requested `resource_id` does not exist in DynamoDB. |
| **404 Not Found** | `INCIDENT_NOT_FOUND` | Requested `incident_id` does not exist. |
| **409 Conflict** | `INVALID_STATE_TRANSITION` | Attempted to inject failure on a resource already in failure/recovering state. |
| **422 Unprocessable** | `VALIDATION_ERROR` | Schema validation error (e.g. malformed UUID, invalid enum string). |
| **500 Internal Server** | `DATABASE_ERROR` | DynamoDB or AWS SDK communication failure. |
