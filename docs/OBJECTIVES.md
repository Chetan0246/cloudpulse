# CloudPulse — System Objectives & Success Criteria

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** Architectural Goals & Verification Metrics  
**Version:** 1.0  

---

## 1. Primary Objectives

### PO-1: Autonomous Closed-Loop Self-Healing
Design and implement an autonomous, closed-loop resilience lifecycle:
131280	ext{Healthy} \longrightarrow 	ext{Failure} \longrightarrow 	ext{Detection} \longrightarrow 	ext{Event Routing} \longrightarrow 	ext{Remediation} \longrightarrow 	ext{Verification} \longrightarrow 	ext{Recovered}131280
Eliminate human intervention for known, deterministic infrastructure failure scenarios.

### PO-2: Deterministic Failure Simulation (FS-01 to FS-05)
Construct a safe, reproducible simulation engine covering five fundamental cloud failure modes:
1. **FS-01 (High CPU):** CPU utilization spike beyond 85%.
2. **FS-02 (Service Failure):** Critical health degradation with heartbeat interruption.
3. **FS-03 (Storage Exhaustion):** Disk utilization spike beyond 90%.
4. **FS-04 (Network Latency):** Round-trip transit delay exceeding 500 ms.
5. **FS-05 (Service Downtime):** Sustained unresponsiveness requiring instance failover.

### PO-3: Cloud-Native Observability & Anomaly Detection
Publish real-time telemetry as Amazon CloudWatch custom metrics under the `CloudPulse` namespace. Implement metric threshold alarms and an algorithmic composite `ServiceHealth` score (bash.0 - 100.0$) derived from weighted headroom.

### PO-4: Decoupled Event-Driven Remediation Engine
Decouple monitoring from remediation using Amazon EventBridge:
- Ingest CloudWatch Alarm state-change events.
- Support direct-injected simulation events to allow sub-second demo progression.
- Invoke an isolated AWS Lambda recovery function equipped with deterministic remediation strategies.

### PO-5: Comprehensive Incident Audit Trail & Alerting
Persist an immutable, 14-field incident lifecycle in Amazon DynamoDB (`cloudpulse-incidents-{env}`). Ensure all state changes, timestamps, recovery actions, and retry counts are preserved. Dispatch human-readable notifications via Amazon SNS with automated duplicate suppression.

### PO-6: Mathematical SRE Reliability Derivation
Implement a zero-invention metric calculator deriving 8 core Site Reliability Engineering (SRE) indicators directly from stored DynamoDB records:
- Total Incident Count
- Recovery Success Rate (%)
- Recovery Failure Rate (%)
- Average Recovery Time (seconds)
- Mean Time to Recovery (MTTR)
- Average Detection Time (seconds)
- Incident Frequency (per hour/day)
- Mean Time Between Failures (MTBF)

### PO-7: Cloud Operations Control Console
Deliver a responsive, professional SRE dashboard in React 18, TypeScript, and Tailwind CSS. Features include fleet health visualization, live failure simulation triggers, incident timeline inspection, and reliability metric reporting.

---

## 2. Engineering & Quality Objectives

### EO-1: Absolute Simulation Safety
Guarantee that simulation code operates strictly on virtual DynamoDB resource items and custom CloudWatch metrics. Under no circumstances may any AWS API call stop, terminate, or modify real AWS EC2, RDS, or VPC assets.

### EO-2: Concurrency & Idempotency Safety
Implement two-tier idempotency guards (in-memory state check + DynamoDB conditional expressions) to ensure that duplicate EventBridge events or concurrent triggers cannot cause race conditions or corrupt incident histories.

### EO-3: Rigorous Automated Verification
Maintain a comprehensive automated test suite covering all architectural layers (Unit, API, Integration, AWS Mocking, Simulation, EventBridge, Recovery, Notification, E2E). Require 100% test pass rate prior to release.

### EO-4: Free-Tier Adherence & Cost Containment
Ensure the entire application can be deployed and demonstrated within the AWS Free Tier. Bound total monthly incremental operational costs to under .00.

### EO-5: Reproducible Infrastructure as Code (IaC)
Define 100% of AWS infrastructure (Lambda, DynamoDB, API Gateway, EventBridge, CloudWatch Alarms, SNS, SQS DLQ, IAM) in a declarative AWS SAM template (`infrastructure/template.yaml`).

---

## 3. Success Criteria & Verification Matrix

| Objective ID | Success Criterion | Verification Method | Status |
|---|---|---|---|
| **PO-1** | Closed-loop cycle completes from failure to recovery | E2E closed-loop automated test (`test_e2e_closed_loop.py`) | ✅ Verified |
| **PO-2** | All 5 failure scenarios execute deterministically | Scenario test suite (`test_simulation_layer.py`) | ✅ Verified |
| **PO-3** | CloudWatch metrics and alarms deploy cleanly | AWS integration tests + SAM linter | ✅ Verified |
| **PO-4** | EventBridge triggers Recovery Lambda on alarm | EventBridge mock routing tests (`test_eventbridge_layer.py`) | ✅ Verified |
| **PO-5** | Incidents track full 14-field lifecycle and send SNS | Notification tests (`test_notification_layer.py`) | ✅ Verified |
| **PO-6** | All 8 SRE metrics mathematically derived | Calculator test suite (`test_reliability_calculator.py`) | ✅ Verified |
| **PO-7** | React dashboard builds and renders 9 sections | Vitest suite (49 tests) + TypeScript build (`tsc --noEmit`) | ✅ Verified |
| **EO-1** | Zero real AWS resources modified | Security audit (`SECURITY.md`) + IAM policy inspection | ✅ Verified |
| **EO-2** | Duplicate events safely ignored without error | Idempotency tests (`test_edge_cases_and_resilience.py`) | ✅ Verified |
| **EO-3** | Backend test suite passes completely | Pytest run (367 passed in ~9.4s) | ✅ Verified |
| **EO-4** | SAM template validated and cost bounded | Cost management audit (`COST_MANAGEMENT.md`) | ✅ Verified |
