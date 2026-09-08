# ADR-001: IaC Tool — AWS SAM vs AWS CDK

**Date:** 2026-09-08  
**Status:** Proposed

## Context
We need Infrastructure as Code to provision all AWS resources reproducibly. The two main AWS-native options are AWS SAM and AWS CDK.

## Decision
**Proposed: AWS SAM**

## Rationale
- SAM is purpose-built for serverless (Lambda + API Gateway + DynamoDB) — which is exactly what CloudPulse uses.
- SAM templates are YAML-based and more readable for academic review.
- SAM CLI provides `sam local start-api` and `sam local invoke` for local testing without deploying.
- Lower learning curve. CDK requires familiarity with a general-purpose programming language for IaC.
- SAM is sufficient for the complexity of this project.

## Consequences
Positive:
- Simple, readable YAML template.
- Local testing support via SAM CLI.
- Lower dependency footprint.

Negative:
- Less expressive than CDK for complex dynamic resource generation.
- SAM is less flexible if the project later needs complex constructs (e.g., VPCs, ECS clusters).

## Alternatives Considered
- **AWS CDK (Python)**: More powerful, better for large projects. Overkill for this scope.
- **Terraform**: Not AWS-native; adds a third-party dependency without benefit for an AWS-only project.
- **CloudFormation (raw)**: Too verbose. SAM is a superset, so no reason to use raw CFN.
