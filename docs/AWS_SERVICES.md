# CloudPulse — AWS Services Mapping & Infrastructure Reference

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** AWS Services Architecture & Well-Architected Review  
**Version:** 1.0  
**Status:** Implemented & Verified in AWS SAM  

---

## 1. Overview & Service Landscape

CloudPulse leverages a 100% serverless, pay-per-use architecture on Amazon Web Services. The system deliberately excludes long-running virtual machines, unmanaged containers, or provisioned database clusters to maximize operational resilience, minimize maintenance overhead, and guarantee zero-cost idle operation within the AWS Free Tier.

| AWS Service | Architecture Layer | Specific Role in CloudPulse | Billing / Tier |
|---|---|---|---|
| **AWS Lambda** | Compute | Hosts API Gateway proxy, scheduled telemetry simulation, and autonomous recovery engine | Always-Free (1M req/mo) |
| **Amazon API Gateway** | API Ingress | Low-latency HTTP API (v2) proxying requests to FastAPI via Mangum | 12-Mo Free (1M req/mo) |
| **Amazon DynamoDB** | Persistence | Stores virtual resource state, complete incident lifecycles, and aggregated reliability metrics | Always-Free (25GB storage) |
| **Amazon CloudWatch** | Observability | Ingests 5 custom metrics per resource, executes 12 metric threshold alarms, and aggregates logs | Partial Free Tier (~$0.80/mo) |
| **Amazon EventBridge** | Event Routing | Serverless event bus routing CloudWatch alarm transitions and simulation events | Always-Free (1M events/mo) |
| **Amazon SNS** | Notification | Fan-out alerting service delivering human-readable incident lifecycle emails | Always-Free (1K emails/mo) |
| **Amazon SQS** | Dead-Letter Queue | Captures unrecoverable or malformed recovery events from Recovery Lambda | Always-Free (1M requests/mo) |
| **Amazon S3** | Static Hosting | Private-by-default static bucket hosting the compiled React 18 / Vite dashboard | Always-Free (5GB storage) |
| **AWS IAM** | Identity & Access | Enforces least-privilege security boundaries with 3 discrete Lambda execution roles | Included (No charge) |

---

## 2. Deep Dive: AWS Service Responsibilities & Configurations

### 2.1 AWS Lambda (Serverless Compute)
CloudPulse partitions compute into three discrete, single-responsibility functions:
1. **`ApiFunction` (Backend Controller):**
   - **Runtime & Architecture:** Python 3.12 on `arm64` (Graviton2, offering 20% better price-performance).
   - **Packaging:** Packages `backend/` application logic as an AWS Lambda Layer (`ApiLayer`). Wrapped with `Mangum(app, lifespan="off")` to serve standard ASGI requests.
   - **Memory & Timeout:** 256 MB memory, 30-second timeout.
2. **`SimulatorFunction` (Synthetic Heartbeat & Drift):**
   - **Invocation:** Triggered on a recurring 2-minute schedule via EventBridge Schedule Rule (`cloudpulse-simulator-schedule`).
   - **Behavior:** Executes a bounded random walk on resource telemetry and evaluates threshold health transitions.
   - **Memory & Timeout:** 128 MB memory, 60-second timeout.
3. **`RecoveryFunction` (Remediation Strategy Engine):**
   - **Invocation:** Triggered asynchronously by EventBridge rules upon alarm breach or direct fault injection.
   - **Behavior:** Executes idempotent remediation strategies, updates DynamoDB records, and resets CloudWatch metrics.
   - **Dead-Letter Queue:** Wired to `RecoveryDLQ` (Amazon SQS) with max retry parameters to guarantee unhandled exceptions are never lost.
   - **Memory & Timeout:** 256 MB memory, 60-second timeout.

---

### 2.2 Amazon API Gateway (HTTP API v2)
- **Protocol:** HTTP API (v2) utilizing Payload Format version `2.0`.
- **Why HTTP API over REST API?**
  - Up to 70% cheaper than standard REST APIs.
  - Sub-10ms baseline latency (eliminating heavyweight API Gateway request translation features not required by FastAPI).
  - Native, first-class CORS support configured at the gateway level.
- **Route Configuration:** Single catch-all greedy proxy route (`ANY /{proxy+}`) routing all traffic to `ApiFunction`.

---

### 2.3 Amazon DynamoDB (NoSQL Data Store)
CloudPulse provisions 3 independent DynamoDB tables in `PAY_PER_REQUEST` (on-demand) billing mode:
1. **`cloudpulse-resources-{env}`:**
   - **Partition Key (PK):** `resource_id` (String, e.g. `VM-001`).
   - **Consistency:** Strongly consistent reads (`ConsistentRead=True`) used for all state machine transitions.
