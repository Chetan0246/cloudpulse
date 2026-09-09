# CloudPulse — Comprehensive QA & Test Execution Report

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Evaluation Milestone:** Project Review 2  
**Test Harness:** `pytest` 8.x, `moto` (AWS in-memory mocking), `vitest`, `@testing-library/react`  
**Execution Timestamp:** 2026-09-09 | Release Candidate Verification  
**Overall Status:** **100% PASS (416 / 416 Total Tests Across Backend & Frontend)**  

---

## 1. Test Execution Summary

```
============================= BACKEND TEST SUMMARY =============================
Platform: Linux (Python 3.12 / pytest)
Executed Layers: 9 Testing Layers + Edge Cases & Resilience
Results: 367 passed in 9.41s
Failures: 0 | Errors: 0 | Skipped: 0

============================ FRONTEND TEST SUMMARY =============================
Platform: Node.js 20 / Vitest 2.1.8
Executed Suites: 17 Test Files (Components, Gauges, Sections, App)
Results: 49 passed in 4.71s
Failures: 0 | Errors: 0 | Skipped: 0

============================ STATIC ANALYSIS & IAC =============================
TypeScript Compiler (tsc --noEmit): 0 errors, 0 warnings
AWS SAM Validation (sam validate --lint): Valid SAM Template (Clean Pass)
```

---

## 2. Granular Backend Test Layer Breakdown (367 Tests)

| Layer # | Testing Layer & Scope | Primary Test Files | Test Count | Status |
|---|---|---|---|---|
| **Layer 1** | **Unit Layer:** Domain models, enums, Pydantic validators, mathematical calculations | `tests/unit/test_unit_layer.py`<br/>`tests/unit/test_reliability_calculator.py`<br/>`backend/tests/unit/test_recovery_strategies.py` | 82 | ✅ PASS |
| **Layer 2** | **Event Parser Unit Tests:** Alarm name parsing, multi-hyphen IDs, error boundaries | `tests/unit/test_parse_event.py` | 19 | ✅ PASS |
| **Layer 3** | **API Layer:** REST routes, HTTP verbs, path/query validation, error codes | `tests/api/test_api_layer.py`<br/>`backend/tests/unit/test_resources_router.py`<br/>`backend/tests/unit/test_incidents_router.py`<br/>`backend/tests/unit/test_simulate_router.py` | 64 | ✅ PASS |
| **Layer 4** | **Integration Layer:** Repository data translation, DynamoDB item serialization | `tests/integration/test_integration_layer.py` | 32 | ✅ PASS |
| **Layer 5** | **AWS Integration Layer:** In-memory Moto mocks for DynamoDB, CloudWatch, SNS, EventBridge | `tests/aws_integration/test_aws_integration_layer.py` | 28 | ✅ PASS |
| **Layer 6** | **Simulation Layer:** Verification of FS-01 through FS-05 failure injection targets | `tests/simulation/test_simulation_layer.py` | 25 | ✅ PASS |
| **Layer 7** | **EventBridge Layer:** Event pattern matching, payload extraction, detail validation | `tests/eventbridge/test_eventbridge_layer.py` | 22 | ✅ PASS |
| **Layer 8** | **Recovery Layer:** Strategy dispatch, metric reset targets, state machine updates | `tests/recovery/test_recovery_layer.py`<br/>`backend/tests/unit/test_recovery_integration.py` | 38 | ✅ PASS |
| **Layer 9** | **Notification Layer:** SNS message templates, duplicate suppression guards | `tests/notification/test_notification_layer.py` | 21 | ✅ PASS |
| **Layer 10** | **End-to-End Closed-Loop:** 9-step full lifecycle verification (Injection $\rightarrow$ UI) | `tests/e2e/test_e2e_closed_loop.py` | 15 | ✅ PASS |
| **Layer 11** | **Edge Cases & Resilience:** Idempotency under duplicate events, partial failures, retries | `tests/edge_cases/test_edge_cases_and_resilience.py` | 21 | ✅ PASS |
| **TOTAL** | | | **367** | **100% PASS** |

---

## 3. Five Failure Scenarios Verification (FS-01 to FS-05)

Every failure scenario is tested across the complete 9-step closed-loop lifecycle in `tests/e2e/test_e2e_closed_loop.py`:

| Scenario Code | Scenario Name | Target Resource | Injected Breach | Verified Recovery Action | Verification Result |
|---|---|---|---|---|---|
| **FS-01** | High CPU Utilization | `VM-001` | CPU $\ge 85\%$ (98%) | `SCALE_OUT` | ✅ 9-Step Closed Loop Verified |
| **FS-02** | Service Failure | `API-001` | Latency $\ge 500\text{ms}$ (1200ms) | `SERVICE_RESTART` | ✅ 9-Step Closed Loop Verified |
| **FS-03** | Storage Exhaustion | `STORAGE-001` | Storage $\ge 90\%$ (96%) | `STORAGE_CLEANUP` | ✅ 9-Step Closed Loop Verified |
| **FS-04** | Network Latency | `DB-001` | Latency $\ge 500\text{ms}$ (1500ms) | `NETWORK_REROUTE` | ✅ 9-Step Closed Loop Verified |
| **FS-05** | Service Downtime | `VM-001` | Latency = 5000ms, CPU = 0% | `FAILOVER` | ✅ 9-Step Closed Loop Verified |

