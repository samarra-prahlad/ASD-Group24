FROM nginx:alpine

COPY index.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Local defaults (rewrites are no-ops). deploy-azure.sh overrides these in the cloud.
# OWN_BACKEND_PORT=0 because the shared backend (5000) is already covered by
# SHARED_BACKEND_PUBLIC; port 0 never appears in the HTML, so that rule is inert.
ENV BACKEND_URL=http://shared-backend:5000 \
    OWN_BACKEND_PORT=0 \
    OWN_BACKEND_PUBLIC=http://localhost:0 \
    SHARED_BACKEND_PUBLIC=http://localhost:5000 \
    SHARED_FRONTEND_PUBLIC=http://localhost:3000 \
    APPOINTMENTS_PUBLIC=http://localhost:3001 \
    EHR_PUBLIC=http://localhost:3002 \
    PHARMACY_PUBLIC=http://localhost:3003 \
    BILLING_PUBLIC=http://localhost:3004 \
    LABTESTS_PUBLIC=http://localhost:3005 \
    WARDBED_PUBLIC=http://localhost:3006

EXPOSE 80
