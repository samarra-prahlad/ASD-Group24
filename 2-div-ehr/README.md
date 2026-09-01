# EHR System

Student 2 (Divyansh) module of the ASD-Group24 healthcare platform. Provides
electronic health record data with a patient view, a staff (admin) view, and
an AI assistant backed by a local Ollama model.

This module is one service group inside the wider `docker-compose.yml`,
alongside the shared services and other students' modules. It is made up of
three containers:

```
ehr-frontend   →  ehr-backend  →  ehr-database
  (nginx, :3002)   (Flask, :5002)   (Flask + SQLite, :6002)
```

- **ehr-frontend** — static HTML/JS. `index.html` shows the patient view
  (view own records, submit a change request) or the staff view (search
  patients, view/add records, approve change requests), depending on the
  logged-in user's role. Includes a chatbot widget and a nav bar linking to
  every other team member's feature.
- **ehr-backend** — validates every request against the shared session
  system before doing anything, then talks to `ehr-database` over HTTP.
  Also exposes `/diagnosis/<patient_id>` for Pharmacy's cross-service call,
  and `/ask` / `/ask-with-context`, which call a local Ollama model.
- **ehr-database** — a Flask + SQLite service owning the `medical_records`
  and `change_requests` tables. Nothing else in the system talks to the
  SQLite file directly.

## Folder structure

```
2-div-ehr/
├── frontend/
│   ├── index.html         # patient view + staff view + chatbot
│   ├── app.js              # all API calls, view logic, nav bar
│   └── Dockerfile
├── backend/
│   ├── app.py               # session checks, record/request CRUD, AI routes
│   ├── requirements.txt
│   ├── Dockerfile
│   └── prompts/
│       ├── implementation_system_prompt.txt
│       └── context_qa_task_prompt.txt
├── database/
│   ├── app.py                # CRUD endpoints, owns the SQLite file
│   ├── init_db.py            # creates tables + seeds sample data
│   ├── requirements.txt
│   └── Dockerfile
└── tests/                     # not yet written
```

## Running it

```bash
docker compose up --build
```

Once running, log in at `http://localhost:5000/login` — the shared portal
issues a session token and links out to EHR (and every other feature) with
that token attached (`http://localhost:3002?token=...`). EHR does not have
its own login screen; identity always comes from the shared session.

Sample accounts (seeded by `shared/database`):
- Patient: `john.smith@example.com` / `PatientPass1!`
- Admin (staff): `grace.hopper@admin.com` / `AdminPass123!`

## What's done

- **Database** — `medical_records` (visit date, diagnosis, doctor, treatment,
  notes, allergies) and `change_requests` (patient-submitted, staff-reviewed)
  tables. Full CRUD on both.
- **Backend** — every route checks the caller's session token against the
  shared backend (`/session/verify`) before doing anything. Patients can only
  see/request changes to their own records; only `admin`-role users can
  add, edit, or delete records, or approve change requests.
- **Cross-service endpoint** — `/diagnosis/<patient_id>` returns the most
  recent diagnosis + allergies for a patient, for Pharmacy to pull when
  issuing a prescription.
- **AI chatbot** — `/ask` (general questions) and `/ask-with-context`
  (grounded in `prompts/context_qa_task_prompt.txt`, which lists this
  feature's real fields and endpoints so the model can't invent
  functionality that doesn't exist). Both use a local Ollama model
  (`qwen2.5:0.5b`) via the OpenAI-compatible client.
- **Frontend** — patient view (own records, submit change request, view own
  requests), staff view (searchable patient table, click through to a
  detail panel showing that patient's records + change requests together,
  add-record form, approve pending requests), chatbot widget, dates shown
  as dd/mm/yyyy, Enter-key submission on the main inputs, and a nav bar
  linking to every other feature with the session token carried over.

## What's left

- Automated tests (`tests/`)
- CI workflow (`.github/workflows/2-div-ehr-ci.yml`)
- Final full-stack verification once every team member's services are
  buildable together
