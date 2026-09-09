# DATABASE_DESIGN.md
## CloudPulse — DynamoDB Schema Reference

**Version:** 1.1
**Last Updated:** 2026-09-08
**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Entities & Relationships](#2-entities--relationships)
3. [Access Patterns](#3-access-patterns)
4. [Table Definitions](#4-table-definitions)
   - [4.1 cloudpulse-resources-{env}](#41-table-cloudpulse-resources-env)
   - [4.2 cloudpulse-incidents-{env}](#42-table-cloudpulse-incidents-env)
   - [4.3 cloudpulse-metrics-{env}](#43-table-cloudpulse-metrics-env)
5. [DynamoDB Item Limits & Constraints](#5-dynamodb-item-limits--constraints)
6. [Serialization Notes](#6-serialization-notes)
7. [Capacity & Cost Estimate](#7-capacity--cost-estimate)
8. [SAM Template GSI Summary](#8-sam-template-gsi-summary)

---

## 1. Design Philosophy

CloudPulse's DynamoDB schema is built on a strict set of principles. Understanding *why* the schema looks the way it does is as important as understanding *what* it looks like.

### 1.1 Access-Patterns First

> **Design Note:** Table structure in DynamoDB is determined entirely by how the application reads and writes data — not by how entities relate to each other. The first step in any schema design is enumerating every access pattern. Primary keys, sort keys, and GSIs are chosen to serve those patterns and nothing else.

Traditional relational modelling asks: *"What entities exist, and how do they relate?"* DynamoDB modelling asks: *"What queries does the application need to execute?"* CloudPulse enumerates all access patterns in [Section 3](#3-access-patterns) first, then derives the key schema from those patterns.

### 1.2 Multi-Table Design

Each entity with a distinct key schema and distinct access patterns gets its own table:

| Table | Entity |
|---|---|
| `cloudpulse-resources-{env}` | `SimulatedResource` |
| `cloudpulse-incidents-{env}` | `Incident` (+ embedded `RecoveryAction`) |
| `cloudpulse-metrics-{env}` | `ReliabilityMetric` |

> **Design Note:** Multi-table design is chosen over single-table (STI/overloaded) design because:
> (a) Each entity has a completely different key schema — there is no natural shared PK hierarchy.
> (b) IAM permissions are cleaner — the Simulator Lambda has no IAM permission on the incidents table.
> (c) CloudWatch metrics per table are isolated — an incidents spike does not inflate resource table metrics.
> (d) At academic scale, the DynamoDB connection overhead of hitting 3 tables vs 1 is immeasurable.

### 1.3 Scan Is Acceptable for Small, Bounded Data

> **Design Note:** A DynamoDB Scan reads every item in the table. For the `cloudpulse-resources` table which has a hard ceiling of **4–20 virtual resources**, a full-table Scan consumes at most 20 Read Capacity Units per request. This is equivalent in cost to 20 `GetItem` calls. Adding a GSI solely to avoid a Scan would add write overhead to every resource update without producing measurable benefit.

This principle applies exclusively to `cloudpulse-resources`. It does **not** apply to `cloudpulse-incidents` which is unbounded.

### 1.4 GSIs Only When Justified

Every Global Secondary Index carries a cost:
- **Write overhead:** Every item write to the base table also writes to each GSI.
- **Storage:** Projected attributes are duplicated in the GSI partition.
- **Operational complexity:** More indexes mean more surfaces to monitor and provision.

> **Design Note:** CloudPulse adds a GSI only when a required access pattern cannot be served by the base table PK/SK and the query selectivity makes a Scan+Filter prohibitively expensive or semantically incorrect. Each GSI in this document includes an explicit justification.

### 1.5 No Relational Thinking

DynamoDB has no foreign keys, no joins, and no referential integrity enforcement. Relationships between items are managed entirely at the application layer:

- The `resource_id` attribute in an `Incident` item is a plain string. DynamoDB will not prevent you from writing an incident with a `resource_id` that does not exist in the resources table.
- The `RecoveryAction` list embedded in an `Incident` is denormalized — recovery actions are not separately addressable entities.
- Domain model validation (Pydantic) and service-layer logic enforce consistency.

### 1.6 ISO 8601 Strings for All Timestamps

> **Design Note:** DynamoDB has no native `Date` or `DateTime` type. Timestamps are stored as **ISO 8601 UTC strings** (e.g., `"2026-09-08T15:00:00Z"`). Because ISO 8601 strings are lexicographically sortable when in UTC, using them as Sort Keys on GSIs produces correct chronological ordering without any numeric conversion. Python's `datetime.isoformat()` with UTC timezone produces the correct format.

---

## 2. Entities & Relationships

CloudPulse has three persistent entity types. Their relationships are shown below.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CloudPulse Entity Map                             │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────┐          ┌──────────────────────────────────┐
  │   SimulatedResource  │  1 ── N  │            Incident              │
  │  ─────────────────── │          │  ────────────────────────────    │
  │  resource_id  (PK)   │◄─────────│  resource_id  (FK-logical)       │
  │  resource_type       │          │  incident_id  (PK, UUID v4)      │
  │  current_state       │          │  failure_type                    │
  │  health_status       │          │  severity                        │
  │  cpu_utilization     │          │  status                          │
  │  memory_utilization  │          │  detected_at                     │
  │  storage_utilization │          │  resolved_at                     │
  │  network_latency_ms  │          │  duration_seconds                │
  │  last_heartbeat      │          │  recovery_actions  (embedded ▼)  │
  │  active_failure_type │          │                                  │
  │  updated_at          │          │  ┌──────────────────────────┐   │
  │  created_at          │          │  │     RecoveryAction        │   │
  └──────────────────────┘          │  │  ──────────────────────   │   │
             │                      │  │  action_id  (UUID v4)     │   │
             │                      │  │  action_type              │   │
             │ 1                    │  │  status                   │   │
             │                      │  │  started_at               │   │
             │ N                    │  │  completed_at             │   │
             ▼                      │  │  outcome_message          │   │
  ┌──────────────────────┐          │  │  error_detail             │   │
  │  ReliabilityMetric   │          │  └──────────────────────────┘   │
  │  ─────────────────── │          └──────────────────────────────────┘
  │  resource_id  (PK)   │
  │  window_key   (SK)   │
  │  window_type         │
  │  window_start        │
  │  window_end          │
  │  total_incidents     │
  │  resolved_incidents  │
  │  failed_recoveries   │
  │  mttr_seconds        │
  │  mtbf_seconds        │
  │  availability_pct    │
  │  failure_type_counts │
  │  computed_at         │
  └──────────────────────┘
```

**Relationship rules (enforced at application layer, not by DynamoDB):**

| Relationship | Cardinality | Notes |
|---|---|---|
| `SimulatedResource` → `Incident` | One-to-many | A resource can have many incidents over time; an incident belongs to exactly one resource |
| `Incident` → `RecoveryAction` | One-to-many (embedded) | Recovery actions are embedded as a `List` attribute in the Incident item — no separate table, no extra `GetItem` required |
| `SimulatedResource` → `ReliabilityMetric` | One-to-many | One metric snapshot per (resource, window) pair; a resource accumulates snapshots across daily, weekly, and cumulative windows |

---

## 3. Access Patterns

All access patterns the application must serve are enumerated here. The key schema in Section 4 is derived directly from this list.

### 3.1 SimulatedResource Access Patterns

| ID | Description | DynamoDB Operation | Key / Index Used | Notes |
|---|---|---|---|---|
| R1 | Get a single resource by its ID | `GetItem` | Base table PK = `resource_id` | O(1), strongly consistent in Recovery Lambda |
| R2 | List all resources (dashboard, simulator tick) | `Scan` | Full table scan | ≤20 items — scan is justified (see §1.3) |
| R3 | Conditionally update resource state (idempotent) | `UpdateItem` + `ConditionExpression` | Base table PK = `resource_id` | Prevents double-recovery race conditions |

> **R2 Scan Justification:** CloudPulse maintains 4–20 virtual resources. At this scale, a Scan is equivalent to 4–20 `GetItem` calls. A GSI-based list would add write overhead to every resource state update (which happens every 2 minutes per resource) without any measurable benefit. The simulator tick and API dashboard endpoint both use a full Scan.

> **R3 Conditional Write Detail:** The Recovery Lambda uses `ConditionExpression="current_state = :expected"` on `UpdateItem`. If the resource has already moved to `RECOVERY_INITIATED` (another Lambda invocation processed it first), the condition fails and the write is rejected — making the operation idempotent without distributed locks.

### 3.2 Incident Access Patterns

| ID | Description | DynamoDB Operation | Key / Index Used | Notes |
|---|---|---|---|---|
| I1 | Get a single incident by its ID | `GetItem` | Base table PK = `incident_id` | Direct lookup, no index needed |
| I2 | List incidents for a specific resource, sorted newest first | `Query` | GSI-1 (`ResourceIndex`): PK = `resource_id`, SK = `detected_at` DESC | Dashboard resource-detail panel |
| I3 | List all currently active incidents (OPEN + RECOVERING) | `Query` × 2 + merge | GSI-2 (`StatusIndex`): PK = `status`, SK = `detected_at` | Two queries — one per active status value |
| I4 | List incidents grouped by failure type (sorted by time) | `Query` | GSI-3 (`FailureTypeIndex`): PK = `failure_type`, SK = `detected_at` | Analytics panel — "which failures dominate?" |
| I5 | List incidents filtered by severity | `Scan` + `FilterExpression` | No GSI — full scan with filter | Low selectivity, rare query, Scan justified |
| I6 | Get full incident history for a resource (oldest first) | `Query` | GSI-1 (`ResourceIndex`): PK = `resource_id`, SK = `detected_at` ASC | Same GSI as I2, ascending order |
| I7 | Count resolved incidents for reliability stat computation | `Query` + `FilterExpression` | GSI-2 (`StatusIndex`): PK = `status=RESOLVED`, SK = `detected_at` | Filter by resource_id within result set |

> **I3/I7 GSI-2 Justification:** `status` has only 4 possible values (`OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`). Querying for active incidents without a GSI would require a full table Scan on an unbounded incidents table. With GSI-2, we issue two `Query` operations — `status=OPEN` and `status=RECOVERING` — and get only the relevant items, sorted by detection time. For I7, `Query(status=RESOLVED)` + `FilterExpression(resource_id = :rid)` avoids scanning the entire table for one resource's resolved count.

> **I5 No-GSI Justification:** Severity filtering (`HIGH`, `CRITICAL`, etc.) is never the only filter — it always appears combined with a resource or failure-type filter on a result set that is already small. Adding a `GSI-4-SeverityIndex` would add a 4th write per incident without enabling a meaningfully cheaper query. A `Scan + FilterExpression` on a table with hundreds of incidents costs pennies and is fast enough for the dashboard load cadence.

> **GSI SK = `detected_at` for All Three GSIs:** All three GSIs share `detected_at` as the Sort Key. This ensures every GSI query returns items in chronological order by default and supports range filters like `SK BETWEEN :start AND :end` for time-windowed queries.

> **GSI Projection = ALL for All Three GSIs:** At academic scale (hundreds of incidents), projecting all attributes costs negligible storage. `ALL` projection means GSI queries return complete incident items — no follow-up `GetItem` calls needed to fetch missing attributes. If this project scaled to millions of incidents, switching to `KEYS_ONLY` + `GetItem` for full items would be the recommended optimisation.

### 3.3 ReliabilityMetric Access Patterns

| ID | Description | DynamoDB Operation | Key / Index Used | Notes |
|---|---|---|---|---|
| M1 | Get a specific metric snapshot (resource + window) | `GetItem` | Base table PK = `resource_id`, SK = `window_key` | Exact point lookup — O(1) |
| M2 | List all snapshots for a resource in a time range | `Query` | Base table PK = `resource_id`, `begins_with(SK, "DAILY#")` | Filter by window type prefix |
| M3 | Get the most recent snapshot for a resource | `Query` | Base table PK = `resource_id`, `ScanIndexForward=False`, `Limit=1` | Descending sort — latest SK returned first |

> **No GSI on Metrics Table:** Every access pattern is a PK-first query. The composite `(resource_id, window_key)` key covers all retrieval needs. Adding a GSI would serve no defined access pattern.

> **SK Lexicographic Sort:** `window_key` values like `CUMULATIVE#ALL`, `DAILY#2026-09-08`, `WEEKLY#2026-09-07` sort correctly as strings because `C < D < W` in ASCII, and date suffixes sort chronologically. `ScanIndexForward=False` returns the most recent daily snapshot first.

---

## 4. Table Definitions

---

### 4.1 Table: `cloudpulse-resources-{env}`

**Purpose:** Stores the current live state of all virtual simulated resources. Each row represents one resource's latest known state — this is a *current-state store*, not a history log.

**Billing:** `PAY_PER_REQUEST` (on-demand)
**Table Class:** `STANDARD_INFREQUENT_ACCESS`
**Streams:** Not enabled

#### Key Schema

| Key | Attribute | Type | Description |
|---|---|---|---|
| Partition Key (PK) | `resource_id` | `S` | Unique resource identifier, e.g. `VM-001`, `API-001` |
| Sort Key | — | — | No sort key. Each resource has exactly one authoritative item. |

> **No Sort Key Rationale:** A resource is a singleton — there is one, and only one, current-state record per resource ID. Adding a sort key (e.g., a version counter or timestamp) would allow historical states but introduce complexity not needed here. Historical state is captured by Incidents, not by versioning resource items.

> **No GSI Rationale:** The only list query on this table is "list all resources" (R2), which is a Scan. Any GSI added to this table would exist to avoid that Scan — but at ≤20 items, the Scan is cheaper than the GSI write overhead accumulated over thousands of simulator ticks.

#### Attribute Reference

| Attribute | Type | Required | Description |
|---|---|---|---|
| `resource_id` | `S` | ✅ PK | Unique resource identifier. Format: `{TYPE}-{NNN}` e.g. `VM-001` |
| `resource_type` | `S` | ✅ | Resource category. Values: `VM` \| `API` \| `DB` \| `STORAGE` |
| `current_state` | `S` | ✅ | Current state machine state. See `ResourceState` enum below |
| `health_status` | `S` | ✅ | Derived health label. Values: `HEALTHY` \| `DEGRADED` \| `CRITICAL` |
| `cpu_utilization` | `N` | ✅ | CPU load percentage. Range: `0.0` – `100.0` |
| `memory_utilization` | `N` | ✅ | Memory usage percentage. Range: `0.0` – `100.0` |
| `storage_utilization` | `N` | ✅ | Storage usage percentage. Range: `0.0` – `100.0` |
| `network_latency_ms` | `N` | ✅ | Simulated network latency in milliseconds. Range: `0.0` – `99999.0` |
| `last_heartbeat` | `S` | ✅ | ISO8601 UTC timestamp of last simulator tick for this resource |
| `active_failure_type` | `S` | ❌ optional | Failure type currently active. Absent when resource is healthy. Values: `HIGH_CPU` \| `SERVICE_FAILURE` \| `NETWORK_LATENCY` \| `STORAGE_EXHAUSTION` \| `MEMORY_LEAK` |
| `updated_at` | `S` | ✅ | ISO8601 UTC timestamp of the last DynamoDB write to this item |
| `created_at` | `S` | ✅ | ISO8601 UTC timestamp when this resource was first seeded |
| `description` | `S` | ❌ optional | Human-readable description of the resource's role |
| `tags` | `M` | ❌ optional | Freeform key-value metadata map, e.g. `{"env": "demo", "region": "us-east-1"}` |

**`ResourceState` Enum Values** (valid values for `current_state`):

| Value | Meaning |
|---|---|
| `HEALTHY` | Resource operating normally |
| `WARNING` | Metrics approaching thresholds; not yet a failure |
| `FAILURE_DETECTED` | Metric threshold breached; awaiting Recovery Lambda |
| `RECOVERY_INITIATED` | Recovery Lambda has claimed this incident |
| `RECOVERY_IN_PROGRESS` | Recovery action is actively executing |
| `RECOVERED` | Recovery action succeeded; resource back to normal |
| `RECOVERY_FAILED` | Recovery action threw an exception |
| `MANUAL_INTERVENTION_REQUIRED` | Max recovery retries exceeded; human action needed |

#### Example Item

```json
{
  "resource_id":         "VM-001",
  "resource_type":       "VM",
  "current_state":       "FAILURE_DETECTED",
  "health_status":       "CRITICAL",
  "cpu_utilization":     95.0,
  "memory_utilization":  60.3,
  "storage_utilization": 21.7,
  "network_latency_ms":  82.4,
  "last_heartbeat":      "2026-09-08T15:00:00Z",
  "active_failure_type": "HIGH_CPU",
  "updated_at":          "2026-09-08T15:00:01Z",
  "created_at":          "2026-09-08T10:00:00Z",
  "description":         "Primary application VM in us-east-1a",
  "tags": {
    "env":    "demo",
    "region": "us-east-1",
    "tier":   "compute"
  }
}
```

> **Number Serialization Note:** `cpu_utilization`, `memory_utilization`, `storage_utilization`, and `network_latency_ms` are stored as DynamoDB type `N` (Number). boto3's `TypeDeserializer` returns them as `Decimal` objects. The repository layer converts them to Python `float` via `float(value)` before constructing Pydantic models. See [Section 6](#6-serialization-notes) for full details.

---

### 4.2 Table: `cloudpulse-incidents-{env}`

**Purpose:** Append-mostly incident log. Each item represents one detected failure event and is updated in-place as recovery progresses through the state machine. Recovery actions are embedded as a `List` attribute — no separate table is used.

**Billing:** `PAY_PER_REQUEST` (on-demand)
**Table Class:** `STANDARD_INFREQUENT_ACCESS`
**Streams:** Not enabled

#### Key Schema

| Key | Attribute | Type | Description |
|---|---|---|---|
| Partition Key (PK) | `incident_id` | `S` | UUID v4 string. Unique per incident. High cardinality ensures even shard distribution. |
| Sort Key | — | — | No table-level sort key. Sorted access provided exclusively via GSIs. |

> **UUID v4 as PK:** Using UUID v4 guarantees even distribution across DynamoDB partitions (high entropy in the first 4 bytes avoids hot-shard problems). Sequential IDs (like timestamp prefixes) would cause all writes to concentrate on a single partition shard — a classic DynamoDB anti-pattern.

> **No Table Sort Key:** The incident is accessed by ID for direct lookup (I1) and by GSI for sorted access (I2–I7). Adding a table-level SK would complicate the PK-only GetItem with no benefit.

#### Attribute Reference

| Attribute | Type | Required | Description |
|---|---|---|---|
| `incident_id` | `S` | ✅ PK | UUID v4. Primary identifier for direct `GetItem` lookup |
| `resource_id` | `S` | ✅ | The resource that failed. GSI-1 PK. Logical FK to `cloudpulse-resources` |
| `failure_type` | `S` | ✅ | Category of failure. GSI-3 PK. Values: `HIGH_CPU` \| `SERVICE_FAILURE` \| `NETWORK_LATENCY` \| `STORAGE_EXHAUSTION` \| `MEMORY_LEAK` |
| `severity` | `S` | ✅ | Impact severity. Values: `LOW` \| `MEDIUM` \| `HIGH` \| `CRITICAL` |
| `status` | `S` | ✅ | Lifecycle status. GSI-2 PK. Values: `OPEN` \| `RECOVERING` \| `RESOLVED` \| `ESCALATED` |
| `detected_at` | `S` | ✅ | ISO8601 UTC when the failure was first detected. **Sort Key for GSI-1, GSI-2, GSI-3** |
| `state_at_detection` | `S` | ✅ | `ResourceState` value at the moment the incident was created |
| `state_at_resolution` | `S` | ❌ optional | `ResourceState` value at resolution time. Absent until resolved |
| `recovery_initiated_at` | `S` | ❌ optional | ISO8601 UTC when Recovery Lambda first claimed this incident |
| `resolved_at` | `S` | ❌ optional | ISO8601 UTC when status transitioned to `RESOLVED` or `ESCALATED` |
| `escalated_at` | `S` | ❌ optional | ISO8601 UTC when max retries were exceeded and status became `ESCALATED` |
| `duration_seconds` | `N` | ❌ optional | Seconds between `detected_at` and `resolved_at`. Computed at close time |
| `recovery_attempts` | `N` | ✅ | Count of recovery attempts made. Starts at `0`; increments on each action |
| `recovery_actions` | `L` | ✅ | List of embedded `RecoveryAction` maps. Empty list `[]` initially |
| `notification_sent` | `BOOL` | ✅ | `true` if an SNS notification was published for this incident |
| `updated_at` | `S` | ✅ | ISO8601 UTC timestamp of the most recent `UpdateItem` call on this item |

#### Embedded RecoveryAction Map Structure

Each element of the `recovery_actions` list (`L`) is a DynamoDB Map (`M`) with the following attributes:

| Attribute | Type | Required | Description |
|---|---|---|---|
| `action_id` | `S` | ✅ | UUID v4. Unique within the parent incident's `recovery_actions` list |
| `action_type` | `S` | ✅ | The simulated remediation performed. Values: `SCALE_OUT` \| `SERVICE_RESTART` \| `STORAGE_CLEANUP` \| `NETWORK_REROUTE` \| `FAILOVER` \| `MANUAL` |
| `status` | `S` | ✅ | Outcome of this action. Values: `PENDING` \| `IN_PROGRESS` \| `SUCCEEDED` \| `FAILED` |
| `started_at` | `S` | ✅ | ISO8601 UTC when this specific action began execution |
| `completed_at` | `S` | ❌ optional | ISO8601 UTC when this action finished. Absent while `IN_PROGRESS` or `PENDING` |
| `outcome_message` | `S` | ✅ | Human-readable description of what happened. Always present |
| `error_detail` | `S` | ❌ optional | Exception message or traceback. Present only when `status=FAILED` |

> **Embedded vs. Separate Table:** RecoveryActions are embedded in the Incident item rather than stored in a separate table. This avoids the need for cross-table DynamoDB transactions when atomically creating an incident and its first recovery action. At up to 10 recovery actions per incident (see [Section 5](#5-dynamodb-item-limits--constraints)), the embedded list stays well within the 400KB item size limit.

#### Example Item (Resolved Incident with One Recovery Action)

```json
{
  "incident_id":           "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "resource_id":           "VM-001",
  "failure_type":          "HIGH_CPU",
  "severity":              "HIGH",
  "status":                "RESOLVED",
  "detected_at":           "2026-09-08T15:00:00Z",
  "state_at_detection":    "FAILURE_DETECTED",
  "state_at_resolution":   "RECOVERED",
  "recovery_initiated_at": "2026-09-08T15:00:05Z",
  "resolved_at":           "2026-09-08T15:00:13Z",
  "duration_seconds":      13,
  "recovery_attempts":     1,
  "recovery_actions": [
    {
      "action_id":       "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "action_type":     "SCALE_OUT",
      "status":          "SUCCEEDED",
      "started_at":      "2026-09-08T15:00:05Z",
      "completed_at":    "2026-09-08T15:00:13Z",
      "outcome_message": "Simulated scale-out: increased virtual CPU allocation from 4 to 8 vCPUs. CPU utilization dropped from 95% to 38%."
    }
  ],
  "notification_sent": true,
  "updated_at":        "2026-09-08T15:00:13Z"
}
```

> **Optional Field Absence:** `state_at_resolution`, `recovery_initiated_at`, `resolved_at`, `escalated_at`, and `duration_seconds` are absent from the DynamoDB item until they are set. DynamoDB does not store `null`-valued attributes — the repository layer strips `None` values before calling `put_item` or `update_item`. See [Section 6](#6-serialization-notes).

#### Global Secondary Indexes

| GSI Name | GSI PK | GSI SK | Projection | Access Patterns Served | Justification |
|---|---|---|---|---|---|
| `ResourceIndex` (GSI-1) | `resource_id` (S) | `detected_at` (S) | `ALL` | I2, I6 | List all incidents for a specific resource, sorted by detection time. Used on every dashboard resource-detail page load. |
| `StatusIndex` (GSI-2) | `status` (S) | `detected_at` (S) | `ALL` | I3, I7 | List active incidents (`OPEN`, `RECOVERING`) and resolved incidents by status. Avoids full table Scan for real-time active incident feed. |
| `FailureTypeIndex` (GSI-3) | `failure_type` (S) | `detected_at` (S) | `ALL` | I4 | Analytics — group and sort incidents by failure category. Enables "top failure types" dashboard panel. |

> **GSI-1 ResourceIndex Detail:** Every incident write and every state update also updates GSI-1 because `resource_id` and `detected_at` are always present. A query `resource_id=VM-001, ScanIndexForward=False` returns that resource's incidents newest-first. Reversing `ScanIndexForward=True` gives the oldest-first history view (I6). One GSI serves two access patterns.

> **GSI-2 StatusIndex Detail:** `status` has only four values. This makes `status` a low-cardinality partition key, which means each GSI-2 partition shard could become hot for busy deployments. At CloudPulse's academic scale (dozens to hundreds of incidents), this is not a concern. A production system with millions of incidents per status value would shard further by appending a random suffix to the status key.

> **GSI-3 FailureTypeIndex Detail:** `failure_type` has five possible values. Querying `failure_type=HIGH_CPU, ScanIndexForward=False` returns the most recent HIGH_CPU incidents — directly serving the analytics panel without scanning the full table.

---

### 4.3 Table: `cloudpulse-metrics-{env}`

**Purpose:** Pre-computed reliability metric snapshots. These are calculated by the Recovery Lambda on incident resolution and by a scheduled aggregator. The table is a *materialized view* — it stores derived data computed from the Incidents table.

**Billing:** `PAY_PER_REQUEST` (on-demand)
**Table Class:** `STANDARD_INFREQUENT_ACCESS`
**Streams:** Not enabled

#### Key Schema

| Key | Attribute | Type | Description |
|---|---|---|---|
| Partition Key (PK) | `resource_id` | `S` | Which resource this snapshot belongs to |
| Sort Key (SK) | `window_key` | `S` | Composite window identifier. Format: `{WINDOW_TYPE}#{DATE_OR_SENTINEL}` |

**`window_key` format examples:**

| `window_key` value | Meaning |
|---|---|
| `DAILY#2026-09-08` | Daily snapshot for September 8, 2026 |
| `DAILY#2026-09-07` | Daily snapshot for September 7, 2026 |
| `WEEKLY#2026-09-07` | Weekly snapshot starting the week of September 7, 2026 (ISO week) |
| `CUMULATIVE#ALL` | All-time cumulative snapshot for this resource |

> **SK Design:** Prefixing with `WINDOW_TYPE#` enables `begins_with(SK, "DAILY#")` queries to fetch only daily snapshots for a resource. The date suffix `YYYY-MM-DD` is lexicographically sortable, so `ScanIndexForward=False, Limit=1, begins_with(SK, "DAILY#")` returns the most recent daily snapshot in a single `Query` call (access pattern M3).

> **`CUMULATIVE#ALL` as a fixed SK:** The cumulative snapshot uses the literal sentinel `ALL` instead of a date. This makes it directly addressable via `GetItem(PK="VM-001", SK="CUMULATIVE#ALL")` and ensures it sorts before `DAILY#` items (alphabetically: `C < D`). The cumulative snapshot is upserted in-place on every incident resolution.

#### Attribute Reference

| Attribute | Type | Required | Description |
|---|---|---|---|
| `resource_id` | `S` | ✅ PK | Which resource this metric snapshot describes |
| `window_key` | `S` | ✅ SK | Window type + date composite key. See format above |
| `window_type` | `S` | ✅ | Human-readable window classification: `DAILY` \| `WEEKLY` \| `CUMULATIVE` |
| `window_start` | `S` | ✅ | ISO8601 UTC start of the measurement window |
| `window_end` | `S` | ✅ | ISO8601 UTC end of the measurement window. For `CUMULATIVE`, this is the time the snapshot was last computed |
| `total_incidents` | `N` | ✅ | Total number of incidents that occurred in this window for this resource |
| `resolved_incidents` | `N` | ✅ | Incidents with final status `RESOLVED` (successful recovery) |
| `failed_recoveries` | `N` | ✅ | Incidents with final status `ESCALATED` (recovery exhausted all retries) |
| `mttr_seconds` | `N` | ❌ optional | Mean Time To Recover in seconds. `sum(duration_seconds) / resolved_incidents`. Absent if `resolved_incidents = 0` |
| `mtbf_seconds` | `N` | ❌ optional | Mean Time Between Failures in seconds. Absent if fewer than 2 incidents in window |
| `availability_pct` | `N` | ❌ optional | Estimated availability percentage. Computed as `(window_duration - total_downtime) / window_duration × 100`. Absent until calculable |
| `failure_type_counts` | `M` | ✅ | Map of `failure_type → count` for all incidents in this window. e.g. `{"HIGH_CPU": 3, "NETWORK_LATENCY": 1}` |
| `computed_at` | `S` | ✅ | ISO8601 UTC timestamp when this snapshot was last computed or updated |

> **Materialized View Pattern:** `ReliabilityMetric` items are *derived* from `Incident` data. They are not the source of truth — they are pre-aggregated snapshots designed to make dashboard reads O(1) (a `GetItem`) instead of expensive `Query + aggregate` operations over the full incidents table. The trade-off is that they must be kept in sync with the incidents table by the Recovery Lambda.

#### Example Item

```json
{
  "resource_id":        "VM-001",
  "window_key":         "DAILY#2026-09-08",
  "window_type":        "DAILY",
  "window_start":       "2026-09-08T00:00:00Z",
  "window_end":         "2026-09-08T23:59:59Z",
  "total_incidents":    4,
  "resolved_incidents": 3,
  "failed_recoveries":  1,
  "mttr_seconds":       9.3,
  "mtbf_seconds":       3720.0,
  "availability_pct":   99.81,
  "failure_type_counts": {
    "HIGH_CPU":           2,
    "NETWORK_LATENCY":    1,
    "STORAGE_EXHAUSTION": 1
  },
  "computed_at": "2026-09-08T18:05:00Z"
}
```

#### No GSIs on Metrics Table

All metric access patterns are served by the `(resource_id, window_key)` base table key:

| Access Pattern | Operation | Key Expression |
|---|---|---|
| Get snapshot for resource + specific window | `GetItem` | `PK=resource_id, SK=window_key` |
| List all DAILY snapshots for a resource | `Query` | `PK=resource_id, begins_with(SK, "DAILY#")` |
| Get latest DAILY snapshot for a resource | `Query` | `PK=resource_id, begins_with(SK, "DAILY#"), ScanIndexForward=False, Limit=1` |
| Get cumulative stats for a resource | `GetItem` | `PK=resource_id, SK="CUMULATIVE#ALL"` |
| List all snapshots of any type for a resource | `Query` | `PK=resource_id` (no SK condition) |

> **No cross-resource queries:** The metrics table is never queried across resources (e.g., "find the resource with the highest MTTR"). Cross-resource aggregations are handled in application memory after fetching each resource's snapshot via individual `GetItem` calls — the resource list is bounded at ≤20 items.

---

## 5. DynamoDB Item Limits & Constraints

| Constraint | Limit | CloudPulse Behaviour |
|---|---|---|
| Maximum item size | **400 KB** | All tables are well under limit. The largest items (Incidents with full recovery_actions) are estimated at ~5–15 KB. |
| `recovery_actions` list per incident | ~100 actions before approaching 400 KB | CloudPulse **caps at 10 recovery actions** per incident. Beyond 10, the incident is escalated to `MANUAL_INTERVENTION_REQUIRED`. |
| `failure_type_counts` map keys | No DynamoDB limit | CloudPulse has exactly **5 failure types** — map has at most 5 keys. |
| DynamoDB number precision | Arbitrary-precision decimal stored as string internally by DynamoDB | boto3 returns numbers as Python `Decimal`. CloudPulse converts to `float` at repository boundary. Precision loss for values beyond `float64` range is not a concern here. |
| String attribute length | 400 KB (per attribute) | ISO8601 timestamps (~25 chars), UUIDs (36 chars), and enum strings (<30 chars) are far below this limit. |
| GSI write overhead | One write unit per GSI per item write | Each incident write consumes **4 write units** (1 base table + 3 GSIs). At ~100 incidents/month, this is negligible. |
| `NULL` type | DynamoDB supports a NULL type | CloudPulse **does not write NULL** typed attributes. Optional absent fields are omitted entirely from the item. |

> **Why cap recovery_actions at 10?** In a real production system, a cascading failure could generate hundreds of recovery attempts. Embedded list growth without a cap would eventually cause an item to exceed 400 KB, making `UpdateItem` return a `ValidationException`. CloudPulse enforces the cap in the Recovery Lambda before appending a new action.

---

## 6. Serialization Notes

The CloudPulse repository layer handles a set of DynamoDB-specific serialization concerns that differ from a standard relational database ORM.

### 6.1 Numbers: Decimal → Float

**Problem:** DynamoDB's `N` type is stored internally as an arbitrary-precision decimal string. The boto3 DynamoDB resource (when using `Table.get_item()`) deserializes numbers as Python `Decimal` objects to avoid floating-point precision loss.

**Solution:** The repository layer converts `Decimal` to `float` using `float(value)` before constructing Pydantic model instances. Pydantic fields are declared as `float`, not `Decimal`, so the conversion must happen in the repository — not in the model.

```python
# Repository deserialization pattern
item["cpu_utilization"] = float(item["cpu_utilization"])
```

### 6.2 None Values: Exclusion Before Write

**Problem:** DynamoDB does not allow writing a `null`-typed attribute using the standard `put_item` with the boto3 resource in `STANDARD` mode. Attempting to write `{"field": None}` raises a `ParamValidationError`.

**Solution:** The repository strips `None` values from item dictionaries before any `put_item` or `update_item` call:

```python
# Strip None values before writing
item = {k: v for k, v in raw_item.items() if v is not None}
table.put_item(Item=item)
```

This means optional attributes are simply *absent* from the DynamoDB item when they have no value — they are not present as `null`. When reading back, missing attributes are handled by Pydantic's `Optional[T] = None` field defaults.

### 6.3 Datetimes: ISO 8601 Strings

**Problem:** DynamoDB has no `DateTime` type.

**Solution:** All timestamps are stored as ISO 8601 UTC strings using Python's `datetime.isoformat()`:

```python
import datetime
# Normalize to Z suffix:
timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
# → "2026-09-08T15:00:00Z"
```

On read, Pydantic validators parse the string back to a `datetime` object. ISO 8601 strings in UTC format sort correctly as strings — critical for GSI sort key behaviour.

### 6.4 Booleans

**Problem:** DynamoDB has a native `BOOL` type, but boto3 must be told to use it.

**Solution:** boto3's DynamoDB resource handles Python `bool` values (`True` / `False`) natively and maps them to DynamoDB's `BOOL` type. No manual conversion is needed. `notification_sent` is stored as a `BOOL` item.

```python
item["notification_sent"] = True  # boto3 writes as DynamoDB BOOL
```

### 6.5 Enums: Stored as String Values

**Problem:** Pydantic `Enum` instances are not JSON/DynamoDB serializable by default.

**Solution:** All enum values are stored as their string `.value` representation:

```python
# Write
item["status"] = incident.status.value        # e.g., "RESOLVED"
item["failure_type"] = incident.failure_type.value  # e.g., "HIGH_CPU"

# Read — Pydantic deserializes string back to enum automatically
# when the field is declared as: status: IncidentStatus
```

Pydantic models with `str`-based enums (inheriting from both `str` and `Enum`) handle this transparently.

### 6.6 Embedded Maps and Lists

DynamoDB `M` (Map) and `L` (List) types are used for `tags`, `failure_type_counts`, and `recovery_actions`. boto3 handles nested Python dicts and lists natively:

```python
# failure_type_counts is a plain Python dict
item["failure_type_counts"] = {"HIGH_CPU": 3, "NETWORK_LATENCY": 1}

# recovery_actions is a list of dicts
item["recovery_actions"] = [
    {"action_id": "...", "action_type": "SCALE_OUT", ...}
]
```

On read, boto3 returns these as Python `dict` and `list` respectively. The Pydantic model validates them into typed `dict[str, int]` and `list[RecoveryAction]` objects.

---

## 7. Capacity & Cost Estimate

All tables use `PAY_PER_REQUEST` billing. There are no provisioned WCU/RCU settings. Costs scale linearly with actual I/O.

| Table | Estimated Write Rate | Estimated Read Rate | Monthly Total |
|---|---|---|---|
| `cloudpulse-resources-{env}` | ~21,600/month (2-min simulator × 4 resources × 30 days) | ~43,200/month (10s API polling × 20 items per scan) | **$0.00** (Free Tier) |
| `cloudpulse-incidents-{env}` | ~100–500/month (incident creates + ~5 updates each × 4 WCU per write due to 3 GSIs) | ~200–1,000/month (dashboard reads + GSI queries) | **$0.00** (Free Tier) |
| `cloudpulse-metrics-{env}` | ~100–500/month (snapshot upserts on incident resolution) | ~400–2,000/month (dashboard metric panel reads) | **$0.00** (Free Tier) |
| **Total** | | | **~$0.00/month** |

**DynamoDB Free Tier (per account, per region):**
- 25 GB storage
- 200 million read request units per month
- 200 million write request units per month

CloudPulse's projected usage is:
- Storage: < 1 MB (far below 25 GB)
- Reads: < 100,000/month (far below 200M)
- Writes: < 50,000/month (far below 200M)

> **GSI Write Multiplier:** Each write to `cloudpulse-incidents` consumes write capacity for the base table **plus** one write per GSI. With 3 GSIs, an incident `put_item` costs 4 WCUs (1 base + 3 GSIs). An `update_item` that modifies a GSI key attribute (e.g., changing `status`) also costs 4 WCUs. An `update_item` that does not touch any GSI key attribute costs only 1 WCU. CloudPulse incident updates (adding a recovery action or updating status) almost always modify `status` — a GSI-2 PK — so most updates cost 4 WCUs.

---

## 8. SAM Template GSI Summary

The SAM template (`infrastructure/template.yaml`) defines the following GSI configurations:

### `cloudpulse-incidents-{env}` — 3 GSIs

```yaml
GlobalSecondaryIndexes:
  - IndexName: ResourceIndex
    KeySchema:
      - AttributeName: resource_id
        KeyType: HASH
      - AttributeName: detected_at
        KeyType: RANGE
    Projection:
      ProjectionType: ALL

  - IndexName: StatusIndex
    KeySchema:
      - AttributeName: status
        KeyType: HASH
      - AttributeName: detected_at
        KeyType: RANGE
    Projection:
      ProjectionType: ALL

  - IndexName: FailureTypeIndex
    KeySchema:
      - AttributeName: failure_type
        KeyType: HASH
      - AttributeName: detected_at
        KeyType: RANGE
    Projection:
      ProjectionType: ALL
```

All three GSIs share `detected_at` as the Sort Key because time-ordered results are the primary need for every GSI query pattern.

### `cloudpulse-resources-{env}` — 0 GSIs

No GSIs defined. Scan is the only list operation and is justified by bounded item count.

### `cloudpulse-metrics-{env}` — 0 GSIs

No GSIs defined. The composite `(resource_id, window_key)` base table key serves all access patterns via `GetItem` and `Query`.

### GSI Overview Table

| Table | GSI Name | PK | SK | Projection | Serves |
|---|---|---|---|---|---|
| `cloudpulse-incidents` | `ResourceIndex` | `resource_id` | `detected_at` | `ALL` | I2, I6 |
| `cloudpulse-incidents` | `StatusIndex` | `status` | `detected_at` | `ALL` | I3, I7 |
| `cloudpulse-incidents` | `FailureTypeIndex` | `failure_type` | `detected_at` | `ALL` | I4 |
| `cloudpulse-resources` | — | — | — | — | No GSIs |
| `cloudpulse-metrics` | — | — | — | — | No GSIs |

---

*End of DATABASE_DESIGN.md — CloudPulse DynamoDB Schema Reference v1.1*
