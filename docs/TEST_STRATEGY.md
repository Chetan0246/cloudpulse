# CloudPulse Comprehensive QA & Reliability Testing Strategy

> **Role**: Senior QA & Reliability Engineer  
> **System Under Test**: CloudPulse Autonomous Self-Healing Infrastructure  
> **Document Version**: 1.0.0  
> **Status**: Approved & Verified  

---

## 1. Executive Summary & Quality Objectives

CloudPulse is an autonomous, event-driven self-healing system designed to detect infrastructure degradations, trigger event-based remediation workflows via Amazon EventBridge, execute deterministic recovery strategies, update incident audit trails in DynamoDB, and notify operations teams via SNS.

Because CloudPulse orchestrates infrastructure reliability, **the testing framework itself must exhibit exceptional rigor, determinism, and safety**.

### Core Quality Principles
1. **Zero Destructive AWS Operations**: All tests execute strictly against hermetic, in-memory local mock environments using `moto` and pytest test harnesses. No live AWS resources are mutated, destroyed, or provisioned during test execution.
2. **100% Determinism**: Metric values, threshold crossings, and recovery state transitions are deterministic to eliminate flakiness and guarantee reproducible CI/CD verification.
3. **Full Closed-Loop Verification**: Every failure scenario must be verified through the complete 9-step closed-loop lifecycle from injection to dashboard reflection.
4. **Resilience to Partial Failures**: Monitoring or notification component outages (e.g. CloudWatch or SNS downtime) must never compromise core state persistence or recovery audit trails.

---

## 2. The 9 Testing Layers

CloudPulse employs a layered testing pyramid designed for maximum isolation, fast feedback, and full end-to-end confidence:

```
                      ┌─────────────────────────┐
                      │    Layer 9: End-to-End  │  (Complete closed loop)
                      ├─────────────────────────┤
                      │ Layer 8: Notification   │  (SNS dispatch & dedup)
                      ├─────────────────────────┤
                      │ Layer 7: Recovery       │  (Strategies & dispatch)
                      ├─────────────────────────┤
                      │ Layer 6: EventBridge    │  (Decomposition & route)
                      ├─────────────────────────┤
                      │ Layer 5: Failure Sim    │  (Threshold breaches)
                      ├─────────────────────────┤
                      │ Layer 4: AWS Integrat.  │  (Moto SDK behavior)
                      ├─────────────────────────┤
                      │ Layer 3: Integration    │  (Service <-> Repo)
                      ├─────────────────────────┤
                      │ Layer 2: API            │  (FastAPI endpoints)
                      ├─────────────────────────┤
                      │ Layer 1: Unit           │  (Domain models & math)
                      └─────────────────────────┘
```

### Layer 1: Unit Testing (`tests/unit/`)
* **Focus**: Pure domain models, Pydantic field validators, DynamoDB item serialization/deserialization, and mathematical scoring algorithms.
* **Key Invariants Verified**:
  - `SimulatedResource`: Strict metric bounds ($0.0 \le \text{utilization} \le 100.0$, $\text{latency} \ge 0.0$).
  - `Incident`: Complete 14-field schema integrity; invariant constraint: `recovery_attempts == len(recovery_actions)`.
  - `ReliabilityMetric`: Daily, weekly, and cumulative sort keys (`build_window_key`, `parse_window_key`).
  - `compute_service_health`: Composite multi-factor weighted health calculation ($100.0$ nominal, decaying proportionally under stress).

### Layer 2: API Testing (`tests/api/`)
* **Focus**: RESTful HTTP API contract validation using FastAPI `TestClient`.
* **Endpoints Verified**:
  - `GET /health`: Component status reporting (`healthy`, `degraded`).
  - `GET /resources`, `GET /resources/{id}`: Resource fleet listing and single-resource lookup.
  - `GET /incidents`, `GET /incidents/{id}`: Incident pagination and detailed audit trail retrieval.
  - `GET /metrics`: Metric window filtering (`DAILY`, `WEEKLY`, `CUMULATIVE`).
  - `POST /simulate/failure`: Valid failure injection (201 Created), validation errors (422), unknown resource (404).
  - `POST /simulate/recover`, `POST /simulate/reset/{id}`: Manual recovery and fleet baseline reset.

### Layer 3: Integration Testing (`tests/integration/`)
* **Focus**: Collaboration between domain services (`ResourceService`, `IncidentService`, `MetricService`, `SimulationService`) and underlying DynamoDB repositories.
* **Key Behaviors Verified**:
  - Filtering incidents by status (`OPEN`, `RESOLVED`, `ESCALATED`) and `resource_id`.
  - Multi-window reliability metric persistence and latest snapshot retrieval.
  - Multi-repository orchestration during state transitions.

