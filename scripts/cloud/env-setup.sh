#!/bin/bash
set -e

# Creates the resource group and stores the generated registry name as a tag.
# Safe to re-run: reuses existing names if the group is already configured.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

echo "=== ASD Group 24 Environment Setup ==="
echo "Resource group: $RESOURCE_GROUP  Location: $LOCATION"

for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  echo "Registering $ns (skips if already registered)..."
  az provider register --namespace "$ns" --wait
done

EXISTING_REGISTRY=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv 2>/dev/null || true)
if [ -n "$EXISTING_REGISTRY" ]; then
  echo "Resource group already configured, reusing existing names."
  az group show --name "$RESOURCE_GROUP" --query tags -o table
  exit 0
fi

# Registry names must be globally unique, lowercase alphanumeric.
REGISTRY_NAME="asd24acr${RANDOM}${RANDOM}"

echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null

echo "Tagging resource group with deployment names..."
az group update --name "$RESOURCE_GROUP" \
  --tags registryName="$REGISTRY_NAME" envName="$ENV_NAME" location="$LOCATION" >/dev/null

echo "=== Environment Setup Complete ==="
az group show --name "$RESOURCE_GROUP" --query tags -o table
