# PROJECT CONSTITUTION
## CloudPulse: Autonomous Cloud Reliability and Self-Healing Simulator

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Version:** 1.0  
**Status:** BINDING — All contributors must read and follow this document.

---

## 1. Project Identity

CloudPulse is an **academic simulation system** that demonstrates autonomous cloud reliability and self-healing concepts using AWS serverless architecture. It is NOT a production system.

---

## 2. Hard Rules (Non-Negotiable)

### 2.1 Cost & AWS Usage
- The system MUST stay within AWS Free Tier limits wherever possible.
- Do NOT provision expensive infrastructure (e.g., EC2 clusters, RDS multi-AZ, NAT Gateways) for demonstration purposes.
- Lambda, DynamoDB (on-demand), S3, CloudWatch, EventBridge, SNS, and API Gateway are the approved AWS services.
- Any addition of a new AWS service requires explicit justification in an Architectural Decision Record (ADR).

### 2.2 Simulation Safety
- Failures MUST be simulated logically (state changes in DynamoDB on virtual resources).
- CloudPulse MUST NEVER intentionally disrupt real AWS infrastructure.
- No Lambda function may terminate, stop, or modify real EC2/RDS/ECS resources without an explicit `--simulation-mode=false` flag AND user confirmation.

### 2.3 Secrets & Credentials
- AWS credentials MUST NEVER be hardcoded in any source file.
- Secrets MUST NEVER be committed to Git.
- All sensitive configuration must use environment variables or AWS Systems Manager Parameter Store.
- `.env` files are local only and MUST be listed in `.gitignore`.

### 2.4 Infrastructure as Code
- All AWS resource provisioning MUST be done via IaC (AWS SAM or AWS CDK).
- No manual console-only resource creation that is not documented and reproducible.

### 2.5 Incremental Delivery
- After every phase, the application MUST be in a runnable state.
- Features MUST NOT be marked as complete unless they are implemented AND tested.
- Each phase ends with a working demo checkpoint.

---

## 3. Approved Technology Stack

### Backend
| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Web Framework | FastAPI |
| Lambda Adapter | Mangum |
| IaC | AWS SAM |
| Testing | pytest, moto (AWS mocking) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18+ |
| Language | TypeScript |
| Build Tool | Vite |
| HTTP Client | Axios or native fetch |
| Styling | Tailwind CSS |

### AWS Services (Approved)
| Service | Purpose |
|---|---|
| API Gateway (HTTP API) | Frontend to Backend entry point |
| AWS Lambda | All compute |
| Amazon DynamoDB | Incident records, resource state |
| Amazon S3 | Frontend hosting, logs/reports |
| Amazon CloudWatch | Metrics, alarms, dashboards |
| Amazon EventBridge | Event routing (failure events to recovery) |
| Amazon SNS | Notifications (email/SMS) |
| AWS IAM | Least-privilege access control |

---

## 4. Simulated Resource Model

Virtual resources tracked in DynamoDB. These are logical constructs, not real AWS resources.

Fields:
- resourceId        : string (PK)
- resourceType      : enum [VM, API, DB, STORAGE]
- currentState      : enum [HEALTHY, WARNING, FAILURE_DETECTED, RECOVERY_INITIATED, RECOVERY_IN_PROGRESS, RECOVERED, RECOVERY_FAILED, MANUAL_INTERVENTION_REQUIRED]
- cpuUtilization    : float (0-100)
- memoryUtilization : float (0-100)
- storageUtilization: float (0-100)
- networkLatency    : float (ms)
- lastHeartbeat     : ISO8601 timestamp
- healthStatus      : enum [HEALTHY, DEGRADED, CRITICAL]

Seed resources:
- VM-001       — Virtual Machine
- API-001      — API Service
- DB-001       — Database
- STORAGE-001  — Storage Service

---

## 5. Failure & Recovery Model

### Failure Types
| Type | Trigger Condition |
|---|---|
| High CPU | cpuUtilization > 85% |
| Service Failure | healthStatus = CRITICAL + lastHeartbeat stale |
| Storage Exhaustion | storageUtilization > 90% |
| Network Latency | networkLatency > 500ms |
| Service Downtime | currentState = FAILURE_DETECTED for > N minutes |

### Recovery State Machine
HEALTHY
  -> (threshold breach) -> WARNING
  -> (sustained breach) -> FAILURE_DETECTED
  -> (auto-trigger)     -> RECOVERY_INITIATED
  -> (action running)   -> RECOVERY_IN_PROGRESS
  -> (success)          -> RECOVERED -> HEALTHY

RECOVERY_IN_PROGRESS
  -> (failure)          -> RECOVERY_FAILED
  -> (escalation)       -> MANUAL_INTERVENTION_REQUIRED

---

## 6. Code Quality Standards

- Python code must use type hints throughout. TypeScript strict mode enabled.
- Handlers, services, repositories, and models must be in separate modules.
- All Lambda handlers must catch exceptions and return structured error responses.
- Use Python logging module with structured JSON output in Lambda.
- EventBridge rules and Lambda invocations must use appropriate retry/dead-letter configurations.
- Event handlers must be idempotent (use event IDs / conditional DynamoDB writes).
- Each Lambda function gets its own IAM role with only the permissions it needs.

---

## 7. Project Governance

- README.md — Always kept up to date.
- ARCHITECTURE.md — Updated whenever architectural decisions change.
- DEVELOPMENT_PLAN.md — Tracks phases, tasks, and completion status.
- docs/adr/ — Each significant decision is recorded as an Architectural Decision Record.
- CHANGELOG.md — Updated with each phase completion.

---

## 8. What This Project Is NOT

- Not a production reliability platform.
- Not intended to manage real workloads.
- Not authorized to touch or disrupt any real AWS resource outside the project's own Lambda/DynamoDB/S3.
- Not authorized to exceed Free Tier without explicit acknowledgment.

---

*This constitution supersedes any contradictory instruction. When in doubt, ask before building.*
