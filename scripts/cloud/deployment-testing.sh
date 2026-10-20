#!/bin/bash
# Validates the deployed cloud application and writes reports/cloud/deployment-results.md.
# Requires CLOUD_TEST_EMAIL and CLOUD_TEST_PASSWORD (an admin account from the shared seed data),
# passed as environment variables so no credentials live in the repo.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

: "${CLOUD_TEST_EMAIL:?Set CLOUD_TEST_EMAIL to a seeded admin email}"
: "${CLOUD_TEST_PASSWORD:?Set CLOUD_TEST_PASSWORD for that account}"

ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --query properties.defaultDomain -o tsv)
public_url() { echo "https://$1.$DOMAIN"; }

REPORT_DIR="reports/cloud"
REPORT="$REPORT_DIR/deployment-results.md"
mkdir -p "$REPORT_DIR"
BODY=$(mktemp)
PASS=0; FAIL=0; ROWS=""

# Returns the HTTP status, retrying while apps scale up from zero (000/502/503/504).
probe() {
  local method=$1 url=$2 data=${3:-} code="000"
  for _ in $(seq 1 12); do
    if [ -n "$data" ]; then
      code=$(curl -s -o "$BODY" -w '%{http_code}' --max-time 30 -X "$method" \
        -H 'Content-Type: application/json' -d "$data" "$url")
    else
      code=$(curl -s -o "$BODY" -w '%{http_code}' --max-time 30 -X "$method" "$url")
    fi
    case "$code" in 000|502|503|504) sleep 10 ;; *) break ;; esac
  done
  echo "$code"
}

record() {  # name, method, display path, expected status, actual status
  local result="PASS"
  if [ "$5" = "$4" ]; then PASS=$((PASS + 1)); else result="FAIL"; FAIL=$((FAIL + 1)); fi
  ROWS+="| $1 | $2 | \`$3\` | $4 | $5 | $result |"$'\n'
  echo "[$result] $1: $2 $3 -> $5 (expected $4)"
}

echo "=== ASD Group 24 Cloud Deployment Testing ==="
echo "Domain: $DOMAIN"

# 1. Every frontend is reachable from the internet
for entry in "${SERVICES[@]}"; do
  NAME=$(service_field "$entry" 1); TIER=$(service_field "$entry" 4)
  [ "$TIER" = "frontend" ] || continue
  record "$NAME reachable" GET "/" 200 "$(probe GET "$(public_url "$NAME")/")"
done

# 2. Login through the shared frontend (frontend -> shared-backend -> shared-database)
SHARED=$(public_url shared-frontend)
CODE=$(probe POST "$SHARED/login" "{\"email_address\":\"$CLOUD_TEST_EMAIL\",\"password\":\"$CLOUD_TEST_PASSWORD\"}")
record "Admin login" POST "/login" 200 "$CODE"
TOKEN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("token",""))' "$BODY" 2>/dev/null || true)

# 3. CRUD through each feature's frontend proxy (frontend -> backend -> database)
B=$(public_url billing-frontend)
record "Billing: read invoices" GET "/invoices" 200 "$(probe GET "$B/invoices?token=$TOKEN")"
record "Billing: create invoice" POST "/invoices/generate" 201 \
  "$(probe POST "$B/invoices/generate?token=$TOKEN" '{"patient_id": 1}')"
record "Appointments: read" GET "/appointments" 200 "$(probe GET "$(public_url appointments-frontend)/appointments")"
record "EHR: read patients" GET "/patients" 200 "$(probe GET "$(public_url ehr-frontend)/patients?token=$TOKEN")"
record "Pharmacy: read medications" GET "/medications" 200 "$(probe GET "$(public_url pharmacy-frontend)/medications")"
record "Lab Tests: read orders" GET "/orders" 200 "$(probe GET "$(public_url labtests-frontend)/orders")"
record "Ward & Bed: read ward" GET "/wards/1" 200 "$(probe GET "$(public_url wardbed-frontend)/wards/1")"

# 4. Cloud baseline: AI-Mode, MCP, RAG and Multi-Agent disabled on every backend
for entry in "${SERVICES[@]}"; do
  NAME=$(service_field "$entry" 1); TIER=$(service_field "$entry" 4)
  [ "$TIER" = "backend" ] || continue
  FLAGS=$(az containerapp show -n "$NAME" -g "$RESOURCE_GROUP" \
    --query "properties.template.containers[0].env[?ends_with(name,'_ENABLED')].value" -o tsv | sort -u | tr '\n' ' ')
  [ "$(echo "$FLAGS" | xargs)" = "false" ] && ACTUAL=disabled || ACTUAL="${FLAGS:-unset}"
  record "$NAME AI services" ENV "*_ENABLED" disabled "$ACTUAL"
done
rm -f "$BODY"

TOTAL=$((PASS + FAIL))
{
  echo "# Cloud Deployment Results"
  echo
  echo "- **Platform:** Azure Container Apps (standard environment, ${LOCATION})"
  echo "- **Entry point:** $SHARED"
  echo "- **Commit / image tag:** $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "- **Tested at (UTC):** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- **Result:** $PASS/$TOTAL checks passed"
  echo
  echo "| Check | Method | Path | Expected | Actual | Result |"
  echo "|---|---|---|---|---|---|"
  printf "%s" "$ROWS"
  echo
  echo "## Human release decision"
  echo
  echo "Status: (READY / NOT READY)  "
  echo "Approved by:  "
  echo "Date:  "
} > "$REPORT"

echo "=== $PASS/$TOTAL checks passed. Report: $REPORT ==="
[ "$FAIL" -eq 0 ]
