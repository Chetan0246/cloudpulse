# CloudPulse

**Autonomous Cloud Reliability and Self-Healing Simulator Using AWS Serverless Architecture**

Course: BCSE355L – Cloud Architecture Design | Fall 2026-2027

---

## What is CloudPulse?

CloudPulse is an academic simulation platform that demonstrates cloud reliability engineering concepts:
- Autonomous failure detection via CloudWatch metrics and alarms
- Event-driven recovery via EventBridge and Recovery Lambda
- Incident persistence in DynamoDB
- Real-time dashboard built with React

CloudPulse simulates virtual resources (VM, API, DB, Storage). It does NOT manage or disrupt real infrastructure.

---

## Architecture Overview

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full architecture.

```
React Dashboard → API Gateway → FastAPI Lambda → DynamoDB
                                      ↓
                             Simulator Lambda → CloudWatch → EventBridge
                                                                  ↓
                                                         Recovery Lambda → SNS
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Mangum |
| IaC | AWS SAM |
| AWS Services | Lambda, API Gateway, DynamoDB, CloudWatch, EventBridge, SNS, S3, IAM |

---

## Project Structure

See [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) for the full layout.

---

## Getting Started

> Prerequisites: Python 3.12, Node.js 20+, AWS CLI configured, AWS SAM CLI installed.

### 1. Clone and configure

```bash
git clone https://github.com/Chetan0246/cloudpulse.git
cd cloudpulse
cp backend/.env.example backend/.env   # Fill in your values
```

### 2. Run backend locally

```bash
cd backend
pip install -r requirements-dev.txt
sam build
sam local start-api
```

### 3. Run frontend locally

```bash
cd frontend
npm install
cp .env.example .env.local            # Set VITE_API_URL to SAM local URL
npm run dev
```

### 4. Deploy to AWS

```bash
cd backend
sam deploy --guided                    # First deploy only; saves config to samconfig.toml
```

---

## Development Plan

See [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) for the phased implementation plan.

---

## Key Documents

| Document | Purpose |
|---|---|
| [PROJECT_CONSTITUTION.md](./PROJECT_CONSTITUTION.md) | Binding rules and constraints |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | Phase-by-phase implementation plan |
| [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Canonical folder layout |
| [docs/adr/](./docs/adr/) | Architectural Decision Records |
| [CHANGELOG.md](./CHANGELOG.md) | Release history |

---

## Security Notes

- Never commit `.env` files or AWS credentials.
- All secrets go in environment variables or AWS SSM Parameter Store.
- See Section 2.3 of PROJECT_CONSTITUTION.md.

---

## License

Academic project — not for production use.
