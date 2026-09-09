# CloudPulse — Project Overview

**Project Title:** CloudPulse: Autonomous Cloud Reliability and Self-Healing Simulator Using AWS Serverless Architecture  
**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**System Classification:** Academic Cloud Reliability Simulator  
**Current Release Status:** Release Candidate (Verified & Audited)  
**Repository:** [github.com/Chetan0246/cloudpulse](https://github.com/Chetan0246/cloudpulse)

---

## 1. Executive Summary

Modern cloud architectures demand high resilience and rapid incident remediation. However, human-operated incident management suffers from manual triage delays, alert fatigue, and variable response procedures that inflate Mean Time to Recovery (MTTR).

**CloudPulse** is an autonomous, event-driven, self-healing cloud reliability simulator constructed entirely on AWS serverless services. It demonstrates the complete end-to-end lifecycle of autonomous infrastructure remediation:
1. **Continuous Telemetry:** Simulated virtual resources continuously report multi-dimensional health metrics.
2. **Deterministic Failure Injection:** Controlled workloads inject 5 distinct failure scenarios (High CPU, Service Failure, Storage Exhaustion, Network Latency, Service Downtime).
3. **Observability & Detection:** Amazon CloudWatch monitors metrics via threshold alarms and a composite `ServiceHealth` indicator.
4. **Decoupled Event Routing:** Amazon EventBridge routes state-change alarms and fast-track injection events to an autonomous remediation engine.
5. **Idempotent Self-Healing:** An AWS Lambda Recovery Engine executes targeted remediation strategies using a formal 8-state transition machine with atomic DynamoDB guards.
6. **Auditing & Notification:** Every incident records a complete 14-field audit history in DynamoDB, dispatches duplicate-guarded notifications via Amazon SNS, and updates live SRE reliability indicators on a React control console.

---

## 2. Academic & Architectural Boundary: Simulation vs. Real Infrastructure

> **Cardinal Project Rule (Project Constitution §2.2):**  
> CloudPulse is an **academic simulation system**. It does **NOT** provision, mutate, stop, or destroy real AWS compute instances (EC2), managed database clusters (RDS), or networking VPCs.

### How Simulation Operates in CloudPulse
- **Virtual Resource Fleet:** 4 logical resources (`VM-001`, `API-001`, `DB-001`, `STORAGE-001`) are persisted as items in Amazon DynamoDB (`cloudpulse-resources-{env}`).
- **Synthetic Metric Publishing:** Telemetry (CPU, memory, storage utilization, network latency) is computed and published as real AWS CloudWatch custom metrics under the `CloudPulse` namespace.
- **Real AWS Event Pipeline:** While the resource instances are logical, the **entire monitoring, alerting, event routing, compute invocation, and notification pipeline is 100% genuine AWS serverless infrastructure** (CloudWatch, EventBridge, Lambda, DynamoDB, SNS, API Gateway, S3).
- **Remediation Execution:** Self-healing strategies reset resource state and restore synthetic metrics to nominal values in DynamoDB, and publish recovery confirmation data points to CloudWatch.

This design enables complete verification of distributed cloud resilience patterns, event-driven orchestration, and chaos engineering principles within AWS Free Tier limits and with zero operational risk.

---

## 3. High-Level Architecture

```
                                 ┌──────────────────────────────────────────────┐
                                 │            React SRE Console (S3)            │
                                 └──────────────────────┬───────────────────────┘
                                                        │ HTTPS (Adaptive Polling)
                                                        ▼
                                 ┌──────────────────────────────────────────────┐
                                 │           Amazon API Gateway (HTTP)          │
                                 └──────────────────────┬───────────────────────┘
                                                        │ Lambda Proxy
                                                        ▼
                                 ┌──────────────────────────────────────────────┐
                                 │             API Lambda (FastAPI)             │
                                 └─────────┬──────────────────────────┬─────────┘
                       Direct Inject       │                          │ Telemetry & State
                             ┌─────────────┘                          ▼
                             ▼                             ┌────────────────────┐
                ┌─────────────────────────┐                │  Amazon DynamoDB   │
                │    Amazon EventBridge   │◄───────────────┤  Resources Table   │
                │      (Default Bus)      │                │  Incidents Table   │
                └────────────┬────────────┘                │  Metrics Table     │
                             │                             └────────────────────┘
         CloudWatch Alarms   │                                        ▲
         & Direct Triggers   │                                        │ State Update
                             ▼                                        │ & Incident Log
                ┌─────────────────────────┐                           │
                │     Recovery Lambda     ├───────────────────────────┘
                │   (Remediation Engine)  ├───────────────────────────┐
                └─────────────────────────┘                           │
                                                                      ▼
                                                           ┌────────────────────┐
                                                           │     Amazon SNS     │
                                                           │ (Email Alerting)   │
                                                           └────────────────────┘
```

---

## 4. Key Project Artifacts & Verification Summary

| Dimension | Specification / Metric | Status |
|---|---|---|
| **AWS Services** | API Gateway, Lambda (arm64), DynamoDB, EventBridge, CloudWatch, SNS, SQS, S3, IAM | Verified in SAM template |
| **Backend Testing** | 367 automated unit, integration, edge-case, and scenario tests (`pytest`) | 100% Passed (0 failures) |
| **Frontend Testing** | 49 component, gauge, and end-to-end lifecycle tests (`vitest`) | 100% Passed (0 failures) |
| **Frontend Build** | Strict TypeScript compilation (`tsc --noEmit`) and Vite bundle | 0 Errors, 0 Warnings |
| **Infrastructure Validation** | AWS SAM template validation and linter (`sam validate --lint`) | Clean Pass |
| **Security Audit** | Zero hardcoded secrets, least-privilege IAM policies, restricted CORS, atomic conditional writes | Complete (`SECURITY.md`) |
| **Estimated Monthly Cost** | Free-tier compatible execution | ~bash.80 / month |

---

## 5. Navigation to Detailed Documentation

- **Problem & Motivation:** [PROBLEM_STATEMENT.md](./PROBLEM_STATEMENT.md)
- **Project Objectives:** [OBJECTIVES.md](./OBJECTIVES.md)
- **Requirements Matrix:** [REQUIREMENTS.md](./REQUIREMENTS.md)
- **System Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)
- **AWS Service Mapping:** [AWS_SERVICES.md](./AWS_SERVICES.md)
- **DynamoDB Schema:** [DATABASE_DESIGN.md](./DATABASE_DESIGN.md)
- **API Reference:** [API_DESIGN.md](./API_DESIGN.md)
- **Failure Simulation Scenarios:** [FAILURE_SIMULATION.md](./FAILURE_SIMULATION.md)
- **Monitoring & Alarms:** [MONITORING_ARCHITECTURE.md](./MONITORING_ARCHITECTURE.md)
- **Self-Healing State Machine:** [SELF_HEALING_ARCHITECTURE.md](./SELF_HEALING_ARCHITECTURE.md)
- **Testing & QA Strategy:** [TEST_STRATEGY.md](./TEST_STRATEGY.md)
- **Security & Threat Model:** [SECURITY.md](./SECURITY.md)
- **Reliability Metrics (SRE):** [RELIABILITY_METRICS.md](./RELIABILITY_METRICS.md)
- **Cost Analysis:** [COST_MANAGEMENT.md](./COST_MANAGEMENT.md)
- **Academic Review 2 Package:** [docs/REVIEW_2/](./REVIEW_2/)
