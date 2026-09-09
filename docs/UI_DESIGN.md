# CloudPulse React Dashboard — UI/UX Architecture & Design Specification

This document details the user interface architecture, design system, component hierarchy, state management, and API integration contracts for the CloudPulse React Dashboard.

---

## 1. Vision & Design Philosophy

The CloudPulse Dashboard is designed as a **Cloud Reliability Control Center (SRE Operations HUD)** rather than a generic CRUD application. It draws inspiration from mission-critical reliability dashboards like Datadog, Grafana, and AWS CloudWatch, prioritizing:

- **High-Density Telemetry Readability**: Data values, resource states, latencies, and identifiers are formatted in monospace typography (`font-mono`) for precision scanning.
- **Ambient System Awareness**: An overarching global status indicator immediately communicates fleet health (`SYSTEM NOMINAL`, `DEGRADED`, or `SELF-HEALING ACTIVE`) without requiring manual navigation.
- **Dark Mode Mission Control Theme**: Built on a deep `slate-950` background with `slate-900` glassmorphic panels, glowing semantic borders, and pulse animations for in-progress operations.
- **Real-Time Operational Loop**: Continuous background polling (default 5 seconds) provides live telemetry updates, complemented by pause/resume controls and manual synchronization.
- **Zero Mock / Fake Data**: Directly integrates with backend REST endpoints for virtual resources, incidents, failure simulations, and reliability metrics.

---

## 2. Visual Design System

### 2.1 Color Palette

| Token | Class | Semantic Purpose |
|---|---|---|
| Background Base | `bg-slate-950` | Primary app background |
| Surface Panels | `bg-slate-900/80` | Glassmorphic containers with `border-slate-800/80` |
| Deep Inset Wells | `bg-slate-950/60` | Telemetry readouts and code blocks |
| Brand Primary | `indigo-500` / `indigo-600` | Active tabs, control center badges, call-to-action buttons |
| Nominal / Recovered | `emerald-400` / `emerald-500` | Healthy resource states, resolved incidents, SLO compliance |
| Warning / Degraded | `amber-400` / `amber-500` | Warning resource states, medium severity alerts, metric threshold approaches |
| Failure / Critical | `rose-400` / `rose-500` | Critical alarms, failed recoveries, open incidents |
| Remediation / Self-Healing | `cyan-400` / `cyan-500` | Recovery in progress, Lambda execution, MTTR telemetry |
| Escalated / Tier-2 | `purple-400` / `purple-500` | Manual intervention required, escalated incidents |

### 2.2 Typography
- **Headings & Body**: Sans-serif (`font-sans`) for navigation and structural text.
- **Data & Telemetry**: Monospace (`font-mono`) for resource IDs, UUIDs, timestamps, CPU/memory percentages, network latencies, and enum values.

---

## 3. Component Architecture

```
frontend/src/
├── api/
│   ├── client.ts             # Axios instance with baseURL fallback and error interceptors
│   ├── resources.ts          # /resources/ endpoint calls
│   ├── incidents.ts          # /incidents/ endpoint calls
│   ├── simulate.ts           # /simulate/inject and /simulate/reset/{id} calls
│   ├── metrics.ts            # /metrics endpoint calls
│   └── types.ts              # TypeScript interfaces mirroring Pydantic models
├── components/
│   ├── common/
│   │   ├── Badge.tsx         # StateBadge, HealthBadge, StatusBadge, SeverityBadge, FailureTypeBadge
│   │   ├── Card.tsx          # Panel, MetricCard, StatBox
│   │   ├── Gauge.tsx         # LinearGauge (0-100%), LatencyGauge (ms)
│   │   └── StateViews.tsx    # LoadingState, ErrorState, EmptyState
│   ├── navigation/
│   │   ├── Header.tsx        # Brand HUD, system status indicator, live sync controls
│   │   └── TabNav.tsx        # 9-section tab bar with active incident pill counter
│   └── sections/
│       ├── OverviewSection.tsx           # Fleet KPI metrics, alert banner, recent incidents
│       ├── ResourceHealthSection.tsx     # Resource cards/table with live gauges and reset actions
│       ├── FailureSimulatorSection.tsx   # Fault injection controls (FS-01 to FS-05) and execution receipts
│       ├── ActiveIncidentsSection.tsx     # Filterable incident list (status, severity, fault, search)
│       ├── IncidentDetailSection.tsx      # Complete 14-field lifecycle view, stepper, recovery audit
│       ├── RecoveryActivitySection.tsx    # Recovery strategy breakdown, action durations, audit stream
│       ├── ReliabilityMetricsSection.tsx  # Availability, MTTR, MTBF, success rate, window selector
│       ├── ArchitectureViewSection.tsx    # Interactive closed-loop topology map (Resource → SNS)
│       └── SystemEventsSection.tsx        # Real-time chronological telemetry event stream
├── pages/
│   └── Dashboard.tsx         # Orchestrates polling, state management, and section switching
└── App.tsx                   # Top-level shell
```

