#!/bin/bash
set -e

# Creates the Container Apps environment (slow, ~5 min). Safe to re-run.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

az extension add --name containerapp --upgrade --yes --only-show-errors

ENV_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" -o tsv)

if az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Environment $ENV_NAME already exists."
else
  echo "Creating Container Apps environment $ENV_NAME (takes a few minutes)..."
  az containerapp env create --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" -o none
fi

echo "Default domain: $(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --query properties.defaultDomain -o tsv)"
