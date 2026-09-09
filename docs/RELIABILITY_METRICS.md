# CloudPulse SRE Reliability Metrics & Mathematical Derivations

## 1. Principles & Ground Truth Derivation

In Site Reliability Engineering (SRE), reliability metrics must reflect actual operational truth.
A cardinal architectural rule of CloudPulse is:

> **Zero-Invention Principle**: Every metric must be mathematically derivable from stored primary data records in DynamoDB (`cloudpulse-incidents-{env}`, `cloudpulse-resources-{env}`, and `cloudpulse-metrics-{env}`). No metrics are fabricated or estimated using random numbers.

All calculations are implemented in pure, deterministic functions in `backend/app/services/reliability_calculator.py`.

---

## 2. Mathematical Formulations of the 8 SRE Metrics

### Metric 1: Incident Count
The absolute number of operational incidents observed within a given time window $W = [t_{\text{start}}, t_{\text{end}}]$.

$$\text{IncidentCount}(W) = |\{i \in \text{Incidents} \mid t_{\text{start}} \le i.\text{detected\_at} \le t_{\text{end}}\}|$$

- **Primary Source**: `cloudpulse-incidents-{env}` queried via GSI `status-detected_at-index` or filtered by `resource_id`.
- **Edge Case**: If no incidents match the criteria, $\text{IncidentCount} = 0$.

---

### Metric 2: Recovery Success Rate
The percentage of terminal incidents that recovered successfully via automated self-healing without requiring operator escalation.

$$\text{TerminalIncidents} = \{i \in \text{Incidents} \mid i.\text{status} \in \{\text{RESOLVED}, \text{ESCALATED}\}\}$$

$$\text{RecoverySuccessRate}(\%) = \begin{cases} 
100.0, & \text{if } |\text{TerminalIncidents}| = 0 \\
\left(\frac{|\{i \in \text{TerminalIncidents} \mid i.\text{status} = \text{RESOLVED}\}|}{|\text{TerminalIncidents}|}\right) \times 100, & \text{if } |\text{TerminalIncidents}| > 0 
\end{cases}$$

- **Target SLO**: $\ge 95.0\%$ automated self-healing efficacy.
- **Edge Case**: If 0 closed incidents exist, defaults to $100.0\%$ (system has zero failed self-healing actions).

---

### Metric 3: Recovery Failure Rate
The percentage of terminal incidents where automated recovery attempts reached maximum retries and were escalated to manual intervention (`MANUAL_INTERVENTION_REQUIRED`).

$$\text{RecoveryFailureRate}(\%) = \begin{cases} 
0.0, & \text{if } |\text{TerminalIncidents}| = 0 \\
\left(\frac{|\{i \in \text{TerminalIncidents} \mid i.\text{status} = \text{ESCALATED}\}|}{|\text{TerminalIncidents}|}\right) \times 100, & \text{if } |\text{TerminalIncidents}| > 0 
\end{cases}$$

- **Relationship**: $\text{RecoverySuccessRate} + \text{RecoveryFailureRate} = 100.0\%$.

---

### Metric 4: Average Recovery Time
The average execution duration of automated recovery actions for resolved incidents. Measures the pure latency of the recovery script or strategy execution.

$$\text{Actions}_{\text{resolved}} = \{a \in i.\text{recovery\_actions} \mid i.\text{status} = \text{RESOLVED} \land a.\text{status} = \text{SUCCEEDED}\}$$

$$\text{Duration}(a) = a.\text{completed\_at} - a.\text{started\_at}$$

$$\text{AvgRecoveryTime} = \begin{cases} 
\text{None}, & \text{if } |\text{Actions}_{\text{resolved}}| = 0 \\
\frac{1}{|\text{Actions}_{\text{resolved}}|} \sum_{a \in \text{Actions}_{\text{resolved}}} \text{Duration}(a), & \text{if } |\text{Actions}_{\text{resolved}}| > 0 
\end{cases}$$

- **Target**: $< 15.0\text{ seconds}$ per action.

---

### Metric 5: Mean Time to Recovery (MTTR)
The end-to-end elapsed duration from when an incident was first detected until service capability was fully restored (`RESOLVED`). Captures the entire user-perceived outage window (detection + dispatch + recovery execution + verification).

$$\text{ResolvedIncidents} = \{i \in \text{Incidents} \mid i.\text{status} = \text{RESOLVED} \land i.\text{resolved\_at} \ne \text{null}\}$$

$$\text{MTTR} = \begin{cases} 
\text{None}, & \text{if } |\text{ResolvedIncidents}| = 0 \\
\frac{1}{|\text{ResolvedIncidents}|} \sum_{i \in \text{ResolvedIncidents}} (i.\text{resolved\_at} - i.\text{detected\_at}), & \text{if } |\text{ResolvedIncidents}| > 0 
\end{cases}$$

- **Target SLO**: $\text{MTTR} < 30.0\text{ seconds}$ (automated self-healing).

---

### Metric 6: Average Detection Time
The latency between when a failure condition is created in the infrastructure and when the monitoring system/alarm detects it.

$$\text{DetectionLatency}(i) = i.\text{detected\_at} - i.\text{created\_at}$$

$$\text{AvgDetectionTime} = \begin{cases} 
\text{None}, & \text{if } |\text{Incidents}| = 0 \\
\frac{1}{|\text{Incidents}|} \sum_{i \in \text{Incidents}} \text{DetectionLatency}(i), & \text{if } |\text{Incidents}| > 0 
\end{cases}$$

- **Target SLO**: $< 5.0\text{ seconds}$ for simulated faults.

---

