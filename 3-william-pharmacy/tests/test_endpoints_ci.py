"""Post-commit endpoint tests for Feature 3 (Pharmacy).

Tested end to end against real running services (pharmacy backend, pharmacy database,
shared login service):

  Endpoint 1: GET  /medications            (list medications)
  Endpoint 2: POST /admin/prescriptions    (create) + GET /prescriptions/<patient_id> (read back)
  Endpoint 3: POST /multi-agent/workflow   (admin-only guard)
"""
import os
import secrets
import uuid

import pytest
import requests

PHARMACY_URL = os.environ.get("PHARMACY_BACKEND_URL", "http://localhost:5003")
SHARED_URL = os.environ.get("SHARED_BACKEND_URL", "http://localhost:5000")
TIMEOUT = 10


def _reachable(url):
    try:
        requests.get(url, timeout=2)
        return True
    except requests.RequestException:
        return False


if os.environ.get("PHARMACY_ENDPOINT_TESTS_REQUIRED") != "true" and not _reachable(PHARMACY_URL):
    pytest.skip("Pharmacy services are not running; endpoint tests skipped", allow_module_level=True)


# ---------- fixtures ----------

@pytest.fixture
def medication():
    name = f"CI Test Drug {uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{PHARMACY_URL}/admin/medications",
        json={"name": name, "stock": 5, "unit_price": 1.5},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    med = r.json()
    yield med
    requests.delete(f"{PHARMACY_URL}/admin/medications/{med['id']}", timeout=TIMEOUT)


@pytest.fixture
def prescription(medication):
    patient_id = 900_000 + secrets.randbelow(100_000)  # unlikely to clash with real patients
    r = requests.post(
        f"{PHARMACY_URL}/admin/prescriptions",
        json={
            "patient_id": patient_id,
            "medication_id": medication["id"],
            "dosage": "500mg twice daily",
            "prescribing_doctor": "Dr CI",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    yield {"id": body["id"], "patient_id": patient_id, "medication_id": medication["id"]}
    requests.delete(f"{PHARMACY_URL}/admin/prescriptions/{body['id']}", timeout=TIMEOUT)


@pytest.fixture(scope="module")
def patient():
    """A real logged-in patient from the shared service (skipped if it is down)."""
    if not _reachable(SHARED_URL):
        pytest.skip("Shared login service is not running")
    email = f"ci-{uuid.uuid4().hex[:12]}@example.com"
    password = secrets.token_urlsafe(16)
    registered = requests.post(
        f"{SHARED_URL}/register",
        json={
            "first_name": "Ci", "last_name": "Tester", "address": "1 Test St",
            "email_address": email, "password": password,
            "phone_number": "0400000000", "emergency_contact_number": "0400000001",
        },
        timeout=TIMEOUT,
    )
    assert registered.status_code == 201, registered.text
    login = requests.post(
        f"{SHARED_URL}/login",
        json={"email_address": email, "password": password},
        timeout=TIMEOUT,
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["role"] == "patient"
    return {"token": body["token"]}


# ---------- Endpoint 1: GET /medications ----------

def test_get_medications_returns_the_medication_that_was_created(medication):
    r = requests.get(f"{PHARMACY_URL}/medications", timeout=TIMEOUT)
    assert r.status_code == 200
    match = [m for m in r.json() if m["id"] == medication["id"]]
    assert len(match) == 1
    assert match[0]["name"] == medication["name"]
    assert match[0]["stock"] == 5
    assert match[0]["unit_price"] == 1.5


# ---------- Endpoint 2: POST /admin/prescriptions + GET /prescriptions/<patient_id> ----------

def test_get_prescriptions_returns_the_prescription_that_was_created(prescription):
    r = requests.get(f"{PHARMACY_URL}/prescriptions/{prescription['patient_id']}", timeout=TIMEOUT)
    assert r.status_code == 200
    match = [p for p in r.json() if p["id"] == prescription["id"]]
    assert len(match) == 1
    assert int(match[0]["patient_id"]) == prescription["patient_id"]
    assert match[0]["medication_id"] == prescription["medication_id"]
    assert match[0]["dosage"] == "500mg twice daily"
    assert match[0]["prescribing_doctor"] == "Dr CI"
    assert match[0]["status"] == "active"  # default when not supplied


def test_get_prescriptions_unknown_patient_returns_empty_list():
    r = requests.get(f"{PHARMACY_URL}/prescriptions/{secrets.randbelow(10**9) + 10**9}", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json() == []


def test_post_prescription_missing_field_is_rejected(medication):
    r = requests.post(
        f"{PHARMACY_URL}/admin/prescriptions",
        json={"patient_id": 900_001, "medication_id": medication["id"]},
        timeout=TIMEOUT,
    )
    assert r.status_code == 400


def test_post_prescription_unknown_medication_is_rejected():
    r = requests.post(
        f"{PHARMACY_URL}/admin/prescriptions",
        json={
            "patient_id": 900_001, "medication_id": 999_999_999,
            "dosage": "1 tablet", "prescribing_doctor": "Dr CI",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 400


# ---------- Endpoint 3: POST /multi-agent/workflow (admin-only guard) ----------
# These never reach the multi-agent server, so they work whether the flag is on or off.

def _multi_agent_enabled():
    return requests.get(f"{PHARMACY_URL}/multi-agent/config", timeout=TIMEOUT).json()["enabled"]


def test_multi_agent_config_reports_a_boolean():
    r = requests.get(f"{PHARMACY_URL}/multi-agent/config", timeout=TIMEOUT)
    assert r.status_code == 200
    assert isinstance(r.json()["enabled"], bool)


def test_multi_agent_workflow_without_token_is_blocked():
    r = requests.post(f"{PHARMACY_URL}/multi-agent/workflow", json={"user_request": "x"}, timeout=TIMEOUT)
    if _multi_agent_enabled():
        assert r.status_code == 401
        assert r.json()["error"] == "token is required"
    else:
        assert r.status_code == 403  # disabled in this deployment


def test_multi_agent_workflow_is_forbidden_for_a_patient(patient):
    r = requests.post(
        f"{PHARMACY_URL}/multi-agent/workflow",
        headers={"X-Session-Token": patient["token"]},
        json={"user_request": "x"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 403  # "admin only" when enabled, "disabled" when not