2. **`cloudpulse-incidents-{env}`:**
   - **Partition Key (PK):** `incident_id` (String, UUID v4).
   - **Global Secondary Index (GSI):** `ResourceIndex` (PK: `resource_id`) enabling rapid lookup of open incidents per resource without full table scans.
3. **`cloudpulse-metrics-{env}`:**
   - **Partition Key (PK):** `resource_id` (String).
   - **Sort Key (SK):** `window_key` (String, e.g. `DAILY#2026-09-08` or `CUMULATIVE#ALL`).
   - **Access Pattern:** Queries pre-aggregated historical reliability snapshots.

---

### 2.4 Amazon CloudWatch (Metrics, Alarms & Logs)
- **Custom Metrics Namespace:** `CloudPulse`.
- **Telemetry Dimensions:** `ResourceId` (e.g. `VM-001`) and `ResourceType` (e.g. `VM`).
- **Cost-Optimized Batching:** Both the Simulator and API Lambdas use a single batched `put_metric_data` call per evaluation containing all 5 metric data points (`CPUUtilization`, `MemoryUtilization`, `StorageUtilization`, `NetworkLatency`, `ServiceHealth`).
- **Alarms:** 12 total alarms (3 alarms per resource across 4 seed resources):
  - Primary metric alarms evaluated over 2 consecutive 1-minute periods ($M=2, N=2$) to prevent transient flap.
- **CloudWatch Logs:** Dedicated log groups for all 3 Lambdas and API Gateway access logs, each pinned to a 7-day retention policy to prevent unmanaged storage accumulation.

---

### 2.5 Amazon EventBridge (Decoupled Serverless Event Bus)
EventBridge serves as the central nervous system of CloudPulse:
- **Default Event Bus:** Utilizes the standard default event bus, incurring zero base cost.
- **Rule 1 (`AlarmStateChange`):**
  - Pattern: `source: [aws.cloudwatch]`, `detail-type: [CloudWatch Alarm State Change]`, `state.value: [ALARM]`.
  - Filter: Excludes `-SERVICE_HEALTH` composite alarms via `anything-but: suffix: -SERVICE_HEALTH` to avoid unparseable failure types.
- **Rule 2 (`DirectSimulatorEvent`):**
  - Pattern: `source: [cloudpulse.simulator]`, `detail-type: [FailureInjected]`.
  - Enables sub-second demo pacing and instant automated integration tests.

---

### 2.6 Amazon SNS (Simple Notification Service)
- **Topic:** `cloudpulse-notifications-{env}`.
- **Subscription:** Email protocol subscribed to operator address supplied via CloudFormation parameter `NotificationEmail`.
- **Payload Formatting:** Multi-line human-readable alert formatted with incident ID, resource, failure type, severity, status, and duration.
- **Duplicate Protection:** Enforced at the application tier via `notified_transitions` array in the incident model.

---

### 2.7 Amazon S3 (Static Website Hosting)
- **Bucket Configuration:** `cloudpulse-frontend-{env}`.
- **Security Policy:** Parameter-controlled public access. Defaults to `EnablePublicFrontendBucket: false` (strictly private). When enabled, attaches an explicit read-only bucket policy allowing `s3:GetObject` on static assets.
- **Encryption:** Server-side encryption enabled by default (`AES256`).

---

## 3. AWS Well-Architected Framework Alignment

| Well-Architected Pillar | Implementation in CloudPulse |
|---|---|
| **Operational Excellence** | Everything defined as IaC via AWS SAM; structured JSON logging with correlation IDs; automated deployment and teardown scripts (`deploy.sh`, `destroy.sh`). |
| **Security** | Zero hardcoded credentials; dedicated least-privilege IAM roles for each Lambda; restricted CORS configuration; atomic DynamoDB conditional checks. |
| **Reliability** | Distributed event-driven decoupling via EventBridge; automatic retries and SQS Dead-Letter Queue; two-tier idempotency protecting against duplicate deliveries. |
| **Performance Efficiency** | Graviton2 (`arm64`) Lambda runtimes; low-latency HTTP API v2; batched metric publishing; client-side adaptive polling. |
| **Cost Optimization** | 100% serverless on-demand billing; DynamoDB `PAY_PER_REQUEST`; 7-day log retention; batched CloudWatch data points; total incremental cost under $1.00/month. |
