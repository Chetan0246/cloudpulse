# CloudPulse Backend

CloudPulse FastAPI Backend — Pure Python 3.12 application implementing the simulation data model, domain services, DynamoDB repository abstraction, and REST API routes.

---

## 1. Prerequisites

- **Python 3.12+**
- **pip** and `venv`
- **AWS CLI / sam CLI** (optional for local simulation; unit tests mock all AWS interactions via `moto`)

---

## 2. Local Environment Setup

### 2.1 Virtual Environment Installation

From the repository root:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Alternatively, from the project root using Makefile:

```bash
make setup-backend
```

### 2.2 Configuration (.env)

The application loads environment variables via `pydantic-settings` from `backend/.env` or system environment variables. Copy the example template:

```bash
cp ../.env.example .env
```

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `AWS_REGION` | `ap-south-1` | AWS region |
| `DYNAMODB_RESOURCES_TABLE` | `cloudpulse-resources` | DynamoDB table for virtual resources |
| `DYNAMODB_INCIDENTS_TABLE` | `cloudpulse-incidents` | DynamoDB table for incident records |
| `DYNAMODB_METRICS_TABLE` | `cloudpulse-metrics` | DynamoDB table for reliability metrics |
| `DYNAMODB_ENDPOINT_URL` | `null` | Optional local DynamoDB/LocalStack endpoint URL |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Allowed origins for CORS (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 3. Running the API Locally

Start the development server with hot reload:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server starts at `http://127.0.0.1:8000`.

### Interactive API Documentation

- **Swagger UI (interactive OpenAPI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 4. API Endpoints Reference

### Health Probes
- `GET /health` — Liveness probe; returns 200 OK if API is running.
- `GET /health/ready` — Readiness probe; checks DynamoDB connectivity (returns 503 if unreachable).

### Simulated Resources
- `GET /resources` — List all simulated resources (lightweight `ResourceSummary`).
- `GET /resources/{resource_id}` — Get full state and metrics for a specific resource (e.g. `VM-001`).

### Incidents
- `GET /incidents` — List incidents sorted newest first. Supports query filters:
  - `resource_id`: e.g. `?resource_id=VM-001`
  - `status`: `OPEN`, `RECOVERING`, `RESOLVED`, `ESCALATED`
  - `failure_type`: `HIGH_CPU`, `SERVICE_FAILURE`, `STORAGE_EXHAUSTION`, `NETWORK_LATENCY`, `SERVICE_DOWNTIME`
  - `limit`: `1..200` (default: 50)
- `GET /incidents/{incident_id}` — Get detailed incident record including embedded recovery action history.

### Reliability Metrics
- `GET /metrics` — List reliability metric snapshots (summaries).
- `GET /metrics/{resource_id}` — Get latest reliability metric snapshot for a resource.
- `GET /metrics/{resource_id}/{window_key}` — Get specific snapshot (e.g. `DAILY%232026-09-08`).

---

## 5. Running Tests, Linters, and Type Checks

All tests run locally without AWS credentials by leveraging `moto`.

### 5.1 Unit Tests and Coverage

```bash
source .venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
```

### 5.2 Code Formatting and Linting

```bash
# Lint check with Ruff:
ruff check .

# Code format check with Black:
black --check .

# Auto-format:
black .
```

### 5.3 Static Type Checking

```bash
mypy app/
```

---

## 6. Architecture & Code Layout

```
backend/
├── app/
│   ├── aws/                 # AWS client factory (DynamoDB, CloudWatch, SNS, EventBridge)
│   │   ├── __init__.py
│   │   └── clients.py
│   ├── config.py            # Pydantic Settings loaded from env
│   ├── exceptions.py        # Domain exceptions (e.g. ResourceNotFoundError)
│   ├── exception_handlers.py# FastAPI exception handlers (translates to HTTP status)
│   ├── logging_config.py    # Structured JSON logging
│   ├── main.py              # FastAPI app factory (CORS, routers, exception handlers)
│   ├── models/              # Pydantic domain models
│   │   ├── __init__.py
│   │   ├── incident.py      # Incident, RecoveryAction value object
│   │   ├── reliability_metric.py # ReliabilityMetric snapshot model
│   │   └── resource.py      # SimulatedResource model
│   ├── repositories/        # DynamoDB data access layer
│   │   ├── __init__.py
│   │   ├── incident_repository.py
│   │   ├── metric_repository.py
│   │   └── resource_repository.py
│   ├── routers/             # FastAPI route handlers (no direct AWS SDK calls)
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── incidents.py
│   │   ├── metrics.py
│   │   └── resources.py
│   └── services/            # Domain service coordination layer
│       ├── __init__.py
│       ├── incident_service.py
│       ├── metric_service.py
│       └── resource_service.py
├── tests/
│   ├── conftest.py          # Moto mock fixtures and TestClient
│   └── unit/
│       ├── test_aws_clients.py
│       ├── test_config.py
│       ├── test_models.py
│       ├── test_repositories.py
│       ├── test_routers.py
│       └── test_services.py
├── pyproject.toml           # Black, Ruff, Mypy, and Pytest configuration
├── requirements.txt         # Production runtime dependencies
└── requirements-dev.txt     # Local development and test dependencies
```
