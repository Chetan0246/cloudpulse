# CloudPulse — System Requirements Specification (SRS)

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** Formal Requirements & Traceability Matrix  
**Version:** 1.0  

---

## 1. Functional Requirements (FR)

### FR-01: Virtual Resource Management
- **Description:** The system shall maintain state and telemetry for a fleet of simulated virtual cloud resources persisted in DynamoDB (`cloudpulse-resources-{env}`).
- **Specification:** Track 4 canonical seed resources (`VM-001` [VM], `API-001` [API], `DB-001` [DB], `STORAGE-001` [STORAGE]). Each resource item tracks 10 attributes: `resource_id`, `resource_type`, `current_state`, `health_status`, `active_failure_type`, `cpu_utilization`, `memory_utilization`, `storage_utilization`, `network_latency_ms`, and `last_heartbeat`.
- **Traceability:** `backend/app/models/resource.py`, `backend/app/repositories/resource_repository.py`, `scripts/seed_data.py`.

### FR-02: Failure Simulation Engine
- **Description:** The system shall provide an API endpoint to inject 5 distinct failure scenarios deterministically.
- **Specification:**
  - **FS-01 (High CPU):** CPU = 98.0%, Memory = 85.0%
  - **FS-02 (Service Failure):** Network Latency = 1200.0 ms, CPU = 10.0%
  - **FS-03 (Storage Exhaustion):** Storage = 96.0%
  - **FS-04 (Network Latency):** Network Latency = 1500.0 ms
  - **FS-05 (Service Downtime):** CPU = 0.0%, Latency = 5000.0 ms
- **Traceability:** `backend/app/routers/simulate.py`, `backend/app/services/simulation_service.py`, `tests/simulation/test_simulation_layer.py`.

### FR-03: CloudWatch Telemetry & Custom Metrics
- **Description:** The system shall publish 5 custom CloudWatch metrics per resource: `CPUUtilization`, `MemoryUtilization`, `StorageUtilization`, `NetworkLatency`, and composite `ServiceHealth`.
- **Specification:** Metrics are batched in a single `PutMetricData` call under the `CloudPulse` namespace with `ResourceId` and `ResourceType` dimensions.
- **Traceability:** `backend/app/services/monitoring_service.py`, `lambda/simulator/handler.py`.

### FR-04: Metric Anomaly Detection & Alarms
- **Description:** CloudWatch metric alarms shall evaluate resource telemetry and transition to `ALARM` upon threshold breaches.
- **Specification:** Evaluates 2 consecutive 1-minute periods ( \ge 2$). CPU alarm threshold: $\ge 85\%$; Latency: $\ge 500	ext{ ms}$; Storage: $\ge 90\%$; Composite ServiceHealth: $\le 50.0$.
- **Traceability:** `infrastructure/template.yaml` (Resources: `VM001CpuAlarm`, `VM001LatencyAlarm`, etc.).

### FR-05: Autonomous Event Routing (EventBridge)
- **Description:** Amazon EventBridge shall ingest alarm state changes and simulation events, routing them to the Recovery Lambda.
- **Specification:** Rule `cloudpulse-alarm-rule` matches `source: [aws.cloudwatch]`, `detail-type: [CloudWatch Alarm State Change]`, and state `ALARM` (excluding `-SERVICE_HEALTH` composite alarms). Rule `DirectSimulatorEvent` matches `source: [cloudpulse.simulator]`.
- **Traceability:** `infrastructure/template.yaml` (EventBridge rules on `RecoveryFunction`).

