# ADR-004: Frontend Hosting — S3 Only vs S3 + CloudFront

**Date:** 2026-09-08  
**Status:** Proposed

## Context
The React frontend needs to be hosted somewhere. Options are S3 static website hosting alone, or S3 behind CloudFront CDN.

## Decision
**Proposed: S3 static website hosting only (no CloudFront for Phase 1)**

## Rationale
- CloudFront is not in the AWS Free Tier for significant usage; it adds cost complexity.
- For an academic demo with a small number of users, S3 static hosting is sufficient.
- CloudFront adds operational complexity (cache invalidation, distribution setup) without benefit at this scale.
- S3 website hosting is accessible over HTTP from a public URL.
- CloudFront can be added in a later phase if HTTPS is required without a custom domain.

## Consequences
Positive:
- Simpler setup.
- Free Tier compatible.
- Faster to set up in Phase 8.

Negative:
- S3 static website endpoints do not support HTTPS (only HTTP).
- CORS origin must be set to the S3 HTTP URL in API Gateway.
- For a production system, CloudFront would be required.

## Alternatives Considered
- **S3 + CloudFront**: Adds HTTPS, CDN caching, custom domain support. Worth revisiting if project is demonstrated publicly. Can be added as Phase 9+ enhancement.
- **Amplify Hosting**: Over-engineered for this project; introduces an additional service dependency.
