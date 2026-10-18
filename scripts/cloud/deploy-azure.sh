#!/bin/bash
set -e

# Deploys all services to the existing Container Apps environment.
# Order: databases -> backends -> frontends (from services.sh). Only frontends are external.
# AI-Mode, MCP, RAG and Multi-Agent are disabled by default (cloud baseline).
# Images are pulled with a user-assigned managed identity (AcrPull), because the
# express environment on this subscription does not support system-assigned identities.
# Re-runnable: existing apps are updated, not recreated.
# Deploy a subset with: ONLY="billing-backend billing-frontend" bash scripts/cloud/deploy-azure.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

az extension add --name containerapp --upgrade --yes --only-show-errors

REGISTRY_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv)
ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)
LOGIN_SERVER=$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
REGISTRY_ID=$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
DOMAIN=$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --query properties.defaultDomain -o tsv)

if [ -z "$DOMAIN" ]; then
  echo "Environment $ENV_NAME not found. Run scripts/cloud/deploy-azure-env.sh first." >&2
  exit 1
fi

# --- Image pull identity (user-assigned, AcrPull on the registry only) ---
PULL_IDENTITY="asd24-acr-pull"
if ! az identity show --name "$PULL_IDENTITY" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Creating pull identity $PULL_IDENTITY..."
  az identity create --name "$PULL_IDENTITY" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" -o none
fi
PULL_ID=$(az identity show --name "$PULL_IDENTITY" --resource-group "$RESOURCE_GROUP" --query id -o tsv)
PULL_PRINCIPAL=$(az identity show --name "$PULL_IDENTITY" --resource-group "$RESOURCE_GROUP" --query principalId -o tsv)

EXISTING_PULL=$(az role assignment list --assignee "$PULL_PRINCIPAL" --role AcrPull --scope "$REGISTRY_ID" --query "[0].id" -o tsv 2>/dev/null || true)
if [ -z "$EXISTING_PULL" ]; then
  echo "Granting AcrPull on $REGISTRY_NAME to $PULL_IDENTITY..."
  az role assignment create --assignee-object-id "$PULL_PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role AcrPull --scope "$REGISTRY_ID" -o none
  echo "Waiting 60s for the role assignment to propagate..."
  sleep 60
fi

# Container Apps URLs are predictable from the environment's default domain.
internal_url() { echo "https://$1.internal.$DOMAIN"; }
public_url()   { echo "https://$1.$DOMAIN"; }

AI_FLAGS=(AI_INTEGRATIONS_ENABLED=false AI_MODE_ENABLED=false MCP_ENABLED=false RAG_ENABLED=false MULTI_AGENT_ENABLED=false)

echo "=== ASD Group 24 Azure Deployment ==="
echo "Registry: $LOGIN_SERVER  Tag: $IMAGE_TAG  Domain: $DOMAIN"

deploy_app() {
  local name=$1 port=$2 ingress=$3 min=$4 cpu=$5 mem=$6
  shift 6
  local env_args=()
  [ "$#" -gt 0 ] && env_args=("$@")
  local image="$LOGIN_SERVER/$name:$IMAGE_TAG"

  if az containerapp show --name "$name" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    echo "--- Updating $name ---"
    if [ "${#env_args[@]}" -gt 0 ]; then
      az containerapp update --name "$name" --resource-group "$RESOURCE_GROUP" --image "$image" \
        --min-replicas "$min" --max-replicas 1 --set-env-vars "${env_args[@]}" -o none
    else
      az containerapp update --name "$name" --resource-group "$RESOURCE_GROUP" --image "$image" \
        --min-replicas "$min" --max-replicas 1 -o none
    fi
  else
    echo "--- Creating $name ($ingress) ---"
    local extra=()
    [ "${#env_args[@]}" -gt 0 ] && extra=(--env-vars "${env_args[@]}")
    az containerapp create --name "$name" --resource-group "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --target-port "$port" --ingress "$ingress" \
      --user-assigned "$PULL_ID" --registry-server "$LOGIN_SERVER" --registry-identity "$PULL_ID" \
      --cpu "$cpu" --memory "$mem" --min-replicas "$min" --max-replicas 1 \
      "${extra[@]}" -o none
  fi
}

for entry in "${SERVICES[@]}"; do
  NAME=$(service_field "$entry" 1)
  PORT=$(service_field "$entry" 3)
  TIER=$(service_field "$entry" 4)
  service_selected "$NAME" || continue
  BASE="${NAME%-*}"   # e.g. billing-backend -> billing

  case "$TIER" in
    database)
      # SQLite lives in the container: exactly one replica, always on.
      deploy_app "$NAME" "$PORT" internal 1 0.25 0.5Gi
      ;;
    backend)
      ENV=(DATABASE_SERVICE_URL="$(internal_url "$BASE-database")" "${AI_FLAGS[@]}")
      if [ "$BASE" = "shared" ]; then
        MIN=1   # login/session service stays warm
      else
        MIN=0
        ENV+=(SHARED_ACCESS_API_URL="$(internal_url shared-backend)")
      fi
      if [ "$BASE" = "billing" ]; then
        ENV+=(APPOINTMENTS_DATABASE_API_URL="$(internal_url appointments-backend)"
              PHARMACY_DATABASE_API_URL="$(internal_url pharmacy-backend)")
      fi
      deploy_app "$NAME" "$PORT" internal "$MIN" 0.25 0.5Gi "${ENV[@]}"
      ;;
    frontend)
      SHARED_PUBLIC="$(public_url shared-frontend)"
      ENV=(BACKEND_URL="$(internal_url "$BASE-backend")"
           OWN_BACKEND_PUBLIC="$(public_url "$NAME")"
           SHARED_BACKEND_PUBLIC="$SHARED_PUBLIC"
           SHARED_FRONTEND_PUBLIC="$SHARED_PUBLIC"
           APPOINTMENTS_PUBLIC="$(public_url appointments-frontend)"
           EHR_PUBLIC="$(public_url ehr-frontend)"
           PHARMACY_PUBLIC="$(public_url pharmacy-frontend)"
           BILLING_PUBLIC="$(public_url billing-frontend)"
           LABTESTS_PUBLIC="$(public_url labtests-frontend)"
           WARDBED_PUBLIC="$(public_url wardbed-frontend)")
      deploy_app "$NAME" "$PORT" external 0 0.25 0.5Gi "${ENV[@]}"
      ;;
  esac
done

echo "=== Deployment Complete ==="
echo "Entry point: $(public_url shared-frontend)"
