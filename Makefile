# CloudPulse — Developer Makefile
# Usage: make <target>

.PHONY: help setup-backend setup-frontend test-backend test-frontend \
        build deploy seed reset-resources lint type-check clean

help:
	@echo ""
	@echo "CloudPulse Developer Commands"
	@echo "=============================="
	@echo "  make setup-backend      Install Python dev dependencies"
	@echo "  make setup-frontend     Install Node dependencies"
	@echo "  make test-backend       Run backend unit tests (moto mocks)"
	@echo "  make test-frontend      Run frontend unit tests"
	@echo "  make lint               Run all linters"
	@echo "  make type-check         Run mypy + tsc"
	@echo "  make build              sam build (Lambda + Layer)"
	@echo "  make deploy             sam deploy (guided first time)"
	@echo "  make seed               Seed DynamoDB with 4 virtual resources"
	@echo "  make reset-resources    Reset all resources to HEALTHY"
	@echo "  make clean              Remove build artifacts"
	@echo ""

setup-backend:
	cd backend && python -m venv .venv && \
	  .venv/bin/pip install --upgrade pip && \
	  .venv/bin/pip install -r requirements-dev.txt
	@echo "Backend ready. Activate with: source backend/.venv/bin/activate"

setup-frontend:
	cd frontend && npm install
	@echo "Frontend ready."

test-backend:
	cd backend && .venv/bin/pytest tests/unit/ -v --tb=short \
	  --cov=app --cov-report=term-missing

test-frontend:
	cd frontend && npm run test

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/black --check .
	cd frontend && npm run lint

type-check:
	cd backend && .venv/bin/mypy app/
	cd frontend && npm run type-check

build:
	cd infrastructure/sam && sam build

deploy: build
	cd infrastructure/sam && sam deploy

seed:
	cd backend && .venv/bin/python ../scripts/seed_data.py

reset-resources:
	cd backend && .venv/bin/python ../scripts/reset_resources.py

clean:
	rm -rf infrastructure/sam/.aws-sam
	rm -rf frontend/dist
	rm -rf backend/.venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
