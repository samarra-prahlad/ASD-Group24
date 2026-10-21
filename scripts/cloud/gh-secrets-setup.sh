#!/bin/bash
set -e

# One-time, local-only setup for GitHub Actions -> Azure login (OIDC).
# Uses a user-assigned managed identity instead of an app registration,
# because student accounts in the UTS tenant cannot create app registrations.
# The identity lives in its own resource group so cleanup of the app
# resource group never deletes it.
# Re-run from main before the final deploy (trust is per-branch).

IDENTITY_RG="${IDENTITY_RG:-asd24-identity-rg}"
IDENTITY_NAME="asd24-github-oidc"
LOCATION="${LOCATION:-newzealandnorth}"

echo "=== ASD Group 24 GitHub Secrets Setup ==="

if ! az account show >/dev/null 2>&1; then
    az login
fi
echo "Logged in to Azure."

if ! gh auth status >/dev/null 2>&1; then
    gh auth login
fi
echo "Logged in to GitHub."

REPO_URL=$(git config --get remote.origin.url)
REPO_SLUG=$(echo "$REPO_URL" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')
BRANCH=$(git rev-parse --abbrev-ref HEAD)

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "Registering Microsoft.ManagedIdentity provider (skips if already registered)..."
az provider register --namespace Microsoft.ManagedIdentity --wait

if ! az group show --name "$IDENTITY_RG" >/dev/null 2>&1; then
    az group create --name "$IDENTITY_RG" --location "$LOCATION" >/dev/null
    echo "Created resource group $IDENTITY_RG."
fi

if ! az identity show --name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" >/dev/null 2>&1; then
    az identity create --name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" --location "$LOCATION" >/dev/null
    echo "Created managed identity $IDENTITY_NAME."
else
    echo "Found existing managed identity $IDENTITY_NAME."
fi

CLIENT_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" --query principalId -o tsv)

OWNER_NAME=$(echo "$REPO_SLUG" | cut -d/ -f1)
REPO_NAME=$(echo "$REPO_SLUG" | cut -d/ -f2)
OWNER_ID=$(gh api "repos/${REPO_SLUG}" --jq '.owner.id')
REPO_ID=$(gh api "repos/${REPO_SLUG}" --jq '.id')
SUBJECT="repo:${OWNER_NAME}@${OWNER_ID}/${REPO_NAME}@${REPO_ID}:ref:refs/heads/${BRANCH}"

# One federated credential per branch so main and your working branch can both deploy.
FED_CRED_NAME="gha-$(echo "$BRANCH" | tr '/' '-' | tr -cd '[:alnum:]-' | cut -c1-100)"

if az identity federated-credential show --name "$FED_CRED_NAME" --identity-name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" >/dev/null 2>&1; then
    az identity federated-credential update --name "$FED_CRED_NAME" --identity-name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" \
      --issuer "https://token.actions.githubusercontent.com" --subject "$SUBJECT" --audiences "api://AzureADTokenExchange" >/dev/null
    echo "Synced federated credential for branch '$BRANCH'."
else
    az identity federated-credential create --name "$FED_CRED_NAME" --identity-name "$IDENTITY_NAME" --resource-group "$IDENTITY_RG" \
      --issuer "https://token.actions.githubusercontent.com" --subject "$SUBJECT" --audiences "api://AzureADTokenExchange" >/dev/null
    echo "Created federated credential for branch '$BRANCH'."
fi
echo "Subject: $SUBJECT"

# Role assignments use object ID + principal type so no directory lookup is needed
# (the UTS tenant blocks directory reads/writes for students).
EXISTING_CONTRIBUTOR=$(az role assignment list --assignee "$PRINCIPAL_ID" --role "Contributor" --scope "/subscriptions/$SUBSCRIPTION_ID" --query "[0].id" -o tsv 2>/dev/null || true)
if [ -z "$EXISTING_CONTRIBUTOR" ]; then
    az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
      --role Contributor --scope "/subscriptions/$SUBSCRIPTION_ID" >/dev/null
    echo "Granted Contributor role."
else
    echo "Contributor role already assigned."
fi

# Needed so container apps can be auto-granted AcrPull on the registry.
EXISTING_UAA=$(az role assignment list --assignee "$PRINCIPAL_ID" --role "User Access Administrator" --scope "/subscriptions/$SUBSCRIPTION_ID" --query "[0].id" -o tsv 2>/dev/null || true)
if [ -z "$EXISTING_UAA" ]; then
    az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
      --role "User Access Administrator" --scope "/subscriptions/$SUBSCRIPTION_ID" >/dev/null
    echo "Granted User Access Administrator role."
else
    echo "User Access Administrator role already assigned."
fi

gh secret set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID"
gh secret set AZURE_CLIENT_ID --body "$CLIENT_ID"
echo "Pushed AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID to GitHub secrets."

echo "=== Setup Complete (branch: $BRANCH) ==="
