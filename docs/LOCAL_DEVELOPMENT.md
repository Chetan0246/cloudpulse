# Local Development Guide

This guide details how to set up, run, test, and develop the CloudPulse backend locally without connecting to real AWS infrastructure.

---

## 1. Quick Start

### 1.1 Prerequisites
- Python 3.12+ (`python3.12 --version`)
- pip & venv
- Git

### 1.2 Setup Environment

```bash
cd /path/to/cloudpulse

# Use the project Makefile:
make setup-backend

# Or manually:
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 1.3 Configuration
Copy the sample environment file:

```bash
cd backend
cp ../.env.example .env
```

---

## 2. Running the API Locally

Activate your virtual environment and start Uvicorn:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once started:
- API Root: `http://127.0.0.1:8000`
- Swagger Interactive Documentation: `http://127.0.0.1:8000/docs`
- ReDoc Documentation: `http://127.0.0.1:8000/redoc`

---

## 3. Testing

CloudPulse backend unit tests use **Moto** to mock all AWS DynamoDB, CloudWatch, SNS, and EventBridge interactions in-memory. No AWS account or credentials are required.

### 3.1 Running the Full Test Suite

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
```

### 3.2 Running Specific Test Files

```bash
# Domain model validation tests
pytest tests/unit/test_models.py -v

# Repositories (DynamoDB operations with Moto mocks)
pytest tests/unit/test_repositories.py -v

# Domain services tests
pytest tests/unit/test_services.py -v

# API router endpoints and HTTP status code tests
pytest tests/unit/test_routers.py -v
```

---

## 4. Linting and Type Checking

The backend enforces strict code quality with Ruff, Black, and Mypy.

```bash
cd backend
source .venv/bin/activate

# 1. Run Ruff linter:
ruff check .

# 2. Run Black format checker:
black --check .

# 3. Run Mypy static type checker (strict mode):
mypy app/
```

Or via the root Makefile:

```bash
make lint
make type-check
```

---

## 5. Architectural Principles

1. **Separation of Concerns:**
   - `routers/`: Only handle HTTP concerns (request parsing, query parameters, status codes).
   - `services/`: Encapsulate domain rules and orchestrate repositories.
   - `repositories/`: Exclusively interact with DynamoDB tables using boto3.
   - `aws/`: Centralized boto3 client and resource factories.
   - `models/`: Pure Pydantic models with domain validation rules.

2. **No Fake AWS Logic:**
   - Repositories perform real DynamoDB API calls (tested with Moto mocks).
   - Floats are serialised as `Decimal` and deserialised back to Python floats.

3. **Error Handling:**
   - Repositories and services raise domain exceptions (`ResourceNotFoundError`, `IncidentNotFoundError`, `MetricNotFoundError`, `InvalidStateTransitionError`, `DatabaseError`).
   - Exception handlers translate domain errors to standard HTTP status codes (404, 409, 422, 500) with structured JSON bodies.
