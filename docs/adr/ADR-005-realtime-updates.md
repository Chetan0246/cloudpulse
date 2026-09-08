# ADR-005: Real-time Updates — Polling vs WebSocket / SSE

**Date:** 2026-09-08  
**Status:** Proposed

## Context
The dashboard needs to reflect changing resource states and new incidents without the user manually refreshing. Options: client-side polling, WebSockets (API Gateway WebSocket API), or Server-Sent Events (SSE).

## Decision
**Proposed: Client-side polling (every 10–15 seconds)**

## Rationale
- WebSocket API Gateway is significantly more complex: requires connection management, DynamoDB connection table, and Lambda for connect/disconnect/message.
- SSE is not natively supported by API Gateway HTTP APIs.
- For a reliability simulator, resource state changes happen on the order of minutes (CloudWatch alarm period is 1–5 minutes). 10-second polling is more than sufficient.
- Polling is the simplest approach and easy to implement correctly.
- React's `useEffect` with `setInterval` makes polling straightforward.

## Consequences
Positive:
- Simple implementation.
- No additional AWS services needed.
- Sufficient for demo use case.

Negative:
- Not true real-time; there is up to 10–15s latency in state updates on the dashboard.
- Slightly higher API call volume (though negligible for academic use).

## Alternatives Considered
- **WebSocket (API Gateway WebSocket API)**: True real-time, but adds substantial complexity. Not justified for this project scope.
- **SSE**: More efficient than polling but requires Lambda to hold connections open, which is problematic with Lambda's execution model.
