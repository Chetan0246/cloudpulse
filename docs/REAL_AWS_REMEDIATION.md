# Real AWS remediation upgrade

This opt-in adapter adds five real AWS actions while preserving the existing simulator path. The SAM default is **RealRemediationEnabled=false**; leave it that way for normal deployments and tests. No stack was deployed as part of this code change.

## Audit result and architecture boundary

The repository's SAM template provisions API Gateway, Lambdas, DynamoDB, CloudWatch, EventBridge, SNS, SQS, and S3. Its recovery role previously had only DynamoDB, CloudWatch, SNS, and SQS access. The existing recovery strategies only returned simulated metric deltas; they did not operate on EC2. This change adds a conditional, scoped IAM policy and the recovery adapter.

The connected GitHub repository inspection does not provide AWS account access, so the currently deployed CloudFormation stack and its live resources could not be independently inspected. Confirm the deployed stack's parameters/resources in the AWS console or with the AWS CLI before opting in.

A single standalone EC2 instance cannot safely perform all five actions. The real path requires:
- One dedicated, SSM-managed EC2 primary, running cloudpulse-demo.service; install SSM Agent and attach AmazonSSMManagedInstanceCore to its instance profile.
- A dedicated Auto Scaling group containing the demo compute, with a deliberately bounded MaxSize, to provide scale-out capacity.
- An ALB listener rule and alternate target group containing a distinct healthy EC2 target for reroute. The same standby instance may serve as the alternate if registered and healthy in both target groups.
- A target group with both the primary and healthy standby registered for failover.
- Network connectivity from the Recovery Lambda to AWS APIs through normal AWS service endpoints; the EC2 instance must be reachable by Systems Manager.

The adapter only uses deployment parameters for AWS resource IDs and ARNs. It does not treat EventBridge detail, API body, or simulator resource data as a target or command source. Because an allowed failure event can trigger an action against the one configured target, require authenticated operator access to failure injection and restrict API access before enabling real mode. The current SAM HTTP API template does not configure an authorizer, so do not set RealRemediationEnabled=true while the API is publicly reachable until authentication or private operator-only access has been added and verified.

## Five real action mappings

| Failure type | Real action | Safety checks |
|---|---|---|
| HIGH_CPU | Increase the configured ASG desired capacity by one | Reads the named group; refuses if missing or already at its configured MaxSize; honors ASG cooldown |
| SERVICE_FAILURE | SSM runs the fixed systemctl restart cloudpulse-demo.service command | Sends only to the configured instance ID; command and SSM document are constants |
| STORAGE_EXHAUSTION | SSM deletes files older than one day directly under /var/tmp/cloudpulse-demo/cache | Fixed path, files only, no recursive directory deletion, no event-supplied shell |
| NETWORK_LATENCY | Change one configured ALB listener rule to forward to the configured alternate target group | Requires the configured EC2 target to report healthy in that target group |
| SERVICE_DOWNTIME | Deregister the configured primary from the configured failover target group | Requires a distinct configured standby to be healthy in the same target group first |

The CloudPulse virtual resource and incident records remain the control-plane/audit representation and retain simulated metric reset values for the dashboard. The recovery action outcome records the real AWS result when the event's resource ID exactly matches RealAllowedResourceId. Other virtual resource IDs continue down the simulator path even when the feature flag is on. Current CloudWatch alarms still consume the project's CloudPulse synthetic metrics; the real adapter executes AWS actions but does not add real EC2 telemetry collection. For autonomous remediation based on actual EC2 health, first configure CloudWatch Agent or another trusted telemetry source and align alarm namespace/dimensions with the allowlisted resource.

## Deployment and opt-in

First deploy/inspect with real mode disabled. Do not set the flag true until all dedicated resources, SSM access, ARNs, target health, and ASG bounds have been checked.

~~~bash
sam validate --lint --template-file infrastructure/template.yaml
sam build --template-file infrastructure/template.yaml
sam deploy --stack-name cloudpulse-dev \
  --template-file .aws-sam/build/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment=dev \
    RealRemediationEnabled=false
~~~

After preparing the dedicated demo resources and verifying their identifiers, opt in with exact values. Replace each placeholder; do not paste shell commands or accept these identifiers from an API event.

