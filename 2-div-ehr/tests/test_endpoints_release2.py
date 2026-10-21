"""Release 2 post-commit CI/CD endpoint tests for Feature 2 (EHR).

Two endpoint functions of the EHR backend/API (port 5002) are tested end to end
against real running services (shared login service, EHR backend, EHR database):

  Endpoint 1: POST /records            (create_record, staff only)
  Endpoint 2: GET  /records/<patient>  (get_records, staff or the patient themself)
"""
import os
import secrets
import uuid

import pytest
import requests

EHR_URL = os.environ.get("EHR_BACKEND_URL", "http://localhost:5002")
SHARED_URL = os.environ.get("SHARED_BACKEND_URL", "http://localhost:5000")
TIMEOUT = 10


def _services_up():
    try:
        requests.get(f"{EHR_URL}/", timeout=2)
        requests.get(f"{SHARED_URL}/validate", timeout=2)
        return True
    except requests.RequestException:
        return False


if os.environ.get("EHR_ENDPOINT_TESTS_REQUIRED") != "true" and not _services_up():
    pytest.skip("EHR services are not running; endpoint tests skipped", allow_module_level=True)


def _register_and_login(staff):
    suffix = "admin.com" if staff else "example.com"
    email = f"ci-{uuid.uuid4().hex[:12]}@{suffix}"
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
    return {"patient_id": body["patient_id"], "token": body["token"], "role": body["role"]}


@pytest.fixture(scope="module")
def staff():
    user = _register_and_login(staff=True)
    assert user["role"] == "admin"
    return user


@pytest.fixture(scope="module")
def patient():
    user = _register_and_login(staff=False)
    assert user["role"] == "patient"
    return user


@pytest.fixture(scope="module")
def other_patient():
    return _register_and_login(staff=False)


def _create_record(token, patient_id, **overrides):
    payload = {
        "token": token, "patient_id": patient_id, "visit_date": "2026-10-21",
        "diagnosis": "Release 2 CI diagnosis", "doctor_name": "Dr CI",
        "treatment": "CI treatment", "notes": "created by the CI endpoint tests",
        "allergies": "None",
    }
    payload.update(overrides)
    return requests.post(f"{EHR_URL}/records", json=payload, timeout=TIMEOUT)


# ---------- Endpoint 1: POST /records ----------

def test_post_records_staff_creates_record(staff, patient):
    r = _create_record(staff["token"], patient["patient_id"])
    assert r.status_code == 201
    assert isinstance(r.json()["id"], int)


def test_post_records_patient_is_forbidden(patient):
    r = _create_record(patient["token"], patient["patient_id"])
    assert r.status_code == 403
    assert r.json()["error"] == "Only staff can add medical records"


def test_post_records_requires_token(patient):
    r = requests.post(
        f"{EHR_URL}/records",
        json={"patient_id": patient["patient_id"], "diagnosis": "No token"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 400
    assert r.json()["error"] == "token is required"


# ---------- Endpoint 2: GET /records/<patient_id> ----------

def test_get_records_returns_the_record_that_was_created(staff, patient):
    created = _create_record(staff["token"], patient["patient_id"], diagnosis="Round Trip Diagnosis")
    record_id = created.json()["id"]

    r = requests.get(
        f"{EHR_URL}/records/{patient['patient_id']}",
        params={"token": staff["token"]},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    match = [rec for rec in r.json() if rec["id"] == record_id]
    assert len(match) == 1
    assert match[0]["patient_id"] == patient["patient_id"]
    assert match[0]["diagnosis"] == "Round Trip Diagnosis"
    assert match[0]["doctor_name"] == "Dr CI"
    assert match[0]["allergies"] == "None"


def test_get_records_patient_can_read_own_records(staff, patient):
    record_id = _create_record(staff["token"], patient["patient_id"]).json()["id"]
    r = requests.get(
        f"{EHR_URL}/records/{patient['patient_id']}",
        params={"token": patient["token"]},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    assert record_id in [rec["id"] for rec in r.json()]


def test_get_records_patient_cannot_read_another_patients_records(patient, other_patient):
    r = requests.get(
        f"{EHR_URL}/records/{other_patient['patient_id']}",
        params={"token": patient["token"]},
        timeout=TIMEOUT,
    )
    assert r.status_code == 403
    assert r.json()["error"] == "Patients can only access their own records"


def test_get_records_requires_token(patient):
    r = requests.get(f"{EHR_URL}/records/{patient['patient_id']}", timeout=TIMEOUT)
    assert r.status_code == 400
    assert r.json()["error"] == "token is required"