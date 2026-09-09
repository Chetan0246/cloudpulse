# CloudPulse Observability & Distributed Tracing Architecture

## 1. Overview & Observability Principles

CloudPulse is designed as an autonomous, self-healing cloud platform. Reliability engineering in distributed systems demands high-fidelity observability that transcends basic request-response logging. In a self-healing system, an operational event spans multiple asynchronous AWS serverless components:

$$\text{Simulation} \longrightarrow \text{Detection} \longrightarrow \text{Event Routing} \longrightarrow \text{Recovery Execution} \longrightarrow \text{Notification}$$

To make every incident completely transparent, auditable, and debuggable, CloudPulse implements:
1. **Zero-Invention Metric Derivation**: Every SRE metric is strictly computed from stored DynamoDB states (`SimulatedResource`, `Incident`, `ReliabilityMetric`).
2. **Correlation ID & Distributed Tracing**: A continuous trace context flows across synchronous REST endpoints, asynchronous EventBridge buses, Lambda functions, and SNS topics.
3. **Structured JSON Telemetry**: Every log entry is formatted as an RFC 8259 JSON document with standardized operational fields.
4. **Timezone-Safe UTC Synchronization**: All timestamps adhere to strict ISO 8601 UTC representations (`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`), preventing skew across distributed Lambdas and browser frontends.

---

## 2. Distributed Tracing & Correlation Context Flow

### 2.1 The 5-Stage Incident Lifecycle Pipeline

```
┌─────────────────┐
│ 1. SIMULATION   │ POST /simulate/failure
│                 │ • Generates correlationId (UUID v4)
└────────┬────────┘ • Log stage="simulation", correlation_id=<id>
         │
         ▼
┌─────────────────┐
│ 2. DETECTION    │ SimulatedResource telemetry threshold breach
│                 │ • Metric breached (CPU, Latency, Storage)
└────────┬────────┘ • Log stage="detection", alarm triggered
         │
         ▼
┌─────────────────┐
│ 3. EVENT ROUTE  │ EventBridge rule pattern match
│                 │ • Event detail encapsulates correlationId & resourceId
└────────┬────────┘ • Log stage="event", source="aws.cloudwatch"
         │
         ▼
┌─────────────────┐
│ 4. RECOVERY     │ Recovery Lambda execution
│                 │ • Unpacks correlationId from EventBridge detail
└────────┬────────┘ • Log stage="recovery", dispatches strategy
         │
         ▼
┌─────────────────┐
│ 5. NOTIFICATION │ SNS Topic Publish
│                 │ • Embeds "Correlation ID: <id>" into email & logs
└─────────────────┘ • Log stage="notification", incident status updated
```

### 2.2 Trace Context Propagation Across Boundaries

| Stage | Component | Transport Mechanism | Context Carrier | Log Stage Tag |
| :--- | :--- | :--- | :--- | :--- |
| **Simulation** | FastAPI / `SimulationService` | HTTP Request / Service Context | Python `contextvars` (`correlation_id_ctx`) | `simulation` |
| **Detection** | `MonitoringService` / Alarms | CloudWatch Alarm State Change | Alarm description / metric dimension tags | `detection` |
| **Event** | EventBridge Bus | EventBridge Event Envelope | `event["detail"]["correlationId"]` | `event` |
| **Recovery** | Recovery Lambda Handler | Lambda invocation payload | Python `contextvars` (`correlation_id_ctx`, `stage_ctx`) | `recovery` |
| **Notification**| `NotificationService` / SNS | SNS message attributes & payload | SNS Subject & Message body: `Correlation ID: <id>` | `notification` |

### 2.3 Thread & Async-Safe Context Binding

Trace variables are managed through Python's native standard library `contextvars`, ensuring safety across asynchronous tasks and concurrent invocations:

```python
import contextvars

correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)
incident_id_ctx = contextvars.ContextVar("incident_id", default=None)
stage_ctx = contextvars.ContextVar("stage", default=None)

def set_correlation_id(correlation_id: str) -> None:
    correlation_id_ctx.set(correlation_id)

def set_trace_stage(stage: str) -> None:
    stage_ctx.set(stage)
```

When an event enters the Recovery Lambda, the context is initialized immediately:

```python
correlation_id = event.get("detail", {}).get("correlationId") or str(uuid.uuid4())
set_correlation_id(correlation_id)
set_trace_stage("recovery")
```