~~~bash
sam deploy --stack-name cloudpulse-dev \
  --template-file .aws-sam/build/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment=dev \
    RealRemediationEnabled=true \
    RealAllowedResourceId=VM-001 \
    RealEc2InstanceId=i-REPLACE_WITH_DEMO_PRIMARY \
    RealAsgName=REPLACE_WITH_DEDICATED_ASG \
    RealAlbListenerRuleArn=arn:aws:elasticloadbalancing:REGION:ACCOUNT:listener-rule/app/REPLACE/REPLACE/REPLACE \
    RealAlternateTargetGroupArn=arn:aws:elasticloadbalancing:REGION:ACCOUNT:targetgroup/REPLACE/REPLACE \
    RealAlternateInstanceId=i-REPLACE_WITH_HEALTHY_ALTERNATE \
    RealFailoverTargetGroupArn=arn:aws:elasticloadbalancing:REGION:ACCOUNT:targetgroup/REPLACE/REPLACE \
    RealStandbyInstanceId=i-REPLACE_WITH_HEALTHY_STANDBY
~~~

All ARN values must be exact values copied from AWS. The policy resource only exists when the flag is true. The Recovery Lambda timeout is 120 seconds to allow bounded SSM command completion.

Verify the deployed configuration before triggering a demo:

~~~bash
aws cloudformation describe-stacks --stack-name cloudpulse-dev \
  --query 'Stacks[0].Parameters'
RECOVERY_ROLE_ARN="$(aws iam get-role --role-name cloudpulse-recovery-role-dev --query 'Role.Arn' --output text)"
aws iam simulate-principal-policy --policy-source-arn "$RECOVERY_ROLE_ARN" \
  --action-names autoscaling:SetDesiredCapacity \
  --resource-arns REPLACE_WITH_CONFIGURED_ASG_ARN
aws iam simulate-principal-policy --policy-source-arn "$RECOVERY_ROLE_ARN" \
  --action-names ssm:SendCommand \
  --resource-arns arn:aws:ssm:REGION::document/AWS-RunShellScript arn:aws:ec2:REGION:ACCOUNT:instance/PRIMARY_INSTANCE_ID
aws iam simulate-principal-policy --policy-source-arn "$RECOVERY_ROLE_ARN" \
  --action-names elasticloadbalancing:ModifyRule \
  --resource-arns REPLACE_WITH_CONFIGURED_LISTENER_RULE_ARN
aws iam simulate-principal-policy --policy-source-arn "$RECOVERY_ROLE_ARN" \
  --action-names elasticloadbalancing:DeregisterTargets \
  --resource-arns REPLACE_WITH_CONFIGURED_FAILOVER_TARGET_GROUP_ARN
aws ssm describe-instance-information --filters Key=InstanceIds,Values=i-REPLACE_WITH_DEMO_PRIMARY
aws elbv2 describe-target-health --target-group-arn REPLACE_WITH_FAILOVER_TARGET_GROUP_ARN
~~~

Trigger only a VM-001 event for the action being demonstrated. Check the incident recovery action message, Lambda logs, ASG desired capacity, SSM command status, listener rule actions, and target health. The network/failover actions are not safe to test against a production listener or user traffic.

## Test and validate

Run unit tests; these use fakes and make no AWS calls:

~~~bash
cd backend
source .venv/bin/activate
pytest tests/unit/test_real_remediation.py tests/unit/test_recovery_strategies.py -q
pytest tests/unit/test_recovery_handler.py tests/unit/test_recovery_integration.py -q
~~~

Validate SAM and inspect the rendered IAM policy before deployment:

~~~bash
sam validate --lint --template-file infrastructure/template.yaml
sam build --template-file infrastructure/template.yaml
~~~

## Disable and rollback

Immediately disable real actions while retaining the simulator and stack:

~~~bash
sam deploy --stack-name cloudpulse-dev \
  --template-file .aws-sam/build/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides Environment=dev RealRemediationEnabled=false
~~~

Confirm the conditional RecoveryRealRemediationPolicy is absent and the function environment says REAL_REMEDIATION_ENABLED=false. If reverting the code, redeploy the previous known-good SAM template and Lambda package. Do not delete the demo EC2, ASG, load balancer, or target groups as part of application rollback; those are separately managed demo resources.
