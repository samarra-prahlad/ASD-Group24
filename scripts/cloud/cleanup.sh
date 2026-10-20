#!/bin/bash
set -e

# Deletes the app resource group (all container apps, registry, environment) to stop billing.
# Does NOT delete asd24-identity-rg, so GitHub Actions login keeps working.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

echo "This will delete resource group: $RESOURCE_GROUP"
az resource list --resource-group "$RESOURCE_GROUP" --query "[].{name:name, type:type}" -o table || true

if [ -z "${CI:-}" ]; then
  read -r -p "Type the resource group name to confirm: " CONFIRM
  if [ "$CONFIRM" != "$RESOURCE_GROUP" ]; then
    echo "Cancelled."
    exit 1
  fi
fi

az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "Deletion started (runs in the background)."
