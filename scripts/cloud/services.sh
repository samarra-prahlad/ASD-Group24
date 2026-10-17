#!/bin/bash
# Shared config for all cloud scripts. Source this file; do not run it directly.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd24-rg}"
LOCATION="${LOCATION:-newzealandnorth}"
ENV_NAME="${ENV_NAME:-asd24-env}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

# name|build context|container port|tier
# Order matters: deploy-azure.sh deploys top to bottom, so every service
# is listed after the services it depends on (billing-backend needs
# appointments-backend and pharmacy-backend; shared-frontend needs every
# feature frontend's URL).
SERVICES=(
  "shared-database|shared/database|6000|database"
  "appointments-database|1-kathrynna-appointments/database|6001|database"
  "ehr-database|2-div-ehr/database|6002|database"
  "pharmacy-database|3-william-pharmacy/database|6003|database"
  "billing-database|4-samarra-billing/database|6004|database"
  "labtests-database|5-max-labtests/database|6005|database"
  "wardbed-database|6-brian-wardbed/database|6006|database"
  "shared-backend|shared/backend|5000|backend"
  "appointments-backend|1-kathrynna-appointments/backend|5001|backend"
  "ehr-backend|2-div-ehr/backend|5002|backend"
  "pharmacy-backend|3-william-pharmacy/backend|5003|backend"
  "labtests-backend|5-max-labtests/backend|5005|backend"
  "wardbed-backend|6-brian-wardbed/backend|5006|backend"
  "billing-backend|4-samarra-billing/backend|5004|backend"
  "appointments-frontend|1-kathrynna-appointments/frontend|80|frontend"
  "ehr-frontend|2-div-ehr/frontend|80|frontend"
  "pharmacy-frontend|3-william-pharmacy/frontend|80|frontend"
  "billing-frontend|4-samarra-billing/frontend|80|frontend"
  "labtests-frontend|5-max-labtests/frontend|80|frontend"
  "wardbed-frontend|6-brian-wardbed/frontend|80|frontend"
  "shared-frontend|shared/frontend|80|frontend"
)

service_field() { echo "$1" | cut -d'|' -f"$2"; }

# True if ONLY is empty, or if the given service name is listed in ONLY.
service_selected() {
  [ -z "${ONLY:-}" ] && return 0
  echo " $ONLY " | grep -q " $1 "
}
