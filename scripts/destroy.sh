#!/usr/bin/env bash
# ==============================================================================
# CloudPulse — Infrastructure Teardown Script
# ==============================================================================
# Safely tears down all CloudPulse AWS resources to ensure zero ongoing costs.
#
# Usage:
#   ./scripts/destroy.sh [options]
#
# Options:
#   -e, --env <env>        Target environment to destroy (dev, test, prod). Default: dev
#   -r, --region <region>  AWS region. Default: ap-south-1 (or $AWS_REGION)
#   -f, --force, -y, --yes Bypass confirmation prompt (use with care)
#   -h, --help             Show this help message
# ==============================================================================
set -euo pipefail

# Ensure user binaries (~/.local/bin) are accessible
export PATH="${HOME}/.local/bin:${PATH}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Defaults
ENV="dev"
REGION="${AWS_REGION:-ap-south-1}"
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env)
      ENV="$2"
      shift 2
      ;;
    -r|--region)
      REGION="$2"
      shift 2
      ;;
    -f|--force|-y|--yes)
      FORCE=true
      shift
      ;;
    -h|--help)
      cat << 'HELPMSG'
Usage:
  ./scripts/destroy.sh [options]

Options:
  -e, --env <env>        Target environment to destroy (dev, test, prod). Default: dev
  -r, --region <region>  AWS region. Default: ap-south-1 (or $AWS_REGION)
  -f, --force, -y, --yes Bypass confirmation prompt (use with care)
  -h, --help             Show this help message
HELPMSG
      exit 0
      ;;
    *)
      echo -e "${RED}[ERROR] Unknown argument: $1${NC}"
      echo "Use --help to view available options."
      exit 1
      ;;
  esac
done

STACK_NAME="cloudpulse-${ENV}"

echo -e "${BOLD}${RED}====================================================================${NC}"
echo -e "${BOLD}${RED}   CloudPulse — Infrastructure Teardown Manager                     ${NC}"
echo -e "${BOLD}${RED}====================================================================${NC}"
echo -e "  Environment: ${YELLOW}${ENV}${NC}"
echo -e "  Stack Name:  ${YELLOW}${STACK_NAME}${NC}"
echo -e "  AWS Region:  ${YELLOW}${REGION}${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Tooling & AWS Authentication Check
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Step 1/4] Verifying CLI tools and authentication...${NC}"

if ! command -v aws >/dev/null 2>&1; then
  echo -e "${RED}[FAIL] AWS CLI is required to delete CloudPulse resources.${NC}"
  exit 1
fi

if ! CALLER_IDENTITY=$(aws sts get-caller-identity --region "${REGION}" 2>&1); then
  echo -e "${RED}[FAIL] Unable to authenticate with AWS.${NC}"
  echo -e "${YELLOW}${CALLER_IDENTITY}${NC}"
  echo "Configure credentials via 'aws configure' or set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."
  exit 1
fi

ACCOUNT_ID=$(echo "${CALLER_IDENTITY}" | grep -o '"Account": "[^"]*' | cut -d'"' -f4 || echo "unknown")
echo -e "${GREEN}[PASS] Authenticated to AWS Account: ${ACCOUNT_ID}${NC}"

# ------------------------------------------------------------------------------
# 2. Stack Existence Verification
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 2/4] Verifying stack existence...${NC}"

if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo -e "${GREEN}[INFO] CloudFormation stack '${STACK_NAME}' does not exist in region '${REGION}'. Nothing to destroy.${NC}"
  exit 0
fi

echo -e "${YELLOW}[WARN] Stack '${STACK_NAME}' exists and is targeted for deletion.${NC}"

# ------------------------------------------------------------------------------
# Confirmation Gate
# ------------------------------------------------------------------------------
if [[ "${FORCE}" = false ]]; then
  echo ""
  echo -e "${BOLD}${RED}WARNING: This action will permanently delete all CloudPulse infrastructure,${NC}"
  echo -e "${BOLD}${RED}including DynamoDB virtual resource records, incident logs, and Lambda functions.${NC}"
  echo ""
  read -r -p "Type '${STACK_NAME}' to confirm teardown: " CONFIRMATION
  if [[ "${CONFIRMATION}" != "${STACK_NAME}" ]]; then
    echo -e "${YELLOW}Teardown aborted. Confirmation did not match '${STACK_NAME}'.${NC}"
    exit 0
  fi
fi

# ------------------------------------------------------------------------------
# 3. Clean S3 Buckets Prior to Deletion
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 3/4] Cleaning S3 buckets to prevent deletion blocks...${NC}"

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text 2>/dev/null || echo "")

if [[ -n "${FRONTEND_BUCKET}" && "${FRONTEND_BUCKET}" != "None" ]]; then
  echo "Checking if S3 bucket '${FRONTEND_BUCKET}' contains objects..."
  if aws s3 ls "s3://${FRONTEND_BUCKET}" --region "${REGION}" >/dev/null 2>&1; then
    echo "Emptying S3 bucket 's3://${FRONTEND_BUCKET}'..."
    aws s3 rm "s3://${FRONTEND_BUCKET}" --recursive --region "${REGION}" || true
    echo -e "${GREEN}[PASS] S3 bucket emptied.${NC}"
  fi
fi

# ------------------------------------------------------------------------------
# 4. Delete CloudFormation Stack
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 4/4] Initiating stack deletion...${NC}"

if command -v sam >/dev/null 2>&1; then
  echo "Deleting stack using AWS SAM CLI..."
  sam delete \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --no-prompts
else
  echo "Deleting stack using AWS CLI..."
  aws cloudformation delete-stack \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}"

  echo "Waiting for stack deletion to complete (this may take 1-3 minutes)..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}"
fi

echo ""
echo -e "${BOLD}${GREEN}====================================================================${NC}"
echo -e "${BOLD}${GREEN}   CloudPulse stack '${STACK_NAME}' has been successfully deleted.  ${NC}"
echo -e "${BOLD}${GREEN}====================================================================${NC}"
exit 0
