# CloudPulse — Live Demo Checklist & Presentation Script

**Course:** BCSE355L – Cloud Architecture Design | Fall 2026-2027  
**Evaluation Milestone:** Project Review 2  
**Purpose:** Step-by-Step Operator Script for the 11-Stage End-to-End Closed-Loop Demonstration  
**Estimated Duration:** 7 – 10 minutes  

---

## 1. Pre-Demo Preparation (T-10 Minutes)

### 1.1 Terminal & Environment Checklist
- [ ] Terminal 1: Backend running or ready (`cd backend && uvicorn app.main:app --port 8000`)
- [ ] Terminal 2: Frontend running (`cd frontend && npm run dev` on `http://localhost:5173`)
- [ ] Terminal 3: AWS CLI / shell ready for database & log inspection
- [ ] Virtual resources seeded and healthy:
  ```bash
  python scripts/seed_data.py
  # Or reset all resources to baseline:
  python scripts/reset_resources.py
  ```

### 1.2 Browser Tabs to Open in Advance
1. **Tab 1 (Primary):** CloudPulse Dashboard (`http://localhost:5173`) — Overview section.
2. **Tab 2:** CloudPulse Dashboard — Failure Simulator section.
3. **Tab 3:** AWS CloudWatch Metrics Console (`CloudPulse` namespace) / Alarms.
4. **Tab 4:** Amazon DynamoDB Items Console (`cloudpulse-incidents-dev` & `cloudpulse-resources-dev`).
5. **Tab 5:** Subscribed Email Inbox (for Amazon SNS alert notifications).

---

## 2. The 11-Stage Final Demonstration Sequence

### Step 1: Show Healthy Resource Baseline
- **Action:** Open Dashboard Overview & Resource Health sections.
- **Presenter Narration:**  
  *"We begin with our fleet of 4 virtual resources: VM-001, API-001, DB-001, and STORAGE-001. All resources are currently in the HEALTHY state with nominal synthetic metrics: CPU at 25%, memory at 30%, storage at 40%, and latency at 10ms. All gauges indicate 100% health score."*
- **Verification Evidence:** All resource cards display green `HEALTHY` badges. Active incidents count is `0`.

---

### Step 2: Trigger Simulated Failure
- **Action:** Navigate to **Failure Simulator** tab. Select target resource **`VM-001`**, failure scenario **`FS-01: High CPU Utilization`**, severity **`HIGH`**. Click **"Inject Workload Anomaly"**.
- **Presenter Narration:**  
  *"We are now injecting failure scenario FS-01 into VM-001. Notice our safety boundary: CloudPulse simulates failures logically by mutating resource records in DynamoDB and publishing real synthetic metric spikes to CloudWatch. It does not disrupt real cloud hardware."*
- **Verification Evidence:** API returns `201 Created` with `scenario_id: "FS-01"`, `incident_id`, and `metrics_emitted: { CPUUtilization: 98.0, MemoryUtilization: 85.0 }`.

---

### Step 3: Show Changed Simulated State
- **Action:** Point to the live 5-stage lifecycle visualizer on the Failure Simulator section and switch to the **Resource Health** section.
- **Presenter Narration:**  
  *"Immediately upon injection, VM-001 transitions from HEALTHY to FAILURE_DETECTED. Its CPU gauge surges to 98% and health status drops to CRITICAL. The dashboard visualizer highlights the FAILURE state."*
- **Verification Evidence:** Resource table shows `VM-001` in red `FAILURE_DETECTED` state.

---

### Step 4: Show CloudWatch Detection
- **Action:** Open AWS CloudWatch Metrics / Alarms tab (or show CloudWatch CLI output).
- **Presenter Narration:**  
  *"The API Lambda published the anomalous 98% CPU metric to CloudWatch namespace 'CloudPulse' under dimensions ResourceId=VM-001. In an autonomous production run, CloudWatch alarm 'cloudpulse-VM-001-HIGH_CPU' evaluates over 2 periods and transitions to ALARM."*
- **CLI Verification:**
  ```bash
  aws cloudwatch get-metric-data --cli-input-json ... # Or view PutMetricData log
  ```

---

### Step 5: Show EventBridge Event
- **Action:** Display CloudWatch Log Group `/aws/lambda/cloudpulse-recovery-dev` or EventBridge rule structure.
- **Presenter Narration:**  
  *"EventBridge is our decoupled backbone. In fast-track mode, the API emitted a 'cloudpulse.simulator: FailureInjected' event carrying the incident ID and correlation ID. In autonomous mode, the CloudWatch Alarm State Change event is routed. EventBridge matches the rule and asynchronously invokes the Recovery Lambda."*
- **Verification Evidence:** Log shows `event: { "source": "cloudpulse.simulator", "detail-type": "FailureInjected", ... }`.

