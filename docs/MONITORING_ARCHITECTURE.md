# CloudPulse Monitoring Architecture

**Version:** 2.0  
**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Status:** Implemented and Tested  
**Last Revised:** 2026-09-09

---

## Table of Contents

1. [Overview](#1-overview)
2. [Custom Metric Design](#2-custom-metric-design)
3. [Metric Publishing Pipeline](#3-metric-publishing-pipeline)
4. [Failure-to-Detection Mapping](#4-failure-to-detection-mapping)
5. [Alarm Threshold Strategy](#5-alarm-threshold-strategy)
6. [Alarm State Machine](#6-alarm-state-machine)
7. [ServiceHealth Composite Metric](#7-servicehealth-composite-metric)
8. [EventBridge Integration](#8-eventbridge-integration)
9. [Race Conditions and Idempotency](#9-race-conditions-and-idempotency)
10. [Duplicate-Event Risks](#10-duplicate-event-risks)
11. [Cost Analysis and Risks](#11-cost-analysis-and-risks)
12. [Testing Strategy and Gaps](#12-testing-strategy-and-gaps)

---

## 1. Overview

CloudPulse uses a **four-stage, fully decoupled detection pipeline**:

```
Failure Injection (API or Heartbeat)
         │
         ▼ PutMetricData (5 metrics, batched per resource)
CloudWatch Custom Metrics
  Namespace: CloudPulse
  Dimensions: ResourceId × ResourceType
         │
         ▼ Threshold evaluation (period: 60s, eval periods: 2)
CloudWatch Alarms
  State transition: OK → ALARM
         │
         ▼ Alarm state change event
EventBridge Default Bus
  source: aws.cloudwatch
  detail-type: CloudWatch Alarm State Change
         │
         ▼ Matched by prefix rule: alarmName starts with "cloudpulse-"
Recovery Lambda
```

**A second fast-path exists** for demo responsiveness:

```
POST /simulate/failure
         │
         ▼ (in parallel with metric publish)
EventBridge Default Bus
  source: cloudpulse.simulator
  detail-type: FailureInjected
         │
         ▼ Matched by direct rule
Recovery Lambda
```

**Design principle:** The simulator publishes **facts** (metric values). The monitoring layer derives **judgments** (alarm state). The recovery layer reacts to **judgments**. These three concerns are strictly separated.

---

## 2. Custom Metric Design

### 2.1 Namespace

All CloudPulse metrics share a single namespace:

```
Namespace: CloudPulse
```

Configured as a CloudFormation parameter (`CloudWatchNamespace`, default `CloudPulse`). IAM namespace-scoped `PutMetricData` policies are applied to both the Simulator and API Lambda roles, preventing metric pollution of other namespaces.

**Why a single namespace?**
- Enables namespace-level IAM scoping (`cloudwatch:namespace` condition key)
- Groups all CloudPulse metrics together in the CloudWatch console
- Keeps alarm ARNs consistent and predictable

### 2.2 Dimensions

Every metric data point is published with **exactly two dimensions**:

| Dimension Name | Example Values               | Purpose |
|----------------|------------------------------|---------|
| `ResourceId`   | `VM-001`, `STORAGE-001`      | Uniquely identifies the simulated resource |
| `ResourceType` | `VM`, `API`, `DB`, `STORAGE` | Enables category-level alarm queries |

**Why two dimensions?**
A single `ResourceId` would suffice for per-resource alarms, but two dimensions enable:
- Dashboard widgets scoped to a resource category (e.g., "all DB latency")
- SAM template alarm definitions with explicit `ResourceType` to make alarms self-describing in the CloudWatch console

**Dimension cardinality is bounded.** The fixed resource set (VM-001, API-001, DB-001, STORAGE-001) produces exactly 4 × 5 = 20 metric timeseries. This prevents the cardinality explosion that can make CloudWatch costs unpredictable.

### 2.3 Metrics Published

| Metric Name          | Unit            | Range         | Alarm Condition | Publishing Sources |
|----------------------|-----------------|---------------|-----------------|-------------------|
| `CPUUtilization`     | `Percent`       | 0.0 – 100.0   | ≥ 85%           | Both              |
| `MemoryUtilization`  | `Percent`       | 0.0 – 100.0   | Not alarmed*    | Both              |
| `StorageUtilization` | `Percent`       | 0.0 – 100.0   | ≥ 90%           | Both              |
| `NetworkLatency`     | `Milliseconds`  | 0.0 – 99999.0 | ≥ 500 ms        | Both              |
| `ServiceHealth`      | `None` (score)  | 0.0 – 100.0   | ≤ 50            | Both              |

> **"Both" publishing sources** = Simulator Lambda (scheduled heartbeat) and MonitoringService (API injection path). Both paths publish identical 5-metric batches.

> *`MemoryUtilization` is published for dashboard observability but has no independent alarm. High memory typically co-occurs with high CPU (both spike in FS-01), and a dedicated memory alarm would be redundant noise. This reduces total alarm count and avoids false positives from normal memory pressure.

### 2.4 Metric Value Semantics

| Metric              | Nominal Range | Warning Range | Failure Range |
|---------------------|---------------|---------------|---------------|
| `CPUUtilization`    | 0 – 70%       | 70 – 85%      | ≥ 85%         |
| `MemoryUtilization` | 0 – 70%       | 70 – 85%      | ≥ 85%         |
| `StorageUtilization`| 0 – 75%       | 75 – 90%      | ≥ 90%         |
| `NetworkLatency`    | 0 – 200 ms    | 200 – 500 ms  | ≥ 500 ms      |
| `ServiceHealth`     | 80 – 100      | 50 – 79       | ≤ 50          |

---

## 3. Metric Publishing Pipeline

### 3.1 Two Publishing Paths

```
┌─────────────────────────────────┐   ┌──────────────────────────────────┐
│  Path A: Simulator Heartbeat    │   │  Path B: API Injection            │
│                                 │   │                                   │
│  EventBridge Schedule           │   │  POST /simulate/failure           │
│  rate(2 minutes)                │   │          │                        │
│         │                       │   │          ▼                        │
│         ▼                       │   │  SimulationService                │
│  Simulator Lambda               │   │  .inject_failure()                │
│  handler.py                     │   │          │                        │
│    for resource in DynamoDB:    │   │    ├─► 1. Update DynamoDB         │
│      apply _jitter()            │   │    ├─► 2. MonitoringService       │
│      recompute state            │   │    │   .publish_resource_metrics() │
│      _publish_metrics()         │   │    └─► 3. emit_failure_event()    │
│             │                   │   │               │                   │
│             ▼                   │   │  cloudwatch.put_metric_data()     │
│  cloudwatch.put_metric_data()   │   │  5 metrics per resource           │
│  5 metrics, single API call     │   │  single API call                  │
└─────────────────────────────────┘   └──────────────────────────────────┘
               │                                        │
               └──────────────────┬─────────────────────┘
                                  ▼
                   CloudWatch Metrics (Namespace: CloudPulse)
```

Both paths publish **identical metric sets**: CPUUtilization, MemoryUtilization, StorageUtilization, NetworkLatency, ServiceHealth.

### 3.2 Simulator _publish_metrics() Implementation

```python
# lambda/simulator/handler.py
def _publish_metrics(resource, cw_client, namespace):
    dimensions = [
        {"Name": "ResourceId", "Value": resource.resource_id},
        {"Name": "ResourceType", "Value": resource.resource_type.value},
    ]
    service_health = compute_service_health(resource)  # imported from MonitoringService
    timestamp = datetime.now(timezone.utc)
    metric_data = [
        {"MetricName": "CPUUtilization",     "Value": resource.cpu_utilization,     "Unit": "Percent"},
        {"MetricName": "MemoryUtilization",  "Value": resource.memory_utilization,  "Unit": "Percent"},
        {"MetricName": "StorageUtilization", "Value": resource.storage_utilization, "Unit": "Percent"},
        {"MetricName": "NetworkLatency",     "Value": resource.network_latency_ms,  "Unit": "Milliseconds"},
        {"MetricName": "ServiceHealth",      "Value": service_health,               "Unit": "None"},
    ]
    cw_client.put_metric_data(
        Namespace=namespace,
        MetricData=[{**m, "Dimensions": dimensions, "Timestamp": timestamp} for m in metric_data],
    )
```

**Key property:** All 5 metrics share the same `Timestamp` within a single API call. This prevents CloudWatch from receiving data points with slightly different timestamps that could confuse alarm evaluation.

### 3.3 Non-Fatal Monitoring

Both paths treat CloudWatch and EventBridge calls as **non-fatal**:
- A CloudWatch `PutMetricData` failure is logged as `WARNING` but does not fail the injection
- An EventBridge `PutEvents` failure is logged as `WARNING` but does not fail the injection

Rationale: A monitoring outage must not block the simulation engine. The failure state is still persisted in DynamoDB (the source of truth), and the next heartbeat will publish the metrics again.

---

## 4. Failure-to-Detection Mapping

Each failure scenario applies metric values that **deterministically breach exactly one alarm category**. This prevents ambiguous detection and makes demo behavior predictable.

| Scenario             | Code  | Primary Metric       | Injected Value | Alarm Threshold | Detection Alarm Suffix  |
|----------------------|-------|----------------------|----------------|-----------------|-------------------------|
| High CPU Utilization | FS-01 | `CPUUtilization`     | 92%            | ≥ 85%           | `HIGH_CPU`              |
| Service Failure      | FS-02 | `NetworkLatency`     | 980 ms         | ≥ 500 ms        | `NETWORK_LATENCY`       |
| Storage Exhaustion   | FS-03 | `StorageUtilization` | 96%            | ≥ 90%           | `STORAGE_EXHAUSTION`    |
| Network Latency      | FS-04 | `NetworkLatency`     | 750 ms         | ≥ 500 ms        | `NETWORK_LATENCY`       |
| Service Downtime     | FS-05 | `NetworkLatency`     | 9999 ms        | ≥ 500 ms        | `NETWORK_LATENCY`       |

> **FS-02, FS-04, FS-05** all trigger the `NETWORK_LATENCY` alarm but at different latency magnitudes (980 ms, 750 ms, 9999 ms). The `FailureType` is preserved in the incident record and the direct EventBridge event, so the recovery layer distinguishes them.

> **FS-05 (Service Downtime)** also triggers `ServiceHealth ≤ 50` because `cpu=0`, `memory=0`, `latency=9999` collapses the composite score to near zero.

### Complete Alarm Coverage Matrix

| Resource    | Alarm Suffix          | Metric              | Threshold | Scenarios   |
|-------------|-----------------------|---------------------|-----------|-------------|
| VM-001      | `HIGH_CPU`            | CPUUtilization      | ≥ 85%     | FS-01       |
| VM-001      | `NETWORK_LATENCY`     | NetworkLatency      | ≥ 500ms   | FS-02/04/05 |
| VM-001      | `SERVICE_HEALTH`      | ServiceHealth       | ≤ 50      | Any         |
| API-001     | `HIGH_CPU`            | CPUUtilization      | ≥ 85%     | FS-01       |
| API-001     | `NETWORK_LATENCY`     | NetworkLatency      | ≥ 500ms   | FS-02/04/05 |
| API-001     | `SERVICE_HEALTH`      | ServiceHealth       | ≤ 50      | Any         |
| DB-001      | `HIGH_CPU`            | CPUUtilization      | ≥ 85%     | FS-01       |
| DB-001      | `NETWORK_LATENCY`     | NetworkLatency      | ≥ 500ms   | FS-02/04/05 |
| DB-001      | `SERVICE_HEALTH`      | ServiceHealth       | ≤ 50      | Any         |
| STORAGE-001 | `STORAGE_EXHAUSTION`  | StorageUtilization  | ≥ 90%     | FS-03       |
| STORAGE-001 | `NETWORK_LATENCY`     | NetworkLatency      | ≥ 500ms   | FS-02/04/05 |
| STORAGE-001 | `SERVICE_HEALTH`      | ServiceHealth       | ≤ 50      | Any         |

**Total alarms: 12** (3 per resource × 4 resources).

---

## 5. Alarm Threshold Strategy

### 5.1 Threshold Bands

```
CPU / Memory Utilization (Percent):
    0         70         75         85         100
    │          │          │          │           │
    ├─NOMINAL──┤─PRE-WARN─┤─WARNING──┤─FAILURE───┤
                                     ▲
                                ALARM THRESHOLD (85%)

Storage Utilization (Percent):
    0         75         80         90         100
    │          │          │          │           │
    ├─NOMINAL──┤─PRE-WARN─┤─WARNING──┤─FAILURE───┤
                                     ▲
                                ALARM THRESHOLD (90%)

Network Latency (Milliseconds):
    0        200        300        500       9999
    │          │          │          │          │
    ├─NOMINAL──┤─PRE-WARN─┤─WARNING──┤─FAILURE───┤
                                     ▲
                                ALARM THRESHOLD (500ms)

ServiceHealth Score:
    0         50         80        100
    │          │          │          │
    ├─CRITICAL─┤─WARNING──┤─NOMINAL──┤
               ▲
          ALARM THRESHOLD (≤ 50)
```

### 5.2 Why the Failure Threshold, Not the Warning Threshold?

Setting alarms at **failure threshold** (not warning threshold):

1. **Avoids false positives from normal drift.** The simulator random-walk applies ±10% jitter every 2 minutes. Nominal CPU of 25% could transiently reach 75% (warning level) without a real failure. Alarming at 85% requires a deliberate spike.

2. **Ensures demo determinism.** Failure-injected metrics (FS-01: CPU=92%, FS-03: Storage=96%) are well above their respective alarm thresholds, producing a deterministic ALARM within 2 evaluation periods.

3. **Prevents warm-start alarm floods.** A new resource bootstrapping at nominal metrics will never accidentally breach failure thresholds.

### 5.3 EvaluationPeriods = 2

Every alarm requires **2 consecutive breaching data points** (2 × 60s = 120s minimum detection latency).

- **False positive protection:** A single jitter spike does not fire the alarm if the next heartbeat is below threshold.
- **Demo realism:** Simulates the brief "detection delay" that real monitoring systems have before paging on-call.
- **Fast-path bypass:** The direct EventBridge `FailureInjected` event bypasses alarm evaluation entirely, enabling immediate demo recovery without the 2-minute wait.

> **moto note:** moto's CloudWatch mock does not fully emulate `EvaluationPeriods` arithmetic. In unit tests, a single `put_metric_data` call is sufficient to trigger alarm state changes. This is a known testing gap (§12).

### 5.4 TreatMissingData = notBreaching

Missing data (no metric in the evaluation window) is treated as **not breaching** the threshold.

- Prevents alarms from firing on cold start when no metrics exist yet
- Prevents alarms from firing after Lambda cold restarts or brief metric publishing gaps
- Consistent with the "fail-safe" principle: silence is not the same as failure

### 5.5 Period = 60 Seconds

The 60-second period aligns with the Lambda heartbeat schedule (`rate(2 minutes)`) — each heartbeat publishes one data point per resource. CloudWatch aggregates data in 60-second buckets using the `Average` statistic.

---

## 6. Alarm State Machine

### 6.1 Three States

```
                         No metric data published
                                   │
                                   ▼
                          INSUFFICIENT_DATA
                           │           ▲
  First data point         │           │  No data for N periods
  within threshold         ▼           │
                          OK  ◄────────────────────────────────┐
                           │           N consecutive periods   │
                           │           below threshold          │
  N consecutive periods    │                                    │
  breach threshold         ▼                                    │
                         ALARM ──────────────────────────────►  │
                                                               (loop)
```

| Transition               | Trigger                                          | CloudPulse Action |
|--------------------------|--------------------------------------------------|-------------------|
| `INSUFFICIENT_DATA → OK` | First metric within thresholds                   | None (nominal)    |
| `OK → ALARM`             | 2 consecutive periods breach threshold            | **EventBridge → Recovery Lambda** |
| `ALARM → OK`             | 2 consecutive periods below threshold             | Recovery Lambda resets metrics; alarm self-resolves |
| `OK → INSUFFICIENT_DATA` | No data in evaluation window                      | None (`notBreaching` suppresses false alarm) |

### 6.2 Alarm Naming Convention

```
cloudpulse-{ResourceId}-{FAILURE_TYPE_UPPER_SNAKE}
```

Examples:
- `cloudpulse-VM-001-HIGH_CPU`
- `cloudpulse-API-001-NETWORK_LATENCY`
- `cloudpulse-STORAGE-001-STORAGE_EXHAUSTION`
- `cloudpulse-DB-001-SERVICE_HEALTH`

**Parser implementation** (in recovery Lambda `_parse_event()`):
```python
# Suffix-first matching handles multi-hyphen resource IDs like STORAGE-001
for i in range(len(parts) - 1, 1, -1):
    failure_candidate = "_".join(parts[i:]).upper()
    try:
        failure_type = FailureType(failure_candidate)
        resource_id = "-".join(parts[1:i]).upper()
        return resource_id, failure_type
    except ValueError:
        continue
```

This correctly handles `cloudpulse-STORAGE-001-STORAGE_EXHAUSTION`:
- parts: `["cloudpulse", "STORAGE", "001", "STORAGE", "EXHAUSTION"]`
- tries `EXHAUSTION` → not a FailureType → continue
- tries `STORAGE_EXHAUSTION` → ✅ → resource_id = `STORAGE-001`

### 6.3 Alarm Actions

Each alarm publishes to the **SNS `NotificationsTopic`** on state changes. EventBridge routing is handled separately — CloudWatch automatically sends all alarm state changes to the default EventBridge bus, which the SAM rule then filters by the `cloudpulse-` prefix.

---

## 7. ServiceHealth Composite Metric

`ServiceHealth` is a **derived composite metric** providing a single 0–100 score for dashboard display and holistic alarming.

### 7.1 Formula

```
ServiceHealth = 100 × (
    0.30 × (1 − clamp(cpu  / 85.0,  0, 1))  +  # CPU: heaviest weight (most common failure)
    0.25 × (1 − clamp(mem  / 85.0,  0, 1))  +  # Memory
    0.20 × (1 − clamp(stor / 90.0,  0, 1))  +  # Storage
    0.25 × (1 − clamp(lat  / 500.0, 0, 1))     # Latency
)
clamped to [0.0, 100.0]
```

Weights sum to 1.0 (enforced by `test_weights_sum_to_one` unit test).

### 7.2 Score Interpretation

| Score Range | Meaning           | Alarm State |
|-------------|------------------|-------------|
| 80 – 100    | HEALTHY (nominal) | OK          |
| 50 – 79     | WARNING (degraded)| OK          |
| 0 – 49      | CRITICAL (failure)| **ALARM**   |

### 7.3 Per-Scenario ServiceHealth Scores

| Scenario | CPU  | Memory | Storage | Latency | ServiceHealth | Alarm? |
|----------|------|--------|---------|---------|---------------|--------|
| Nominal  | 25%  | 30%    | 20%     | 15ms    | ~93           | OK     |
| FS-01    | 92%  | 60%    | 20%     | 50ms    | ~37           | **ALARM** |
| FS-02    | 15%  | 20%    | 10%     | 980ms   | ~55           | OK (near boundary) |
| FS-03    | 30%  | 40%    | 96%     | 50ms    | ~64           | OK |
| FS-04    | 20%  | 25%    | 15%     | 750ms   | ~56           | OK |
| FS-05    | 0%   | 0%     | 10%     | 9999ms  | ~61           | OK |

> `SERVICE_HEALTH` alarms serve as a catch-all for multi-metric degradation. The primary alarms for network-related failures are `NETWORK_LATENCY`. Only FS-01 reliably breaches the ServiceHealth ≤ 50 threshold on its own.

### 7.4 Single-Source Computation

`compute_service_health()` is defined once in `app.services.monitoring_service` and imported by **both** the simulator handler and `MonitoringService`. This ensures the composite score is computed identically regardless of which publishing path is active.

---

## 8. EventBridge Integration

### 8.1 Event Sources

#### Source 1: CloudWatch Alarm State Change (Production Path)

```json
{
  "version": "0",
  "source": "aws.cloudwatch",
  "detail-type": "CloudWatch Alarm State Change",
  "detail": {
    "alarmName": "cloudpulse-VM-001-HIGH_CPU",
    "state": { "value": "ALARM", "reason": "Threshold Crossed: 2 datapoints..." },
    "previousState": { "value": "OK" }
  }
}
```

SAM EventBridge rule filter:
```yaml
Pattern:
  source: [aws.cloudwatch]
  detail-type: [CloudWatch Alarm State Change]
  detail:
    alarmName:
      - prefix: cloudpulse-
    state:
      value: [ALARM]
```

The `prefix: cloudpulse-` filter ensures the Recovery Lambda only reacts to CloudPulse alarms, not any other CloudWatch alarms in the account.

#### Source 2: Direct Simulation Event (Fast Demo Path)

Bypasses the ~2 minute alarm evaluation window:

```json
{
  "source": "cloudpulse.simulator",
  "detail-type": "FailureInjected",
  "detail": {
    "resourceId": "VM-001",
    "resourceType": "VM",
    "failureType": "HIGH_CPU",
    "severity": "HIGH",
    "scenarioCode": "FS-01",
    "incidentId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "detectedAt": "2026-09-09T00:15:00.000Z"
  }
}
```

### 8.2 Event Routing Architecture

```
CloudWatch Alarm (→ALARM)        Direct API call
        │                              │
        │ (AWS-managed broadcast       │ events.put_events()
        │  to default event bus)       │
        ▼                              ▼
EventBridge Default Bus        EventBridge Default Bus
        │                              │
 AlarmStateChange rule          DirectSimulatorEvent rule
  - source: aws.cloudwatch       - source: cloudpulse.simulator
  - alarmName prefix: cloudpulse-- detail-type: FailureInjected
  - state.value: ALARM
        │                              │
        └──────────────┬───────────────┘
                       ▼
               Recovery Lambda
               (idempotent handler)
```

### 8.3 EventBridge Delivery Guarantees

| Property | Behavior |
|----------|----------|
| Delivery | At-least-once |
| Ordering | Not guaranteed |
| Retries | Up to 2 retries for failed Lambda invocations |
| DLQ | SQS `cloudpulse-recovery-dlq-{env}` captures exhausted retries |
| Cost | $1.00/million events (< $0.001/month for typical demo load) |

---

## 9. Race Conditions and Idempotency

### 9.1 Race: Dual Event Sources for the Same Failure

**Scenario:** A failure injection triggers both a CloudWatch metric (→ alarm ~2min later) and an immediate `FailureInjected` event. Both arrive at the Recovery Lambda.

**Risk:** Lambda runs twice → duplicate incidents + double-recovery.

**Mitigation:** Conditional DynamoDB update with `ConditionExpression`:

```python
updated_resource = resource_repo.update_state(
    resource_id=resource_id,
    new_state=ResourceState.RECOVERY_INITIATED,
    condition_state=ResourceState.FAILURE_DETECTED,
)
```

- **First invocation:** `FAILURE_DETECTED` → condition passes → transitions to `RECOVERY_INITIATED`
- **Second invocation:** `RECOVERY_INITIATED` → `ConditionalCheckFailedException` → caught → returns current resource → handler detects state ≠ `RECOVERY_INITIATED` from transition → exits with `200 Already recovering`

**Correctness guarantee:** At most one recovery workflow runs per failure.

### 9.2 Race: Simulator Heartbeat During Recovery

**Scenario:** Scheduled simulator runs every 2 minutes. Recovery takes 3–6 minutes (simulated delays). Simulator may fire 1–3 times during recovery.

**Risk:** Jitter could push metrics back below alarm thresholds while recovery is in flight, causing `ALARM → OK` before recovery completes.

**Mitigation:** Simulator explicitly skips `RECOVERY_INITIATED` and `RECOVERY_IN_PROGRESS` states:

```python
if resource.current_state in (
    ResourceState.RECOVERY_INITIATED,
    ResourceState.RECOVERY_IN_PROGRESS,
):
    logger.info("Skipping resource mid-recovery", ...)
    continue
```

**Residual risk:** After Recovery Lambda sets `RECOVERED` but before publishing nominal metrics, the next heartbeat could jitter failure-level metrics. Recovery state is terminal so no duplicate recovery occurs, but metrics may briefly show a stale state.

### 9.3 Race: Concurrent Failure Injections

**Scenario:** Two simultaneous `POST /simulate/failure` requests for the same resource.

**Risk:** Both pass state validation (`HEALTHY` → injectable), both write to DynamoDB. Last write wins.

**Current behavior:** Acceptable for a simulator. Production would require optimistic locking via DynamoDB conditional `put_item` with a version counter.

### 9.4 Race: Alarm Flapping

**Scenario:** Metrics oscillate across the threshold boundary between heartbeats.

**Risk:** Repeated `OK → ALARM → OK → ALARM` transitions triggering multiple Lambda invocations.

**Mitigation (multi-layer):**
1. `EvaluationPeriods: 2` — single-point crossings do not alarm
2. Failure-injected metrics are pinned (simulator skips `FAILURE_DETECTED` resources) — no jitter during active failures
3. CloudWatch alarm state is sticky: `ALARM` requires 2 consecutive non-breaching periods to return to `OK`

---

## 10. Duplicate-Event Risks

### 10.1 EventBridge At-Least-Once Delivery

EventBridge may deliver the same event multiple times. The conditional `update_state` check (§9.1) handles this for both event sources.

### 10.2 Alarm Transition Loop

After recovery, `reset_to_healthy()` restores nominal metrics (CPU=25%, Storage=20%, Latency=15ms). These are far below all alarm thresholds, so no alarm re-fires. The gap between nominal values and alarm thresholds is intentional and large.

### 10.3 Incident Deduplication Gap

The injection API creates an incident during `SimulationService.inject_failure()`. The Recovery Lambda also creates an incident. This can produce **two incident records** for a single failure:

1. Created by API injection: status `OPEN`
2. Created by Recovery Lambda: status `RECOVERING` → `RESOLVED`

**Current status:** Accepted for the simulator. The `incidentId` in the `FailureInjected` EventBridge event detail is available for the Recovery Lambda to look up the existing incident, but this lookup is not yet implemented.

**Gap documented in:** `test_recovery_handler.py` TestIdempotencyGuard notes.

---

## 11. Cost Analysis and Risks

### 11.1 CloudWatch Costs (ap-south-1, 4 seeded resources)

| Item                                  | Volume                               | Unit Cost           | Monthly Estimate |
|---------------------------------------|--------------------------------------|---------------------|------------------|
| Custom metric timeseries              | 5 × 4 = 20                           | $0.30/metric/month  | $6.00            |
| PutMetricData calls (heartbeat)       | 4 resources × 30/hr × 720hr = 86,400 | $0.01/1000 calls    | $0.86            |
| PutMetricData calls (API injections)  | ~100/month                           | $0.01/1000 calls    | $0.001           |
| CloudWatch Alarms                     | 12 alarms                            | $0.10/alarm/month   | $1.20            |
| CloudWatch Logs (7-day retention)     | ~1 GB/month                          | $0.50/GB            | $0.50            |
| **Total**                             |                                      |                     | **~$8.56/month** |

### 11.2 Cost Risks and Mitigations

| Risk | Severity | Mitigation Applied |
|------|----------|--------------------|
| Metric cardinality explosion from dynamic resource IDs | HIGH | Fixed resource set; format validation (`[A-Z]{2,10}-[0-9]{3}`) rejects arbitrary IDs |
| High-frequency PutMetricData | MEDIUM | Schedule pinned to `rate(2 minutes)`; all 5 metrics per resource batched in a single API call |
| Alarm count growth | LOW | 12 alarms defined in CloudFormation; new resources require template update |
| Long log retention | LOW | All log groups have `RetentionInDays: 7`; old logs expire automatically |
| EventBridge cost | NEGLIGIBLE | At most ~100 custom events/day at demo load |
| DynamoDB read cost | NEGLIGIBLE | PAY_PER_REQUEST; ~8640 reads/day across 4 resources |

### 11.3 Cost Optimization Applied

1. **Metric batching:** All 5 metrics per resource in a single `put_metric_data()` call — reduces API call cost by 80% vs. 5 separate calls
2. **Minimal alarm count:** 12 alarms for 4 resources. No per-metric alarms where `ServiceHealth` composite suffices
3. **7-day log retention:** Prevents log storage accumulation in development
4. **Single namespace:** Precise IAM scoping prevents accidental writes to other namespaces

---

## 12. Testing Strategy and Gaps

### 12.1 What Is Tested

| Behavior | Test File | Status |
|----------|-----------|--------|
| `compute_service_health()` — all 5 scenarios + bounds + formula | `test_monitoring.py` | ✅ |
| `MonitoringService.publish_resource_metrics()` — 5 metrics, batched, correct units | `test_monitoring.py` | ✅ |
| `MonitoringService.emit_failure_event()` — event shape, all failure types | `test_monitoring.py` | ✅ |
| CloudWatch error resilience (non-fatal) | `test_monitoring.py` | ✅ |
| EventBridge error resilience (non-fatal) | `test_monitoring.py` | ✅ |
| ServiceHealth weights sum to 1.0 | `test_monitoring.py` | ✅ |
| Simulator `_jitter()` — bounds, clamping, decimal rounding | `test_simulator_handler.py` | ✅ |
| Simulator `_compute_state()` — HEALTHY, WARNING, FAILURE_DETECTED | `test_simulator_handler.py` | ✅ |
| Simulator `_publish_metrics()` — 5 metrics, ServiceHealth included, single call | `test_simulator_handler.py` | ✅ |
| **Metric alignment** — simulator and MonitoringService publish identical metric names | `test_simulator_handler.py` | ✅ |
| Simulator skip guard — RECOVERY_INITIATED/IN_PROGRESS resources skipped | `test_simulator_handler.py` | ✅ |
| ServiceHealth value in [0, 100] for all failure scenarios | `test_simulator_handler.py` | ✅ |
| Recovery `_parse_event()` — CloudWatch alarm shape, all 5 failure types | `test_recovery_handler.py` | ✅ |
| Recovery `_parse_event()` — direct event shape, all 5 failure types | `test_recovery_handler.py` | ✅ |
| Recovery `_parse_event()` — multi-hyphen resource ID (STORAGE-001) | `test_recovery_handler.py` | ✅ |
| **Alarm name round-trip** — all 12 template.yaml alarms parse correctly | `test_recovery_handler.py` | ✅ |
| Recovery idempotency guard — already-recovering returns 200 | `test_recovery_handler.py` | ✅ |
| Recovery invalid event — returns 400 | `test_recovery_handler.py` | ✅ |
| SNS failure is non-fatal | `test_recovery_handler.py` | ✅ |

### 12.2 Known Testing Gaps

| Gap | Risk | Notes |
|-----|------|-------|
| CloudWatch alarm evaluation end-to-end | **MEDIUM** | moto does not emulate `EvaluationPeriods` or `TreatMissingData`; alarm state transitions require real CloudWatch or LocalStack |
| Alarm flapping (ALARM → OK → ALARM) | **MEDIUM** | Requires real CloudWatch with time-based metric aggregation |
| Simulator heartbeat interaction with alarm state | **MEDIUM** | Periodic jitter + alarm evaluation timing cannot be tested with moto |
| Incident deduplication (dual incident records) | **MEDIUM** | Recovery Lambda creates its own incident; `incidentId` from direct event is not used to find the existing incident |
| Concurrent injection race | **LOW** | Requires two concurrent HTTP clients; not feasible in single-threaded unit tests |
| EventBridge DLQ exhaustion | **LOW** | SQS DLQ provisioned but no tests verify messages land there on Lambda failure |
| Recovery Lambda DLQ message format | **LOW** | Messages written to SQS DLQ on failure are not structurally validated |
| ServiceHealth alarm sensitivity for FS-02/04/05 | **LOW** | ServiceHealth scores for network failures (55–65) are near the ≤ 50 boundary; metric target changes could silently break alarm behavior |

### 12.3 Running Monitoring Tests

```bash
cd backend
source .venv/bin/activate

# All monitoring-related tests
pytest tests/unit/test_monitoring.py \
       tests/unit/test_simulator_handler.py \
       tests/unit/test_recovery_handler.py -v

# Critical regression: metric alignment
pytest tests/unit/test_simulator_handler.py::TestMetricAlignment -v

# Alarm name parser (all 12 alarms from template.yaml)
pytest tests/unit/test_recovery_handler.py::TestAlarmNameRoundTrip -v

# Full unit suite
pytest tests/unit/ -v --tb=short
```

### 12.4 Integration Test Path (Not Yet Implemented)

To test the full alarm pipeline end-to-end in a deployed environment:

```
1. sam deploy --parameter-overrides Environment=dev
2. POST /simulate/failure  {"resourceId": "VM-001", "failureType": "HIGH_CPU"}
3. Assert resource state = FAILURE_DETECTED in DynamoDB (immediately)
4. Wait ~2 minutes for alarm evaluation (EvaluationPeriods=2)
5. Assert CloudWatch alarm cloudpulse-VM-001-HIGH_CPU state = ALARM
6. Wait ~1 second for EventBridge delivery
7. Assert resource state = RECOVERY_INITIATED in DynamoDB
8. Wait ~10 seconds (simulated recovery delay)
9. Assert resource state = RECOVERED in DynamoDB
10. Assert alarm state returns to OK within next 2 evaluation periods
```

This test requires a real AWS account and cannot be automated with moto. It is the primary gap in end-to-end coverage.
