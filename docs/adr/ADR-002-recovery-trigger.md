# ADR-002: Recovery Trigger — EventBridge vs Direct Lambda Invocation

**Date:** 2026-09-08  
**Status:** Proposed

## Context
When a CloudWatch alarm fires, we need to invoke the Recovery Lambda. We can either:
(a) Route the alarm event through EventBridge with a rule targeting the Recovery Lambda, or
(b) Have the API Lambda directly invoke the Recovery Lambda (synchronous or async).

## Decision
**Proposed: EventBridge (alarm event → EventBridge rule → Recovery Lambda)**

## Rationale
- Demonstrates event-driven architecture, which is an explicit course requirement.
- Decouples the alarm source from the recovery executor — the Recovery Lambda has no knowledge of what triggered it.
- EventBridge provides built-in retry, filtering, and dead-letter queue support.
- Supports multiple consumers in the future (e.g., also route to a logging Lambda).
- Alarm state change events from CloudWatch natively appear in EventBridge.

## Consequences
Positive:
- True event-driven decoupling.
- Meets course architecture requirements.
- Retry and DLQ built in.

Negative:
- CloudWatch alarm state changes can take 1–5 minutes. Demo may feel slow.
- Mitigation: Provide a `/simulate/inject` API endpoint that puts an EventBridge event directly, bypassing alarm delay for demo purposes.

## Alternatives Considered
- **Direct Lambda invocation from API Lambda**: Simpler but tightly coupled. Doesn't demonstrate EventBridge.
- **SQS queue**: Valid but adds complexity. EventBridge is more appropriate for event routing with filtering.
