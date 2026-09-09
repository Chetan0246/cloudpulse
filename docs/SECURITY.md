# CloudPulse Security Architecture & Threat Model

This document outlines the security architecture, threat model, control implementations, and residual tradeoffs for the **CloudPulse Autonomous Cloud Reliability and Self-Healing Simulator**.

---

## 1. Executive Summary

CloudPulse is designed around the principle of **least-privilege, event-driven isolation**. Because CloudPulse simulates infrastructure failures and executes autonomous remediation actions, strict architectural boundaries ensure that the engine can **never perform destructive actions against real AWS infrastructure**.

### Key Security Highlights
- **Zero Real Infrastructure Mutation**: Remediation actions mutate virtual state in DynamoDB and emit CloudWatch metrics; no EC2, RDS, or VPC management APIs are granted or called.
- **Dedicated Least-Privilege IAM Roles**: Separate IAM roles for API, Simulator, and Recovery Lambda functions with zero wildcard actions.
- **Two-Tier Idempotency & Replay Defense**: Pre-read state evaluation combined with atomic DynamoDB conditional expressions prevents duplicate recovery runs and race conditions.
- **Default Private S3 Storage**: The frontend S3 bucket blocks all public ACLs and bucket policies by default via parameter-guarded `PublicAccessBlockConfiguration`.
- **Strict Input Validation**: Strong regex filtering on all resource IDs (`^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$`), UUID v4 validation on incidents, bounded query limits (`le=200`), and Pydantic enum validation.
- **Zero Secret Exposure**: No credentials or private keys are stored in source control; local environment files are ignored via root `.gitignore`.

---

## 2. Threat Model (STRIDE Analysis)

| Threat Category | Potential Risk in CloudPulse | Architectural Mitigation | Status |
|---|---|---|---|
| **Spoofing** | Unauthorized entity masquerading as EventBridge alarm event | Recovery Lambda validates event source (`aws.cloudwatch` or `cloudpulse.simulator`) and parses alarm name pattern before execution. | **Mitigated** |
| **Tampering** | Malicious alteration of resource state or metric history in DynamoDB | Strict IAM policies restrict table writes: only API and Simulator can write resources; only Recovery can update state to `RECOVERED`. Strongly consistent reads (`ConsistentRead=True`) prevent stale state tampering. | **Mitigated** |
| **Repudiation** | Operator or component claims recovery action did not execute | Complete 14-field incident lifecycle stored in DynamoDB with timestamps, attempt counts, individual `RecoveryAction` audit records, and SNS delivery logs. | **Mitigated** |
| **Information Disclosure** | Leakage of AWS credentials, sensitive tokens, or system telemetry | CloudWatch Logs use structured JSON with zero credential logging; API Gateway access logs omit authorization headers and request bodies; `.gitignore` strictly protects `.env` files. | **Mitigated** |
| **Denial of Service (DoS)** | Excessive API querying or repeated fault injections overloading Lambda | REST list endpoints enforce `limit <= 200`; failure injection enforces state machine validation (cannot inject failure on already degraded resource); Lambda timeouts bounded (30s API, 60s Recovery). | **Mitigated** |
| **Elevation of Privilege** | Compromised Lambda role performing unauthorized AWS actions | Least-privilege IAM roles; no IAM write permissions (`iam:*`); CloudWatch metric publishing scoped strictly to `CloudPulse` namespace via IAM conditions. | **Mitigated** |

---

## 3. Identity & Access Management (IAM) Architecture

### 3.1 Role Segregation