### Metric 7: Incident Frequency & Mean Time Between Failures (MTBF)
Measures the rate of incident occurrences per unit of time, and the average uptime between successive failure events.

Let $T_{\text{window}}$ be the duration of the observation window in seconds:
$$T_{\text{hours}} = \frac{T_{\text{window}}}{3600}, \quad T_{\text{days}} = \frac{T_{\text{window}}}{86400}$$

$$\text{Frequency}_{\text{hourly}} = \frac{|\text{Incidents}|}{\max(1.0, T_{\text{hours}})}, \quad \text{Frequency}_{\text{daily}} = \frac{|\text{Incidents}|}{\max(1.0, T_{\text{days}})}$$

**Mean Time Between Failures (MTBF)**:
Given incidents ordered chronologically by detection time $t_1 \le t_2 \le \dots \le t_n$:

$$\text{MTBF} = \begin{cases} 
\text{None}, & \text{if } n < 2 \\
\frac{1}{n - 1} \sum_{k=1}^{n-1} (t_{k+1} - t_k), & \text{if } n \ge 2 
\end{cases}$$

- **Stability Benchmark**: Higher MTBF indicates higher fleet resilience.

---

### Metric 8: Current Resource Health Distribution
A real-time categorical snapshot of the entire simulated fleet across both lifecycle states and health statuses.

$$\text{TotalResources} = |\text{Resources}|$$

1. **Category Counts**:
   - $\text{HealthyCount} = |\{r \mid r.\text{current\_state} \in \{\text{HEALTHY}, \text{RECOVERED}\}\}|$
   - $\text{WarningCount} = |\{r \mid r.\text{current\_state} = \text{WARNING}\}|$
   - $\text{FailedCount} = |\{r \mid r.\text{current\_state} \in \{\text{FAILURE\_DETECTED}, \text{RECOVERY\_FAILED}, \text{MANUAL\_INTERVENTION\_REQUIRED}\}\}|$
   - $\text{RecoveringCount} = |\{r \mid r.\text{current\_state} \in \{\text{RECOVERY\_INITIATED}, \text{RECOVERY\_IN\_PROGRESS}\}\}|$

2. **Fleet Health Index**:
   $$\text{HealthyPct} = \left(\frac{\text{HealthyCount}}{\max(1, \text{TotalResources})}\right) \times 100$$

3. **By Lifecycle State Histogram**:
   $$\text{by\_state}[s] = |\{r \mid r.\text{current\_state} = s\}|, \quad \forall s \in \text{ResourceState}$$

4. **By Health Status Histogram**:
   $$\text{by\_status}[h] = |\{r \mid r.\text{health\_status} = h\}|, \quad \forall h \in \{\text{HEALTHY}, \text{DEGRADED}, \text{CRITICAL}\}$$

---

## 3. REST API Contract

### Endpoint: `GET /metrics/overview` (Alias: `GET /metrics/summary`)
Returns the complete fleet-wide SRE observability report.

**Query Parameters:**
- `window_type` (`DAILY`, `WEEKLY`, `CUMULATIVE`; default: `DAILY`)

**Response Schema (`FleetReliabilityOverview`):**
```json
{
  "incident_count": 8,
  "recovery_success_rate_pct": 87.5,
  "recovery_failure_rate_pct": 12.5,
  "avg_recovery_time_seconds": 6.2,
  "mttr_seconds": 9.4,
  "avg_detection_time_seconds": 3.8,
  "incident_frequency_per_hour": 2.0,
  "incident_frequency_per_day": 48.0,
  "mtbf_seconds": 1800.0,
  "health_distribution": {
    "total_resources": 4,
    "healthy_count": 3,
    "warning_count": 1,
    "failed_count": 0,
    "recovering_count": 0,
    "healthy_pct": 75.0,
    "by_state": {
      "HEALTHY": 3,
      "WARNING": 1,
      "FAILURE_DETECTED": 0,
      "RECOVERY_INITIATED": 0,
      "RECOVERY_IN_PROGRESS": 0,
      "RECOVERED": 0,
      "RECOVERY_FAILED": 0,
      "MANUAL_INTERVENTION_REQUIRED": 0
    },
    "by_status": {
      "HEALTHY": 3,
      "DEGRADED": 1,
      "CRITICAL": 0
    }
  },
  "computed_at": "2026-09-09T18:55:00.000000+00:00"
}
```

---

## 4. Frontend Visualization Mapping

The 8 metrics are integrated across the CloudPulse React Dashboard:

| Metric | Overview Section | Reliability Metrics Section | Visual Component |
| :--- | :--- | :--- | :--- |
| **Incident Count** | Active Incidents KPI Card | Operational Telemetry Card | Numeric KPI Card (`📋`) |
| **Recovery Success Rate** | Self-Healing Efficacy Card | Primary SRE KPI Card | Percent Badge / KPI (`🎯`) |
| **Recovery Failure Rate** | Derived / Escalation Alert | Primary SRE KPI Card | Alert Card (`⚡`) |
| **Average Recovery Time** | Metric Snapshot | Operational Telemetry Card | Latency in seconds (`🔧`) |
| **MTTR** | Core MTTR Metric Card | Primary SRE KPI Card | Latency in seconds (`⏱️`) |
| **Average Detection Time** | — | Operational Telemetry Card | Detection delay in seconds (`🔍`) |
| **Incident Frequency** | — | Hourly/Daily Rate & MTBF Card | Rate per hour/day & MTBF (`⏳`) |
| **Health Distribution** | Fleet status pills & banner | Comprehensive Health Panel | 4-tier cards, LinearGauge, state chips |
