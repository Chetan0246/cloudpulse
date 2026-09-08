# FOLDER STRUCTURE
## CloudPulse

This document defines the canonical folder structure for the project.
All contributors must follow this layout. Do not create top-level folders
without updating this document.

---

```
cloudpulse/
│
├── PROJECT_CONSTITUTION.md       # Binding rules and principles
├── ARCHITECTURE.md               # System architecture documentation
├── DEVELOPMENT_PLAN.md           # Phased development plan with task tracking
├── FOLDER_STRUCTURE.md           # This file
├── CHANGELOG.md                  # Release history
├── README.md                     # Setup and getting started guide
├── Makefile                      # Developer shortcuts (dev, test, deploy, etc.)
├── .gitignore
│
├── backend/                      # All Python / AWS Lambda source code
│   │
│   ├── template.yaml             # AWS SAM template (all AWS resources)
│   ├── samconfig.toml            # SAM deploy configuration
│   ├── pyproject.toml            # Python project config (deps, tools)
│   ├── requirements.txt          # Runtime dependencies
│   ├── requirements-dev.txt      # Dev/test dependencies
│   │
│   ├── src/                      # Lambda function source packages
│   │   │
│   │   ├── common/               # Shared code across Lambdas
│   │   │   ├── __init__.py
│   │   │   ├── config.py         # Environment variable loading
│   │   │   ├── logging.py        # Structured JSON logger setup
│   │   │   ├── models.py         # Pydantic models (Resource, Incident, enums)
│   │   │   └── exceptions.py     # Custom exception classes
│   │   │
│   │   ├── api/                  # API Lambda (FastAPI + Mangum)
│   │   │   ├── __init__.py
│   │   │   ├── handler.py        # Lambda handler entry point (Mangum wrapper)
│   │   │   ├── app.py            # FastAPI application factory
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── resources.py  # /resources routes
│   │   │   │   ├── incidents.py  # /incidents routes
│   │   │   │   ├── simulate.py   # /simulate routes (failure injection)
│   │   │   │   └── metrics.py    # /metrics routes (CloudWatch summaries)
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── resource_service.py
│   │   │   │   ├── incident_service.py
│   │   │   │   └── simulation_service.py
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       ├── resource_repository.py
│   │   │       └── incident_repository.py
│   │   │
│   │   ├── simulator/            # Simulator Lambda
│   │   │   ├── __init__.py
│   │   │   ├── handler.py        # Lambda handler entry point
│   │   │   ├── metric_generator.py   # Random metric walk logic
│   │   │   ├── cloudwatch_publisher.py  # Publish to CloudWatch
│   │   │   └── state_evaluator.py    # Evaluate thresholds, update state
│   │   │
│   │   └── recovery/             # Recovery Lambda
│   │       ├── __init__.py
│   │       ├── handler.py        # Lambda handler entry point
│   │       ├── event_parser.py   # Parse EventBridge/CloudWatch event
│   │       ├── state_machine.py  # Recovery state machine transitions
│   │       ├── actions/
│   │       │   ├── __init__.py
│   │       │   ├── base_action.py
│   │       │   ├── cpu_recovery.py
│   │       │   ├── service_restart.py
│   │       │   ├── storage_cleanup.py
│   │       │   ├── network_reroute.py
│   │       │   └── service_downtime.py
│   │       └── notifier.py       # SNS notification publisher
│   │
│   ├── scripts/
│   │   ├── seed_data.py          # Seed 4 virtual resources into DynamoDB
│   │   └── cleanup.py            # Delete all data from tables (dev reset)
│   │
│   └── tests/
│       ├── conftest.py           # pytest fixtures (moto mocks, test client)
│       ├── unit/
│       │   ├── test_models.py
│       │   ├── test_resource_repository.py
│       │   ├── test_incident_repository.py
│       │   ├── test_metric_generator.py
│       │   ├── test_state_evaluator.py
│       │   ├── test_state_machine.py
│       │   ├── test_recovery_actions.py
│       │   └── test_api_routes.py
│       └── integration/
│           ├── test_failure_to_recovery.py  # End-to-end pipeline test
│           └── test_api_integration.py
│
├── frontend/                     # React TypeScript application
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   ├── .env.example              # Template for .env.local (not committed)
│   │
│   ├── public/
│   │   └── favicon.ico
│   │
│   └── src/
│       ├── main.tsx              # React entry point
│       ├── App.tsx               # Root component + routing
│       │
│       ├── api/                  # API client layer
│       │   ├── client.ts         # Axios/fetch base client
│       │   ├── resources.ts      # Resource API calls
│       │   ├── incidents.ts      # Incident API calls
│       │   ├── simulate.ts       # Simulation trigger API calls
│       │   └── types.ts          # TypeScript types matching backend models
│       │
│       ├── components/           # Reusable UI components
│       │   ├── ResourceCard.tsx
│       │   ├── ResourceGrid.tsx
│       │   ├── IncidentTable.tsx
│       │   ├── MetricsChart.tsx
│       │   ├── HealthBadge.tsx
│       │   ├── StateBadge.tsx
│       │   └── InjectFailureModal.tsx
│       │
│       ├── pages/                # Top-level page components
│       │   ├── Dashboard.tsx     # Main dashboard page
│       │   └── IncidentDetail.tsx
│       │
│       ├── hooks/                # Custom React hooks
│       │   ├── useResources.ts   # Polling hook for resources
│       │   └── useIncidents.ts   # Polling hook for incidents
│       │
│       └── tests/
│           ├── components/
│           └── hooks/
│
└── docs/
    ├── adr/
    │   ├── README.md             # ADR template and index
    │   ├── ADR-001-iac-tool.md
    │   ├── ADR-002-recovery-trigger.md
    │   ├── ADR-003-dynamodb-design.md
    │   ├── ADR-004-frontend-hosting.md
    │   ├── ADR-005-realtime-updates.md
    │   └── ADR-006-api-serving.md
    │
    └── diagrams/
        ├── architecture.png      # Exported architecture diagram
        └── state-machine.png     # Recovery state machine diagram
```

---

## Key Layout Decisions

1. **Mono-repo**: Frontend and backend share one Git repository for simplicity in an academic project.
2. **`src/` under `backend/`**: All Lambda code lives under `backend/src/`. Each Lambda is its own sub-package. Shared code lives in `common/`.
3. **SAM template at `backend/template.yaml`**: Single SAM template defines all AWS resources. This keeps IaC co-located with the code it deploys.
4. **Separate `services/` and `repositories/`**: Services contain business logic; repositories contain only DynamoDB operations. This makes testing cleaner.
5. **`actions/` sub-package in recovery**: Each failure type has its own recovery action module. Adding a new failure type means adding one file without touching others.
6. **`frontend/src/api/`**: All API calls go through this layer. Components never call fetch/axios directly. Makes mocking easy for tests.
7. **`docs/adr/`**: Every significant architectural decision is recorded. This is a course requirement and good engineering practice.

