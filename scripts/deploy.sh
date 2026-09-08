#!/usr/bin/env bash
# ==============================================================================
# CloudPulse — Infrastructure Deployment Script
# ==============================================================================
# Builds and deploys the CloudPulse serverless architecture using AWS SAM.
#
# Usage:
#   ./scripts/deploy.sh [options]
#
# Options:
#   -e, --env <env>        Deployment environment (dev, test, prod). Default: dev
#   -r, --region <region>  AWS region. Default: ap-south-1 (or $AWS_REGION)
#   -m, --email <email>    Notification email for SNS topic alerts. Default: ""
#   -g, --guided           Run SAM deploy in interactive guided mode
#   -d, --dry-run          Validate and build SAM artifacts without deploying
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
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-}"
GUIDED=false
DRY_RUN=false

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_FILE="${ROOT_DIR}/infrastructure/template.yaml"

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
    -m|--email)
      NOTIFICATION_EMAIL="$2"
      shift 2
      ;;
    -g|--guided)
      GUIDED=true
      shift
      ;;
    -d|--dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      cat << 'HELPMSG'
Usage:
  ./scripts/deploy.sh [options]

Options:
  -e, --env <env>        Deployment environment (dev, test, prod). Default: dev
  -r, --region <region>  AWS region. Default: ap-south-1 (or $AWS_REGION)
  -m, --email <email>    Notification email for SNS topic alerts. Default: ""
  -g, --guided           Run SAM deploy in interactive guided mode
  -d, --dry-run          Validate and build SAM artifacts without deploying
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

echo -e "${BOLD}${BLUE}====================================================================${NC}"
echo -e "${BOLD}${BLUE}   CloudPulse — Infrastructure Deployment Manager                   ${NC}"
echo -e "${BOLD}${BLUE}====================================================================${NC}"
echo -e "  Environment:        ${YELLOW}${ENV}${NC}"
echo -e "  Stack Name:         ${YELLOW}${STACK_NAME}${NC}"
echo -e "  AWS Region:         ${YELLOW}${REGION}${NC}"
echo -e "  Template:           ${YELLOW}${TEMPLATE_FILE}${NC}"
echo -e "  Notification Email: ${YELLOW}${NOTIFICATION_EMAIL:-<none>}${NC}"
echo -e "  Dry Run:            ${YELLOW}${DRY_RUN}${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Prerequisites & AWS Authentication Check
# ------------------------------------------------------------------------------
echo -e "${BOLD}[Step 1/5] Checking CLI tools and AWS credentials...${NC}"

if ! command -v sam >/dev/null 2>&1; then
  echo -e "${RED}[FAIL] AWS SAM CLI is required but not found in PATH.${NC}"
  echo "Install via: pip install aws-sam-cli"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo -e "${RED}[FAIL] AWS CLI is required but not found in PATH.${NC}"
  exit 1
fi

if [[ "${DRY_RUN}" = false ]]; then
  echo "Verifying AWS credentials..."
  if ! CALLER_IDENTITY=$(aws sts get-caller-identity --region "${REGION}" 2>&1); then
    echo -e "${RED}[FAIL] Unable to authenticate with AWS.${NC}"
    echo -e "${YELLOW}${CALLER_IDENTITY}${NC}"
    echo ""
    echo "To configure credentials, please run:"
    echo "  aws configure"
    echo "or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN"
    exit 1
  fi
  ACCOUNT_ID=$(echo "${CALLER_IDENTITY}" | grep -o '"Account": "[^"]*' | cut -d'"' -f4 || echo "unknown")
  echo -e "${GREEN}[PASS] Authenticated to AWS Account: ${ACCOUNT_ID}${NC}"
else
  echo -e "${YELLOW}[INFO] Dry-run enabled. Skipping active AWS credentials check.${NC}"
fi

# ------------------------------------------------------------------------------
# 2. Template Validation
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 2/5] Running template validation...${NC}"
if ! "${SCRIPT_DIR}/validate.sh" "${TEMPLATE_FILE}"; then
  echo -e "${RED}[FAIL] Validation script failed. Aborting deployment.${NC}"
  exit 1
fi

# ------------------------------------------------------------------------------
# 3. Build Serverless Artifacts
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 3/5] Building AWS SAM application artifacts...${NC}"
echo "Running 'sam build'..."

BUILD_DIR="${ROOT_DIR}/.aws-sam/build"
if ! sam build -t "${TEMPLATE_FILE}" --build-dir "${BUILD_DIR}"; then
  echo -e "${RED}[FAIL] 'sam build' encountered errors.${NC}"
  exit 1
fi
echo -e "${GREEN}[PASS] SAM build succeeded.${NC}"

# ------------------------------------------------------------------------------
# 4. Dry Run Check
# ------------------------------------------------------------------------------
if [[ "${DRY_RUN}" = true ]]; then
  echo ""
  echo -e "${BOLD}${GREEN}====================================================================${NC}"
  echo -e "${BOLD}${GREEN}   Dry run completed successfully! No AWS resources were deployed.  ${NC}"
  echo -e "${BOLD}${GREEN}====================================================================${NC}"
  exit 0
fi

# ------------------------------------------------------------------------------
# 5. Deploy to AWS CloudFormation
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[Step 5/5] Deploying CloudPulse stack to AWS...${NC}"

if [[ "${GUIDED}" = true ]]; then
  echo "Launching interactive guided deployment..."
  sam deploy --guided \
    -t "${BUILD_DIR}/template.yaml" \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
else
  PARAM_OVERRIDES="Environment=${ENV}"
  if [[ -n "${NOTIFICATION_EMAIL}" ]]; then
    PARAM_OVERRIDES="${PARAM_OVERRIDES} NotificationEmail=${NOTIFICATION_EMAIL}"
  fi

  echo "Executing non-interactive deployment with parameter overrides: ${PARAM_OVERRIDES}"
  sam deploy \
    -t "${BUILD_DIR}/template.yaml" \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides ${PARAM_OVERRIDES} \
    --no-fail-on-empty-changeset \
    --resolve-s3
fi

# ------------------------------------------------------------------------------
# Summary and Outputs
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}====================================================================${NC}"
echo -e "${BOLD}${GREEN}   CloudPulse stack deployed successfully!                          ${NC}"
echo -e "${BOLD}${GREEN}====================================================================${NC}"

echo "Retrieving stack outputs..."
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
  --output table || true

echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Seed virtual resources into DynamoDB:"
echo -e "     ${YELLOW}make seed${NC}  or  ${YELLOW}python scripts/seed_data.py --table cloudpulse-resources-${ENV}${NC}"
echo -e "  2. Test health endpoint:"
echo -e "     ${YELLOW}curl \$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query \"Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue\" --output text)/health${NC}"
echo -e "  3. Deploy frontend SPA:"
echo -e "     ${YELLOW}./scripts/deploy_frontend.sh ${ENV}${NC}"
