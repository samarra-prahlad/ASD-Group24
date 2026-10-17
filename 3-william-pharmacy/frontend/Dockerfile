FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY admin.html /usr/share/nginx/html/admin.html
COPY styles.css /usr/share/nginx/html/styles.css
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Local defaults (rewrites are no-ops). deploy-azure.sh overrides these in the cloud.
ENV BACKEND_URL=http://pharmacy-backend:5003 \
    OWN_BACKEND_PORT=5003 \
    OWN_BACKEND_PUBLIC=http://localhost:5003 \
    SHARED_BACKEND_PUBLIC=http://localhost:5000 \
    SHARED_FRONTEND_PUBLIC=http://localhost:3000 \
    APPOINTMENTS_PUBLIC=http://localhost:3001 \
    EHR_PUBLIC=http://localhost:3002 \
    PHARMACY_PUBLIC=http://localhost:3003 \
    BILLING_PUBLIC=http://localhost:3004 \
    LABTESTS_PUBLIC=http://localhost:3005 \
    WARDBED_PUBLIC=http://localhost:3006

EXPOSE 80
