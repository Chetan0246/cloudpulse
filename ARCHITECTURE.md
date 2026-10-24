# CloudPulse — System Architecture Reference

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** Core Architectural Reference  
**Version:** 2.0  
**Status:** Implemented, Audited & Verified  

---

## 1. System Overview & Philosophy

CloudPulse is an enterprise-grade autonomous cloud reliability control plane operating across real AWS multi-service infrastructure:
- **Real AWS Managed Workload Fleet:** Amazon EC2 (`i-083e8c6b1fc9ca0b7`), Auto Scaling Group (`asg-cloudpulse-fleet`), Application Load Balancer (`alb-cloudpulse-gw`), Amazon RDS PostgreSQL (`rds-cloudpulse-db`), and AWS Systems Manager (SSM Agent).
- **Autonomous Detection:** Real CloudWatch metric threshold alarms evaluating live workload telemetry.
- **Decoupled Event Bus:** EventBridge rules routing state-change and direct injection events.
- **Deterministic Self-Healing:** Lambda Recovery Engine executing genuine AWS SDK (`boto3`) remediation calls (`ec2:RebootInstances`, `autoscaling:SetDesiredCapacity`, `rds:RebootDBInstance`, `ssm:SendCommand`).
- **Incident Audit Trail:** 14-field incident records with embedded recovery action histories in DynamoDB.
- **Alert Dispatch:** Automated email and SMS notifications via Amazon SNS.
- **Live SRE Console:** React 19 + TypeScript SPA hosted on Amazon S3 static website hosting.

> **SAFETY BOUNDARY & EXECUTION MODES:**  
> CloudPulse features dual execution modes: `REAL_AWS`/`HYBRID` (executes genuine AWS SDK remediation on live infrastructure) and `SIMULATION` (non-destructive digital-twin mode). In `REAL_AWS`/`HYBRID` mode, operations are strictly guarded by **`REAL_AWS_ALLOWLIST`**. The recovery engine will NEVER modify, reboot, or disrupt any AWS resource not explicitly present in the allowlist.

---

## 2. Component Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (Static Web Hosting)"]
        UI["React 18 Dashboard<br/>(TypeScript + Tailwind)"]
        S3["Amazon S3 Bucket<br/>(Private, Website Config)"]
        S3 -.->|Delivers SPA| UI
    end

    subgraph IngressLayer ["Ingress & Management Layer"]
        APIGW["Amazon API Gateway<br/>(HTTP API v2 / Payload 2.0)"]
        UI -->|HTTPS / Adaptive Polling| APIGW
        APILambda["API Lambda Function<br/>(FastAPI + Mangum / arm64)"]
        APIGW -->|Proxy Request| APILambda
    end

    subgraph DataLayer ["Data & Telemetry Persistence Layer"]
        DDB_Res[("DynamoDB Resources Table<br/>PK: resource_id")]
        DDB_Inc[("DynamoDB Incidents Table<br/>PK: incident_id | GSI: ResourceIndex")]
        DDB_Met[("DynamoDB Metrics Table<br/>PK: resource_id | SK: window_key")]
        APILambda <-->|Read / Write State| DDB_Res
        APILambda <-->|Query Incidents| DDB_Inc
        APILambda <-->|Read Metrics| DDB_Met
    end

    subgraph ObservabilityLayer ["Observability & Event Bus Layer"]
        CW_Met["CloudWatch Custom Metrics<br/>(Namespace: CloudPulse)"]
        CW_Alarms["CloudWatch Metric Alarms<br/>(CPU, Latency, Storage, Health)"]
        EB["Amazon EventBridge<br/>(Default Event Bus)"]
        
        APILambda -->|PutMetricData| CW_Met
        CW_Met -->|Threshold Evaluation| CW_Alarms
        CW_Alarms -->|Alarm State Change| EB
        APILambda -.->|Direct Fast-Track Event| EB
    end

    subgraph RecoveryLayer ["Autonomous Self-Healing Layer"]
        RecLambda["Recovery Lambda Function<br/>(Strategy Engine / arm64)"]
        EB -->|Rule Match / Invoke| RecLambda
        DLQ[("Amazon SQS<br/>Recovery DLQ")]
        RecLambda -.->|Persistent Failure| DLQ
        
        RecLambda -->|Conditional Update| DDB_Res
        RecLambda -->|Update Incident Record| DDB_Inc
        RecLambda -->|Metric Reset| CW_Met
    end

    subgraph NotificationLayer ["Alerting Layer"]
        SNS["Amazon SNS Topic<br/>(cloudpulse-notifications)"]
        Email(["Operations Engineer<br/>(Email Subscriber)"])
        RecLambda -->|Publish Notification| SNS
        APILambda -->|Publish Failure Notification| SNS
        SNS -->|Deliver Alert| Email
    end
