# Cloud Deployment Results

- **Platform:** Azure Container Apps (standard environment, newzealandnorth)
- **Entry point:** https://shared-frontend.lemonbay-2af38055.newzealandnorth.azurecontainerapps.io
- **Commit / image tag:** 0ee6c4a
- **Tested at (UTC):** 2026-10-19T03:47:23Z
- **Result:** 22/22 checks passed

| Check | Method | Path | Expected | Actual | Result |
|---|---|---|---|---|---|
| appointments-frontend reachable | GET | `/` | 200 | 200 | PASS |
| ehr-frontend reachable | GET | `/` | 200 | 200 | PASS |
| pharmacy-frontend reachable | GET | `/` | 200 | 200 | PASS |
| billing-frontend reachable | GET | `/` | 200 | 200 | PASS |
| labtests-frontend reachable | GET | `/` | 200 | 200 | PASS |
| wardbed-frontend reachable | GET | `/` | 200 | 200 | PASS |
| shared-frontend reachable | GET | `/` | 200 | 200 | PASS |
| Admin login | POST | `/login` | 200 | 200 | PASS |
| Billing: read invoices | GET | `/invoices` | 200 | 200 | PASS |
| Billing: create invoice | POST | `/invoices/generate` | 201 | 201 | PASS |
| Appointments: read | GET | `/appointments` | 200 | 200 | PASS |
| EHR: read patients | GET | `/patients` | 200 | 200 | PASS |
| Pharmacy: read medications | GET | `/medications` | 200 | 200 | PASS |
| Lab Tests: read orders | GET | `/orders` | 200 | 200 | PASS |
| Ward & Bed: read ward | GET | `/wards/1` | 200 | 200 | PASS |
| shared-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| appointments-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| ehr-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| pharmacy-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| labtests-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| wardbed-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |
| billing-backend AI services | ENV | `*_ENABLED` | disabled | disabled | PASS |

## Human release decision

Status: (READY / NOT READY)  
Approved by:  
Date:  
