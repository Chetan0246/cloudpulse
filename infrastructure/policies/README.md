# IAM Policies

IAM roles and policies are defined inline in the SAM template
(`infrastructure/sam/template.yaml`) for each Lambda function.

This directory is reserved for:
- Standalone IAM policy documents that need to be referenced externally
- Policy documentation and justifications
- Least-privilege audit notes

## Principle of Least Privilege

Each Lambda function has its own IAM role with only the permissions it needs:

| Function | DynamoDB | CloudWatch | EventBridge | SNS | SQS |
|---|---|---|---|---|---|
| cloudpulse-api | R+W resources, R incidents | PutMetricData | PutEvents | — | — |
| cloudpulse-simulator | R+W resources | PutMetricData | — | — | — |
| cloudpulse-recovery | R+W resources, R+W incidents | — | — | Publish | SendMessage (DLQ) |

No Lambda has admin, full-DynamoDB, or wildcard resource permissions.