---

### Step 6: Show Recovery Lambda Execution
- **Action:** View CloudWatch Logs for the Recovery Lambda showing structured JSON log entries.
- **Presenter Narration:**  
  *"The Recovery Lambda executes with two-tier idempotency. First, it performs a pre-read check on DynamoDB to prevent duplicate executions. Second, it executes an atomic conditional update transitioning the resource from FAILURE_DETECTED to RECOVERY_INITIATED, then RECOVERY_IN_PROGRESS. It dispatches the SCALE_OUT recovery strategy."*
- **Verification Evidence:** Log output shows:
  - `Recovery Lambda invoked` with matching `correlation_id`
  - `Executing recovery strategy: Simulated scale-out: increased virtual CPU allocation`

---

### Step 7: Show Recovery Result & Metric Reset
- **Action:** Highlight the Recovery Lambda log completion and metric reset confirmation.
- **Presenter Narration:**  
  *"The strategy successfully completes. It applies the target metrics delta: CPU is reset to nominal 25%, and memory is restored to 30%. The Recovery Lambda writes these nominal values back to DynamoDB and calls PutMetricData on CloudWatch to restore the monitoring alarm."*
- **Verification Evidence:** Log line: `Recovery action completed successfully` with `duration_seconds: 3.24s`.

---

### Step 8: Show DynamoDB Incident Audit Trail
- **Action:** Open AWS DynamoDB Console (or run CLI command) to view the incident record in `cloudpulse-incidents-dev`.
- **Presenter Narration:**  
  *"In DynamoDB, we inspect the full 14-field incident record. Notice the complete lifecycle audit: incident_id, detected_at, recovery_started_at, recovered_at, recovery_action (SCALE_OUT), recovery_result, status (RESOLVED), and the embedded recovery_actions array."*
- **CLI Verification:**
  ```bash
  aws dynamodb scan --table-name cloudpulse-incidents-dev --limit 1 --query "Items[0]"
  ```

---

### Step 9: Show SNS Email Notification
- **Action:** Switch to Email Inbox tab and open the received CloudPulse alert email.
- **Presenter Narration:**  
  *"Amazon SNS published human-readable email alerts to operations subscribers for each major lifecycle transition: Failure Detected, Recovery Started, and Recovered. Notice that duplicate notifications were automatically suppressed by our notified_transitions guard."*
- **Verification Evidence:**
  - Subject: `[CloudPulse] RECOVERED: VM-001 — HIGH_CPU`
  - Body contains Incident ID, Resource, Status `RESOLVED`, Recovery Action `SCALE_OUT`, and Duration.

---

### Step 10: Show Dashboard Recovery (Closed-Loop Complete)
- **Action:** Return to CloudPulse Dashboard Overview & Active Incidents sections.
- **Presenter Narration:**  
  *"The React dashboard, via adaptive polling, automatically picks up the state changes. The 5-stage visualizer advances to RECOVERED and returns to HEALTHY. The incident is now archived under Recent Incidents as RESOLVED."*
- **Verification Evidence:** All 4 resources green. Incident table shows `Status: RESOLVED` with green checkmark.

---

### Step 11: Show Updated SRE Reliability Metrics
- **Action:** Navigate to **Reliability Metrics** section on the dashboard.
- **Presenter Narration:**  
  *"Finally, we examine the SRE Reliability Metrics panel. Notice that these values are not fabricated or hardcoded: the Total Incident Count has incremented, Recovery Success Rate reflects 100%, and the Mean Time to Recovery (MTTR) and Average Detection Time have been mathematically recalculated from the stored DynamoDB timestamps."*
- **Verification Evidence:** Metric cards and trend graphs show updated MTTR, Success Rate, and Fleet Health Distribution.

---

## 3. Post-Demo Reset & Cleanup

To reset the demonstration fleet back to virgin baseline state:

```bash
# Reset all 4 virtual resources to HEALTHY and clear active failures
python scripts/reset_resources.py

# Or re-seed initial data
python scripts/seed_data.py
```

---

## 4. Live Presentation Troubleshooting & Fallback

| Issue During Demo | Root Cause | Instant Remediation |
|---|---|---|
| Dashboard not updating | Browser tab inactive or polling paused | Click the manual **Refresh Telemetry** button on the dashboard header. |
| API returns 409 Conflict | Target resource is already recovering | Use a different resource (e.g. `API-001`) or click **Reset Resource** first. |
| SNS Email delayed | Standard email provider delivery queue | Show the CloudWatch Log line confirming `SNS notification published successfully` with message ID. |
| Local backend connection error | Uvicorn stopped | Restart with `cd backend && uvicorn app.main:app --port 8000`. |
