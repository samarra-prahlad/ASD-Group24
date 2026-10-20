FROM nginx:alpine

COPY index.html /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Local defaults (rewrites are no-ops). deploy-azure.sh overrides these in the cloud.
ENV BACKEND_URL=http://ehr-backend:5002 \
    OWN_BACKEND_PORT=5002 \
    OWN_BACKEND_PUBLIC=http://localhost:5002 \
    SHARED_BACKEND_PUBLIC=http://localhost:5000 \
    SHARED_FRONTEND_PUBLIC=http://localhost:3000 \
    APPOINTMENTS_PUBLIC=http://localhost:3001 \
    EHR_PUBLIC=http://localhost:3002 \
    PHARMACY_PUBLIC=http://localhost:3003 \
    BILLING_PUBLIC=http://localhost:3004 \
    LABTESTS_PUBLIC=http://localhost:3005 \
    WARDBED_PUBLIC=http://localhost:3006

EXPOSE 80
