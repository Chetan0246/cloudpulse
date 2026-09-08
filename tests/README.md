# Tests

## Structure

```
tests/
├── integration/   # Tests against real AWS (dev account). Require credentials.
├── e2e/           # End-to-end tests against deployed S3 + API Gateway URL
└── fixtures/      # Shared test data (DynamoDB seed items, mock events)
```

Unit tests live co-located with each package:
- `backend/tests/unit/`  — pytest + moto for all backend code
- Unit tests for lambda handlers are also in `backend/tests/unit/`

## Running Integration Tests

```bash
# Requires: AWS credentials configured, dev stack deployed
export CLOUDPULSE_API_URL=$(aws cloudformation describe-stacks \
  --stack-name cloudpulse-dev \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

cd tests/integration
pytest -v --tb=short
```

## Fixtures

`fixtures/` contains:
- `seed_resources.json` — 4 virtual resources for test setup
- `mock_alarm_event.json` — Sample CloudWatch alarm EventBridge event
- `mock_inject_event.json` — Sample direct injection EventBridge event