---

## 4. Detailed Section Specifications

### 4.1 Overview (`OverviewSection`)
- **Fleet Metrics Grid**:
  - Healthy resources count (green)
  - Warning resources count (amber)
  - Failed resources count (rose)
  - Recovering resources count (cyan)
- **Reliability Metrics**:
  - Active incidents count (OPEN + RECOVERING)
  - Recovery success rate percentage
  - Average recovery time (MTTR in seconds)
- **Active Incident Alert Banner**: Dynamically renders when active incidents are in-flight with direct deep link to inspect incidents.
- **Recent Incidents Table**: Shows the 5 newest incidents with status, severity, fault scenario, detection time, and quick link to lifecycle inspection.

### 4.2 Resource Health (`ResourceHealthSection`)
- **Fleet Filter**: Filter resources by type (`ALL`, `VM`, `API`, `DB`, `STORAGE`).
- **Layout Modes**: Toggleable Grid view and Tabular grid view.
- **Resource Cards**:
  - Resource ID and Type
  - Health Status (`HEALTHY`, `DEGRADED`, `CRITICAL`) and Current State badges
  - Live linear progress gauges for CPU %, Memory %, and Storage % with dynamic warning (>70%) and critical (>85%) color transitions
  - Network Latency gauge with ms readout
  - Heartbeat status (relative elapsed time and exact ISO timestamp)
  - Quick action buttons: **"Inject Fault"** (switches to simulator with resource pre-selected) and **"Reset to Healthy"** (calls `/simulate/reset/{id}`).