### Layer 4: AWS Integration Testing (`tests/aws_integration/`)
* **Focus**: AWS SDK (`boto3`) interaction fidelity against moto-mocked AWS services.
* **Capabilities Verified**:
  - CloudWatch `PutMetricData`: Custom namespace and multi-dimensional metric batches.
  - DynamoDB Conditional Expressions: Atomic state locking (`current_state = :expected`).
  - SNS `Publish`: Topic publishing and message formatting.
  - EventBridge `PutEvents`: Custom event bus ingestion with `Detail` JSON payloads.
  - Client caching and singleton management across invocations.

### Layer 5: Failure Simulation Testing (`tests/simulation/`)
* **Focus**: Deterministic metric mutation and alarm threshold crossing for all simulated failure modes.
* **Key Behaviors Verified**:
  - Explicit metric target breaches for each failure type.
  - Custom parameter override handling.
  - Concurrent injection guards: Prevents triggering a failure on a resource already in `FAILURE_DETECTED`.

### Layer 6: EventBridge Flow Testing (`tests/eventbridge/`)
* **Focus**: Ingestion, schema validation, and routing of asynchronous EventBridge events.
* **Key Behaviors Verified**:
  - CloudWatch Alarm format parsing: Suffix-first parsing decomposing `cloudpulse-{ResourceId}-{FailureType}`.
  - Handles multi-hyphenated resource IDs (e.g. `STORAGE-001`).
  - Direct simulation event parsing (`source: cloudpulse.simulator`).
  - Malformed alarm name and unsupported source rejection.

### Layer 7: Recovery Testing (`tests/recovery/`)
* **Focus**: Recovery strategy dispatcher, execution handlers, and state machine transitions.
* **Key Behaviors Verified**:
  - Strategy mapping:
    * `HIGH_CPU` $\to$ `SCALE_OUT`
    * `SERVICE_FAILURE` $\to$ `SERVICE_RESTART`
    * `STORAGE_EXHAUSTION` $\to$ `STORAGE_CLEANUP`
    * `NETWORK_LATENCY` $\to$ `NETWORK_REROUTE`
    * `SERVICE_DOWNTIME` $\to$ `FAILOVER`
  - Lambda execution: Transitioning resource from `FAILURE_DETECTED` $\to$ `RECOVERY_INITIATED` $\to$ `RECOVERY_IN_PROGRESS` $\to$ `RECOVERED`.
  - Idempotency pre-read gate: Early return (200 OK) if resource is not in `FAILURE_DETECTED`.

### Layer 8: Notification Testing (`tests/notification/`)
* **Focus**: SNS notification templating, transition filters, and duplicate suppression.
* **Key Behaviors Verified**:
  - Formats human-readable alerts for 4 transitions:
    1. `FAILURE_DETECTED`
    2. `RECOVERY_STARTED`
    3. `RECOVERY_SUCCESSFUL`
    4. `RECOVERY_FAILED`
  - Required fields in notifications: Incident ID, Resource ID, Failure Type, Status, Recovery Duration.
  - Deduplication: `notified_transitions` tracking prevents duplicate emails for the same state.
  - Fault tolerance: SNS `ClientError` caught and logged without aborting caller execution.

### Layer 9: End-to-End Closed-Loop Testing (`tests/e2e/`)
* **Focus**: Complete automated closed loop verifying the full system from failure injection to dashboard REST response across all 5 scenarios.

---

## 3. Failure Scenario Matrix (FS-01 through FS-05)

| Scenario ID | Name | Failure Type | Target Resource | Breached Metric & Threshold | Recovery Action | Nominal Baseline Post-Recovery |
|---|---|---|---|---|---|---|
| **FS-01** | High CPU | `HIGH_CPU` | `VM-001` | `cpu_utilization` $\ge 85.0\%$ | `SCALE_OUT` | CPU = 25.0%, Memory = 30.0% |
| **FS-02** | Service Failure | `SERVICE_FAILURE` | `API-001` | `network_latency_ms` $\ge 500.0\text{ ms}$ | `SERVICE_RESTART` | Latency = 15.0 ms, CPU = 25.0% |
| **FS-03** | Storage Exhaustion | `STORAGE_EXHAUSTION` | `STORAGE-001` | `storage_utilization` $\ge 90.0\%$ | `STORAGE_CLEANUP` | Storage = 20.0% |
| **FS-04** | Network Latency | `NETWORK_LATENCY` | `VM-001` | `network_latency_ms` $\ge 500.0\text{ ms}$ | `NETWORK_REROUTE` | Latency = 15.0 ms |
| **FS-05** | Service Downtime | `SERVICE_DOWNTIME` | `DB-001` | `network_latency_ms` $\ge 500.0\text{ ms}$ | `FAILOVER` | Latency = 15.0 ms, CPU = 25.0%, Storage = 20.0% |

