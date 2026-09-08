# ADR-006: API Serving — Mangum + API Gateway vs Lambda Function URL

**Date:** 2026-09-08  
**Status:** Proposed

## Context
FastAPI needs to run in Lambda. Two approaches:
(a) API Gateway HTTP API → Lambda proxy → Mangum (ASGI adapter for Lambda)
(b) Lambda Function URL (direct HTTPS endpoint on the Lambda, no API Gateway)

## Decision
**Proposed: API Gateway (HTTP API) + Mangum**

## Rationale
- API Gateway is an explicit project requirement (per course constraints).
- API Gateway provides built-in CORS configuration, request throttling, and access logging.
- Mangum is a well-maintained, widely-used library for exactly this purpose.
- Lambda Function URLs are simpler but bypass API Gateway, which is a required service.

## Consequences
Positive:
- Meets course requirement for API Gateway.
- CORS, throttling, and logging configured in one place.
- API Gateway HTTP API is cheaper and faster than REST API.

Negative:
- Mangum version must be pinned carefully to match FastAPI version.
- Slightly more complex SAM template than a plain Function URL.
- Cold start time slightly higher with FastAPI + Mangum vs a plain Lambda handler.

## Alternatives Considered
- **Lambda Function URL**: Simpler, no API Gateway needed. But API Gateway is a course requirement.
- **API Gateway REST API**: More features but more expensive and more complex than HTTP API. HTTP API is sufficient.
