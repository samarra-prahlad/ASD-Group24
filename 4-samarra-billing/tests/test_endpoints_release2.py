"""Release 2 post-commit CI/CD endpoint tests for Feature 4 (Billing & Insurance).

Two endpoint functions of the billing backend/API (port 5004) are tested
against the real running services (shared-database, shared-backend,
billing-database, billing-backend) started by 4-samarra-billing-ci.yml:

  Endpoint 1: GET  /invoices           (get_invoices)     - admin-only invoice list
  Endpoint 2: POST /invoices/generate  (generate_invoice) - admin-only invoice creation

Neither endpoint needs Ollama, MCP, RAG or the Multi-Agent Server.
These tests only run when BILLING_ENDPOINT_TESTS=1 (set by the CI job),
so the normal unit-test run skips them.
"""
import os

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("BILLING_ENDPOINT_TESTS") != "1",
    reason="live endpoint tests run only in the post-commit CI job",
)

BILLING_URL = os.environ.get("BILLING_URL", "http://localhost:5004")
SHARED_URL = os.environ.get("SHARED_URL", "http://localhost:5000")
TIMEOUT = 10

# Seeded accounts from shared/database/init_db.py (test data, not real credentials)
ADMIN = {"email_address": "grace.hopper@admin.com", "password": "AdminPass123!"}  # pragma: allowlist secret
PATIENT = {"email_address": "john.smith@example.com", "password": "PatientPass1!"}  # pragma: allowlist secret


def login(account):
    r = requests.post(f"{SHARED_URL}/login", json=account, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return login(ADMIN)


@pytest.fixture(scope="module")
def patient_token():
    return login(PATIENT)


# ---------- Endpoint 1: GET /invoices ----------

def test_get_invoices_returns_seeded_invoices_for_admin(admin_token):
    r = requests.get(f"{BILLING_URL}/invoices", params={"token": admin_token}, timeout=TIMEOUT)
    assert r.status_code == 200
    invoices = r.json()
    assert isinstance(invoices, list) and len(invoices) >= 1
    first = invoices[0]
    for field in ("id", "patient_id", "total_amount", "insurance_covered_amount",
                  "patient_owed_amount", "status"):
        assert field in first


def test_get_invoices_rejects_missing_token():
    r = requests.get(f"{BILLING_URL}/invoices", timeout=TIMEOUT)
    assert r.status_code == 401


def test_get_invoices_forbidden_for_patient(patient_token):
    r = requests.get(f"{BILLING_URL}/invoices", params={"token": patient_token}, timeout=TIMEOUT)
    assert r.status_code == 403


# ---------- Endpoint 2: POST /invoices/generate ----------

def test_generate_invoice_creates_invoice_with_insurance_split(admin_token):
    r = requests.post(
        f"{BILLING_URL}/invoices/generate",
        params={"token": admin_token},
        json={"patient_id": 1, "appointment_id": 999, "insurance_provider_id": 302},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert isinstance(body["invoice_id"], int)
    # Appointments is not running in this job, so Billing falls back to the
    # flat $150 mock cost; Medibank Premium (302) covers 85%.
    assert body["cost_sources"]["appointment_cost"] == "mock"
    assert body["total_amount"] == pytest.approx(150.0)
    assert body["insurance_covered_amount"] == pytest.approx(127.5)
    assert body["patient_owed_amount"] == pytest.approx(22.5)

    created = requests.get(
        f"{BILLING_URL}/invoices/{body['invoice_id']}", params={"token": admin_token}, timeout=TIMEOUT
    )
    assert created.status_code == 200
    assert created.json()["patient_id"] == 1


def test_generate_invoice_requires_patient_id(admin_token):
    r = requests.post(
        f"{BILLING_URL}/invoices/generate", params={"token": admin_token}, json={"appointment_id": 1},
        timeout=TIMEOUT,
    )
    assert r.status_code == 400
    assert r.json()["error"] == "patient_id is required"


def test_generate_invoice_forbidden_for_patient(patient_token):
    r = requests.post(
        f"{BILLING_URL}/invoices/generate", params={"token": patient_token}, json={"patient_id": 1},
        timeout=TIMEOUT,
    )
    assert r.status_code == 403
