# EHR System

Student 2 (Divyansh) module of the ASD-Group24 healthcare platform. Provides
electronic health record data with a patient view, a staff (admin) view, and
an AI-assisted patient history summary backed by a local Ollama model.

This module is one service group inside the wider `docker-compose.yml`,
alongside the shared services and other students' modules. It is made up of
three containers:

```
ehr-frontend   →  ehr-backend  →  ehr-database
  (nginx, :3002)   (Flask, :5002)   (Flask + SQLite, :6002)
```

- **ehr-frontend** — static HTML/JS. `index.html` shows the patient view
  (view own records, submit a change request, get an AI summary of their
  own history) or the staff view (search patients, view/add/edit/delete
  records, approve change requests, get an AI summary for any patient),
  depending on the logged-in user's role. Includes a nav bar linking to
  every other team member's feature.
- **ehr-backend** — validates every request against the shared session
  system before doing anything, then talks to `ehr-database` over HTTP.
  Also exposes `/diagnosis/<patient_id>` for Pharmacy's cross-service call,
  and `/summarize`, which pulls a patient's real record history from the
  database and grounds an Ollama-generated summary in it.
- **ehr-database** — a Flask + SQLite service owning the `medical_records`
  and `change_requests` tables. Nothing else in the system talks to the
  SQLite file directly.

## Folder structure

```
2-div-ehr/
├── frontend/
│   ├── index.html          # patient view + staff view + AI summary
│   ├── app.js               # all API calls, view logic, nav bar
│   └── Dockerfile
├── backend/
│   ├── app.py                # session checks, record/request CRUD, /diagnosis, /summarize
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   ├── app.py                 # CRUD endpoints, owns the SQLite file
│   ├── init_db.py             # creates tables + seeds sample data
│   ├── requirements.txt
│   └── Dockerfile
└── tests/
    ├── test_backend_app.py     # Route behaviour on the Flask API
    ├── test_database_app.py    # CRUD behaviour on the database service
    └── test_init_db.py         # schema, seed data, idempotency
```

CI runs against this feature via `.github/workflows/2-div-ehr-ci.yml`.

## Running it

```bash
docker compose up --build
```

Once running, log in at `http://localhost:5000/login` — the shared portal
issues a session token and links out to EHR (and every other feature) with
that token attached (`http://localhost:3002?token=...`). 

Sample accounts:
- Patient: `john.smith@example.com` / `PatientPass1!`
- Admin (staff): `grace.hopper@admin.com` / `AdminPass123!`

## Features

- **Database** — `medical_records` (visit date, diagnosis, doctor, treatment,
  notes, allergies) and `change_requests` (patient-submitted, staff-reviewed)
  tables. Full CRUD on both.
- **Backend** — every route checks the caller's session token against the
  shared backend (`/session/verify`) before doing anything. Patients can only
  see/request changes to their own records; only `admin`-role users can
  add, edit, or delete records, or approve change requests.
- **Cross-service endpoint** — `/diagnosis/<patient_id>` returns the most
  recent diagnosis + allergies for a patient, for Pharmacy to pull when
  issuing a prescription. This route intentionally has no session check,
  since it's meant for direct service-to-service calls.
- **AI-assisted summary** — `/summarize` pulls a patient's actual record
  history from the database and asks a local Ollama model
  (`qwen2.5:0.5b`, via the OpenAI-compatible client) to summarise it in
  plain language, grounded in the real data rather than invented.
  Available to patients for their own history and to staff for any
  patient they're viewing.
- **Frontend** — patient view (own records, submit change request, view own
  requests, AI summary of own history), staff view (searchable patient
  table, click through to a detail panel showing that patient's records +
  change requests together, add/edit/delete records, approve pending
  requests, AI summary for the selected patient), dates shown as
  dd/mm/yyyy, Enter-key submission on the main inputs, and a nav bar
  linking to every other feature with the session token carried over.

## Testing

```bash
pip install -r backend/requirements.txt -r database/requirements.txt pytest
pytest tests/ -v
```