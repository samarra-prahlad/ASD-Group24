"""
Pytest suite for the Billing & Insurance Flask database-tier service (app.py).

Run with:
    pytest tests/test_app.py -v
"""

import os
import sys
import sqlite3
import subprocess

import pytest

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(FEATURE_ROOT, "database")
INIT_SCRIPT = os.path.join(DATABASE_DIR, "init_db.py")

# Local test runs write here instead of the container path (/app/data).
# Must be set BEFORE app.py is imported, since app.py reads DB_DATA_DIR
# at import time to build DATABASE_NAME.
TEST_DATA_DIR = os.path.join(FEATURE_ROOT, "tests", ".test_data")
DATABASE_NAME = os.path.join(TEST_DATA_DIR, "billing.db")
os.environ["DB_DATA_DIR"] = TEST_DATA_DIR

sys.path.insert(0, DATABASE_DIR)
import app as billing_app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def fresh_database():
    """
    Wipe and rebuild billing.db by running init_db.py, once for this test module,
    so every test in this file starts from the same known seed data.
    """
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)

    env = os.environ.copy()
    env["DB_DATA_DIR"] = TEST_DATA_DIR

    result = subprocess.run(
        [sys.executable, INIT_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"init_db.py failed: {result.stderr}"

    yield


@pytest.fixture
def client():
    billing_app.app.config["TESTING"] = True
    with billing_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def db_conn():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_check_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_reports_service_name(self, client):
        response = client.get("/")
        data = response.get_json()
        assert data["service"] == "billing-database"
        assert data["status"] == "running"


# ---------------------------------------------------------------------------
# GET /invoices
# ---------------------------------------------------------------------------

class TestGetInvoices:

    def test_get_all_invoices_returns_200(self, client):
        response = client.get("/invoices")
        assert response.status_code == 200

    def test_get_all_invoices_returns_seeded_count(self, client):
        response = client.get("/invoices")
        data = response.get_json()
        assert len(data) >= 10

    def test_get_all_invoices_includes_provider_name(self, client):
        response = client.get("/invoices")
        data = response.get_json()
        insured = [inv for inv in data if inv["insurance_provider_id"] is not None]
        assert all("insurance_provider_name" in inv for inv in insured)

    def test_get_single_invoice_returns_200(self, client):
        response = client.get("/invoices/3")
        assert response.status_code == 200

    def test_get_single_invoice_returns_correct_data(self, client):
        response = client.get("/invoices/3")
        data = response.get_json()
        assert data["id"] == 3
        assert data["patient_id"] == 101
        assert data["insurance_provider_id"] == 302

    def test_get_nonexistent_invoice_returns_404(self, client):
        response = client.get("/invoices/999999")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_get_invoices_by_patient(self, client):
        response = client.get("/invoices/patient/101")
        data = response.get_json()
        assert response.status_code == 200
        assert len(data) >= 1
        assert all(inv["patient_id"] == 101 for inv in data)

    def test_get_invoices_by_patient_with_no_invoices_returns_empty_list(self, client):
        response = client.get("/invoices/patient/999999")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_get_invoices_by_provider(self, client):
        response = client.get("/invoices/provider/302")
        data = response.get_json()
        assert response.status_code == 200
        assert all(inv["insurance_provider_id"] == 302 for inv in data)


# ---------------------------------------------------------------------------
# GET /insurance-providers
# ---------------------------------------------------------------------------

class TestGetInsuranceProviders:

    def test_get_all_providers_returns_200(self, client):
        response = client.get("/insurance-providers")
        assert response.status_code == 200

    def test_get_all_providers_returns_seeded_count(self, client):
        response = client.get("/insurance-providers")
        data = response.get_json()
        assert len(data) >= 10

    def test_get_single_provider_returns_200(self, client):
        response = client.get("/insurance-providers/305")
        assert response.status_code == 200

    def test_get_single_provider_returns_correct_data(self, client):
        response = client.get("/insurance-providers/305")
        data = response.get_json()
        assert data["id"] == 305
        assert data["name"] == "HCF"

    def test_get_nonexistent_provider_returns_404(self, client):
        response = client.get("/insurance-providers/999999")
        assert response.status_code == 404
        assert "error" in response.get_json()


# ---------------------------------------------------------------------------
# POST /invoices
# ---------------------------------------------------------------------------

class TestCreateInvoice:

    def test_create_invoice_with_insurance_returns_201(self, client):
        response = client.post("/invoices", json={
            "patient_id": 501,
            "insurance_provider_id": 302,  # Medibank Premium, 85% coverage
            "appointment_cost": 150,
            "medication_cost": 20,
            "bed_charges": 0,
        })
        assert response.status_code == 201

    def test_create_invoice_with_insurance_computes_correct_amounts(self, client):
        response = client.post("/invoices", json={
            "patient_id": 502,
            "insurance_provider_id": 302,  # 85% coverage
            "appointment_cost": 150,
            "medication_cost": 20,
            "bed_charges": 0,
        })
        data = response.get_json()
        assert data["total_amount"] == 170
        assert data["insurance_covered_amount"] == 144.5
        assert data["patient_owed_amount"] == 25.5

    def test_create_invoice_without_insurance_has_zero_coverage(self, client):
        response = client.post("/invoices", json={
            "patient_id": 503,
            "appointment_cost": 100,
        })
        data = response.get_json()
        assert data["insurance_covered_amount"] == 0.0
        assert data["patient_owed_amount"] == 100.0

    def test_create_invoice_missing_patient_id_returns_400(self, client):
        response = client.post("/invoices", json={"appointment_cost": 100})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_create_invoice_with_invalid_provider_returns_404(self, client):
        response = client.post("/invoices", json={
            "patient_id": 504,
            "insurance_provider_id": 999999,
        })
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_create_invoice_with_no_body_returns_400(self, client):
        response = client.post("/invoices", data="", content_type="application/json")
        assert response.status_code == 400

    def test_create_invoice_defaults_status_to_pending(self, client):
        response = client.post("/invoices", json={"patient_id": 505, "appointment_cost": 50})
        invoice_id = response.get_json()["invoice_id"]

        get_response = client.get(f"/invoices/{invoice_id}")
        assert get_response.get_json()["status"] == "pending"

    def test_create_invoice_persists_to_database(self, client, db_conn):
        response = client.post("/invoices", json={"patient_id": 506, "appointment_cost": 75})
        invoice_id = response.get_json()["invoice_id"]

        row = db_conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        assert row is not None
        assert row["patient_id"] == 506


# ---------------------------------------------------------------------------
# PUT /invoices/<id>
# ---------------------------------------------------------------------------

class TestUpdateInvoice:

    def test_update_invoice_status_returns_200(self, client):
        create_response = client.post("/invoices", json={"patient_id": 601, "appointment_cost": 100})
        invoice_id = create_response.get_json()["invoice_id"]

        response = client.put(f"/invoices/{invoice_id}", json={"status": "paid"})
        assert response.status_code == 200

    def test_update_invoice_status_persists(self, client):
        create_response = client.post("/invoices", json={"patient_id": 602, "appointment_cost": 100})
        invoice_id = create_response.get_json()["invoice_id"]

        client.put(f"/invoices/{invoice_id}", json={"status": "paid"})

        get_response = client.get(f"/invoices/{invoice_id}")
        assert get_response.get_json()["status"] == "paid"

    def test_update_invoice_costs_recomputes_totals(self, client):
        create_response = client.post("/invoices", json={
            "patient_id": 603,
            "insurance_provider_id": 305,  # HCF, 70% coverage
            "appointment_cost": 100,
        })
        invoice_id = create_response.get_json()["invoice_id"]

        response = client.put(f"/invoices/{invoice_id}", json={"medication_cost": 50})
        data = response.get_json()
        assert data["total_amount"] == 150
        assert data["insurance_covered_amount"] == 105.0
        assert data["patient_owed_amount"] == 45.0

    def test_update_invoice_partial_update_keeps_other_fields(self, client):
        create_response = client.post("/invoices", json={
            "patient_id": 604,
            "appointment_cost": 100,
        })
        invoice_id = create_response.get_json()["invoice_id"]

        client.put(f"/invoices/{invoice_id}", json={"status": "paid"})

        get_response = client.get(f"/invoices/{invoice_id}")
        data = get_response.get_json()
        assert data["patient_id"] == 604
        assert data["appointment_cost"] == 100

    def test_update_nonexistent_invoice_returns_404(self, client):
        response = client.put("/invoices/999999", json={"status": "paid"})
        assert response.status_code == 404

    def test_update_invoice_with_invalid_provider_returns_404(self, client):
        create_response = client.post("/invoices", json={"patient_id": 605, "appointment_cost": 100})
        invoice_id = create_response.get_json()["invoice_id"]

        response = client.put(f"/invoices/{invoice_id}", json={"insurance_provider_id": 999999})
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /invoices/<id>
# ---------------------------------------------------------------------------

class TestDeleteInvoice:

    def test_delete_invoice_returns_200(self, client):
        create_response = client.post("/invoices", json={"patient_id": 701, "appointment_cost": 100})
        invoice_id = create_response.get_json()["invoice_id"]

        response = client.delete(f"/invoices/{invoice_id}")
        assert response.status_code == 200

    def test_delete_invoice_removes_it(self, client):
        create_response = client.post("/invoices", json={"patient_id": 702, "appointment_cost": 100})
        invoice_id = create_response.get_json()["invoice_id"]

        client.delete(f"/invoices/{invoice_id}")

        get_response = client.get(f"/invoices/{invoice_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_invoice_returns_404(self, client):
        response = client.delete("/invoices/999999")
        assert response.status_code == 404