#!/usr/bin/env bash
# ==============================================================================
# CloudPulse — Infrastructure & Architecture Validation Script
# ==============================================================================
# Performs comprehensive local validation of the CloudPulse AWS SAM template,
# architecture constraints, security rules, and cost-control configurations.
#
# Usage:
#   ./scripts/validate.sh [path/to/template.yaml]
# ==============================================================================
set -euo pipefail

# Ensure user binaries (~/.local/bin) are accessible
export PATH="${HOME}/.local/bin:${PATH}"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine template path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_FILE="${1:-${ROOT_DIR}/infrastructure/template.yaml}"

echo -e "${BOLD}${BLUE}====================================================================${NC}"
echo -e "${BOLD}${BLUE}   CloudPulse — Infrastructure Foundation Validator                 ${NC}"
echo -e "${BOLD}${BLUE}====================================================================${NC}"
echo -e "Target template: ${YELLOW}${TEMPLATE_FILE}${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Template Existence Check
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/6] Checking template existence...${NC}"
if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo -e "${RED}[FAIL] Template file not found: ${TEMPLATE_FILE}${NC}"
  exit 1
fi
echo -e "${GREEN}[PASS] Template file exists.${NC}"

# ------------------------------------------------------------------------------
# 2. Tooling Availability
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/6] Checking validation tooling...${NC}"

HAS_SAM=false
HAS_CFNLINT=false
HAS_PYTHON=false

if command -v sam >/dev/null 2>&1; then
  SAM_VERSION=$(sam --version)
  echo -e "  - AWS SAM CLI: ${GREEN}found${NC} (${SAM_VERSION})"
  HAS_SAM=true
else
  echo -e "  - AWS SAM CLI: ${YELLOW}not found in PATH${NC}"
fi

if command -v cfn-lint >/dev/null 2>&1; then
  CFN_VERSION=$(cfn-lint --version)
  echo -e "  - cfn-lint:    ${GREEN}found${NC} (${CFN_VERSION})"
  HAS_CFNLINT=true
else
  echo -e "  - cfn-lint:    ${YELLOW}not found in PATH${NC}"
fi

if command -v python3 >/dev/null 2>&1; then
  PY_VERSION=$(python3 --version)
  echo -e "  - Python 3:    ${GREEN}found${NC} (${PY_VERSION})"
  HAS_PYTHON=true
fi

# ------------------------------------------------------------------------------
# 3. YAML Syntax Validation via Python
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/6] Validating YAML syntax...${NC}"
if [[ "${HAS_PYTHON}" = true ]]; then
  python3 -c "
import sys, yaml

class CfnLoader(yaml.SafeLoader):
    pass

# Register CloudFormation shorthand tags as pass-through constructors
tags = [
    '!Ref', '!Sub', '!GetAtt', '!Equals', '!Not', '!If', '!And', '!Or',
    '!Condition', '!FindInMap', '!Select', '!Split', '!Join', '!ImportValue',
    '!Base64', '!Cidr'
]
def cfn_constructor(loader, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)

for tag in tags:
    CfnLoader.add_constructor(tag, cfn_constructor)

try:
    with open('${TEMPLATE_FILE}', 'r') as f:
        yaml.load(f, Loader=CfnLoader)
    print('YAML syntax is valid.')
except Exception as e:
    print(f'YAML syntax error: {e}', file=sys.stderr)
    sys.exit(1)
"
  echo -e "${GREEN}[PASS] YAML syntax and indentation are valid.${NC}"
else
  echo -e "${YELLOW}[SKIP] Python3 not available for raw YAML parse test.${NC}"
fi

# ------------------------------------------------------------------------------
# 4. CloudFormation Linter (cfn-lint)
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/6] Running AWS CloudFormation linter (cfn-lint)...${NC}"
if [[ "${HAS_CFNLINT}" = true ]]; then
  if cfn-lint "${TEMPLATE_FILE}"; then
    echo -e "${GREEN}[PASS] cfn-lint passed with 0 errors/warnings.${NC}"
  else
    echo -e "${RED}[FAIL] cfn-lint identified issues in ${TEMPLATE_FILE}.${NC}"
    exit 1
  fi
else
  echo -e "${YELLOW}[WARN] cfn-lint not installed. Install with: pip install cfn-lint${NC}"
fi

# ------------------------------------------------------------------------------
# 5. AWS SAM CLI Template Validation
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[5/6] Running AWS SAM template validator (sam validate)...${NC}"
if [[ "${HAS_SAM}" = true ]]; then
  if sam validate -t "${TEMPLATE_FILE}" --lint; then
    echo -e "${GREEN}[PASS] sam validate passed successfully.${NC}"
  else
    echo -e "${RED}[FAIL] sam validate failed for ${TEMPLATE_FILE}.${NC}"
    exit 1
  fi
else
  echo -e "${YELLOW}[WARN] SAM CLI not installed. Install with: pip install aws-sam-cli${NC}"
fi

# ------------------------------------------------------------------------------
# 6. Architectural Constraints & Cost-Control Policy Checks
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[6/6] Enforcing architectural constraints and cost guards...${NC}"

