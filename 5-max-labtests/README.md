# Lab Tests & Diagnostics — Maximilian

## Overview
Staff can create, view, update, and delete lab orders, and record results.
Results are automatically checked for abnormalities by a local LLM (Ollama, qwen2.5:0.5b).
Patients get a separate read-only view of their own results, plus a chatbot for lab-related questions.

## Ports
- Frontend: 3005
- Backend/API: 5005
- Database: 6005

## Structure
- `database/` — SQLite (lab_orders, lab_results), seeded with 10 sample orders and 10 results
- `backend/` — Flask API: full CRUD on orders and results, patient validation (via shared-database), AI-assisted flagging, chatbot, patient-filtered results
- `frontend/` — index.html (admin/staff view), customer.html (patient view)
- `tests/` — pytest suite (20 tests) covering CRUD, validation, AI flagging, and edge cases

## Known limitations
- No API-level role enforcement (staff/patient split is UI-navigation only)