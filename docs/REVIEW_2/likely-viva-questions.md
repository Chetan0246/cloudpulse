# CloudPulse — Comprehensive Viva & Architecture Review Q&A

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Evaluation Milestone:** Project Review 2  
**Purpose:** Technical Preparation for Evaluator / Examiner Viva Voce  

---

## Category 1: System Architecture & Design Choices

### Q1: Why did you choose a serverless event-driven architecture instead of running a traditional microservices cluster (e.g. ECS Fargate or EKS)?
**Answer:**  
CloudPulse is fundamentally designed around asynchronous anomaly detection, event routing, and episodic remediation. Running container clusters on ECS or EKS requires continuous compute provisioning, cluster control planes, and VPC NAT Gateways, easily exceeding $50–$100/month even when completely idle.  
In contrast, a serverless architecture (API Gateway, AWS Lambda, DynamoDB, EventBridge) features **pure pay-per-use scaling to zero**. When no failures are occurring, compute cost is exactly $0.00. Furthermore, AWS EventBridge provides native, managed event bus routing with sub-second latency, built-in retry policies, and dead-letter queues that would otherwise require managing Apache Kafka or RabbitMQ clusters.

---

### Q2: Why is FastAPI wrapped with Mangum inside AWS Lambda rather than writing separate native Lambda functions for every API endpoint?
**Answer:**  
This is recorded in **ADR-006**. While single-purpose Lambda functions offer granular IAM and slightly faster cold starts, adopting a monolithic FastAPI app wrapped by Mangum provides critical architectural benefits:
1. **Developer Velocity & Local Testing:** The exact same `app` instance runs locally via `uvicorn app.main:app --reload` and is tested via `fastapi.testclient.TestClient` with zero AWS dependencies or container emulation.
2. **Unified OpenAPI Documentation:** FastAPI auto-generates Swagger/OpenAPI specifications, models, and JSON schema validation in a single place.
3. **Cold Start Trade-off:** Mangum adds ~1.2s to cold starts (measured during cold invocation), which is completely acceptable for an academic demonstration and control console where queries occur via background polling.

---

### Q3: What is the cardinal safety boundary of CloudPulse? Does it touch real AWS EC2 instances?
**Answer:**  
No. As strictly mandated by the **Project Constitution (§2.2)**, CloudPulse simulates failures exclusively through **virtual state and metric mutations** persisted in DynamoDB and published to CloudWatch custom metrics. It **never** invokes EC2, RDS, or VPC modification APIs.  
This boundary guarantees:
- **Zero Destructive Risk:** No risk of accidental production termination, data corruption, or orphaned cloud hardware.
- **Strict Cost Containment:** Runs within the AWS Free Tier.
- **High Determinism:** Chaos experiments produce reproducible, testable metric deltas without non-deterministic hardware spin-up delays.  
Importantly, the **monitoring, alerting, event routing, compute invocation, and notification pipeline is 100% genuine AWS serverless infrastructure**.

---

## Category 2: Event Routing & Amazon EventBridge

### Q4: How does EventBridge decouple the monitoring layer from the recovery layer?
**Answer:**  
CloudPulse adheres to the principle of loose coupling. CloudWatch Alarms do not directly invoke the Recovery Lambda, nor does the Simulator know which remediation engine will execute.  
Instead:
1. CloudWatch alarms publish standard state-change events (`source: "aws.cloudwatch"`) to the default event bus.
2. EventBridge evaluates JSON event patterns independently of the event producer.
3. EventBridge rules match specific alarm prefixes and forward events to targets asynchronously.  
This allows operators to add additional targets (e.g. SQS queues, third-party webhooks, AWS Step Functions) without modifying a single line of monitoring or simulation code.

---