```

---

## 3. Data Flows

### 3.1 Autonomous Failure-to-Recovery Flow (Closed Loop)
1. **Heartbeat / Drift:** Scheduled Simulator Lambda or running service mutates synthetic metric in DynamoDB.
2. **Metric Publishing:** `PutMetricData` sends CPU, memory, storage, and latency data points to CloudWatch.
3. **Alarm Evaluation:** CloudWatch detects that metric exceeds threshold for 2 consecutive 1-minute periods and transitions alarm to `ALARM` state.
4. **Alarm Event Generation:** CloudWatch emits a `CloudWatch Alarm State Change` event to the EventBridge default bus.
5. **Rule Matching:** EventBridge rule `AlarmStateChange` matches the event (filtering out `-SERVICE_HEALTH` composite alarms) and invokes the Recovery Lambda asynchronously.
6. **Idempotency Verification:** Recovery Lambda checks DynamoDB resource state. If state is already `RECOVERY_INITIATED` or `RECOVERY_IN_PROGRESS`, execution terminates safely.
7. **Incident Correlation:** Recovery Lambda retrieves existing open incident or creates a new incident record in DynamoDB.
8. **State Transition:** Resource transitions atomically from `FAILURE_DETECTED` to `RECOVERY_INITIATED` then `RECOVERY_IN_PROGRESS`.
9. **Strategy Execution:** The remediation strategy mapped to the failure type executes, returning nominal metric resets.
10. **Telemetry & State Restoration:** Resource state transitions to `RECOVERED` with nominal metrics; incident status transitions to `RESOLVED`.
11. **Confirmation Metrics:** Nominal metrics are published back to CloudWatch, restoring alarms to `OK`.
12. **Alert Dispatch:** An SNS notification with full incident duration and outcome details is dispatched to subscribers.

### 3.2 Direct Simulation Flow (Fast-Track for Demos & Testing)
1. **Operator Action:** User clicks **Inject Failure** on the React Console or issues `POST /simulate/failure`.
2. **Atomic Failure Recording:** API Lambda validates the resource state, updates DynamoDB state to `FAILURE_DETECTED`, and creates an `OPEN` incident record.
3. **Metric Spike:** API Lambda publishes anomalous metric values to CloudWatch immediately.
4. **Direct Event Emission:** API Lambda publishes a `cloudpulse.simulator: FailureInjected` event to EventBridge with the `incidentId` and `correlationId` in the detail payload.
5. **Instant Execution:** EventBridge rule `DirectSimulatorEvent` routes the event directly to Recovery Lambda without waiting for the 2-minute CloudWatch alarm evaluation window.
6. **Recovery & UI Reflection:** Recovery Lambda resolves the exact incident created in Step 2 and notifies the frontend via the next polling cycle.

---

## 4. Formal Recovery State Machine

The recovery engine operates on an 8-state deterministic state machine:

```
       [ HEALTHY ]
            │
            ▼ (Metric threshold breached)
       [ WARNING ]
            │
            ▼ (Threshold sustained / Anomaly injected)
   [ FAILURE_DETECTED ] ◄──────────┐
            │                      │ Retry (Attempts < 3)
            ▼                      │
  [ RECOVERY_INITIATED ]           │
            │                      │
            ▼                      │
 [ RECOVERY_IN_PROGRESS ]          │
      │            │               │
      │ (Success)  │ (Strategy     │
      │            │  Exception)   │
      ▼            ▼               │
 [ RECOVERED ]   [ RECOVERY_FAILED ]
      │                            │
      │ (Metrics nominal)          ▼ (Attempts >= 3)
      ▼            [ MANUAL_INTERVENTION_REQUIRED ]
  [ HEALTHY ]
