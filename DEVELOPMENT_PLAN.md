# DEVELOPMENT PLAN
## CloudPulse: Autonomous Cloud Reliability and Self-Healing Simulator

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Version:** 1.0

Status legend: [ ] Not started | [~] In progress | [x] Complete

---

## Phase 0: Foundation & Repository Setup
**Goal:** Clean repo structure, tooling configured, CI skeleton, no AWS resources yet.

- [ ] 0.1 Initialize project folder structure
- [ ] 0.2 Create root .gitignore (Python, Node, SAM, .env, __pycache__, dist, .aws-sam)
- [ ] 0.3 Create root README.md with project overview and setup instructions
- [ ] 0.4 Create CHANGELOG.md
- [ ] 0.5 Create docs/adr/ directory with README and ADR template
- [ ] 0.6 Write ADR-001 through ADR-006 (key architectural decisions)
- [ ] 0.7 Set up backend Python project (pyproject.toml or requirements files)
- [ ] 0.8 Set up frontend React+TypeScript project (Vite)
- [ ] 0.9 Configure pre-commit hooks (black, ruff, mypy for backend; eslint for frontend)
- [ ] 0.10 Verify local development environment runs (backend + frontend)

**Checkpoint 0:** `make dev` starts both backend and frontend locally. Repo committed and pushed.

---

## Phase 1: Data Layer & Resource Model
**Goal:** DynamoDB tables defined in SAM, seed data loadable, resource API working end-to-end.

- [ ] 1.1 Write SAM template for DynamoDB tables (resources + incidents)
- [ ] 1.2 Define Python Pydantic models for Resource and Incident
- [ ] 1.3 Implement DynamoDB repository layer (resource_repository.py, incident_repository.py)
- [ ] 1.4 Implement seed script to populate 4 virtual resources
- [ ] 1.5 Implement FastAPI app skeleton with Mangum adapter
- [ ] 1.6 Implement GET /resources and GET /resources/{resourceId} endpoints
- [ ] 1.7 Implement GET /incidents and GET /incidents/{incidentId} endpoints
- [ ] 1.8 Write SAM template for API Lambda + API Gateway
- [ ] 1.9 Write unit tests for repository layer (with moto mocking)
- [ ] 1.10 Write unit tests for API endpoints
- [ ] 1.11 Test locally with `sam local start-api`
- [ ] 1.12 Deploy Phase 1 to AWS and verify

**Checkpoint 1:** API returns resources and incidents from DynamoDB. Works locally (SAM) and on AWS.

---

## Phase 2: Simulator Lambda
**Goal:** Autonomous metric simulation running on schedule, publishing to CloudWatch.

- [ ] 2.1 Implement Simulator Lambda handler
- [ ] 2.2 Implement metric generation logic (random walk within bounds, occasional spikes)
- [ ] 2.3 Implement CloudWatch metric publisher (custom namespace: CloudPulse)
- [ ] 2.4 Write SAM template for Simulator Lambda + EventBridge schedule rule
- [ ] 2.5 Implement resource state updater (HEALTHY → WARNING based on thresholds)
- [ ] 2.6 Write unit tests for metric generation and state transition logic
- [ ] 2.7 Test locally with `sam local invoke`
- [ ] 2.8 Deploy Phase 2 and verify metrics appear in CloudWatch console

**Checkpoint 2:** CloudWatch shows live-updating custom metrics every 2 minutes. Resource states change in DynamoDB.

---

## Phase 3: CloudWatch Alarms & EventBridge Integration
**Goal:** Alarms fire when thresholds breached, events routed correctly.

- [ ] 3.1 Define CloudWatch Alarms in SAM template (one per resource per failure type)
- [ ] 3.2 Create EventBridge rule for CloudWatch Alarm state change events
- [ ] 3.3 Implement CloudWatch alarm event parser (extract resourceId, failureType from alarm name convention)
- [ ] 3.4 Create EventBridge schedule rule for heartbeat (already in Phase 2, verify)
- [ ] 3.5 Write integration test: inject metric spike → verify alarm fires → verify EventBridge event
- [ ] 3.6 Deploy Phase 3 and verify alarm → EventBridge pipeline works

**Checkpoint 3:** Alarm breaches produce EventBridge events. Alarm state visible in CloudWatch console.

---

## Phase 4: Recovery Lambda & Incident Management
**Goal:** Recovery executes automatically, incidents persisted, state machine complete.

- [ ] 4.1 Implement Recovery Lambda handler
- [ ] 4.2 Implement recovery state machine (FAILURE_DETECTED → ... → RECOVERED)
- [ ] 4.3 Implement recovery action strategies per failure type
- [ ] 4.4 Implement incident creation and update logic
- [ ] 4.5 Implement idempotency guard (skip if already recovering)
- [ ] 4.6 Add Dead Letter Queue (SQS or SNS) for failed Recovery Lambda invocations
- [ ] 4.7 Write SAM template for Recovery Lambda + DLQ
- [ ] 4.8 Write unit tests for recovery state machine
- [ ] 4.9 Write unit tests for each recovery action strategy
- [ ] 4.10 Test locally with `sam local invoke` using mock EventBridge events
- [ ] 4.11 Deploy Phase 4 and verify end-to-end: metric spike → alarm → recovery → incident created

