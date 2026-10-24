#!/usr/bin/env bash
# ==============================================================================
# CloudPulse — restore the demo ALB to a healthy, publicly reachable state
#
# The FS-04 NETWORK_REROUTE recovery action switches the ALB listener to the
# standby target group and the workload security group has no public ingress.
# This script is idempotent: it puts the listener back on the primary target
# group, publishes HTTP 80 through a dedicated ALB security group, and makes
# sure the EC2 target serves a small health page.
#
# Usage: ./scripts/restore_demo_alb.sh
# Override any of the variables below through the environment.
# ==============================================================================
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
ALB_NAME="${ALB_NAME:-alb-cloudpulse-gw}"
PRIMARY_TG="${PRIMARY_TG:-tg-cloudpulse-primary}"
INSTANCE_ID="${INSTANCE_ID:-i-083e8c6b1fc9ca0b7}"
ALB_SG_NAME="${ALB_SG_NAME:-cloudpulse-alb-sg}"

say() { printf '\033[1;34m[alb]\033[0m %s\n' "$*"; }

ALB_ARN=$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --region "$REGION" \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)
VPC_ID=$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --region "$REGION" \
  --query 'LoadBalancers[0].VpcId' --output text)
ALB_DNS=$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --region "$REGION" \
  --query 'LoadBalancers[0].DNSName' --output text)
LISTENER_ARN=$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --region "$REGION" \
  --query 'Listeners[0].ListenerArn' --output text)
PRIMARY_ARN=$(aws elbv2 describe-target-groups --names "$PRIMARY_TG" --region "$REGION" \
  --query 'TargetGroups[0].TargetGroupArn' --output text)
INSTANCE_SG=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

say "ALB ${ALB_NAME} in ${VPC_ID}; instance ${INSTANCE_ID} (${INSTANCE_SG})"

# ── 1. Dedicated ALB security group with public HTTP ingress ─────────────────
ALB_SG=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=group-name,Values=${ALB_SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [[ -z "${ALB_SG}" || "${ALB_SG}" == "None" ]]; then
  ALB_SG=$(aws ec2 create-security-group --region "$REGION" \
    --group-name "$ALB_SG_NAME" \
    --description "CloudPulse ALB ingress (HTTP 80)" \
    --vpc-id "$VPC_ID" --query 'GroupId' --output text)
  aws ec2 create-tags --region "$REGION" --resources "$ALB_SG" \
    --tags Key=Name,Value="$ALB_SG_NAME" Key=Project,Value=CloudPulse
  say "created security group ${ALB_SG}"
fi

allow() {
  local group="$1"; shift
  if ! aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$group" "$@" 2>/tmp/cp-alb-sg.err; then
    if grep -q 'InvalidPermission.Duplicate' /tmp/cp-alb-sg.err; then
      return 0
    fi
    cat /tmp/cp-alb-sg.err >&2
    return 1
  fi
}

allow "$ALB_SG" --protocol tcp --port 80 --cidr 0.0.0.0/0
allow "$INSTANCE_SG" --protocol tcp --port 80 --source-group "$ALB_SG"
aws elbv2 set-security-groups --region "$REGION" \
  --load-balancer-arn "$ALB_ARN" --security-groups "$ALB_SG" >/dev/null
say "ALB attached to ${ALB_SG}; instance accepts 80 only from the ALB"

# ── 2. Restore the listener to the primary target group ─────────────────────
aws elbv2 modify-listener --region "$REGION" --listener-arn "$LISTENER_ARN" \
  --default-actions "Type=forward,TargetGroupArn=${PRIMARY_ARN}" >/dev/null
say "listener restored to ${PRIMARY_TG}"

# ── 3. Ensure the EC2 target serves a health page on port 80 ────────────────
WEB_SETUP=$(cat <<'WEB'
#!/bin/bash
set -e
mkdir -p /opt/cloudpulse/www
cat > /opt/cloudpulse/www/index.html <<'HTML'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CloudPulse ALB Target</title></head>
<body style="font-family:system-ui;background:#0b1220;color:#e6edf7;display:grid;place-items:center;height:100vh;margin:0">
<main style="text-align:center">
<h1 style="margin:0 0 8px">CloudPulse</h1>
<p style="margin:0 0 16px">Application Load Balancer target is healthy.</p>
</main>
</body>
</html>
HTML
cat > /etc/systemd/system/cloudpulse-web.service <<'UNIT'
[Unit]
Description=CloudPulse demo HTTP target
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/cloudpulse/www
ExecStart=/usr/bin/python3 -m http.server 80
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable cloudpulse-web >/dev/null 2>&1
systemctl restart cloudpulse-web
sleep 2
systemctl is-active cloudpulse-web
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost/
WEB
)
PAYLOAD=$(printf '%s' "$WEB_SETUP" | base64 -w0)
CMD_ID=$(aws ssm send-command --region "$REGION" --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "commands=[\"echo ${PAYLOAD} | base64 -d > /tmp/cp_web.sh\",\"bash /tmp/cp_web.sh\"]" \
  --query 'Command.CommandId' --output text)
say "SSM command ${CMD_ID} dispatched; waiting..."
for _ in $(seq 1 20); do
  STATUS=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" \
    --instance-id "$INSTANCE_ID" --query 'Status' --output text 2>/dev/null || echo Pending)
  [[ "$STATUS" == "Success" ]] && break
  [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" ]] && {
    aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" \
      --instance-id "$INSTANCE_ID" --query '{Status:Status,Err:StandardErrorContent}' --output json >&2
    exit 1
  }
  sleep 3
done
say "web target status: ${STATUS}"

# ── 4. Wait for the target to become healthy ────────────────────────────────
TG_ARN=$(aws elbv2 describe-target-groups --names "$PRIMARY_TG" --region "$REGION" \
  --query 'TargetGroups[0].TargetGroupArn' --output text)
for _ in $(seq 1 20); do
  HEALTH=$(aws elbv2 describe-target-health --region "$REGION" --target-group-arn "$TG_ARN" \
    --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text)
  say "target health: ${HEALTH}"
  [[ "$HEALTH" == "healthy" ]] && break
  sleep 10
done

# ── 5. Verify end-to-end ────────────────────────────────────────────────────
CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "http://${ALB_DNS}/" || true)
say "http://${ALB_DNS}/ -> ${CODE}"
[[ "$CODE" == "200" ]]
