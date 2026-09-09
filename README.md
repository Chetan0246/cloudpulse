# ☁️ CloudPulse

**Autonomous Cloud Reliability and Self-Healing Simulator Using AWS Serverless Architecture**

> Course: BCSE355L – Cloud Architecture Design | Fall 2026-2027

---

## What is CloudPulse?

CloudPulse simulates cloud reliability concepts on real AWS serverless infrastructure:

| Concept | Implementation |
|---|---|
| Resource monitoring | CloudWatch custom metrics (CPU, memory, storage, latency) |
| Failure detection | CloudWatch Alarms + EventBridge event routing |
| Automated recovery | Recovery Lambda with per-failure-type actions |
| Incident management | DynamoDB incident records with full lifecycle |
| Notifications | SNS email on failure/recovery events |
| Dashboard | React SPA polling API Gateway every 10 seconds |

**CloudPulse never touches real compute infrastructure.** Failures are state changes on logical DynamoDB records.

---

## Architecture at a Glance

```
React Dashboard (S3)
        ↓  poll every 10s
  API Gateway (HTTP API)
        ↓  Lambda proxy
  FastAPI Lambda (Mangum)
        ↓  read/write
  DynamoDB (resources + incidents)
        
  Simulator Lambda ──► CloudWatch Metrics ──► CloudWatch Alarms
         ↑ schedule 2min                              ↓
   EventBridge ◄─────────────────────── alarm state change
         │
         ↓ event rule
  Recovery Lambda ──► DynamoDB (state + incident) ──► SNS (email)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full design.

---

## Project Structure

```
cloudpulse/
├── backend/          # FastAPI application (pure Python, no Lambda code)
├── lambda/           # Lambda entry points: api, simulator, recovery
├── infrastructure/   # AWS SAM template and deployment config
├── frontend/         # React + TypeScript + Tailwind dashboard
├── tests/            # Integration + E2E tests; fixtures
├── docs/             # ADRs, diagrams, runbooks
├── scripts/          # seed_data.py, deploy_frontend.sh, reset_resources.py
└── Makefile          # Developer shortcuts
```

See [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) for detailed layout.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| AWS CLI | v2 | [docs.aws.amazon.com](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| AWS SAM CLI | latest | [docs.aws.amazon.com](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Docker | latest | Required by SAM local (optional for deploy-only) |

---

## Local Development Setup

```bash
# 1. Clone
git clone https://github.com/Chetan0246/cloudpulse.git
cd cloudpulse

# 2. Configure environment
cp .env.example .env
# Edit .env: at minimum set NOTIFICATION_EMAIL

# 3. Install dependencies
make setup-backend
make setup-frontend

# 4. Run backend unit tests (no AWS needed)
make test-backend

# 5a. Start API locally with uvicorn (recommended for fast iteration)
cd backend
uvicorn app.main:app --reload --port 8000

# 5b. Or run via SAM local (requires Docker, uses port 3000)
# make build && sam local start-api --env-vars local-env.json

# 6. Start frontend
cd frontend
cp .env.example .env.local
# VITE_API_BASE_URL defaults to http://localhost:8000 (uvicorn)
# Change to http://localhost:3000 if using SAM local
npm run dev
```

---

## Deploy to AWS

```bash
# First-time deploy (interactive guided mode)
make build
cd infrastructure/sam
sam deploy --guided \
  --parameter-overrides \
    NotificationEmail=your@email.com \
    CorsAllowedOrigins="*"

# After deploy — seed DynamoDB with virtual resources
make seed

# Deploy frontend to S3
./scripts/deploy_frontend.sh dev
```

### Outputs after deploy
- **API URL:** printed as `ApiEndpoint` in sam deploy output
- **Frontend URL:** printed as `FrontendBucketWebsiteURL`

---

## Development Commands

```bash
make help              # Show all commands
make test-backend      # Backend unit tests (moto mocks, no AWS needed)
make test-frontend     # Frontend component tests
make lint              # Ruff + black + eslint
make type-check        # mypy + tsc
make build             # sam build
make deploy            # sam build + sam deploy
make seed              # Load 4 virtual resources into DynamoDB
make reset-resources   # Reset all resources to HEALTHY (demo reset)
make clean             # Remove build artifacts
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, Mangum |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| IaC | AWS SAM |
| Testing | pytest, moto, vitest, testing-library |
| AWS | Lambda (arm64), API Gateway (HTTP), DynamoDB, CloudWatch, EventBridge, SNS, S3, IAM |

---

## Key Documents

| Document | Purpose |
|---|---|
| [PROJECT_CONSTITUTION.md](./PROJECT_CONSTITUTION.md) | Binding rules — read first |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Full system design |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | Phased implementation plan |
| [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Directory layout reference |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Dev setup and contribution guide |
| [docs/adr/](./docs/adr/) | Architectural Decision Records |
| [CHANGELOG.md](./CHANGELOG.md) | Release notes |

---

## Security

- No credentials in source code.
- `.env` files are gitignored.
- Each Lambda has a least-privilege IAM role.
- DynamoDB is not publicly accessible.
- S3 frontend bucket: public read for `GetObject` only.

---

## Cost Estimate (Monthly, AWS Free Tier)

| Service | Usage | Free Tier | Est. Cost |
|---|---|---|---|
| Lambda | ~22K invocations, ~256MB | 1M invocations | $0.00 |
| DynamoDB | <1K reads/writes | 25GB + 200M req | $0.00 |
| CloudWatch | ~16 custom metrics, 5 alarms | 10 metrics, 10 alarms | ~$0.30 |
| EventBridge | ~22K events/month | 1M events | $0.00 |
| S3 | <100MB static files | 5GB | $0.00 |
| SNS | <100 emails | 1K email/month | $0.00 |
| API Gateway | <10K requests/month | 1M requests | $0.00 |
| **Total** | | | **~$0.30/month** |

---

*Academic project. Not for production use.*
