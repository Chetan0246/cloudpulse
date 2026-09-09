# CloudPulse — Problem Statement

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** Architectural & Engineering Problem Definition  
**Version:** 1.0  

---

## 1. Context & Operational Background

Modern enterprise architectures increasingly rely on distributed, multi-tier cloud deployments across compute, database, and storage layers. In these environments, failures are inevitable:
- CPU saturation from unexpected traffic spikes
- Memory leaks leading to unhandled service crashes
- Storage capacity exhaustion halting database write logs
- Network partitioning and transit latency degrading API SLAs
- Complete service downtime requiring automated failover

In conventional Operations and Site Reliability Engineering (SRE) setups, incident response follows a **human-in-the-loop** workflow:
1. An anomaly occurs.
2. A monitoring tool detects the symptom after a polling delay.
3. An alert is sent (email, PagerDuty).
4. An on-call engineer wakes up, context-switches, and accesses diagnostic consoles.
5. The engineer identifies the appropriate runbook and manually executes recovery commands (e.g. scaling up, restarting services, purging caches).
6. The engineer verifies that the incident is resolved and manually closes the ticket.

---

## 2. Core Industry & Architectural Problems

### 2.1 Latency & High Mean Time to Recovery (MTTR)
The human-in-the-loop lifecycle introduces human latency at every stage: detection latency, triage latency, and manual intervention latency. In critical workloads, downtime costs can reach thousands of dollars per minute. A self-healing system must eliminate human intervention for predictable, well-understood failure modes.

### 2.2 Alert Fatigue & Operator Inconsistency
Operators bombarded by dozens of alarms per shift suffer from alert fatigue. During high-stress outages, engineers may misapply remediation runbooks, leading to cascading failures or incomplete recoveries.

### 2.3 Fragile Remediation Scripts & Lack of Idempotency
Many traditional remediation scripts are non-idempotent bash jobs or cron tasks. If triggered concurrently by duplicate alarm notifications, they can trigger race conditions (e.g. double failovers, simultaneous scaling conflicts, or duplicate incident tracking).

### 2.4 The Academic & Laboratory Dilemma
Validating self-healing and chaos engineering architectures in educational and testing environments poses severe practical hurdles:
- **Cost Prohibitions:** Running real multi-tier clusters (e.g. Multi-AZ EC2 Auto Scaling Groups, Amazon RDS clusters, NAT Gateways, Transit Gateways) incurs substantial ongoing charges that far exceed student and academic budgets.
- **Safety Hazards:** Inexperienced operators executing destructive failure scripts on live infrastructure risk permanent data loss, orphaned resources, or unintended cloud bill spikes.
- **Reproducibility:** Chaos experiments on real cloud hardware frequently exhibit nondeterministic recovery windows, making automated testing and grading unreliable.

---

## 3. The CloudPulse Problem Formulation

To address these challenges, **CloudPulse** formulates the following design problem:

> **How can we construct an event-driven, closed-loop cloud reliability system using AWS serverless primitives that:**
> 1. **Faithfully mirrors real-world cloud reliability workflows** (detection, decoupled event routing, automated strategy remediation, incident lifecycle management, and alerting)?
> 2. **Remains 100% safe and non-destructive**, simulating resource state mutations in DynamoDB without touching real cloud hardware?
> 3. **Guarantees concurrency safety, determinism, and idempotency** across all recovery workflows?
> 4. **Operates entirely within AWS Free Tier limits** while providing live SRE telemetry and an interactive control console?

---

## 4. Scope & Non-Goals

### Within Scope
- Serverless event-driven architecture utilizing AWS Lambda, DynamoDB, CloudWatch, EventBridge, and SNS.
- Five deterministic failure scenarios representing common infrastructure faults.
- Formal 8-state recovery state machine with atomic DynamoDB conditional guards.
- Duplicate-guarded notifications and automated SRE metric derivations.
- Interactive SRE web dashboard built in React/TypeScript with live telemetry polling.

### Out of Scope (Non-Goals)
- Managing, terminating, or modifying real AWS EC2, RDS, or VPC resources.
- General-purpose autonomous agent for arbitrary production workloads.
- Long-term big-data telemetry analytics beyond standard SRE sliding windows.
