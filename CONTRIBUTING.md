# Contributing to CloudPulse

> This is an academic project for BCSE355L – Cloud Architecture Design (Fall 2026-2027).
> Read [PROJECT_CONSTITUTION.md](./PROJECT_CONSTITUTION.md) before contributing anything.

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend / Lambda |
| Node.js | 20+ | Frontend |
| AWS CLI | v2 | AWS interaction |
| AWS SAM CLI | latest | Local Lambda testing & deploy |
| Docker | latest | SAM local requires Docker |

### Local Setup

```bash
# 1. Clone
git clone https://github.com/Chetan0246/cloudpulse.git
cd cloudpulse

# 2. Configure environment
cp .env.example .env
# Edit .env with your values

# 3. Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 4. Frontend
cd ../frontend
npm install
cp .env.example .env.local
# Edit .env.local: set VITE_API_BASE_URL

# 5. Run locally (SAM + Vite)
# Terminal 1 – API
cd ../infrastructure
sam build && sam local start-api --env-vars ../local-env.json

# Terminal 2 – Frontend
cd ../frontend && npm run dev
```

---

## Branch & Commit Strategy

| Branch | Purpose |
|---|---|
| `main` | Protected. Only merges from phase branches. |
| `phase/N-name` | Feature work for each development phase. |
| `fix/short-description` | Bug fixes. |

### Commit Message Format

```
<type>(<scope>): <short summary>

Types: feat | fix | test | docs | refactor | chore | infra
Scope: backend | frontend | lambda | infra | tests | docs

Examples:
feat(backend): add resource health score calculator
fix(lambda): handle missing resourceId in recovery event
infra(sam): add DynamoDB GSI for incident status queries
test(backend): add moto mock for resource repository
```

---

## Code Standards

### Python (backend/ and lambda/)

- **Formatter:** `black` (line length 100)
- **Linter:** `ruff`
- **Type checker:** `mypy` (strict)
- **Type hints required on all functions**
- **Docstrings required on all public functions and classes**

Run checks:
```bash
cd backend
black --check .
ruff check .
mypy .
pytest
```

### TypeScript (frontend/)

- **TypeScript strict mode** enabled
- **ESLint + Prettier** configured
- No `any` types without explicit justification comment
- Components must have prop interface definitions

Run checks:
```bash
cd frontend
npm run lint
npm run type-check
npm run test
```

---

## Testing Requirements

| Layer | Tool | Requirement |
|---|---|---|
| Backend unit | pytest + moto | Every service/repository function |
| Lambda unit | pytest + moto | Every handler with mock events |
| Frontend unit | vitest + testing-library | Every component and hook |
| Integration | pytest (real AWS dev account) | Full pipeline tests |

### Running Tests

```bash
# Backend unit tests (no AWS needed — uses moto)
cd backend && pytest tests/unit/ -v

# Lambda unit tests
cd lambda && pytest tests/ -v

# Integration tests (requires AWS dev credentials)
cd tests/integration && pytest -v

# Frontend tests
cd frontend && npm run test
```

---

## Environment Variables

- Never hardcode credentials or ARNs.
- Local dev: use `.env` (gitignored).
- Lambda: environment variables are injected by the SAM template.
- Sensitive values in SAM: use `--parameter-overrides` or SSM Parameter Store references.

---

## Adding a New AWS Service

1. Justify it. Write a new ADR in `docs/adr/`.
2. Add it to the SAM template in `infrastructure/sam/template.yaml`.
3. Add the IAM permission to the specific Lambda role that needs it.
4. Update `ARCHITECTURE.md`.
5. Update `.env.example` if a new environment variable is needed.

---

## Pull Request Checklist

Before opening a PR:
- [ ] Tests pass locally
- [ ] No secrets in diff
- [ ] Type checks pass
- [ ] `DEVELOPMENT_PLAN.md` tasks updated
- [ ] If adding AWS service: ADR written
- [ ] If changing API: routes documented in `docs/api.md`
