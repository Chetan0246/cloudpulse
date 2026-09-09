# CloudPulse Security Checklist

This operational checklist is used to audit, verify, and maintain the security posture of the CloudPulse system before deployment and during routine reliability operations.

---

## 1. Pre-Deployment Infrastructure Audit

- [x] **IAM Least Privilege Verification**
  - [x] Every Lambda function has a dedicated IAM execution role (`ApiFunctionRole`, `SimulatorFunctionRole`, `RecoveryFunctionRole`).
  - [x] Zero wildcard actions (`"Action": "*"`) are present in custom policies.
  - [x] DynamoDB access is restricted to exact table ARNs (`ResourcesTable`, `IncidentsTable`, `MetricsTable`).
  - [x] CloudWatch metric publishing is scoped to `cloudwatch:namespace = CloudPulse`.
  - [x] SNS publish permissions are restricted to `NotificationsTopic`.
  - [x] SQS permissions are restricted to `RecoveryDLQ`.
  - [x] EventBridge permissions are restricted to the default bus ARN.

- [x] **S3 Storage Security**
  - [x] Frontend S3 bucket has server-side encryption enabled (`SSEAlgorithm: AES256`).
  - [x] S3 `PublicAccessBlockConfiguration` is guarded by parameter `EnablePublicFrontendBucket`.
  - [x] Bucket is 100% private by default (`EnablePublicFrontendBucket: "false"`).
  - [x] Public read bucket policy is conditional on `IsPublicFrontendEnabled`.

- [x] **DynamoDB Table Protection**
  - [x] All tables use `BillingMode: PAY_PER_REQUEST` to prevent cost overruns.
  - [x] Partition keys are strongly typed strings (`resource_id`, `incident_id`).
  - [x] Secondary indexes project required attributes without unbounded storage duplication.

- [x] **CloudWatch & Logging**
  - [x] Explicit 7-day retention (`RetentionInDays: 7`) configured on all 4 log groups.
  - [x] API Gateway access logging enabled with structured JSON format.
  - [x] No sensitive tokens, authorization headers, or request payloads in access log format.

---

## 2. Codebase & Application Security

- [x] **Input Validation & Sanitization**
  - [x] `resource_id` strictly validated via regex `^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$` across all endpoints.
  - [x] `incident_id` validated against UUID v4 pattern.
  - [x] Pagination queries bounded (`limit <= 200`) to prevent denial-of-service scans.
  - [x] Pydantic models enforce strict enum parsing for `FailureType`, `IncidentSeverity`, and `IncidentStatus`.

- [x] **Concurrency & Race Condition Defense**
  - [x] Recovery Lambda implements pre-read state gate to fast-exit on already recovering resources.
  - [x] DynamoDB conditional write (`expected_state = FAILURE_DETECTED`) prevents concurrent execution race conditions.
  - [x] SNS notifications deduplicated via `incident.notified_transitions`.

- [x] **CORS & Network Boundaries**
  - [x] `allow_credentials=False` enforced in FastAPI `CORSMiddleware`.
  - [x] `AllowHeaders` restricted to `Content-Type` and `Authorization`.
  - [x] HTTP methods restricted to `GET`, `POST`, and `OPTIONS`.
  - [x] Pre-flight cache duration configured (`MaxAge: 300`).

---

## 3. Secrets & Repository Hygiene

- [x] **Credential Exposure Scan**
  - [x] Repository scanned for AWS access keys (`AKIA...`), secret keys, and passwords (0 findings).
  - [x] Local `.env` files protected by `.gitignore`.
  - [x] No SSH keys, `.pem` files, or `.key` certificates tracked in git.
  - [x] Test credentials in `conftest.py` use dummy mock strings (`"testing"`).

---

## 4. Operational & Deployment Verification

Run before deploying to any AWS environment:

```bash
# 1. Validate infrastructure template, IAM policies, and cost guards
./scripts/validate.sh

# 2. Run backend security and unit test suite (272 tests)
cd backend && source .venv/bin/activate && pytest tests/unit/ -v

# 3. Run frontend test suite (47 tests) and build check
cd ../frontend && npm test && npm run build

# 4. Scan repository for accidental secret leaks
git grep -i -E "AKIA[0-9A-Z]{16}|aws_secret_access_key"
```

---

## 5. Continuous Monitoring & Incident Checklist

In the event of an unexpected alert or anomaly:
1. **Check SQS Dead-Letter Queue**: Inspect `cloudpulse-recovery-dlq` for failed recovery Lambda invocations.
2. **Review CloudWatch Alarms**: Verify if alarm state transitioned to `ALARM` and whether EventBridge rule fired.
3. **Query Access Logs**: Use CloudWatch Logs Insights on `/aws/apigateway/cloudpulse-{env}` to identify abnormal traffic patterns or IPs.
4. **Inspect Incident History**: Query `GET /incidents?status=ESCALATED` to identify resources requiring tier-2 manual intervention.
