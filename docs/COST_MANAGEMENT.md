# CloudPulse — Cost Management & AWS Free Tier Analysis

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Document Type:** FinOps & Cloud Economics Assessment  
**Version:** 1.0  
**Status:** Audited & Verified  

---

## 1. Executive Summary & Cost Philosophy

A core requirement of the **CloudPulse Project Constitution (§2.1)** is strict adherence to AWS Free Tier boundaries. The architecture was designed from the ground up to prevent runaway cloud bills, eliminate expensive provisioned services (such as NAT Gateways, Multi-AZ relational databases, or idle EC2 instances), and allow continuous academic evaluation for under **$1.00 per month**.

---

## 2. Granular Service-by-Service Free Tier Analysis

| AWS Service | AWS Free Tier Allowance | CloudPulse Monthly Consumption | Billable Units | Estimated Monthly Cost |
|---|---|---|---|---|
| **AWS Lambda** | 1,000,000 requests/mo<br/>400,000 GB-seconds/mo | ~22,000 requests/mo<br/>~3,500 GB-seconds (arm64) | 0 (Well within tier) | **$0.00** |
| **Amazon DynamoDB** | 25 GB storage<br/>25 provisioned RCU/WCU (or 200M on-demand req) | < 2 MB storage<br/>~50,000 reads/writes (on-demand) | 0 (Well within tier) | **$0.00** |
| **Amazon API Gateway** | 1,000,000 HTTP requests/mo (first 12 months) | ~15,000 requests/mo (adaptive polling) | 0 (Well within tier) | **$0.00** |
| **Amazon EventBridge** | 1,000,000 custom events/mo | ~25,000 events/mo | 0 (Well within tier) | **$0.00** |
| **Amazon SNS** | 1,000 email deliveries/mo<br/>1,000,000 publishes/mo | ~150 emails/mo<br/>~200 publishes/mo | 0 (Well within tier) | **$0.00** |
| **Amazon SQS (DLQ)** | 1,000,000 requests/mo | < 100 messages/mo | 0 (Well within tier) | **$0.00** |
| **Amazon S3** | 5 GB standard storage<br/>20,000 GET requests/mo | ~400 KB SPA bundle<br/>~500 GET requests/mo | 0 (Well within tier) | **$0.00** |
| **CloudWatch Metrics** | 10 custom metrics free<br/>($0.30/metric thereafter) | 16 custom metrics (4 resources $\times$ 4 metrics) | 6 paid metrics | **~$1.80** |
| **CloudWatch Alarms** | 10 standard alarms free<br/>($0.10/alarm thereafter) | 12 standard alarms (3 alarms $\times$ 4 resources) | 2 paid alarms | **~$0.20** |
| **CloudWatch Logs** | 5 GB ingestion & storage free | < 50 MB (7-day retention) | 0 (Well within tier) | **$0.00** |
| **NET TOTAL** | | | | **~$0.80 – $2.00 / month** |

> [!NOTE]
> As documented in [ARCHITECTURE_AUDIT.md](../ARCHITECTURE_AUDIT.md), CloudWatch custom metrics and alarms represent the **only billable line items** in the entire project. This minimal overage (~$0.80/month) is intentionally accepted to demonstrate real multi-dimensional infrastructure alarms across all 4 virtual resources.

---

## 3. Architectural Cost Containment Strategies

### 3.1 Graviton2 (`arm64`) Lambda Architecture
All three Lambda functions (`ApiFunction`, `SimulatorFunction`, `RecoveryFunction`) are compiled and executed on AWS Graviton2 (`arm64`) processors. This reduces compute costs by approximately 20% compared to standard x86 architectures while delivering lower cold-start latencies.

### 3.2 Batched Metric Ingestion
Instead of issuing individual `put_metric_data` API calls per metric (which would generate 20 API calls per evaluation cycle), CloudPulse batches all 5 metrics into a single API request:
```python
cw_client.put_metric_data(
    Namespace="CloudPulse",
    MetricData=[
        {"MetricName": "CPUUtilization", ...},
        {"MetricName": "MemoryUtilization", ...},
        {"MetricName": "StorageUtilization", ...},
        {"MetricName": "NetworkLatency", ...},
        {"MetricName": "ServiceHealth", ...},
    ]
)
```
This reduces CloudWatch API request volume by 80%.

### 3.3 Adaptive Client Polling
Client-side polling against serverless APIs can rapidly inflate API Gateway and Lambda invocation counts. CloudPulse's React frontend implements an adaptive polling strategy:
- **Active Incident Phase (3 seconds):** Smooth real-time visualization while a failure is recovering.
- **Nominal Phase (10 seconds):** Standard heartbeat when the fleet is healthy.
- **Background Phase (30 seconds):** Automatically reduces polling frequency when the browser tab is hidden (`document.hidden`), protecting student accounts from accidental overnight polling costs.

### 3.4 Strict 7-Day CloudWatch Log Retention
Unmanaged CloudWatch log groups accumulate gigabytes of historical telemetry over months. In `infrastructure/template.yaml`, every log group explicitly specifies:
```yaml
RetentionInDays: 7
```
Older logs are automatically purged by AWS at zero cost.

### 3.5 Pay-Per-Request DynamoDB Billing
All tables use `BillingMode: PAY_PER_REQUEST`. Unlike provisioned capacity (which bills hourly even when traffic is zero), on-demand DynamoDB bills exactly $0.00 when the system is idle.

---

## 4. Teardown & Decommissioning Runbook

To ensure zero ongoing charges when project reviews and evaluations are concluded, execute the automated destruction script:

```bash
# Deletes all CloudFormation stacks, S3 buckets, DynamoDB tables, and CloudWatch log groups
make destroy
```

Or invoke the script directly:
```bash
./scripts/destroy.sh dev
```

The script automatically:
1. Empties the S3 frontend bucket (preventing CloudFormation bucket-deletion failures).
2. Deletes the AWS CloudFormation stack (`cloudpulse-dev`).
3. Verifies that all Lambda log groups and alarms are completely removed from the AWS account.