### The 9 Verified Steps in Each Scenario:
1. Failure triggered via API
2. Failure state recorded in DynamoDB (`FAILURE_DETECTED`)
3. Monitoring condition emitted to CloudWatch metrics
4. Event generated / routed via EventBridge
5. Recovery initiated (`RECOVERY_INITIATED`)
6. Recovery completed (`RECOVERED`)
7. Incident record updated with duration and action (`RESOLVED`)
8. Notification generated via SNS (duplicate suppressed)
9. Dashboard reflection verified through telemetry APIs

---

## 4. Resilience & Edge-Case Verification

| Edge Case Test | Test Description | Observed Behavior | Status |
|---|---|---|---|
| **Duplicate Event Handling** | Concurrent duplicate EventBridge events sent for same incident | Pre-read and DynamoDB conditional write short-circuits second execution safely | ✅ PASS |
| **Recovery Strategy Error** | Simulated strategy raises `RecoveryStrategyError` | Resource transitions to `RECOVERY_FAILED`, increments retry count, updates incident | ✅ PASS |
| **Retry Exhaustion** | 3 consecutive recovery failures on same resource | Resource escalates to `MANUAL_INTERVENTION_REQUIRED`, incident status becomes `ESCALATED` | ✅ PASS |
| **CloudWatch Partial Outage** | CloudWatch API raises `ClientError` during metric publishing | Error logged as non-fatal warning; core state persistence and recovery succeed | ✅ PASS |
| **SNS Partial Outage** | SNS raises `ClientError` during alert dispatch | Error logged as non-fatal warning; incident marked `notification_status: FAILED` | ✅ PASS |
| **DynamoDB Outage** | DynamoDB raises `ClientError` on state update | Handled via custom domain `DatabaseError` and mapped to HTTP 500 response | ✅ PASS |
| **Invalid Failure Type** | API receives non-existent failure type string | Rejected at FastAPI boundary with HTTP 422 Unprocessable Entity | ✅ PASS |
| **Invalid EventBridge Source** | Lambda receives event with unknown source | Re-raises exception so Lambda retry policy and SQS DLQ engage | ✅ PASS |

---

## 5. Frontend Test Breakdown (49 Tests Across 17 Suites)

| Component / Section Suite | Focus of Verification | Test Count | Status |
|---|---|---|---|
| `Gauge.test.tsx` | Circular SVG health & metric gauge visualization | 3 | ✅ PASS |
| `StatusBadge.test.tsx` | Accessible status pill indicators with correct colors | 4 | ✅ PASS |
| `MetricCard.test.tsx` | SRE metric card formatting, trends, and empty states | 4 | ✅ PASS |
| `IncidentTimeline.test.tsx` | Multi-step incident lifecycle timeline rendering | 4 | ✅ PASS |
| `App.test.tsx` | Global layout, navigation bar, and tab routing | 3 | ✅ PASS |
| `OverviewSection.test.tsx` | Fleet summary counts, active incidents, quick actions | 4 | ✅ PASS |
| `ResourceHealthSection.test.tsx` | Resource grid, filtering by status, detail inspect | 5 | ✅ PASS |
| `FailureSimulatorSection.test.tsx` | Complete 5-stage visualizer transition (Healthy $\rightarrow$ Recovered) | 3 | ✅ PASS |
| `ActiveIncidentsSection.test.tsx` | Active incident table, severity badges, time display | 3 | ✅ PASS |
| `IncidentDetailsSection.test.tsx` | 14-field inspection, embedded recovery action audit log | 4 | ✅ PASS |
| `RecoveryActivitySection.test.tsx` | Live recovery action feed, status icons, durations | 3 | ✅ PASS |
| `ReliabilityMetricsSection.test.tsx`| SRE reliability indicators, MTTR/MTBF trend charts | 4 | ✅ PASS |
| `ArchitectureViewSection.test.tsx` | Interactive architecture blueprint and service map | 2 | ✅ PASS |
| `SystemEventsSection.test.tsx` | Event log table, level badges, JSON modal viewer | 3 | ✅ PASS |
| **TOTAL FRONTEND TESTS** | | **49** | **100% PASS** |

---

## 6. How to Reproduce Test Results Locally

```bash
# 1. Run full backend suite
backend/.venv/bin/pytest tests/ backend/tests/ -q

# 2. Run frontend suite
cd frontend && npm test -- --run

# 3. Verify TypeScript build
cd frontend && npm run build
```
