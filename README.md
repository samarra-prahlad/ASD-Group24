# ASD Group 24 — Healthcare Microservices App

ASD T2 2026 · Release 0 — Agentic AI Foundation and DevOps (ASD 41026)

## Status

**Working right now:**
- `docker-compose.yml` — all 22 service containers wired and validated
- `shared/database` — built, tested, returns real patient data
- `shared/backend` — built, tested, confirmed calling `shared/database` over HTTP
- `shared/frontend` — Dockerfile ready; HTML/CSS content in progress
- `ai-services/ai-mode` — built and tested standalone (full Plan → Act → Observe → Adapt cycle runs and exits cleanly); full integration pending student backends
- `.github/workflows/4-samarra-billing-ci.yml` — correctly scoped with `paths:` filter, triggers on push, fails as expected (billing service code not yet written)

**Not started yet:**
- All six student feature folders — Dockerfiles exist, `app.py`/`requirements.txt` still empty/non-existent
- Other five `*-ci.yml` files need the `paths:` filter added (currently trigger on every push, not just their own folder)

## Team & feature allocation

| # | Name | Feature | Frontend | Backend/API | Database |
|---|------|---------|----------|--------------|----------|
| 1 | Kathrynna | Appointments | 3001 | 5001 | 6001 |
| 2 | Divyansh | EHR | 3002 | 5002 | 6002 |
| 3 | William | Pharmacy | 3003 | 5003 | 6003 |
| 4 | Samarra | Billing & Insurance | 3004 | 5004 | 6004 |
| 5 | Maximilian | Lab Tests | 3005 | 5005 | 6005 |
| 6 | Brian | Ward & Bed Management | 3006 | 5006 | 6006 |
| — | Shared (team-owned) | Access API & identity | 3000 | 5000 | 6000 |
| — | Shared (team-owned) | ai-mode | — | 5100 | — |

## Prerequisites

- Docker Desktop
- Python 3.x
- Ollama, with `qwen2.5:0.5b` and `llama3.1:8b` pulled
- Git

## Getting started

```bash
git clone <repo-url>
cd ASD-Group24
git checkout -b <yourname>/<feature>   # never work directly on main
```

Each feature folder follows this structure:
```
<n>-<name>-<feature>/
├── frontend/
│   └── Dockerfile
├── backend/
│   └── Dockerfile
├── database/
│   └── Dockerfile
├── tests/
└── README.md
```

## The pattern to follow

`shared/database` and `shared/backend` are fully built, tested, and working — use them as your copy-paste reference. Each of your three services needs exactly these files:

**`database/`**: `requirements.txt`, `init_db.py`, `app.py`, `Dockerfile`
**`backend/`**: `requirements.txt`, `app.py`, `Dockerfile`
**`frontend/`**: `index.html`, `css/`, `Dockerfile`

Your `backend/app.py` should:
1. Read `DATABASE_SERVICE_URL` and `SHARED_ACCESS_API_URL` from environment variables (already set in `docker-compose.yml` for your service)
2. Call `GET {SHARED_ACCESS_API_URL}/validate?patient_id=X` before creating/returning patient-tied data
3. Talk to your own database only through its exposed API — never touch another service's SQLite file directly

## Confirmed cross-service dependencies

| Calling service | Calls | Purpose |
|---|---|---|
| Pharmacy backend | EHR database API | Pull diagnosis context when issuing a prescription |
| Billing backend | Appointments database API | Pull appointment cost/duration |
| Billing backend | Pharmacy database API | Pull medication costs |
| Billing backend | Ward & Bed database API | Pull room/bed charges |

If your service needs one of these, the URL is already wired into your `docker-compose.yml` environment block (e.g. `APPOINTMENTS_DATABASE_API_URL`).

## Running your own service in isolation

You don't need the whole stack running to develop. Example for Appointments:

```bash
docker-compose up appointments-frontend appointments-backend appointments-database shared-backend shared-database --build
```

## Running everything

```bash
docker-compose up --build
```

Note: this will only fully succeed once all six feature folders have their files filled in. Until then, build errors on folders you haven't touched are expected, build and test your own service in isolation instead (see above).

## Branching & PRs

- Never commit directly to `main`
- One branch per feature/task: `<yourname>/<short-description>`
- Open a PR into `main` when your service builds and its endpoints return real data via `curl`. This means that main will consistently be updated as features are built and working
- Resolve conflicts before merging

## CI workflows (GitHub Actions)

Each feature has its own workflow in `.github/workflows/`, named `<n>-<name>-<feature>-ci.yml`. Every workflow must scope itself to its own folder using a `paths:` filter — otherwise a push to any file in the repo triggers every workflow, wasting CI minutes.

Reference pattern (from `4-samarra-billing-ci.yml`, already working correctly):

```yaml
on:
  push:
    branches: [main]
    paths:
      - '<your-folder>/**'
  pull_request:
    branches: [main]
    paths:
      - '<your-folder>/**'
```

Each workflow runs two jobs:
1. **Pre-commit pytest validation** — installs your backend/database `requirements.txt`, runs `pytest <your-folder>/tests/`
2. **Post-commit AI-assisted unit testing** — currently a placeholder step; team to confirm what "AI-assisted" testing means for our services before filling in

**Action needed from everyone**: add the `paths:` filter above to your own `*-ci.yml` if it's missing — check by pushing a small change and confirming only your workflow triggers, not all six.

`cloud-deployment.yml` is a Release 2 requirement (not needed yet) and `integration-ci.yml` is currently unscoped — confirm with the team whether it's intentional before Release 0 submission.

## Questions / blockers

- Make sure to write comprehensive test cases (using pytest) before implementing
- Run the verification script before pushing: `bash scripts/test/verify-setup.sh`

Ping Samarra (team lead) or raise it in the group chat, please don't sit on a blocker!