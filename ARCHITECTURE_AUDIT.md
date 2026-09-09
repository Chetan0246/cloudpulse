# ARCHITECTURE AUDIT — CloudPulse
**Auditor:** Principal Cloud Architect review  
**Date:** 2026-09-09  
**Project:** CloudPulse — Autonomous Cloud Reliability and Self-Healing Simulator  
**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Baseline test counts:** 348 backend / 49 frontend — all passing before audit.

---

## Summary Table

| ID | Area | Finding | Severity | Status |
|----|------|---------|----------|--------|
| A-01 | IAM | CloudWatch `PutMetricData Resource: "*"` — AWS does not support resource ARNs here; namespace condition is the only control | LOW | Accepted |
| A-02 | SAM / API GW | Default `CorsAllowedOrigins: "*"` — any origin allowed in production | **HIGH** | **Fixed** |
| A-03 | FastAPI CORS | `allow_methods` includes `PUT` and `DELETE` — no router defines those verbs | MEDIUM | **Fixed** |
| A-04 | DynamoDB | `IncidentRepository.list()` does a full table Scan; ResourceIndex GSI exists but is unused | MEDIUM | Accepted (academic scale) |
| A-05 | Architecture | `/simulate/reset` does NOT emit EventBridge; recovery is inline — inconsistent with autonomous path | LOW | Documented |
| A-06 | Recovery Lambda | Parse error returns HTTP 400 — Lambda treats this as success, bypasses DLQ | **HIGH** | **Fixed** |
| A-07 | Recovery Lambda | `dispatch_strategy()` called twice per invocation (preview + execute) | LOW | **Fixed** |
| A-08 | Domain model | CamelCase `@computed_field` blocks duplicated verbatim in Incident, IncidentSummary, IncidentDetail | MEDIUM | Accepted |
| A-09 | Python | `import re` inside validator method body in resource.py | LOW | **Fixed** |
| A-10 | DynamoDB | `IncidentRepository.update()` uses unconditional `put_item` — race-condition window | **HIGH** | **Fixed** |
| A-11 | Architecture | Incident written by API Lambda AND may be matched by Recovery Lambda — dual write path undocumented | MEDIUM | Documented |
| A-12 | S3 | `WebsiteConfiguration` always attached even when public access disabled | LOW | Accepted |
| A-13 | CloudWatch | FS-02 (SERVICE_FAILURE) and FS-04 (NETWORK_LATENCY) share the same alarm; wrong recovery action on autonomous path | **HIGH** | Documented |
| A-14 | EventBridge | `SERVICE_HEALTH` alarms match `cloudpulse-*` rule; `_parse_event` cannot parse SERVICE_HEALTH as FailureType — silent discard | **CRITICAL** | **Fixed** |
| A-15 | DynamoDB | MetricsTable has no TTL — unbounded growth of time-windowed snapshots | MEDIUM | Documented |
| A-16 | Testing | No tests for `_parse_event` edge cases (SERVICE_HEALTH alarm, unknown source) | MEDIUM | **Fixed** |
| A-17 | Cost | 16 custom CloudWatch metrics slightly exceeds 10-metric free tier | LOW | Accepted |
| A-18 | IAM | `ApiFunctionRole` has `dynamodb:Scan` on IncidentsTable; Query on GSI is sufficient | LOW | **Fixed** |
| A-19 | Notifications | RECOVERY_STARTED sent before strategy executes; user may receive STARTED then FAILED for same attempt | LOW | Accepted |
| A-20 | Parser | `_parse_event` alarm-name loop is O(n) over suffix combinations | LOW | Accepted |

---

## CRITICAL

### A-14 — SERVICE_HEALTH alarms route to Recovery Lambda; `_parse_event` silently fails

**Root cause:** Template creates alarms named `cloudpulse-VM-001-SERVICE_HEALTH` etc. The EventBridge rule
`cloudpulse-alarm-rule` matches ALL `cloudpulse-*` alarm names in ALARM state. When `_parse_event`
receives `alarmName="cloudpulse-VM-001-SERVICE_HEALTH"`, it tries every suffix combination:
`HEALTH`, `SERVICE_HEALTH` — neither is a valid `FailureType`. The loop exits, `ValueError` is raised,
the handler catches it, and returns `{"statusCode": 400}`. Lambda marks the invocation **successful**,
no DLQ message is produced, the event is silently lost.

**Impact:** Any autonomous detection via the composite ServiceHealth alarm produces zero recovery. The
alarm-driven self-healing path is broken for this alarm family.

**Fix:** Two-part:
1. Add an `alarmName` exclusion to the EventBridge rule pattern to skip `SERVICE_HEALTH` alarms.
2. In `_parse_event`, after the loop exhaustion, raise `ValueError` explicitly (also fixes A-06).

---

## HIGH

### A-02 — Default CORS origin `"*"`

Default `CorsAllowedOrigins` SAM parameter is `"*"`. Propagated to both API Gateway CORS
config and FastAPI middleware. Any web page can call the API cross-origin.

**Fix:** Changed default to `"http://localhost:5173"`.

---

### A-06 — Recovery Lambda parse error bypasses DLQ

On unknown event source, handler returns `{"statusCode": 400}` — Lambda treats non-exception
returns as successes, DLQ not triggered.

**Fix:** Re-raise `ValueError` after logging so Lambda's retry policy and DLQ engage.

---

### A-10 — `IncidentRepository.update()` unconditional `put_item`

Full-item overwrite with no condition expression. Concurrent writes (API reset racing
with Recovery Lambda) can silently clobber each other's `recovery_actions` list.

**Fix:** Added `ConditionExpression="attribute_exists(incident_id)"` as a minimum guard.

