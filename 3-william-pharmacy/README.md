# Pharmacy System

Student 3 (William) module of the ASD-Group24 healthcare platform. Provides
medication and prescription data with an admin interface for managing stock,
and an AI assistant backed by a local Ollama model.

This module is one service group inside the wider `docker-compose.yml`,
alongside the shared services and other students' modules. It is made up of
three containers:

```
pharmacy-frontend   →  pharmacy-backend  →  pharmacy-database
   (nginx, :3003)        (Flask, :5003)      (Flask + SQLite, :6003)
```

- **pharmacy-frontend** — static HTML/JS. `index.html` is the patient view
  (browse medications, look up prescriptions by patient ID, ask the AI
  assistant). `admin.html` is the admin view (create/edit/delete medications
  and prescriptions).
- **pharmacy-backend** — a thin Flask proxy in front of the database
  service. Forwards every request as-is (same method, body, and status
  code) and additionally exposes `/ask` and `/ask-with-context`, which call
  a local Ollama model.
- **pharmacy-database** — a Flask + SQLite service owning the
  `medications` and `prescriptions` tables. Nothing else in the system
  talks to the SQLite file directly.

## Folder structure

```
3-william-pharmacy/
├── frontend/
│   ├── index.html        # patient view
│   ├── admin.html         # admin view (CRUD)
│   └── Dockerfile
├── backend/
│   ├── app.py              # proxy + AI assistant endpoints
│   ├── requirements.txt
│   ├── Dockerfile
│   └── prompts/
│       ├── implementation_system_prompt.txt
│       └── context_qa_task_prompt.txt
├── database/
│   ├── app.py               # CRUD endpoints, owns the SQLite file
│   ├── init_db.py           # creates tables + seeds sample data
│   ├── requirements.txt
│   └── Dockerfile
└── tests/
    ├── requirements.txt
    ├── test_backend_service.py
    └── test_database_service.py
```

## Running it

```bash
docker compose up --build
```

Once running:

| Service | URL |
|---|---|
| Patient view | http://localhost:3003 |
| Admin view | http://localhost:3003/admin.html |
| Backend API | http://localhost:5003 |
| Database API (internal — not usually called directly) | http://localhost:6003 |

To reset all pharmacy data back to the seeded sample set:

```bash
docker compose down --volumes
docker compose up --build
```

(`--volumes` removes the `pharmacy_data` named volume, so `init_db.py` reseeds
from scratch on next start-up.)

### Running services outside Docker (local dev)

Each service can also run directly with Python, useful for faster iteration:

```bash
# database service
cd 3-william-pharmacy/database
pip install -r requirements.txt
python init_db.py     # creates tables + sample data
python app.py          # listens on :6003

# backend service (separate terminal)
cd 3-william-pharmacy/backend
pip install -r requirements.txt
set DATABASE_SERVICE_URL=http://localhost:6003
python app.py          # listens on :5003

# frontend — just open frontend/index.html and frontend/admin.html
# directly in a browser, or serve the folder with any static file server
```

Ollama must be running locally (`ollama serve`) with the `qwen2.5:0.5b`
model pulled for `/ask` and `/ask-with-context` to work:

```bash
ollama pull qwen2.5:0.5b
```

## Environment variables

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `DATABASE_PATH` | database | `/app/data/pharmacy.db` | Path to the SQLite file |
| `DATABASE_SERVICE_URL` | backend | `http://localhost:6003` | Where the backend forwards requests |
| `SHARED_ACCESS_API_URL` | backend | — | URL of the shared team backend |
| `OLLAMA_BASE_URL` | backend | `http://localhost:11434/v1` | Ollama's OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | backend | `qwen2.5:0.5b` | Model used for the AI assistant endpoints |

In Docker Compose, `OLLAMA_BASE_URL` is set to
`http://host.docker.internal:11434/v1` so the container can reach Ollama
running on the host machine.

## API reference

All endpoints below are exposed by **pharmacy-backend** (`:5003`), which
proxies straight through to **pharmacy-database** (`:6003`) with the same
method, body, and status code — so the shapes match on both services.

### Read

| Method | Path | Description |
|---|---|---|
| `GET` | `/medications` | List all medications |
| `GET` | `/prescriptions/<patient_id>` | List prescriptions for a patient |

### Admin — medications

| Method | Path | Body | Notes |
|---|---|---|---|
| `POST` | `/admin/medications` | `{name, stock, unit_price}` | `stock` defaults to `0` if omitted. Returns `201` |
| `PUT` | `/admin/medications/<id>` | any subset of `{name, stock, unit_price}` | Returns `404` if `id` doesn't exist |
| `DELETE` | `/admin/medications/<id>` | — | Returns `404` if `id` doesn't exist |

Validation: `name` and `unit_price` are required on create; `stock` must be
a non-negative integer; `unit_price` must be non-negative.

### Admin — prescriptions

| Method | Path | Body | Notes |
|---|---|---|---|
| `POST` | `/admin/prescriptions` | `{patient_id, medication_id, dosage, prescribing_doctor, status?}` | `status` defaults to `"active"` in the database. Returns `201`. `medication_id` must reference an existing medication (`400` otherwise) |
| `PUT` | `/admin/prescriptions/<id>` | any subset of `{dosage, prescribing_doctor, status, medication_id, patient_id}` | Returns `404` if `id` doesn't exist |
| `DELETE` | `/admin/prescriptions/<id>` | — | Returns `404` if `id` doesn't exist |


### AI assistant

| Method | Path | Body (form) | Description |
|---|---|---|---|
| `POST` | `/ask` | `question` | General-purpose question to the local model |
| `POST` | `/ask-with-context` | `question` | Same, using the system/task prompts in `backend/prompts/` |

Both return `503` with an error message if Ollama isn't reachable or the
model isn't installed.

## Running the tests

```bash
cd 3-william-pharmacy
pip install -r tests/requirements.txt
python -m pytest -v
```

Tests are fully isolated — they don't require Docker, a running database
file, or Ollama:

- `test_database_service.py` points the app at a fresh temp SQLite file
  per test.
- `test_backend_service.py` monkeypatches `requests.request` (no network
  call reaches the database service) and the OpenAI client (no call
  reaches Ollama).

Run from the `3-william-pharmacy` directory so the tests can locate each
service's `app.py` via relative path.