Three separate IAM roles are provisioned in [`infrastructure/template.yaml`](file:///home/chetan/cloudpulse/infrastructure/template.yaml), ensuring zero cross-function privilege escalation:

```
[ApiFunctionRole]        ──► DynamoDB (Resources, Incidents, Metrics)
                         ──► CloudWatch (PutMetricData: CloudPulse namespace)
                         ──► EventBridge (PutEvents: default bus)
                         ──► SNS (Publish: NotificationsTopic)

[SimulatorFunctionRole]  ──► DynamoDB (Resources: Get/Scan/Put/Update)
                         ──► CloudWatch (PutMetricData: CloudPulse namespace)

[RecoveryFunctionRole]   ──► DynamoDB (Resources: Get/Put/Update; Incidents: Get/Scan/Put/Update)
                         ──► SNS (Publish: NotificationsTopic)
                         ──► SQS (SendMessage: RecoveryDLQ)
                         ──► CloudWatch (PutMetricData: CloudPulse namespace)
```

### 3.2 Action-Level Scoping & Condition Keys

- **No Action Wildcards**: Policies enumerate exact actions (`dynamodb:GetItem`, `dynamodb:PutItem`, etc.) rather than `dynamodb:*`.
- **Namespace-Scoped CloudWatch Permissions**: Because CloudWatch `PutMetricData` does not support resource ARNs, least-privilege scoping is enforced via IAM conditions:
  ```yaml
  - Effect: Allow
    Action:
      - cloudwatch:PutMetricData
    Resource: "*"
    Condition:
      StringEquals:
        cloudwatch:namespace: !Ref CloudWatchNamespace
  ```
- **EventBridge Scoping**: Event emission is locked to the specific account default bus ARN (`arn:aws:events:${AWS::Region}:${AWS::AccountId}:event-bus/default`).
- **Dead-Letter Queue Scoping**: Recovery failures are routed to a dedicated SQS queue with least-privilege `sqs:SendMessage` permissions.

---

## 4. Storage & Data Protection

### 4.1 DynamoDB Security
- **Data Encryption at Rest**: Encrypted using AWS-owned keys (default free tier compliant AES-256).
- **Partition Isolation**: Tables use distinct hash keys (`resource_id`, `incident_id`, composite `resource_id + window_key`).
- **Atomic State Transitions**: Resource state updates require `expected_state` conditional expressions, preventing concurrent race conditions.

### 4.2 S3 Bucket Security & Static Hosting
- **Server-Side Encryption**: Enabled by default via AES-256 (`SSEAlgorithm: AES256`).
- **Public Access Block (Default Safe)**:
  ```yaml
  PublicAccessBlockConfiguration:
    BlockPublicAcls: !If [IsPublicFrontendEnabled, false, true]
    BlockPublicPolicy: !If [IsPublicFrontendEnabled, false, true]
    IgnorePublicAcls: !If [IsPublicFrontendEnabled, false, true]
    RestrictPublicBuckets: !If [IsPublicFrontendEnabled, false, true]
  ```
- **Conditional Public Website**: By default (`EnablePublicFrontendBucket: "false"`), the bucket is **100% private** with zero public access. Only if explicitly overridden for demo hosting is the read-only bucket policy attached.

---

## 5. API Gateway & Network Security

### 5.1 CORS Policy
- Configured in API Gateway HTTP API and reinforced by FastAPI `CORSMiddleware`.
- `allow_credentials=False` ensures cookies and HTTP basic auth credentials are never exposed across origins.
- `AllowHeaders` is restricted to `Content-Type` and `Authorization`.
- Pre-flight `OPTIONS` requests are cached (`MaxAge: 300`) to mitigate pre-flight flood DoS.

### 5.2 Input Validation & Injection Prevention
- **Resource ID Sanitization**: Validated via strict regex `^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$` across all path and body parameters.
- **Incident ID Sanitization**: Validated against RFC 4122 UUID v4 regex pattern.
- **Pagination Protection**: Query parameter `limit` bounded between 1 and 200 items.
- **Pydantic Enum Binding**: Enums strictly parse failure types (`HIGH_CPU`, `SERVICE_FAILURE`, etc.) and reject arbitrary payloads.

---

## 6. Event Replay & Concurrency Defense

### 6.1 Two-Tier Recovery Idempotency
When an alarm triggers EventBridge, duplicate events or retries could cause redundant recovery actions. CloudPulse implements two defense tiers:
1. **Tier 1 (Memory/Read Gate)**: Fast pre-read checks if `current_state != FAILURE_DETECTED`. If the resource is already recovering or healthy, execution returns `200 OK ("Already recovering")` without initiating duplicate workflows.
2. **Tier 2 (Atomic Conditional Write)**: DynamoDB write enforces `attribute_exists(resource_id) AND current_state = :expected`. Only one execution can transition the resource from `FAILURE_DETECTED` to `RECOVERY_INITIATED`.

### 6.2 Notification Deduplication
`NotificationService` records each dispatched lifecycle transition in `incident.notified_transitions: list[str]`. Before publishing to SNS, the service verifies that the transition has not been previously notified, preventing alert fatigue and duplicate emails.

---

## 7. Logging & Observability Security

- **Log Sanitization**: Logs are structured as single-line JSON objects via `JsonFormatter`. Sensitive environment keys, tokens, and credentials are excluded from log contexts.
- **CloudWatch Log Retention**: All 4 log groups (`ApiLogGroup`, `SimulatorLogGroup`, `RecoveryLogGroup`, `ApiAccessLogGroup`) have an explicit `RetentionInDays: 7` setting, preventing unbounded data retention and accidental compliance violations.
- **Access Logs**: API Gateway access logs record request ID, source IP, method, route, status code, and latency, omitting request payloads and headers.

---

## 8. Residual Security Tradeoffs (Student/Demo vs Enterprise)

To maintain a zero-to-low-cost deployment on student budgets, specific enterprise controls are intentionally traded off:

| Control | Student / Demo Implementation | Enterprise Production Recommendation | Justification & Risk Assessment |
|---|---|---|---|
| **API Authentication** | Open HTTP API routes (no authorizer) | AWS Cognito User Pools or OAuth2 JWT Authorizer | Low risk in synthetic demo environment; high developer velocity. In production, prevents unauthorized simulation triggering. |
| **Web Application Firewall (WAF)** | No AWS WAF attached | AWS WAF with rate-based rules and common OWASP rulesets | WAF incurs ~$5/rule/month + request fees. Acceptable tradeoff for cost control; input validation handled in application code. |
| **S3 / CDN Architecture** | Direct S3 static website hosting (when enabled) | Amazon CloudFront distribution with Origin Access Control (OAC) | CloudFront adds custom TLS 1.3 certificates and edge caching. S3 website hosting chosen to eliminate CDN distribution costs. |
| **KMS Encryption Keys** | Default AWS-owned KMS keys | Customer Managed Keys (CMKs) with annual rotation | CMKs cost $1/key/month. AWS-managed encryption provides transparent AES-256 encryption at zero cost. |
| **Database Continuous Backup** | `PointInTimeRecoveryEnabled: false` | `PointInTimeRecoveryEnabled: true` | PITR adds continuous backup storage costs. Synthetic test data is reproducible via seed scripts. |
| **CORS Allowed Origins** | Parameterized; defaults to `*` in SAM template | Explicit domain white-list (e.g. `https://cloudpulse.domain.com`) | Broad default allows local Vite dev server and remote S3 access without re-deploying templates. |