### The 9-Step Verification Chain
For every scenario listed above, `test_complete_9_step_closed_loop_for_all_scenarios` systematically asserts:

```
[1. Failure Triggered]
       │
       ▼
[2. Failure Recorded in DynamoDB]
       │
       ▼
[3. Monitoring Condition Detected]  ───> CloudWatch Metric Threshold Breached
       │
       ▼
[4. Event Generated]                ───> EventBridge Ingests Alarm State Change
       │
       ▼
[5. Recovery Initiated]             ───> Pre-read Gate Passed; State: RECOVERY_INITIATED
       │
       ▼
[6. Recovery Completed]             ───> Strategy Executed; Synthetic Metrics Reset; State: RECOVERED
       │
       ▼
[7. Incident Updated]               ───> Status: RESOLVED; RecoveryAction Embedded; Duration Logged
       │
       ▼
[8. Notification Generated]         ───> SNS Email Dispatched; notified_transitions Recorded
       │
       ▼
[9. Dashboard Reflects Result]      ───> GET /resources/{id} & GET /incidents/{id} Return Healthy
```

---

## 4. Resilience & Edge Cases Test Suite (`tests/edge_cases/`)

Reliability engineering requires validating how the system handles adverse conditions, transient network failures, duplicate deliveries, and unexpected inputs:

### 1. Recovery Strategy Failure
* **Mechanism**: Recovery strategy raises `RecoveryStrategyError` during execution (e.g. simulated EC2 API throttling).
* **Verification**:
  - Recovery Lambda returns HTTP 500.
  - Resource enters `RECOVERY_FAILED`.
  - Incident remains `RECOVERING` with 1 `FAILED` `RecoveryAction` containing error details.
  - SNS failure alert dispatched.

### 2. Retry Exhaustion & Automatic Escalation
* **Mechanism**: Recovery fails across consecutive retries up to `MAX_RECOVERY_ATTEMPTS = 3`.
* **Verification**:
  - On the 3rd failed attempt, resource transitions to `MANUAL_INTERVENTION_REQUIRED`.
  - Incident transitions to `ESCALATED` with `escalated_at` timestamp set.
  - Embedded audit trail contains 3 distinct `RecoveryAction` records.

### 3. Duplicate Event Idempotency
* **Mechanism**: CloudWatch Alarm fires repeatedly or EventBridge delivers at-least-once duplicate events for a resource currently in `RECOVERY_INITIATED`, `RECOVERY_IN_PROGRESS`, or `RECOVERED`.
* **Verification**:
  - Layer 1 pre-read gate detects current state is not `FAILURE_DETECTED`.
  - Exits immediately with HTTP 200 `"Already recovering"`.
  - Zero duplicate recovery actions or state overwrites.

### 4. Invalid Resource Handling
* **Mechanism**: Requests specifying unregistered or non-existent resource IDs (e.g. `NON-EXISTENT-999`).
* **Verification**:
  - `GET /resources/{id}` returns HTTP 404 Not Found.
  - `POST /simulate/failure` returns HTTP 404 Not Found with explicit error payload.

### 5. Invalid Failure Type Validation
* **Mechanism**: Requests or events specifying unregistered failure enums (e.g. `TOTAL_SYSTEM_MELTDOWN`).
* **Verification**:
  - API boundary: FastAPI / Pydantic schema validation returns HTTP 422 Unprocessable Entity.
  - EventBridge boundary: `_parse_event` rejects invalid event and returns HTTP 400 Bad Request.

### 6. Partial Failure: CloudWatch Outage
* **Mechanism**: CloudWatch `put_metric_data` raises `ClientError` (`ServiceUnavailable`) during failure injection or metric reset.
* **Verification**:
  - Core simulation persists resource state and incident record in DynamoDB.
  - Recovery Lambda successfully finishes recovery, persists `RECOVERED` state, and updates incident to `RESOLVED`.
  - Outage is logged non-fatally; core business transactions are not aborted.

### 7. SNS Notification Failure
* **Mechanism**: SNS `publish` raises `ClientError` (e.g. topic quota exceeded or network drop).
* **Verification**:
  - `NotificationService.send_notification` catches `ClientError`, logs a warning, and returns `False`.
  - Calling recovery handler completes with HTTP 200; incident resolution proceeds unimpeded.