```

---

## 5. Remediation Strategy Dispatch Matrix

| Failure Type | Real AWS Target | Logical Resource | Remediation Strategy | Real AWS SDK Action Dispatched | Target Metrics Reset |
|---|---|---|---|---|---|
| `HIGH_CPU` | `asg-cloudpulse-fleet` | `VM-001`, `API-001` | Scale Out Strategy | `autoscaling:SetDesiredCapacity(cur+1)` or `ec2:RebootInstances` | CPU = 25.0%, Memory = 30.0% |
| `SERVICE_FAILURE` | `i-083e8c6b1fc9ca0b7` | `API-001`, `VM-001` | Service Restart Strategy | `ec2:RebootInstances(InstanceIds=[...])` | Latency = 15.0 ms, CPU = 25.0% |
| `STORAGE_EXHAUSTION` | `i-083e8c6b1fc9ca0b7` | `STORAGE-001` | Storage Cleanup Strategy | `ssm:SendCommand(Document='AWS-RunShellScript')` | Storage = 20.0% |
| `NETWORK_LATENCY` | `alb-cloudpulse-gw` | `DB-001`, `API-001` | Network Reroute Strategy | `elbv2:ModifyListener` / Target Group Deregistration | Latency = 15.0 ms |
| `SERVICE_DOWNTIME` | `rds-cloudpulse-db` | `DB-001` | Failover Standby Strategy | `rds:RebootDBInstance(ForceFailover=True)` | CPU = 25%, Mem = 30%, Stor = 20%, Lat = 15ms |

---

## 6. IAM Least-Privilege Architecture

| Role | Principal | Permitted Actions | Resource Scope |
|---|---|---|---|
| **ApiFunctionRole** | `lambda.amazonaws.com` | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Scan` on Resources/Metrics; `dynamodb:Query` on Incidents GSI | Scoped to project tables and GSI ARNs |
| | | `cloudwatch:PutMetricData` | `Resource: "*"` with `Condition: cloudwatch:namespace = "CloudPulse"` |
| | | `events:PutEvents` | Scoped to default EventBus |
| | | `sns:Publish` | Scoped to `cloudpulse-notifications` topic ARN |
| **RecoveryFunctionRole** | `lambda.amazonaws.com` | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Scan`, `dynamodb:Query` | Scoped to ResourcesTable and IncidentsTable ARNs |
| | | `cloudwatch:PutMetricData` | Scoped to `CloudPulse` namespace |
| | | `sns:Publish` | Scoped to `cloudpulse-notifications` topic ARN |
| | | `sqs:SendMessage` | Scoped to `RecoveryDLQ` ARN |
| | | `ec2:RebootInstances`, `ec2:DescribeInstances` | Scoped to project tag / allowlisted EC2 instances |
| | | `autoscaling:SetDesiredCapacity`, `autoscaling:Describe*` | Scoped to `asg-cloudpulse-fleet` |
| | | `rds:RebootDBInstance`, `rds:DescribeDBInstances` | Scoped to `rds-cloudpulse-db` |
| | | `ssm:SendCommand`, `ssm:GetCommandInvocation` | Scoped to `AWS-RunShellScript` and managed instances |
