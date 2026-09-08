# Architectural Decision Records (ADRs)

This directory contains the Architectural Decision Records for CloudPulse.

## What is an ADR?

An ADR documents a significant architectural decision: what was decided, why, and what the consequences are. Once accepted, ADRs are immutable (mark superseded ones with a link to the superseding ADR instead of editing).

## Template

```markdown
# ADR-NNN: Title

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Superseded by ADR-NNN | Deprecated

## Context
What is the situation that forces us to make this decision?

## Decision
What have we decided to do?

## Consequences
What are the positive and negative consequences of this decision?

## Alternatives Considered
What other options were evaluated and why were they rejected?
```

## Index

| ADR | Title | Status |
|---|---|---|
| ADR-001 | IaC Tool: SAM vs CDK | Proposed |
| ADR-002 | Recovery Trigger: EventBridge vs Direct Invocation | Proposed |
| ADR-003 | DynamoDB Design: Single-table vs Multi-table | Proposed |
| ADR-004 | Frontend Hosting: S3 Only vs CloudFront | Proposed |
| ADR-005 | Real-time Updates: Polling vs WebSocket/SSE | Proposed |
| ADR-006 | API Serving: Mangum+APIGW vs Lambda Function URL | Proposed |