**Checkpoint 4:** Full failure-to-recovery pipeline works autonomously on AWS.

---

## Phase 5: SNS Notifications
**Goal:** Email notifications sent on key incidents.

- [ ] 5.1 Create SNS topic in SAM template
- [ ] 5.2 Configure SNS subscription (email via environment variable)
- [ ] 5.3 Implement SNS notification publisher in Recovery Lambda
- [ ] 5.4 Define notification templates for each event type (failure detected, recovered, failed, escalated)
- [ ] 5.5 Write unit tests for notification publisher
- [ ] 5.6 Deploy and verify emails are received

**Checkpoint 5:** Email notifications received for failures and recoveries.

---

## Phase 6: Manual Failure Injection API
**Goal:** User can trigger simulated failures via dashboard API.

- [ ] 6.1 Implement POST /simulate/inject endpoint (resource + failure type)
- [ ] 6.2 Implement validation: only allow valid resource IDs and failure types
- [ ] 6.3 Implement metric override in DynamoDB + CloudWatch
- [ ] 6.4 Option: directly put EventBridge event to bypass alarm wait time for demo
- [ ] 6.5 Write unit and integration tests
- [ ] 6.6 Deploy and test end-to-end via curl / Postman

**Checkpoint 6:** Failure injection via API triggers the full recovery pipeline.

---

## Phase 7: React Frontend — Dashboard
**Goal:** Functional, real-time-feeling dashboard showing resource health and incidents.

- [ ] 7.1 Set up React + TypeScript + Vite + Tailwind CSS
- [ ] 7.2 Configure environment variable for API Gateway URL
- [ ] 7.3 Implement API service layer (axios/fetch wrappers)
- [ ] 7.4 Implement ResourceCard component (shows state, metrics, health badge)
- [ ] 7.5 Implement ResourceGrid layout
- [ ] 7.6 Implement IncidentTable component
- [ ] 7.7 Implement MetricsChart component (line chart for CPU/memory/latency over time)
- [ ] 7.8 Implement auto-polling (every 10 seconds)
- [ ] 7.9 Implement "Inject Failure" button per resource
- [ ] 7.10 Implement status badge with color coding by health state
- [ ] 7.11 Write component unit tests (vitest + testing-library)
- [ ] 7.12 Build frontend and test static output

**Checkpoint 7:** Dashboard shows live resource states and incidents. Failure injection works from UI.

---

## Phase 8: S3 Frontend Hosting & CORS Configuration
**Goal:** Frontend hosted on S3, accessible publicly for demo.

- [ ] 8.1 Create S3 bucket for frontend in SAM template
- [ ] 8.2 Configure S3 static website hosting
- [ ] 8.3 Configure CORS on API Gateway for S3 frontend origin
- [ ] 8.4 Write deploy script: build React app → upload to S3
- [ ] 8.5 Configure S3 bucket policy for public read
- [ ] 8.6 Verify end-to-end from S3 URL

**Checkpoint 8:** Full system accessible via S3 URL. Demo-ready.

---

## Phase 9: Testing, Hardening & Documentation
**Goal:** Project is submission-ready with tests, docs, and clean code.

- [ ] 9.1 Achieve >80% unit test coverage on backend
- [ ] 9.2 Write integration test suite (uses real AWS dev environment)
- [ ] 9.3 Review and complete all ADRs
- [ ] 9.4 Update README with final setup, deploy, and demo instructions
- [ ] 9.5 Update ARCHITECTURE.md with any changes from implementation
- [ ] 9.6 Review IAM roles for least-privilege compliance
- [ ] 9.7 Security review: no secrets in code, no overly permissive policies
- [ ] 9.8 Performance test: simulate 10 concurrent failure events
- [ ] 9.9 Record demo video or prepare live demo script
- [ ] 9.10 Final commit, tag v1.0.0, push to GitHub

**Checkpoint 9:** Project complete and submission-ready.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CloudWatch alarm delay (1-5 min) makes demo feel slow | High | Medium | Provide direct EventBridge injection endpoint for fast demo |
| Free Tier CloudWatch metric limit (10 custom metrics) exceeded | Medium | Low | Aggregate metrics; use fewer alarms; cost is <$1/month |
| SAM local testing diverges from real Lambda behavior | Medium | Medium | Run integration tests on real AWS dev account |
| Mangum version incompatibility with FastAPI | Low | High | Pin exact versions; test thoroughly in Phase 1 |
| DynamoDB eventual consistency causes stale reads | Medium | Low | Use strongly consistent reads for state-critical operations |
| S3 CORS misconfiguration blocks frontend | Medium | Medium | Test CORS in Phase 8 before demo |
| EventBridge event schema changes between AWS regions | Low | Medium | Use explicit event pattern matching; test in target region |

---

## Implementation Sequence Summary

Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9

Each phase must pass its checkpoint before the next begins.