### 4.3 Failure Simulator (`FailureSimulatorSection`)
- **Chaos Injection Controls**:
  - Target resource selector (interactive cards showing current state)
  - Failure scenario selector:
    - `FS-01`: High CPU Utilization (`HIGH_CPU`)
    - `FS-02`: Simulated Service Failure (`SERVICE_FAILURE`)
    - `FS-03`: Storage Volume Exhaustion (`STORAGE_EXHAUSTION`)
    - `FS-04`: Network Latency Spike (`NETWORK_LATENCY`)
    - `FS-05`: Unrecoverable Service Downtime (`SERVICE_DOWNTIME`)
  - Severity level selector (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - **"Trigger Failure Scenario"** action button with loading animation
  - **"Reset Target Resource"** action button
- **Architecture Blueprint Card**: Explains the simulated failure mechanism, target CloudWatch metric, alarm trigger threshold, and automated recovery strategy.
- **Simulator Output Receipt**: Displays real-time API execution message, created Incident ID, emitted CloudWatch metrics, and direct link to inspect the incident.

### 4.4 Active Incidents (`ActiveIncidentsSection`)
- **Multi-Dimensional Filtering**:
  - Lifecycle status filter: `ALL`, `OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`
  - Severity filter: `ALL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
  - Failure type dropdown: `ALL`, `HIGH_CPU`, `SERVICE_FAILURE`, etc.
  - Text search: Real-time filtering by Incident ID or Resource ID
- **Incidents Table**:
  - Columns: Incident ID, Resource, Failure Scenario, Severity, Status, Detected At, Duration, Recovery Action, Inspect Action.
  - Clickable rows navigate directly into Incident Details.
  - Formatted durations (`X.Xs` or `Xm Ys`).

### 4.5 Incident Details (`IncidentDetailSection`)
- **Incident Switcher**: Dropdown allowing instant switching between any incident in history.
- **Visual Lifecycle Stepper**:
  - Step 1: `Detected` (with timestamp)
  - Step 2: `Recovery Initiated` (with timestamp)
  - Step 3: `Action Executed` (strategy type)
  - Step 4: `Resolution / Final State` (`RESOLVED` or `ESCALATED`)
- **The 14 Incident Lifecycle Fields**:
  1. `incidentId` (`incident_id` / UUID v4)
  2. `resourceId` (`resource_id`)
  3. `failureType` (`failure_type`)
  4. `severity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  5. `createdAt` (`created_at`)
  6. `detectedAt` (`detected_at`)
  7. `recoveryStartedAt` (`recovery_started_at` / `recovery_initiated_at`)
  8. `recoveredAt` (`recovered_at` / `resolved_at`)
  9. `status` (`OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`)
  10. `recoveryAction` (`recovery_action` / strategy type)
  11. `recoveryResult` (`recovery_result` / `SUCCEEDED` or `FAILED`)
  12. `notificationStatus` (`notification_status` / SNS dispatch confirmation)
  13. `retryCount` (`retry_count` / `recovery_attempts`)
  14. `errorMessage` (`error_message` with dedicated callout banner if present)
- **Recovery Actions Audit Log**: Detailed breakdown of every executed remediation action (Action ID, Action Type, Execution Outcome, Start/Completion timestamps, Error Detail).
- **SNS Notification Dispatch Panel**: Shows delivery status and logged transition events (`FAILURE_DETECTED`, `RECOVERY_STARTED`, `RECOVERY_SUCCEEDED`, `RECOVERY_FAILED`).

### 4.6 Recovery Activity (`RecoveryActivitySection`)
- **KPI Summary**: Total actions executed, Succeeded actions, Failed actions, Average execution duration.
- **Strategy Distribution Cards**:
  - `SCALE_OUT`: Dynamic capacity scaling
  - `SERVICE_RESTART`: Worker process restart
  - `STORAGE_CLEANUP`: Volume log truncation
  - `NETWORK_REROUTE`: VPC transit re-routing
  - `FAILOVER`: Standby replica promotion
  - Filterable by clicking any strategy card.
- **Recovery Execution Stream**: Chronological audit feed of all remediation operations with durations, retries, and outcome messages.

### 4.7 Reliability Metrics (`ReliabilityMetricsSection`)
- **SLO & SRE Scorecard**:
  - Availability % (computed against 99.900% target)
  - Mean Time to Recovery (MTTR in seconds)
  - Mean Time Between Failures (MTBF in seconds)
  - Self-Healing Success Rate (%)
- **Window Filter**: Toggle between `DAILY`, `WEEKLY`, and `CUMULATIVE` aggregation windows.
- **Resource Reliability Breakdown**: Tabular comparison of availability %, MTTR, MTBF, incident counts, resolutions, and failures per resource.
- **Failure Scenario Distribution**: Visual bar distribution of incident frequency by failure scenario.

### 4.8 Architecture View (`ArchitectureViewSection`)
- **Interactive Closed-Loop Topology Map**:
  - Node 1: Virtual Infrastructure Fleet (Compute/DB/Storage)
  - Node 2: CloudWatch Custom Metrics (`CloudPulse/SimulatedFleet`)
  - Node 3: CloudWatch Alarms (Evaluates thresholds, Ok → Alarm)
  - Node 4: Amazon EventBridge (State change pattern matching)
  - Node 5: Self-Healing Recovery Lambda (Strategy dispatch & remediation)
  - Node 6: DynamoDB & SNS Alerts (Incident persistence & engineer notification)
- **Dynamic State Lighting**:
  - If alarms are triggered, the Alarm node pulses red.
  - If recovery is active, the Lambda node pulses cyan.
  - Flow lines pulse to visualize continuous observability loop.
- **Technical Specification Drawer**: Clicking any node renders technical contracts, dimensions, evaluation intervals, and operational responsibilities.

### 4.9 System Events (`SystemEventsSection`)
- **Chronological Observability Stream**: Aggregates real-time events from:
  - Anomaly detections (`FAILURE_DETECTED`)
  - Self-healing triggers (`RECOVERY_STARTED`)
  - Incident resolutions (`RESOLVED` / `RECOVERED`)
  - SNS notifications dispatched
- **Event Category Filtering**: Filter by `ALL`, `FAILURE`, `RECOVERY`, `RESOLUTION`, `ALERT`.
- **Resource Filtering**: Filter stream by target resource.
- **Interactive Audit Links**: Clicking any event inspects the corresponding incident lifecycle.

---

## 5. State Management & Real-Time Polling Strategy

### 5.1 Low-Cost Adaptive Refresh Strategy
To optimize for low-cost student deployment while delivering a real-time SRE command center experience, CloudPulse implements an **adaptive polling strategy**:
- **Idle Polling Rate (`10s`)**: When all fleet resources are `HEALTHY` and 0 incidents are active, the dashboard polls every 10 seconds.
- **Active Remediation Polling Rate (`3s`)**: When an incident is detected, in recovery, or degraded resources are observed, polling accelerates to 3-second intervals to provide high-frequency visibility into self-healing state machine transitions.
- **Page Visibility API Integration**: Background polling is automatically **suspended** when the browser tab is hidden or minimized (`document.visibilityState === 'hidden'`). Polling immediately resumes upon tab focus with a fresh telemetry sync, avoiding wasteful AWS Lambda and API Gateway invocations.
- **In-Flight Lock Protection**: Uses `isFetchingRef` to guarantee that slow network responses never stack overlapping concurrent poll cycles.
- **Manual Telemetry Sync**: The "Sync" action in the header triggers an immediate parallel refresh across all endpoints with a visual spinning indicator.
- **Safe Optimistic Updates**: Failure injection and resource resets apply instant optimistic state updates to local state for zero-latency operator feedback, verified and reconciled upon backend response.

### 5.2 Explicit State Views
Every section implements explicit:
- **Loading State**: Rotating radar spinner with descriptive context message (`Connecting to CloudPulse observability engine`).
- **Error State**: SRE callout displaying normalized error detail (`normalizedMessage`), HTTP status code, and a prominent "Retry Connection" action.
- **Empty State**: Tailored illustration, description, and direct call-to-action (e.g. "Inject First Failure") when data collections are empty.

---

## 6. API Integration Contracts & Client Architecture

### 6.1 Endpoints Connected
The React dashboard communicates directly with the FastAPI backend without intermediate proxy layers:

| HTTP Verb | Path | Description | Frontend Consumer |
|---|---|---|---|
| `GET` | `/health` & `/health/ready` | Liveness & DynamoDB readiness probes | `Header.tsx` (API connectivity indicator) |
| `GET` | `/resources` | List all virtual resources (lightweight summaries) | `OverviewSection`, `ResourceHealthSection` |
| `GET` | `/resources/{id}` | Detailed telemetry and metric targets for single resource | `ResourceHealthSection` |
| `GET` | `/incidents` | List incidents with optional status/severity filters | `OverviewSection`, `ActiveIncidentsSection` |
| `GET` | `/incidents/{id}` | Full 14-field incident lifecycle & recovery actions | `IncidentDetailSection` |
| `GET` | `/metrics` | Reliability metric snapshots (availability, MTTR, MTBF) | `ReliabilityMetricsSection`, `OverviewSection` |
| `POST` | `/simulate/failure` | Inject simulated failure (FS-01 to FS-05) | `FailureSimulatorSection` (with `/simulate/inject` alias fallback) |
| `POST` | `/simulate/recover` | Dispatch manual self-healing remediation | `FailureSimulatorSection` |
| `POST` | `/simulate/reset/{id}`| Reset resource metrics to nominal baseline | `ResourceHealthSection`, `FailureSimulatorSection` |

### 6.2 Retry & Error Normalization Policy
- **Configured Axios Client** (`frontend/src/api/client.ts`):
  - Base URL resolved from `VITE_API_BASE_URL` or fallback `http://localhost:8000`.
  - 10-second request timeout (`timeout: 10000`).
  - **Idempotent Retry Policy**: Automatically retries with exponential backoff (`300ms`, `600ms`) **strictly** on idempotent `GET` and `HEAD` requests encountering transient server errors (502, 503, 504) or network disconnects (`ECONNABORTED`, `ERR_NETWORK`).
  - **Mutating Requests**: Mutating `POST`, `PUT`, and `DELETE` requests are **never retried** automatically to prevent duplicate side effects.
  - **Error Normalization**: All errors are normalized into human-readable messages extracting FastAPI `detail` or custom error objects.

### 6.3 5-Stage Visible Failure & Recovery Lifecycle
In `FailureSimulatorSection.tsx`, operators observe the complete self-healing lifecycle through an interactive 5-stage progression stepper:

```
[1. HEALTHY] ──► [2. FAILURE] ──► [3. DETECTION] ──► [4. RECOVERY] ──► [5. RECOVERED]
 Nominal         Fault Injected   Alarm Breached      Remediation        Nominal
 Baseline        Telemetry Drops  Incident Opened     Lambda Active      Restored
```

1. **Stage 1: Healthy**: Target resource operates at nominal baseline metrics.
2. **Stage 2: Failure**: Workload anomaly injected (`POST /simulate/failure`), optimistic UI metrics shift.
3. **Stage 3: Detection**: CloudWatch metric threshold breached, incident created with `status=OPEN`.
4. **Stage 4: Recovery**: Self-Healing Lambda dispatches remediation strategy via `POST /simulate/recover`.
5. **Stage 5: Recovered**: Verification succeeds, resource restored to `HEALTHY`, incident transitioned to `RESOLVED`.

---

## 7. Testing & Verification Summary

- **Frontend Test Suite**: Built on Vitest v2 and `@testing-library/react`.
  - **17 test suites, 47 unit & integration tests passing (100% success)**.
  - Covers all common HUD components, navigation bars, all 9 sections, API client retry logic, and full 5-stage lifecycle progression.
- **Backend Test Suite**: Built on pytest and moto.
  - **272 unit & integration tests passing (100% success)**.
  - Includes `test_frontend_api_flow.py` asserting exact contracts, lifecycle transitions, and responses.
- **Type Checking**: Strict TypeScript validation (`tsc --noEmit`) passes cleanly with 0 errors.
- **Production Bundle**: Built via Vite (`npm run build`) producing optimized CSS and JS assets in under 1.5 seconds.