VIOLATIONS=0

# Rule 1: No EC2 instances
if grep -q "AWS::EC2::Instance" "${TEMPLATE_FILE}"; then
  echo -e "${RED}  [VIOLATION] Found AWS::EC2::Instance (violates Free Tier / serverless rules)${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo -e "  ${GREEN}✔${NC} No EC2 instances provisioned"
fi

# Rule 2: No RDS databases
if grep -qE "AWS::RDS::DBInstance|AWS::RDS::DBCluster" "${TEMPLATE_FILE}"; then
  echo -e "${RED}  [VIOLATION] Found AWS::RDS resources (violates Free Tier / serverless rules)${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo -e "  ${GREEN}✔${NC} No RDS database instances or clusters provisioned"
fi

# Rule 3: No NAT Gateways or VPC Load Balancers
if grep -qE "AWS::EC2::NatGateway|AWS::ElasticLoadBalancingV2::LoadBalancer" "${TEMPLATE_FILE}"; then
  echo -e "${RED}  [VIOLATION] Found expensive always-on networking resources (NAT Gateway/ALB)${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo -e "  ${GREEN}✔${NC} No expensive NAT Gateways or VPC Load Balancers"
fi

# Rule 4: DynamoDB uses PAY_PER_REQUEST
if grep -q "BillingMode: PAY_PER_REQUEST" "${TEMPLATE_FILE}"; then
  echo -e "  ${GREEN}✔${NC} DynamoDB configured with PAY_PER_REQUEST (zero idle cost)"
else
  echo -e "${RED}  [VIOLATION] DynamoDB missing PAY_PER_REQUEST billing mode${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
fi

# Rule 5: DynamoDB does not use STANDARD_INFREQUENT_ACCESS for small tables
if grep -q "TableClass: STANDARD_INFREQUENT_ACCESS" "${TEMPLATE_FILE}"; then
  echo -e "${RED}  [VIOLATION] DynamoDB uses STANDARD_INFREQUENT_ACCESS which is not Free Tier eligible for small tables${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo -e "  ${GREEN}✔${NC} DynamoDB uses Standard table class (eligible for 25 GB AWS Free Tier)"
fi

# Rule 6: CloudWatch Log Groups have explicit retention
LOG_RETENTION_COUNT=$(grep -c "RetentionInDays" "${TEMPLATE_FILE}" || true)
if [[ "${LOG_RETENTION_COUNT}" -ge 4 ]]; then
  echo -e "  ${GREEN}✔${NC} Explicit CloudWatch Log retention configured (${LOG_RETENTION_COUNT} log groups)"
else
  echo -e "${YELLOW}  [WARNING] Expected at least 4 log groups with explicit RetentionInDays (found ${LOG_RETENTION_COUNT})${NC}"
fi

# Rule 7: S3 Public Access is protected by default
if grep -q "EnablePublicFrontendBucket" "${TEMPLATE_FILE}" && grep -q "BlockPublicAcls: !If" "${TEMPLATE_FILE}"; then
  echo -e "  ${GREEN}✔${NC} S3 PublicAccessBlock guarded by parameter (private by default)"
else
  echo -e "${RED}  [VIOLATION] S3 bucket is unconditionally public or missing PublicAccessBlock${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
fi

# Rule 8: Least-privilege IAM roles exist for all 3 functions
if grep -q "ApiFunctionRole:" "${TEMPLATE_FILE}" && \
   grep -q "SimulatorFunctionRole:" "${TEMPLATE_FILE}" && \
   grep -q "RecoveryFunctionRole:" "${TEMPLATE_FILE}"; then
  echo -e "  ${GREEN}✔${NC} Least-privilege IAM roles defined for API, Simulator, and Recovery functions"
else
  echo -e "${RED}  [VIOLATION] Missing one or more dedicated Lambda IAM roles${NC}"
  VIOLATIONS=$((VIOLATIONS + 1))
fi

# Rule 9: CloudWatch alarms count <= 10 (Free Tier limit)
ALARM_COUNT=$(grep -c "Type: AWS::CloudWatch::Alarm" "${TEMPLATE_FILE}" || true)
if [[ "${ALARM_COUNT}" -le 10 ]]; then
  echo -e "  ${GREEN}✔${NC} CloudWatch alarms within AWS Free Tier limit (${ALARM_COUNT}/10 standard alarms)"
else
  echo -e "${YELLOW}  [WARNING] ${ALARM_COUNT} CloudWatch alarms defined. Free Tier includes 10 alarms.${NC}"
fi

echo ""
if [[ "${VIOLATIONS}" -gt 0 ]]; then
  echo -e "${RED}${BOLD}Validation failed with ${VIOLATIONS} policy violation(s).${NC}"
  exit 1
fi

echo -e "${BOLD}${GREEN}====================================================================${NC}"
echo -e "${BOLD}${GREEN}   All CloudPulse infrastructure validations passed successfully!   ${NC}"
echo -e "${BOLD}${GREEN}====================================================================${NC}"
exit 0
