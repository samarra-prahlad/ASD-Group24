#!/bin/bash
set -e

# Creates the container registry (if missing), then builds and pushes images.
# Uses docker build/push rather than az acr build, because ACR Tasks can be
# restricted on student subscriptions.
# Build a subset with: ONLY="billing-database billing-backend" bash scripts/cloud/build-images.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
source scripts/cloud/services.sh

echo "=== ASD Group 24 Image Build ==="

REGISTRY_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" -o tsv 2>/dev/null || true)
if [ -z "$REGISTRY_NAME" ]; then
  echo "Resource group $RESOURCE_GROUP is missing deployment tags. Run scripts/cloud/env-setup.sh first." >&2
  exit 1
fi

if ! az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Creating container registry $REGISTRY_NAME..."
  az acr create --resource-group "$RESOURCE_GROUP" --name "$REGISTRY_NAME" \
    --sku Basic --location "$LOCATION" >/dev/null
fi

LOGIN_SERVER=$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)

# A new registry can report ready before its hostname resolves.
echo "Waiting for $LOGIN_SERVER to resolve..."
for i in $(seq 1 24); do
  if python3 -c "import socket,sys; socket.gethostbyname(sys.argv[1])" "$LOGIN_SERVER" 2>/dev/null; then
    echo "$LOGIN_SERVER is resolvable."
    break
  fi
  if [ "$i" -eq 24 ]; then
    echo "Timed out waiting for $LOGIN_SERVER to resolve." >&2
    exit 1
  fi
  sleep 5
done

az acr login --name "$REGISTRY_NAME"

BUILT=0
for entry in "${SERVICES[@]}"; do
  NAME=$(service_field "$entry" 1)
  CONTEXT=$(service_field "$entry" 2)
  service_selected "$NAME" || continue

  IMAGE="$LOGIN_SERVER/$NAME:$IMAGE_TAG"
  echo "--- Building $NAME from $CONTEXT ---"
  docker build --platform linux/amd64 -t "$IMAGE" "$CONTEXT"
  docker push "$IMAGE"
  BUILT=$((BUILT + 1))
done

echo "=== Built and pushed $BUILT image(s) to $LOGIN_SERVER with tag $IMAGE_TAG ==="
