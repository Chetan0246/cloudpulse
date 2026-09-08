#!/usr/bin/env bash
# Deploy the React frontend to S3.
# Run this after `sam deploy` — the S3 bucket must already exist.
#
# Usage: ./scripts/deploy_frontend.sh [environment]
# Example: ./scripts/deploy_frontend.sh dev
set -euo pipefail

ENV="${1:-dev}"
STACK_NAME="cloudpulse-${ENV}"
REGION="${AWS_REGION:-ap-south-1}"

echo "==> Getting S3 bucket name from CloudFormation stack: ${STACK_NAME}"
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketWebsiteURL'].OutputValue" \
  --output text | sed 's|http://||' | cut -d. -f1)

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

echo "==> Building frontend with VITE_API_BASE_URL=${API_URL}"
cd "$(dirname "$0")/../frontend"
VITE_API_BASE_URL="${API_URL}" npm run build

echo "==> Uploading to S3 bucket: ${BUCKET}"
aws s3 sync dist/ "s3://${BUCKET}" --delete --region "${REGION}"

echo "==> Done. Frontend deployed."
echo "    URL: http://${BUCKET}.s3-website.${REGION}.amazonaws.com"