### Q5: What was the critical bug identified in the architecture audit regarding composite `SERVICE_HEALTH` alarms, and how was it solved?
**Answer:**  
As documented in **ARCHITECTURE_AUDIT.md (Finding A-14)**:  
The SAM template generates alarms named `cloudpulse-{ResourceId}-SERVICE_HEALTH`. Originally, the EventBridge rule matched all `prefix: "cloudpulse-"` alarms. When a `SERVICE_HEALTH` alarm fired, the Recovery Lambda attempted to parse `SERVICE_HEALTH` as a `FailureType` enum member (`HIGH_CPU`, `SERVICE_FAILURE`, `STORAGE_EXHAUSTION`, `NETWORK_LATENCY`, `SERVICE_DOWNTIME`). Because `SERVICE_HEALTH` is not a failure type, parsing failed, returning an HTTP 400 that Lambda treated as a success, silently dropping the event.  
**The Solution:**  
We updated the EventBridge rule pattern in `template.yaml` to explicitly exclude composite health alarms:
```yaml
detail:
  alarmName:
    - prefix: cloudpulse-
    - anything-but:
        suffix: -SERVICE_HEALTH
```
Primary metric alarms (CPU, Latency, Storage) trigger the autonomous self-healing path, while composite health is reserved for dashboard visualization and operator alerting.

---

## Category 3: Concurrency, Idempotency & Failure Modes

### Q6: How does CloudPulse guarantee idempotency if EventBridge delivers duplicate alarm events?
**Answer:**  
Distributed event brokers guarantee **at-least-once delivery**, meaning duplicate invocations can and do happen. CloudPulse deploys a **two-tier defense**:
1. **Tier 1 (In-Memory Pre-Read Gate):** Upon invocation, the Recovery Lambda performs a strongly consistent read (`ConsistentRead=True`) of the target resource in DynamoDB. If the resource's `current_state` is already `RECOVERY_INITIATED`, `RECOVERY_IN_PROGRESS`, or `RECOVERED`, the handler terminates immediately with `200 OK ("Already recovering")`, avoiding unnecessary processing.
2. **Tier 2 (Atomic DynamoDB Conditional Expression):** The state transition update executes with:
   ```python
   ConditionExpression="current_state = :cs"
   ExpressionAttributeValues={":cs": "FAILURE_DETECTED"}
   ```
   If two Lambda instances race past Tier 1 simultaneously, DynamoDB's atomic transaction engine ensures only one write succeeds. The second execution catches `ConditionalCheckFailedException` and terminates safely without double-executing remediation actions.

---

### Q7: What happens when an automated recovery action fails? Describe the retry and escalation workflow.
**Answer:**  
In `lambda/recovery/handler.py`:
1. If a recovery strategy raises `RecoveryStrategyError` or any unhandled exception, the failure path catches it.
2. A `RecoveryAction` record is appended with `status: FAILED` and the exception trace.
3. The function checks `new_attempts = len(incident.recovery_actions)`.
4. If `new_attempts < MAX_RECOVERY_ATTEMPTS` (3):
   - The resource transitions to `RECOVERY_FAILED`.
   - The incident remains in `RECOVERING` status.
   - An SNS failure notification is dispatched (`Attempt X of 3 failed`).
5. If `new_attempts >= 3` (retries exhausted):
   - The resource transitions to `MANUAL_INTERVENTION_REQUIRED`.
   - The incident status transitions to `ESCALATED` with timestamp `escalated_at`.
   - An urgent escalation notification is dispatched to operations.

---

## Category 4: DynamoDB Data Modeling & SRE Metrics

### Q8: Explain your DynamoDB table structure and why you chose a multi-table design over single-table design.
**Answer:**  
Recorded in **docs/DATABASE_DESIGN.md**:  
CloudPulse provisions three independent tables:
1. `cloudpulse-resources-{env}` (PK: `resource_id`)
2. `cloudpulse-incidents-{env}` (PK: `incident_id`, GSI: `ResourceIndex` on `resource_id`)
3. `cloudpulse-metrics-{env}` (PK: `resource_id`, SK: `window_key`)