---

## 3. Structured JSON Logging Schema

All CloudPulse backend services and Lambda handlers utilize `JsonFormatter` (`backend/app/logging_config.py`). Log lines are emitted to standard output and ingested by CloudWatch Logs as JSON objects.

### 3.1 JSON Log Schema Definition

```json
{
  "timestamp": "2026-09-09T18:45:12.104251+00:00",
  "level": "INFO",
  "logger": "app.services.simulation_service",
  "message": "Injected simulated failure HIGH_CPU into VM-001",
  "correlation_id": "c9e2b104-58f2-4911-9e2c-389d3184a410",
  "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "stage": "simulation",
  "resource_id": "VM-001",
  "failure_type": "HIGH_CPU",
  "action_type": "SCALE_OUT"
}
```

### 3.2 Field Descriptions

| Field | Type | Mandatory | Description |
| :--- | :--- | :--- | :--- |
| `timestamp` | string (ISO 8601) | Yes | UTC timestamp with explicit timezone offset (`+00:00` or `Z`) |
| `level` | string | Yes | Log severity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `logger` | string | Yes | Fully qualified Python logger name (e.g. `app.services.recovery_service`) |
| `message` | string | Yes | Human-readable log narrative describing the operational action |
| `correlation_id` | string (UUID v4) | Conditional | Unique correlation ID linking all operations triggered by a fault event |
| `incident_id` | string (UUID v4) | Conditional | DynamoDB `Incident` primary key once an incident record is established |
| `stage` | string | Yes | Pipeline stage: `simulation`, `detection`, `event`, `recovery`, `notification` |
| `resource_id` | string | Optional | Identifier of target resource (`VM-001`, `API-001`, `DB-001`, `STORAGE-001`) |
| `failure_type` | string | Optional | Fault category (`HIGH_CPU`, `SERVICE_FAILURE`, etc.) |
| `duration_ms` | float | Optional | Execution latency of an action or query in milliseconds |

---

## 4. CloudWatch Insights Tracing Queries

With structured JSON logging and persistent correlation IDs, engineers can query logs across multiple Lambda functions and API containers in CloudWatch Logs Insights.

### Query 1: Trace an Incident Across the Complete 5-Stage Flow
```sql
fields @timestamp, stage, correlation_id, incident_id, message, level
| filter correlation_id = "c9e2b104-58f2-4911-9e2c-389d3184a410"
| sort @timestamp asc
| limit 100
```
*Output demonstrates the unbroken progression from `simulation` through `recovery` and `notification`.*

### Query 2: Locate All Failed Recovery Attempts with Error Trace
```sql
fields @timestamp, resource_id, failure_type, correlation_id, message
| filter stage = "recovery" and level = "ERROR"
| sort @timestamp desc
| limit 50
```

### Query 3: Measure Recovery Action Execution Duration
```sql
fields @timestamp, resource_id, action_type, duration_seconds
| filter stage = "recovery" and ispresent(duration_seconds)
| stats avg(duration_seconds) as avg_recovery, max(duration_seconds) as max_recovery by action_type
```

### Query 4: Audit Notification Dispatches
```sql
fields @timestamp, incident_id, correlation_id, message
| filter stage = "notification"
| sort @timestamp desc
| limit 25
```

---

## 5. Timezone Safety & Timestamp Guarantees

Distributed cloud systems frequently suffer from "timestamp drift" or local timezone ambiguities (e.g., mixing UTC and local system times), corrupting MTTR and duration measurements.

CloudPulse enforces strict timezone guarantees:
1. **Explicit UTC Instantiation**: All server-side datetime generation uses `datetime.now(UTC)`:
   ```python
   from datetime import UTC, datetime
   now = datetime.now(UTC)
   ```
2. **ISO 8601 Serialization**: Timestamps are stored and exposed over REST APIs formatted with standard UTC specifiers:
   ```
   2026-09-09T18:45:12.104251+00:00
   ```
3. **Lexicographic Sortability**: DynamoDB Sort Keys (`window_key`, `detected_at`) format dates as `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS.ffffffZ` to support DynamoDB `begins_with` and `BETWEEN` range operations.
4. **Browser Localization**: The React frontend ingests strict UTC ISO strings and formats them locally in the client browser using `Intl.DateTimeFormat` or `Date.toLocaleTimeString()`.