### FR-06: Autonomous Recovery Engine
- **Description:** The Recovery Lambda shall execute deterministic remediation strategies mapped to the detected failure type.
- **Specification:**
  - `HIGH_CPU` $\longrightarrow$ `SCALE_OUT` (resets CPU=25.0%, Memory=30.0%)
  - `SERVICE_FAILURE` $\longrightarrow$ `SERVICE_RESTART` (resets Latency=15.0 ms, CPU=25.0%)
  - `STORAGE_EXHAUSTION` $\longrightarrow$ `STORAGE_CLEANUP` (resets Storage=20.0%)
  - `NETWORK_LATENCY` $\longrightarrow$ `NETWORK_REROUTE` (resets Latency=15.0 ms)
  - `SERVICE_DOWNTIME` $\longrightarrow$ `FAILOVER` (resets all 4 metrics)
- **Traceability:** `lambda/recovery/handler.py`, `lambda/recovery/strategies.py`.

### FR-07: Incident Lifecycle Management
- **Description:** All incidents shall persist a complete 14-field lifecycle in DynamoDB (`cloudpulse-incidents-{env}`).
- **Specification:** Fields: `incident_id`, `resource_id`, `failure_type`, `severity`, `status` (`OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`), `created_at`, `detected_at`, `recovery_started_at`, `recovered_at`, `recovery_action`, `recovery_result`, `notification_status`, `retry_count`, and `error_message`. Embedded list of `RecoveryAction` objects.
- **Traceability:** `backend/app/models/incident.py`, `backend/app/repositories/incident_repository.py`.

### FR-08: Alerting & SNS Notifications
- **Description:** The system shall publish human-readable notifications to Amazon SNS for key lifecycle transitions.
- **Specification:** Triggers on: 1) Failure Detected, 2) Recovery Started, 3) Recovery Successful, 4) Recovery Failed. Enforces duplicate suppression via `notified_transitions` array.
- **Traceability:** `backend/app/services/notification_service.py`, `tests/notification/test_notification_layer.py`.

### FR-09: SRE Reliability Analytics
- **Description:** The system shall calculate and expose 8 standard SRE metrics derived strictly from stored records.
- **Specification:** Exposes Incident Count, Recovery Success Rate, Recovery Failure Rate, MTTR, MTBF, Average Detection Time, and Incident Frequency.
- **Traceability:** `backend/app/services/reliability_calculator.py`, `backend/app/routers/metrics.py`.

### FR-10: Operator Dashboard UI
- **Description:** The system shall provide a responsive, real-time React web application.
- **Specification:** 9 primary views: Overview, Resource Health, Failure Simulator, Active Incidents, Incident Details, Recovery Activity, Reliability Metrics, Architecture View, and System Events.
- **Traceability:** `frontend/src/App.tsx`, `frontend/src/components/sections/*`.

---

## 2. Non-Functional Requirements (NFR)

| ID | Category | Requirement Specification | Verification |
|---|---|---|---|
| **NFR-01** | **Simulation Safety** | Zero AWS API calls shall terminate or modify real EC2/RDS/VPC resources. | IAM audit + code review |
| **NFR-02** | **Idempotency** | Duplicate events received within any window shall not cause duplicate recovery executions. | Pytest idempotency tests |
| **NFR-03** | **Cost Containment** | Monthly cloud infrastructure spend shall not exceed .00 under Free Tier usage. | Cost audit (`COST_MANAGEMENT.md`) |
| **NFR-04** | **Least Privilege** | Each Lambda role shall strictly allow only specific DynamoDB tables, SNS topics, and namespaces. | SAM template IAM policy check |
| **NFR-05** | **Traceability** | All log entries shall be structured JSON with propagated `correlation_id` and `incident_id`. | CloudWatch log formatter check |
| **NFR-06** | **Test Reliability** | 100% of backend tests shall run deterministically in isolated mock environments without external calls. | 367 backend tests pass in ~9.4s |
| **NFR-07** | **UI Responsiveness** | Dashboard shall adaptively poll (3s during active incidents, 10s idle, 30s background). | Verified in Dashboard component |
| **NFR-08** | **Reproducibility** | Entire stack deployable via a single `sam deploy` command. | `infrastructure/template.yaml` validation |