**Why Multi-Table over Single-Table?**  
In an academic project focused on clarity, verification, and maintainability, single-table design (overloading `PK`/`SK` with prefixes like `RES#...` and `INC#...`) obscures schema validation and complicates direct console inspection for evaluators. Multi-table design allows:
- Explicit Pydantic model binding per table.
- Isolated IAM policies (Simulator has read-only access to Resources and zero access to Incidents).
- Clear, distinct lifecycle boundaries.  
To support fast lookup of all incidents for a specific resource, we provisioned the `ResourceIndex` GSI on the Incidents table.

---

### Q9: What is the "Zero-Invention Principle" in your reliability metrics calculation?
**Answer:**  
Recorded in **docs/RELIABILITY_METRICS.md**:  
Many demo applications display hardcoded or randomized SRE metrics (like static "99.9% uptime" labels). CloudPulse strictly prohibits this.  
Every single metric displayed on the dashboard is derived mathematically from stored DynamoDB records via pure deterministic functions in `backend/app/services/reliability_calculator.py`:
- **MTTR:** $\frac{\sum (\text{resolved\_at} - \text{detected\_at})}{\text{Resolved Incident Count}}$
- **Success Rate:** $\frac{\text{Resolved Incidents}}{\text{Terminal Incidents}} \times 100$
- **MTBF:** $\frac{\text{Total Fleet Operating Seconds} - \text{Total Downtime}}{\text{Total Incident Count}}$
- **Detection Latency:** $\text{detected\_at} - \text{injected\_at}$  
If no incidents exist, the system accurately displays `null` or `100%` according to formal limit conditions rather than inventing sample numbers.

---

## Category 5: Security, IAM & Cost Governance

### Q10: How did you implement least-privilege IAM access for your Lambda functions?
**Answer:**  
Documented in **docs/SECURITY.md** and implemented in `template.yaml`:  
Each Lambda function has its own dedicated execution role:
1. **`ApiFunctionRole`:** Granted read/write on Resources and Metrics tables; query on Incidents GSI; permission to publish custom metrics scoped strictly to `Namespace: "CloudPulse"`; and publish permission to EventBridge.
2. **`SimulatorFunctionRole`:** Can read/write Resources; publish CloudWatch metrics; zero access to Incidents table or SNS.
3. **`RecoveryFunctionRole`:** Can update Resources and Incidents; publish recovery confirmation metrics; publish to SNS; and send failed events to `RecoveryDLQ`.  
**Zero wildcard permissions (`*`)** are used on any DynamoDB table or SNS topic.

---

### Q11: How do you prevent notification spam and duplicate SNS emails?
**Answer:**  
In `backend/app/services/notification_service.py`, the `Incident` domain model tracks an array: `notified_transitions: list[str]`.  
When a transition occurs (e.g. `FAILURE_DETECTED`), `notification_service.notify()` checks:
```python
if transition.value in incident.notified_transitions:
    return incident, False # Skip duplicate
```
Only if the transition is new does SNS publish the message, after which `notified_transitions` is appended and saved to DynamoDB. This completely prevents duplicate emails when multiple alarms or retries touch the same incident.

---

### Q12: What are the primary cost drivers of CloudPulse, and how do you keep total cost under $1.00/month?
**Answer:**  
Documented in **docs/COST_MANAGEMENT.md**:  
- Lambda, DynamoDB, API Gateway, S3, SQS, and EventBridge fall entirely within their respective AWS Free Tier allowances.
- The **only billable line item** is CloudWatch custom metrics (16 metrics, where 10 are free; 6 cost ~$1.80/month) and alarms (12 alarms, where 10 are free; 2 cost ~$0.20/month).  
To prevent unexpected costs:
1. All CloudWatch Log Groups enforce a strict `RetentionInDays: 7` setting.
2. Metrics are published in single batched API calls, reducing API requests by 80%.
3. Frontend polling adaptively drops to 30 seconds when the browser tab is hidden.
4. An automated teardown script (`make destroy` / `destroy.sh`) completely purges all stack resources when testing concludes.
