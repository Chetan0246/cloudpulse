# ADR-003: DynamoDB Design — Single-table vs Multi-table

**Date:** 2026-09-08  
**Status:** Proposed

## Context
DynamoDB can be used with a single-table design (all entity types in one table, distinguished by key prefixes and sort keys) or a multi-table design (one table per entity type).

## Decision
**Proposed: Multi-table (separate tables for Resources and Incidents)**

## Rationale
- Multi-table is easier to understand, document, and teach in an academic context.
- Access patterns for Resources and Incidents are completely separate — no join-like access patterns that would benefit from single-table.
- Single-table design requires careful key design upfront and is harder to reason about for reviewers unfamiliar with the pattern.
- Two tables are well within DynamoDB Free Tier limits.

## Consequences
Positive:
- Simpler, more readable data model.
- Easier to query and reason about.
- Appropriate for the access patterns of this project.

Negative:
- If access patterns require joining resource + incident data frequently, this requires two separate reads and application-level joining.
- Mitigation: The API service layer handles joining where needed.

## Alternatives Considered
- **Single-table design**: More DynamoDB-idiomatic for complex access patterns, but overkill here and harder to explain academically.
