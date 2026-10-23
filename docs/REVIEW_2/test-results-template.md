# CloudPulse — Comprehensive QA & Test Execution Report

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Evaluation Milestone:** Project Review 2  
**Test Harness:** `pytest` 8.x, `moto` (AWS in-memory mocking), `vitest`, `@testing-library/react`  
**Execution Timestamp:** 2026-10-24 | Release Candidate Verification  
**Overall Status:** **100% PASS (421 / 421 Total Tests Across Backend & Frontend)**  

---

## 1. Test Execution Summary

```
============================= BACKEND TEST SUMMARY =============================
Platform: Linux (Python 3.12 / pytest)
Executed Layers: Root suite (10 groups) + Backend unit suite (15 files)
Results: 372 passed
Failures: 0 | Errors: 0 | Skipped: 0

============================ FRONTEND TEST SUMMARY =============================
Platform: Node.js 20 / Vitest 2.1.9
Executed Suites: 17 Test Files (Components, Gauges, Sections, App)
Results: 49 passed
Failures: 0 | Errors: 0 | Skipped: 0

============================ STATIC ANALYSIS & IAC =============================
TypeScript Compiler (tsc --noEmit): 0 errors
Python Type Checker (mypy app/): Success — no issues in 30 source files
Frontend Production Build (vite build): Success
AWS SAM Validation (sam validate --lint): Valid SAM Template
AWS SAM Build (sam build): Build Succeeded
```

---

## 2. Granular Backend Test Breakdown (372 Tests)

### 2.1 Root integration suite — `tests/` (95 tests)

| Layer # | Testing Layer & Scope | Primary Test Files | Test Count | Status |
|---|---|---|---|---|
| **L1** | **Unit & Parsing:** Domain model rules, reliability math, alarm/event parsing | `tests/unit/test_unit_layer.py`<br/>`tests/unit/test_reliability_calculator.py`<br/>`tests/unit/test_parse_event.py` | 37 | ✅ PASS |
| **L2** | **API Layer:** REST routes, HTTP verbs, path/query validation, error codes | `tests/api/test_api_layer.py` | 5 | ✅ PASS |
| **L3** | **Integration Layer:** Repository data translation, DynamoDB item serialization | `tests/integration/test_integration_layer.py` | 4 | ✅ PASS |
| **L4** | **AWS Integration Layer:** In-memory Moto mocks for DynamoDB, CloudWatch, SNS, EventBridge | `tests/aws_integration/test_aws_integration_layer.py` | 5 | ✅ PASS |
| **L5** | **Simulation Layer:** Verification of FS-01 through FS-05 failure injection targets | `tests/simulation/test_simulation_layer.py` | 7 | ✅ PASS |
| **L6** | **EventBridge Layer:** Event pattern matching, payload extraction, detail validation | `tests/eventbridge/test_eventbridge_layer.py` | 9 | ✅ PASS |
| **L7** | **Recovery Layer:** Strategy dispatch, metric reset targets, state machine updates | `tests/recovery/test_recovery_layer.py` | 7 | ✅ PASS |
| **L8** | **Notification Layer:** SNS message templates, duplicate suppression guards | `tests/notification/test_notification_layer.py` | 4 | ✅ PASS |
| **L9** | **End-to-End Closed-Loop:** 9-step full lifecycle verification (Injection → UI) | `tests/e2e/test_e2e_closed_loop.py` | 5 | ✅ PASS |
| **L10** | **Edge Cases & Resilience:** Idempotency under duplicate events, partial failures, retries | `tests/edge_cases/test_edge_cases_and_resilience.py` | 12 | ✅ PASS |
| **SUBTOTAL** | | | **95** | **100% PASS** |

### 2.2 Backend unit suite — `backend/tests/unit/` (277 tests)

| Layer # | Testing Layer & Scope | Primary Test Files | Test Count | Status |
|---|---|---|---|---|
| **B1** | **Domain Models & Lifecycle:** Pydantic validators, state machine, incident transitions | `test_models.py` (116)<br/>`test_incident_lifecycle.py` (12) | 128 | ✅ PASS |
| **B2** | **Services & Telemetry:** Simulation service, monitoring, metric publishing | `test_services.py` (3)<br/>`test_simulation.py` (15)<br/>`test_monitoring.py` (23) | 41 | ✅ PASS |
| **B3** | **Lambda Handlers:** Simulator event handling, API handler wiring | `test_simulator_handler.py` (24)<br/>`test_api_handler.py` (5) | 29 | ✅ PASS |
| **B4** | **Persistence & AWS Clients:** DynamoDB repositories, client factories, configuration | `test_repositories.py` (3)<br/>`test_aws_clients.py` (3)<br/>`test_config.py` (3) | 9 | ✅ PASS |
| **B5** | **Recovery Engine:** Handler retry/escalation, strategy dispatch, end-to-end recovery | `test_recovery_handler.py` (31)<br/>`test_recovery_integration.py` (13)<br/>`test_recovery_strategies.py` (17) | 61 | ✅ PASS |
| **B6** | **API Routers & Frontend Flow:** FastAPI routers, dashboard-facing response shapes | `test_routers.py` (6)<br/>`test_frontend_api_flow.py` (3) | 9 | ✅ PASS |
| **SUBTOTAL** | | | **277** | **100% PASS** |

**Backend total: 95 + 277 = 372 tests, all passing.**

---