### 8. DynamoDB Conditional Write Conflict
* **Mechanism**: Two concurrent workers attempt to mutate resource state simultaneously.
* **Verification**:
  - DynamoDB `ConditionalCheckFailedException` is caught by `ResourceRepository.update_state`.
  - Operation returns current state idempotently without crashing.
  - Any unhandled AWS SDK client errors are wrapped and raised as domain `DatabaseError`.

---

## 5. Test Data Strategy

A robust test suite depends on realistic, immutable test data fixtures that isolate test cases from one another:

### Test Fixtures Hierarchy (`tests/fixtures/`)
1. **`seed_resources.json`**: Baseline fleet of 4 heterogeneous resources:
   - `VM-001` (`ResourceType.VM`)
   - `API-001` (`ResourceType.API`)
   - `STORAGE-001` (`ResourceType.STORAGE`)
   - `DB-001` (`ResourceType.DATABASE`)
2. **`scenarios.json`**: Authoritative parameter matrix defining injection values, thresholds, recovery actions, and expected nominal baselines for FS-01 through FS-05.
3. **`mock_alarm_event.json`**: Standard CloudWatch Alarm State Change EventBridge envelope.
4. **`mock_inject_event.json`**: Direct injection event envelope from `cloudpulse.simulator`.

### State Isolation & Environment Hermeticity
* Each test function receives a fresh instance of the DynamoDB tables (`resources`, `incidents`, `metrics`), SNS topic, and EventBridge bus via the `mock_aws_env` pytest fixture.
* AWS environment variables (`AWS_DEFAULT_REGION`, `DYNAMODB_TABLE_RESOURCES`, etc.) are isolated using pytest's `monkeypatch` fixture.
* No persistence occurs to disk or live cloud providers.

---

## 6. Directory Structure

```
tests/
├── conftest.py                             # Root fixtures (moto AWS, seed fleet, event factories)
├── fixtures/
│   ├── mock_alarm_event.json               # CloudWatch alarm event payload template
│   ├── mock_inject_event.json              # Simulator direct injection payload template
│   ├── scenarios.json                      # Parameter matrix for scenarios FS-01 - FS-05
│   └── seed_resources.json                 # Baseline 4-resource fleet definitions
├── unit/
│   └── test_unit_layer.py                  # Layer 1: Models, constraints, scoring
├── api/
│   └── test_api_layer.py                   # Layer 2: FastAPI endpoints and error codes
├── integration/
│   └── test_integration_layer.py          # Layer 3: Service <-> Repository collaboration
├── aws_integration/
│   └── test_aws_integration_layer.py      # Layer 4: Boto3 client interactions & caching
├── simulation/
│   └── test_simulation_layer.py           # Layer 5: Failure injection & threshold breach
├── eventbridge/
│   └── test_eventbridge_layer.py          # Layer 6: Event parsing & decomposition
├── recovery/
│   └── test_recovery_layer.py             # Layer 7: Recovery strategies & state transitions
├── notification/
│   └── test_notification_layer.py         # Layer 8: SNS templates & deduplication
├── e2e/
│   └── test_e2e_closed_loop.py            # Layer 9: 9-step closed-loop lifecycle for FS-01 - FS-05
└── edge_cases/
    └── test_edge_cases_and_resilience.py  # Fault modes: Retries, partial failures, idempotency
```

---

## 7. Execution Commands & Failure Reporting Guide

### Running the Test Suite
```bash
# Activate virtual environment
source backend/.venv/bin/activate

# 1. Run all comprehensive tests across all 9 layers & edge cases
pytest tests/ -v

# 2. Run only the 9-step End-to-End closed-loop suite
pytest tests/e2e/ -v

# 3. Run resilience and edge-case tests
pytest tests/edge_cases/ -v

# 4. Run entire project test suite (including backend unit tests)
pytest tests/ backend/tests/ -q
```

### Interpreting Failure Reports
If a test fails, verify the failure layer using this diagnostic triage:
1. **Layer 1-3 failure**: Domain validation rule changed; check model validators or repository query signatures.
2. **Layer 4-6 failure**: EventBridge pattern or boto3 parameter mismatch; inspect event shape in `fixtures/`.
3. **Layer 7-8 failure**: Strategy outcome format or SNS template mismatch; check `strategies.py` or `notification_service.py`.
4. **Layer 9 failure**: End-to-end coordination broken; determine which of the 9 steps in the closed-loop chain failed.
5. **Edge case failure**: Concurrency or non-fatal exception handling regression; check conditional expressions and error logs.
