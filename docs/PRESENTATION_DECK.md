# CloudPulse — Architecture & Demo Presentation Deck (Transcript & Speaker Notes)

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Evaluation Milestone:** Project Review 2 / Viva Voce  
**Binary PowerPoint Presentation:** [`docs/CloudPulse_Architecture_and_Demo.pptx`](file:///home/chetan/cloudpulse/docs/CloudPulse_Architecture_and_Demo.pptx)  
**Total Slides:** 14 Slides (16:9 Widescreen)  
**Estimated Presentation Duration:** 8 – 10 Minutes  

---

## Slide 1: Title Slide
- **Header Badge:** `BCSE355L: CLOUD ARCHITECTURE DESIGN`
- **Main Title:** CloudPulse: Autonomous Event-Driven Self-Healing Cloud Reliability Simulator
- **Subtitle:** Closed-loop autonomic computing demonstrating real-time fault detection, asynchronous event routing, automated self-healing remediation, and SRE reliability telemetry on AWS Serverless.
- **Presenter & Context:** CloudPulse Engineering Team | AWS Region: `ap-south-1` | Stack: `cloudpulse-dev`
- **Speaker Notes (0:00 - 0:45):**
  > *"Good morning/afternoon, Professor. Today I am presenting CloudPulse, an autonomous, event-driven, self-healing cloud reliability simulator built natively on AWS Serverless architecture. Our goal is to demonstrate how modern distributed systems can eliminate manual triage and reduce Mean Time to Recovery (MTTR) from 45 minutes to sub-second autonomous self-healing, while strictly adhering to cloud architecture best practices and cost governance."*

---

## Slide 2: Problem Statement & Motivation
- **Header:** `1. MOTIVATION & CHALLENGE` — The Cloud Operations & Reliability Crisis
- **Card 1 (The Modern Cloud Reality):**
  - Distributed & Ephemeral: Microservices, serverless functions, and distributed datastores make manual tracking impossible.
  - Cascading Latency: A bottleneck in compute or database locks quickly cascades across the topology.
  - Alert Fatigue: Operators face hundreds of unprioritized notifications daily.
- **Card 2 (The MTTR Bottleneck):**
  - Human-in-the-Loop Latency: Traditional operations rely on on-call paging, manual log grepping, and PDF playbooks.
  - Average Outage Duration: Industry statistics show 30–45 minutes MTTR for routine failures.
  - Cost of Downtime: Even brief cloud outages cost thousands of dollars per minute.
- **Card 3 (The Autonomous Solution):**
  - Autonomic Closed Loop: Fully automated MAPE-K cycle (Monitor $\rightarrow$ Analyze $\rightarrow$ Plan $\rightarrow$ Execute $\rightarrow$ Knowledge).
  - Sub-Second Detection: CloudWatch high-resolution metrics trigger real-time alarm state transitions.
  - Deterministic Self-Healing: Automated targeted remediation strategies restore nominal metrics within seconds.
- **Speaker Notes (0:45 - 1:45):**
  > *"The core problem in cloud operations today is the MTTR bottleneck. When an anomaly occurs, human operators spend 80% of the outage window just paging an engineer, checking logs, and reading playbooks. CloudPulse transforms this reactive model into an autonomic closed loop where detection, event routing, and remediation happen automatically without human latency."*

---

## Slide 3: Project Objectives & Core Engineering Innovation
- **Header:** `2. PROJECT GOALS & INNOVATION` — Engineering Objectives & Innovation
- **Card 1 (Primary Engineering Objectives):**
  - End-to-End Closed Loop: Build an autonomous feedback cycle connecting fault injection, metric detection, event routing, and remediation.
  - Zero Destructive Hardware Risk: Simulate faults logically via state & metric mutations in DynamoDB without terminating real cloud servers.
  - Decoupled Architecture: Decouple monitoring from healing using Amazon EventBridge asynchronous routing rules.
  - Deterministic SRE Metrics: Provide exact mathematical derivation of MTTR, detection latency, and recovery success rates without fake data.
  - 100% Free Tier Compliance: Pure serverless pay-per-use design with $0.00 idle compute cost.
- **Card 2 (Key Architectural Innovations):**
  - Dual-Mode Event Ingestion: Supports both autonomous CloudWatch alarm state-machine routing and fast-track synthetic fault injection.
  - Two-Tier Idempotency Engine: Eliminates duplicate recovery executions caused by at-least-once distributed event broker delivery.
  - Circuit Breaker Escalation: Limits failed remediation attempts to 3 before escalating to human manual intervention.
  - Dynamic Base Path Stripping: Mangum ASGI adapter dynamically resolves API Gateway stage prefixes (`/dev`) preventing route mismatch.
  - Comprehensive Auditability: Full 14-field incident lifecycle tracked with immutable ISO 8601 timestamps and correlation IDs.
- **Speaker Notes (1:45 - 2:30):**
  > *"Two critical engineering principles define CloudPulse: First, our cardinal safety boundary—we mutate virtual resource states and publish real synthetic CloudWatch metrics, ensuring zero destructive hardware risk and strictly zero idle costs. Second, our architecture is 100% genuine AWS serverless services—API Gateway, Lambda, DynamoDB, EventBridge, CloudWatch, and SNS."*

---

## Slide 4: System Architecture & AWS Service Mapping
- **Header:** `3. SYSTEM ARCHITECTURE` — High-Level Serverless Architecture
- **Tier 1: Presentation Tier:**
  - React 18 + Vite SPA hosted on Amazon S3 static website hosting.
  - Responsive SRE Ops Console with live 5-stage lifecycle stepper and interactive controls.
- **Tier 2: Ingestion & API Tier:**
  - Amazon API Gateway HTTP API v2 + AWS Lambda (Python 3.12 ARM64).
  - FastAPI with Mangum adapter; sub-millisecond route proxying; zero idle compute cost.
- **Tier 3: Persistence & State Tier:**
  - Amazon DynamoDB Pay-Per-Request.
  - `cloudpulse-resources-dev` (telemetry state) and `cloudpulse-incidents-dev` (audit trail).
  - Atomic conditional writes (`ConditionExpression`).
- **Tier 4: Autonomic Self-Healing Tier:**
  - Amazon CloudWatch custom metrics (`CloudPulse` namespace) and metric alarms.
  - Amazon EventBridge asynchronous decoupled event bus.
  - Recovery Lambda executing targeted self-healing strategies.
  - Amazon SNS automated email alert notifications.
- **Speaker Notes (2:30 - 3:30):**
  > *"Here is the 4-tier architecture. Notice how clean the separation of concerns is: The React dashboard on S3 talks to API Gateway. API Gateway runs our FastAPI application inside Lambda. Telemetry and incident records persist in DynamoDB. When an anomaly occurs, CloudWatch evaluates the threshold and emits an event to the EventBridge bus, which asynchronously triggers the Recovery Lambda. Finally, Amazon SNS notifies operations engineers."*

---

## Slide 5: Telemetry Ingestion & CloudWatch Monitoring
- **Header:** `4. INGESTION & MONITORING` — Telemetry Ingestion & CloudWatch Monitoring
- **Card 1 (Virtual Resource Heartbeat Simulator):**
  - Scheduled Trigger: Amazon EventBridge invokes Simulator Lambda every 2 minutes (`rate(2 minutes)`).
  - 4 Virtual Resource Archetypes: `VM-001` (Compute), `API-001` (Gateway), `DB-001` (Storage), `STORAGE-001` (Object).
  - Synthetic Gaussian Jitter: Emits realistic metric variations around nominal baselines.
  - Concurrency Guard: Skips resources currently in `RECOVERY_INITIATED` or `RECOVERY_IN_PROGRESS`.
  - Batch API Calls: Bundles all 5 metrics into a single `PutMetricData` call to conserve API quotas.
- **Card 2 (CloudWatch Custom Metrics & Alarm Topology):**
  - Namespace: `CloudPulse`.
  - 5 High-Resolution Dimensions: `CPUUtilization`, `MemoryUtilization`, `StorageUtilization`, `NetworkLatency`, and `ServiceHealth`.
  - Static Thresholds: Evaluated over 60s evaluation periods (e.g. CPU > 85%, Latency > 150ms).
  - Composite Health Formula: $\text{Health} = 100 - (0.4 \times \text{CPU} + 0.3 \times \text{Mem} + 0.3 \times \text{Latency})$.
- **Speaker Notes (3:30 - 4:15):**
  > *"To maintain live telemetry, our Simulator Lambda runs on a 2-minute EventBridge schedule. It computes realistic metrics for all 4 virtual resources and calls CloudWatch PutMetricData in batches. CloudWatch alarms evaluate high-resolution metrics continuously, triggering state changes the moment thresholds are breached."*

---

## Slide 6: Asynchronous Decoupled Event Routing (EventBridge)
- **Header:** `5. ASYNCHRONOUS EVENT ROUTING` — Decoupled Event Routing via Amazon EventBridge
- **Card 1 (Why EventBridge Over Direct Invocation?):**
  - Loose Coupling: Monitoring alarms do not call recovery code directly. Healing logic can be refactored with zero impact on monitoring.
  - Multi-Subscriber Fanout: An alarm event can simultaneously trigger healing Lambda, log to compliance SQS, and page Slack.
  - Content-Based Filtering: EventBridge inspects JSON payloads at wire speed without executing intermediate code.
  - SQS Dead-Letter Queue (DLQ): Unhandled events divert to `cloudpulse-recovery-dlq-dev`.
- **Card 2 (Architectural Audit Finding A-14 Fix):**
  - The Bug: Originally, EventBridge matched all `prefix: "cloudpulse-"` alarms. When composite `SERVICE_HEALTH` alarms fired, Recovery Lambda failed because `SERVICE_HEALTH` is not an actionable failure type.
  - The Fix: Updated SAM pattern to exclude composite health alarms:
    `alarmName: [{ prefix: "cloudpulse-" }, { anything-but: { suffix: "-SERVICE_HEALTH" } }]`
  - Result: Autonomous recovery only fires for specific root-cause faults (CPU, Latency, Storage).
- **Speaker Notes (4:15 - 5:00):**
  > *"EventBridge is our architectural centerpiece. In traditional designs, systems use tight coupling where monitoring directly triggers scripts. CloudPulse routes everything through the EventBridge default bus. This decouples our detection plane from our remediation plane. Furthermore, during our architectural audit, we caught and resolved Finding A-14, ensuring composite health alarms don't trigger invalid recovery runs."*

---

## Slide 7: Autonomous Self-Healing Engine & Recovery Strategies
- **Header:** `6. AUTONOMIC REMEDIATION` — Autonomous Self-Healing Engine & Strategies
- **Card 1 (Deterministic Strategy Dispatcher):**
  - `FS-01: HIGH_CPU` $\rightarrow$ **`SCALE_OUT`**: Simulates horizontal scaling; resets CPU to 25% and memory to 30%.
  - `FS-02: SERVICE_FAILURE` $\rightarrow$ **`SERVICE_RESTART`**: Restarts application container; resets latency to 15ms.
  - `FS-03: STORAGE_EXHAUSTION` $\rightarrow$ **`STORAGE_CLEANUP`**: Rotates logs and purges temp cache; resets storage to 20%.
  - `FS-04: NETWORK_LATENCY` $\rightarrow$ **`NETWORK_REROUTE`**: Reroutes virtual traffic through alternate VPC path; resets latency to 15ms.
  - `FS-05: SERVICE_DOWNTIME` $\rightarrow$ **`FAILOVER`**: Initiates multi-AZ standby failover; resets all 4 metrics to nominal.
- **Card 2 (Resilience & Circuit-Breaker Pattern):**
  - Max Retries: `MAX_RECOVERY_ATTEMPTS = 3` strictly enforced.
  - Recovery Action Auditing: Every attempt generates an immutable UUID v4 `RecoveryAction` record.
  - Automatic Escalation: If recovery fails 3 times, resource state transitions to `MANUAL_INTERVENTION_REQUIRED`.
  - Incident Status: Moves to `ESCALATED` with `escalated_at` timestamp.
  - Operator Alert: Sends urgent SNS email notifying on-call humans of automated remediation exhaustion.
- **Speaker Notes (5:00 - 5:45):**
  > *"When the Recovery Lambda receives an event, it maps the failure scenario to a deterministic remediation strategy. For instance, high CPU dispatches SCALE_OUT, which resets the metric delta to nominal baselines. If a strategy fails repeatedly, our circuit breaker prevents infinite retry loops: after 3 failed attempts, the incident automatically escalates to MANUAL_INTERVENTION_REQUIRED and pages human engineers."*

---

## Slide 8: Two-Tier Idempotency & Concurrency Guarantees
- **Header:** `7. CONCURRENCY & RELIABILITY` — Two-Tier Idempotency & Concurrency Guarantees
- **Card 1 (The Distributed Race Condition Threat):**
  - At-Least-Once Delivery: Cloud brokers (EventBridge, SQS) can deliver duplicate event copies.
  - Concurrent Triggers: If an operator injects a fault while CloudWatch alarm fires, two Lambda containers run in parallel.
  - The Double-Recovery Risk: Two Lambdas could both attempt `SCALE_OUT`, corrupting metrics and incident attempt counters.
  - ElastiCache/Redis Rejected: Avoids $30+/month running costs and VPC cold start latency.
- **Card 2 (The CloudPulse Two-Tier Defense):**
  - **Tier 1 (Pre-Read Consistent Gate):** Calls `get_item(ConsistentRead=True)`. If already `RECOVERY_INITIATED`, `RECOVERY_IN_PROGRESS`, or `RECOVERED`, exits immediately with HTTP 200 `"Already recovering"`.
  - **Tier 2 (Atomic Conditional Write):** State mutation uses:
    `ConditionExpression="current_state = :cs"` where `:cs = FAILURE_DETECTED`.
  - If two Lambdas race past Tier 1, DynamoDB's engine accepts only one write. The second throws `ConditionalCheckFailedException` and aborts safely.
- **Speaker Notes (5:45 - 6:30):**
  > *"In cloud computing, you cannot assume exactly-once delivery. To guarantee idempotency without adding an expensive Redis cluster, we designed a two-tier defense: First, a strongly consistent pre-read gate exits immediately if the resource is already healing. Second, an atomic DynamoDB conditional write guarantees that only one Lambda wins the race to update the state, completely preventing double-recovery."*

---

## Slide 9: The 5-Stage Closed-Loop Failure & Recovery Lifecycle
- **Header:** `8. INCIDENT LIFECYCLE` — The 5-Stage Closed-Loop Failure & Recovery Lifecycle
- **Stage 1 (HEALTHY):** Fleet nominal. CPU: 25%, Memory: 30%, Storage: 20%, Latency: 15ms. Active Incidents = 0.
- **Stage 2 (FAILURE):** Anomaly injected via API. State mutates to `FAILURE_DETECTED`. Telemetry spikes (CPU: 92%). Incident created with status `OPEN`.
- **Stage 3 (DETECTED):** CloudWatch alarm triggers. EventBridge matches rule pattern and asynchronously invokes Recovery Lambda.
- **Stage 4 (HEALING):** Recovery Lambda acquires atomic lock. Transitions state to `RECOVERY_INITIATED` $\rightarrow$ `RECOVERY_IN_PROGRESS`. Dispatches strategy (`SCALE_OUT`).
- **Stage 5 (RECOVERED):** Metrics reset to nominal baselines. State updated to `RECOVERED`. Incident closed as `RESOLVED`. Audit sealed. SNS alert sent.
- **Speaker Notes (6:30 - 7:15):**
  > *"Here is the 5-stage lifecycle that the evaluator will see on our live dashboard: Healthy baseline $\rightarrow$ Failure injection $\rightarrow$ CloudWatch detection $\rightarrow$ Automated healing $\rightarrow$ Recovered. Every state change is synchronized in real-time across DynamoDB, CloudWatch, and the React UI."*

---

## Slide 10: SRE Reliability Metrics & Observability Layer
- **Header:** `9. SRE OBSERVABILITY` — Reliability Metrics & End-to-End Tracing
- **Card 1 (Mathematical Reliability Formulations):**
  - Mean Time to Recovery: $\text{MTTR} = \frac{\sum (\text{resolved\_at} - \text{detected\_at})}{\text{Total Resolved Incidents}}$
  - Recovery Success Rate: $\text{Success Rate} = \frac{\text{Successful Recovery Actions}}{\text{Total Recovery Attempts}} \times 100\%$
  - Average Detection Latency: $\text{MTTA} = \frac{\sum (\text{detected\_at} - \text{started\_at})}{\text{Total Incidents}}$
  - Fleet Health Distribution: Percentage breakdown across HEALTHY, DEGRADED, and CRITICAL.
- **Card 2 (Correlation ID & Distributed Tracing):**
  - Correlation ID (UUID v4) assigned at failure injection and passed through all stages.
  - Single-Trace Audit: Ingestion $\rightarrow$ CloudWatch $\rightarrow$ EventBridge $\rightarrow$ Lambda $\rightarrow$ DynamoDB $\rightarrow$ SNS.
  - Notification Guards: `notified_transitions` bitmap suppresses duplicate alert emails.
- **Speaker Notes (7:15 - 8:00):**
  > *"Every SRE metric shown on our dashboard is mathematically derived from DynamoDB timestamp records—we do not invent or hardcode metrics. MTTR measures actual resolution duration, and every incident carries a correlation ID that lets us trace an anomaly from initial injection all the way to the final SNS email."*

---

## Slide 11: Security, IAM Boundaries & Cost Governance
- **Header:** `10. SECURITY & GOVERNANCE` — IAM Least Privilege, Security & Cost Governance
- **Card 1 (IAM Least-Privilege Role Boundaries):**
  - Dedicated IAM Roles: `ApiFunctionRole`, `SimulatorFunctionRole`, and `RecoveryFunctionRole`.
  - Resource ARN Scoping: DynamoDB policies restricted strictly to `cloudpulse-*-dev` ARNs and GSI indexes.
  - CloudWatch Condition Blocks: `PutMetricData` restricted via `StringEquals: cloudwatch:namespace = "CloudPulse"`.
  - Zero Committed Secrets: No credentials or tokens committed to version control.
- **Card 2 (Cost Governance & Free-Tier Containment):**
  - Serverless Pay-Per-Use: Scale-to-zero compute. When idle, compute cost is exactly $0.00.
  - DynamoDB On-Demand: Billed only for actual read/write request units consumed.
  - Log Retention Policies: All CloudWatch log groups have `RetentionInDays: 7` to avoid storage billing creep.
  - Total Operating Cost: Under $1.50/month under continuous demonstration workloads.
- **Speaker Notes (8:00 - 8:45):**
  > *"Security and cost governance were core design considerations. Every Lambda runs under a dedicated, least-privilege IAM role. On the cost side, our serverless architecture scales to zero, log retention is capped at 7 days, and the entire project runs well within the AWS Free Tier."*

---

## Slide 12: Live Demonstration Walkthrough
- **Header:** `11. DEMONSTRATION WALKTHROUGH` — Live Demonstration Script & Expected Outcomes
- **Step 1:** Establish Baseline $\rightarrow$ Show all 4 virtual resources healthy with nominal telemetry.
- **Step 2:** Inject Failure $\rightarrow$ Trigger `FS-01: High CPU` on `VM-001`. Receive HTTP 201 Created.
- **Step 3:** State Mutation $\rightarrow$ Observe `VM-001` turn `FAILURE_DETECTED`, CPU surge to 92%, health drop to CRITICAL.
- **Step 4:** Event Routing $\rightarrow$ EventBridge evaluates pattern filter and triggers Recovery Lambda asynchronously.
- **Step 5:** Strategy Execution $\rightarrow$ Recovery Lambda acquires atomic lock and executes `SCALE_OUT`.
- **Step 6:** Metric Reset $\rightarrow$ CPU restored to nominal 25%, resource returns to `HEALTHY`, incident marked `RESOLVED`.
- **Step 7:** Audit Verification $\rightarrow$ Inspect DynamoDB 14-field record, verify SNS email alert, and check SRE MTTR calculation.
- **Speaker Notes (8:45 - 9:30):**
  > *"Now let's switch to the live demonstration. In 7 clear steps, we will observe the healthy baseline, trigger a high CPU fault, watch CloudWatch and EventBridge orchestrate self-healing, and verify the resulting DynamoDB audit trail and SNS alert."*

---

## Slide 13: Automated Testing & Technical Verification
- **Header:** `12. VERIFICATION & QUALITY` — Automated Testing & Technical Verification
- **Stats Callouts:**
  - **277** Backend Unit Tests (`pytest`) — Passed
  - **95** E2E Closed-Loop Tests (`pytest`) — Passed
  - **49** Frontend Vitest Tests — Passed
  - **421 Total Automated Tests (100% Pass Rate)**
- **Card 1 (Test Coverage Categories):**
  - Data Models & Schema: Pydantic models with UUID v4 validation and timestamp timezone checks.
  - Idempotency & Race Conditions: Verifies pre-read gates and conditional write failure handling.
  - Recovery Strategy Execution: Unit tests for all 5 strategies verifying deterministic metric deltas.
  - API Gateway Stage Stripping: Mangum tests verifying path normalization across `/dev` and `$default`.
- **Card 2 (Execution Velocity):**
  - 277 backend tests execute in 6.93s.
  - 49 frontend tests execute in 8.36s.
  - 100% pass rate ready for production deployment.
- **Speaker Notes (9:30 - 10:00):**
  > *"To ensure reliability, CloudPulse is backed by 421 automated tests across backend units, end-to-end event loops, and React UI components. All 421 tests pass with 100% success rate, ensuring zero regressions."*

---

## Slide 14: Conclusion, Academic Merits & Future Roadmap
- **Header:** `13. CONCLUSION & ROADMAP` — Summary, Academic Impact & Future Roadmap
- **Card 1 (Academic & Architectural Contributions):**
  - Closed-Loop Autonomics: Practical realization of IBM's MAPE-K model using modern cloud primitives.
  - Event Decoupling Mastery: Proves how asynchronous event routers cleanly separate telemetry from remediation.
  - Formal Architecture Records: Documented in 6 formal ADRs and rigorous security/cost audits.
  - Enterprise SRE Relevance: Delivers tangible operational value through autonomous MTTR reduction.
- **Card 2 (Enterprise Production Roadmap):**
  - AWS Step Functions Workflows: Orchestrating complex multi-tier rollbacks and approval gates.
  - Multi-Region Active-Active: DynamoDB Global Tables and Route 53 Application Recovery Controller.
  - Amazon Bedrock GenAI Diagnosis: LLM-powered root-cause analysis for unknown or compound incident types.
- **Speaker Notes (10:00 - 10:30):**
  > *"In conclusion, CloudPulse demonstrates that self-healing cloud reliability is both feasible and cost-effective using native AWS serverless services. For future enhancements, we plan to incorporate AWS Step Functions for multi-tier rollbacks and Amazon Bedrock for GenAI root-cause analysis. Thank you, and I am now ready for your questions."*

---

## Quick Reference: Top 5 Viva Questions
1. **Why DynamoDB over RDS?** Pay-per-request zero idle cost, atomic conditional writes for idempotency, and single-digit millisecond latency.
2. **How is idempotency guaranteed?** Two-tier defense: ConsistentRead pre-read gate + atomic DynamoDB `ConditionExpression="current_state = :cs"`.
3. **What happens after 3 failed recoveries?** Circuit breaker triggers: resource transitions to `MANUAL_INTERVENTION_REQUIRED`, incident marked `ESCALATED`, and urgent SNS alert is sent.
4. **Why FastAPI with Mangum inside Lambda?** Portability to run locally via uvicorn, fast testability with TestClient, automated OpenAPI schemas, and dynamic stage stripping.
5. **What is simulated vs. real?** Workload fault metrics are simulated; the entire monitoring, event bus, compute, database, and notification infrastructure is 100% genuine AWS serverless.