## 3. Five Failure Scenarios Verification (FS-01 to FS-05)

Every failure scenario is tested across the complete 9-step closed-loop lifecycle in `tests/e2e/test_e2e_closed_loop.py`:

| Scenario Code | Scenario Name | Target Resource | Injected Breach | Verified Recovery Action | Verification Result |
|---|---|---|---|---|---|
| **FS-01** | High CPU Utilization | `VM-001` | CPU ≥ 85% (98%) | `SCALE_OUT` | ✅ 9-Step Closed Loop Verified |
| **FS-02** | Service Failure | `API-001` | Latency ≥ 500 ms (1200 ms) | `SERVICE_RESTART` | ✅ 9-Step Closed Loop Verified |
| **FS-03** | Storage Exhaustion | `STORAGE-001` | Storage ≥ 90% (96%) | `STORAGE_CLEANUP` | ✅ 9-Step Closed Loop Verified |
| **FS-04** | Network Latency | `DB-001` | Latency ≥ 500 ms (1500 ms) | `NETWORK_REROUTE` | ✅ 9-Step Closed Loop Verified |
| **FS-05** | Service Downtime | `VM-001` | Latency = 5000 ms, CPU = 0% | `FAILOVER` | ✅ 9-Step Closed Loop Verified |

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
| **Recovery Strategy Error** | Simulated strategy raises `RecoveryStrategyError` | Resource transitions to `RECOVERY_FAILED`, retry count increments, incident updated, and the handler raises so the Lambda retry policy engages | ✅ PASS |
| **Retry Exhaustion** | 3 consecutive recovery failures on same resource | Resource escalates to `MANUAL_INTERVENTION_REQUIRED`, incident becomes `ESCALATED`, invocation acknowledged with HTTP 200 (terminal) | ✅ PASS |
| **CloudWatch Partial Outage** | CloudWatch API raises `ClientError` during metric publishing | Error logged as non-fatal warning; core state persistence and recovery succeed | ✅ PASS |
| **SNS Partial Outage** | SNS raises `ClientError` during alert dispatch | Error logged as non-fatal warning; incident marked `notification_status: FAILED` and `notification_sent` stays `false` | ✅ PASS |
| **DynamoDB Outage** | DynamoDB raises `ClientError` on state update | Raised as `DatabaseError`; handler re-raises so Lambda retries / the DLQ engages instead of silently losing the event | ✅ PASS |
| **Invalid Failure Type** | API receives non-existent failure type string | Rejected at FastAPI boundary with HTTP 422 Unprocessable Entity | ✅ PASS |
| **Invalid EventBridge Source** | Lambda receives event with unknown source | Re-raises exception so Lambda retry policy and SQS DLQ engage | ✅ PASS |

---

## 5. Frontend Test Breakdown (49 Tests Across 17 Suites)

| Component / Section Suite | Focus of Verification | Test Count | Status |
|---|---|---|---|
| `Gauge.test.tsx` | Circular SVG health & metric gauge visualization | 3 | ✅ PASS |
| `Badge.test.tsx` | Accessible status/severity pill indicators | 5 | ✅ PASS |
| `Card.test.tsx` | SRE metric cards, panels, and empty states | 3 | ✅ PASS |
| `StateViews.test.tsx` | Loading and error state rendering | 3 | ✅ PASS |
| `Navigation.test.tsx` | Header and tab navigation behaviour | 3 | ✅ PASS |
| `api.test.ts` | API client contracts and response mapping | 12 | ✅ PASS |
| `App.test.tsx` | Global layout and top-level routing | 1 | ✅ PASS |
| `Dashboard.test.tsx` | Data loading, error surfacing, and tab switching | 1 | ✅ PASS |
| `OverviewSection.test.tsx` | Fleet summary counts and quick actions | 2 | ✅ PASS |
| `ResourceHealthSection.test.tsx` | Resource grid, filtering, and detail inspection | 3 | ✅ PASS |
| `FailureSimulatorSection.test.tsx` | Complete 5-stage visualizer transition (Healthy → Recovered) | 3 | ✅ PASS |
| `ActiveIncidentsSection.test.tsx` | Active incident table, severity badges, time display | 3 | ✅ PASS |
| `IncidentDetailSection.test.tsx` | Field inspection and embedded recovery action audit log | 2 | ✅ PASS |
| `RecoveryActivitySection.test.tsx` | Live recovery action feed | 1 | ✅ PASS |
| `ReliabilityMetricsSection.test.tsx` | SRE reliability indicators, MTTR/MTBF charts | 2 | ✅ PASS |
| `ArchitectureViewSection.test.tsx` | Interactive architecture blueprint | 1 | ✅ PASS |
| `SystemEventsSection.test.tsx` | Event log table and level badges | 1 | ✅ PASS |
| **TOTAL FRONTEND TESTS** | | **49** | **100% PASS** |

---

## 6. How to Reproduce Test Results Locally

```bash
# 1. Run the full backend suite exactly as CI does (372 tests)
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest tests/ backend/tests/ -q

# 2. Run the frontend suite (49 tests)
cd frontend && npm test -- --run

# 3. Verify TypeScript types and production build
cd frontend && npm run build

# 4. Type-check the backend
cd backend && .venv/bin/mypy app/

# 5. Validate and build the infrastructure template
sam validate --lint -t infrastructure/template.yaml
sam build -t infrastructure/template.yaml
```