---

### A-13 — FS-02 and FS-04 share the same CloudWatch alarm

Both `SERVICE_FAILURE` and `NETWORK_LATENCY` are detected by `NetworkLatency ≥ 500ms`.
The alarm name encodes only the metric name, not the business failure type. On the autonomous
alarm-driven path, the Recovery Lambda always selects the `NETWORK_LATENCY` recovery strategy
even for a `SERVICE_FAILURE` condition.

**Impact:** Wrong recovery action type recorded in the audit trail on autonomous path.
Direct-injection path (POST /simulate/failure) is unaffected — it carries the exact `failureType`
in the EventBridge event detail.

**Decision:** Documented. Adding a dedicated `SERVICE_FAILURE` alarm on a different metric
(e.g., ServiceHealth or a synthetic error-rate metric) would resolve this but requires a
new metric to be defined. Out of scope for this audit.

---

## MEDIUM

### A-03 — FastAPI CORS permits `PUT` and `DELETE`

No router defines PUT or DELETE. The methods are allowed by CORS middleware unnecessarily.
**Fix:** Removed from `allow_methods`.

### A-04 — Full table Scan in `IncidentRepository.list()`

ResourceIndex GSI (PK: resource_id) is provisioned in the template but not used by `list()`.
For the academic dataset size (< 200 incidents) the scan is correct. **TODO comment added.**

### A-08 — CamelCase computed field duplication (3× across model classes)

`Incident`, `IncidentSummary`, `IncidentDetail` each define ~9 identical computed field methods.
No correctness impact. Refactoring deferred.

### A-11 — Dual incident write path (API + Lambda)

`POST /simulate/failure` creates the incident and emits a `FailureInjected` event with the
`incidentId` in the detail. Recovery Lambda finds the existing incident and reuses it correctly.
The CloudWatch alarm path creates a fresh incident (also correct). Undocumented but functional.

### A-15 — MetricsTable has no TTL

Items accumulate indefinitely. Negligible for a demo but architecturally incorrect for a
time-series snapshot store. A 30-day TTL is a 2-line IaC addition (deferred).

### A-16 — Missing `_parse_event` unit tests

No test covers: multi-hyphen resource ID (`STORAGE-001-STORAGE_EXHAUSTION`), composite alarm
name (`VM-001-SERVICE_HEALTH`), unknown source. **New tests added.**

---

## LOW

### A-01 — CloudWatch `PutMetricData Resource: "*"`
AWS limitation — namespace condition key is the only available scope control. Correctly documented.

### A-05 — Manual reset bypasses EventBridge
By design — operator action, not autonomous recovery event. Documented.

### A-07 — `dispatch_strategy` called twice
Stored as one variable and reused. **Fixed.**

### A-09 — `import re` inside validator method
Moved to module level. **Fixed.**

### A-12 — S3 WebsiteConfiguration always present
No data exposure when public access is blocked. Acceptable.

### A-17 — 16 metrics exceeds 10-metric free tier
~$0.30/month overage. Acknowledged in ARCHITECTURE.md.

### A-18 — `dynamodb:Scan` on IncidentsTable
Changed to `dynamodb:Query` in `ApiFunctionRole`. **Fixed.**

### A-19 — STARTED notification before strategy executes
Intentional — gives visibility to slow recoveries. Accepted.

### A-20 — O(n) alarm name parser
Correct. Max 5 FailureType values. Acceptable.

---

## Architecture Conformance Summary

| Principle | Status |
|-----------|--------|
| Only approved AWS services used | ✅ |
| Each Lambda has own IAM role | ✅ |
| IAM least-privilege | ✅ (minor A-18 fixed) |
| No real AWS resource modification | ✅ Confirmed |
| No hardcoded secrets | ✅ |
| Config via environment variables | ✅ |
| Idempotent recovery (two-layer guard) | ✅ |
| DLQ for recovery failures | ✅ (after A-06 fix) |
| Log groups with 7-day retention | ✅ All 4 defined |
| DynamoDB on-demand billing | ✅ |
| arm64 Lambda (cost efficiency) | ✅ All 3 functions |
| Recovery state machine (8 states) | ✅ |
| Alarm naming convention | ⚠️ SERVICE_HEALTH violates (A-14 fixed) |
| CORS origin restriction | ⚠️ Default was "*" (A-02 fixed) |

---

## Remaining Accepted Trade-offs

1. **No CloudFront** — S3 website is HTTP-only. Acceptable for academic demo.
2. **No API authentication** — All data is synthetic; API cannot touch real infrastructure.
3. **DynamoDB full scans** — Bounded dataset; free-tier cost is zero.
4. **FS-02/FS-04 alarm ambiguity** — Demo path (direct injection) always correct; alarm path uses wrong action type. Acceptable.
5. **DLQ not alarmed** — No alert on DLQ depth > 0. Production gap documented.
6. **MetricsTable no TTL** — Technical debt flagged, deferred.
7. **Lambda cold start 1-2s** — Documented and accepted in ADR-006.

---

## Free-Tier Risk

| Service | Free Limit | Estimated Usage | Over-limit cost |
|---------|-----------|----------------|-----------------|
| Lambda | 1M req + 400K GB-s/month | ~22K events | ✅ None |
| DynamoDB | 25 GB + 200M req/month | <1 MB + ~50K req | ✅ None |
| CloudWatch Metrics | 10 free | 16 used | ~$0.30/mo |
| CloudWatch Alarms | 10 free | 15 used | ~$0.50/mo |
| S3 | 5 GB + 20K GET | Minimal | ✅ None |
| SNS | 1K email/month | <100 emails | ✅ None |
| **Total** | | | **~$0.80/month** |
